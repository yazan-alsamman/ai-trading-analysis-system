import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/format/formatters.dart';
import '../../../core/widgets/direction_badge.dart';
import '../../../l10n/app_localizations.dart';
import '../../risk/models/risk_limits.dart';
import '../../risk/models/trade_sizing.dart';
import '../models/assistant_models.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';

/// مصدر أجوبة المساعد - بيتبدّل بتنفيذ API (الخادم بينادي النموذج الحقيقي،
/// والمفاتيح ما بتوصل للجهاز أبدًا). الجواب بلغة [languageCode].
abstract interface class AssistantRepository {
  /// [kind] معروف لما السؤال من الاقتراحات، وإلا المصدر بيصنّف لحاله
  Future<AssistantAnswer> ask(
    String question, {
    ReplyKind? kind,
    required AssistantContext context,
    required String languageCode,
  });
}

/// مساعد قواعد (مش نموذج لغوي): بيصنّف السؤال بكلمات مفتاحية وبيجاوب من
/// بيانات السياق بس (السعر، رأي النموذج، حدود المخاطرة). كل جواب "Simulated".
class RuleBasedAssistantRepository implements AssistantRepository {
  RuleBasedAssistantRepository({this.latency = Duration.zero});

  final Duration latency;

  static final _explainWords = RegExp(r'explain|analys|summar|read|signal|اشرح|تحليل|حلل|ملخص|رأي|إشارة', caseSensitive: false);
  static final _invalidateWords = RegExp(r'invalid|wrong|cancel|break|يبطل|إلغاء|يلغي|يفشل|خطأ', caseSensitive: false);
  static final _riskWords = RegExp(r'risk|size|capital|lot|stop|مخاطر|حجم|رأس المال|وقف', caseSensitive: false);

  static ReplyKind classify(String question) {
    if (_invalidateWords.hasMatch(question)) return ReplyKind.invalidate;
    if (_riskWords.hasMatch(question)) return ReplyKind.risk;
    if (_explainWords.hasMatch(question)) return ReplyKind.explain;
    return ReplyKind.unknown;
  }

  Future<void> _wait() async {
    if (latency > Duration.zero) await Future<void>.delayed(latency);
  }

  @override
  Future<AssistantAnswer> ask(
    String question, {
    ReplyKind? kind,
    required AssistantContext context,
    required String languageCode,
  }) async {
    await _wait();
    final l10n = AppLocalizations(Locale(languageCode));
    final resolved = kind ?? classify(question);
    final instrument = context.instrument;
    if (instrument == null && resolved != ReplyKind.unknown) {
      return AssistantAnswer(kind: resolved, text: l10n.asstNoContext);
    }
    final best = context.read?.best;
    final text = switch (resolved) {
      ReplyKind.explain when best == null => l10n.asstExplainNone(instrument!.symbol),
      ReplyKind.explain => l10n.asstExplain(
          instrument!.symbol,
          best!.timeframe.label,
          best.direction.label(l10n),
          Formatters.percent(best.probability),
          '${context.read!.agreeing}',
          '${context.read!.analysed}',
          instrument.format(best.entryZone.mid),
          instrument.format(best.stopLossZone.mid),
          instrument.format(best.takeProfitZone.mid),
          '1:${Formatters.trimZeros(best.riskReward.toStringAsFixed(1))}',
        ),
      ReplyKind.invalidate when best == null => l10n.asstInvalidateNone(instrument!.symbol),
      ReplyKind.invalidate => l10n.asstInvalidate(
          instrument!.format(best!.stopLossZone.mid),
          Formatters.clock(best.validUntil.toUtc()),
        ),
      ReplyKind.risk => _risk(l10n, context),
      ReplyKind.chart || ReplyKind.unknown => l10n.asstUnknown,
    };
    return AssistantAnswer(kind: resolved == ReplyKind.chart ? ReplyKind.unknown : resolved, text: text);
  }

  String _risk(AppLocalizations l10n, AssistantContext context) {
    final instrument = context.instrument!;
    final best = context.read?.best;
    if (best == null) return l10n.asstRiskNone(instrument.symbol);
    final limits = context.limits;
    if (!limits.hasCapital) return l10n.asstRiskNoCapital;
    final result = computeTradeSize(
      instrument: instrument,
      capital: limits.capital,
      riskPct: limits.maxRiskPerTradePct,
      entry: best.entryZone.mid,
      stop: best.stopLossZone.mid,
      target: best.takeProfitZone.mid,
      maxRiskPerTradePct: limits.maxRiskPerTradePct,
    );
    if (result is! TradeSize) return l10n.asstRiskNone(instrument.symbol);
    return l10n.asstRisk(
      Formatters.money(limits.capital!, RiskLimits.currency),
      Formatters.plainPercent(limits.maxRiskPerTradePct),
      Formatters.grouped(result.pips, decimals: 1),
      Formatters.grouped(result.units),
      Formatters.money(result.moneyAtRisk, RiskLimits.currency),
    );
  }
}

final assistantRepositoryProvider = Provider<AssistantRepository>(
  (ref) => apiSource(
    ref,
    ApiFeature.assistant,
    simulated: () => RuleBasedAssistantRepository(latency: const Duration(milliseconds: 900)),
  ),
);
