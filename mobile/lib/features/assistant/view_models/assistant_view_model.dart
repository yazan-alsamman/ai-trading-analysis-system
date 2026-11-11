import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/network_status.dart';
import '../../../core/data/sha256.dart';
import '../../../core/format/formatters.dart';
import '../../../core/widgets/direction_badge.dart';
import '../../../l10n/app_localizations.dart';
import '../../../providers/locale_provider.dart';
import '../../markets/data/market_providers.dart';
import '../../markets/models/market_models.dart';
import '../../risk/data/risk_limits_repository.dart';
import '../../signals/data/analysis_methods_repository.dart';
import '../../signals/data/signal_profile_repository.dart';
import '../../signals/models/opportunity.dart';
import '../../signals/models/signal_plan.dart';
import '../data/assistant_repository.dart';
import '../data/chart_analysis_repository.dart';
import '../data/chart_image_picker.dart';
import '../models/assistant_models.dart';
import '../models/chart_analysis.dart';
import 'chart_quota_view_model.dart';

/// الطلب الأخير (لزر Retry لو فشل)
@immutable
final class _AskRequest {
  const _AskRequest(this.text, this.kind);

  final String text;
  final ReplyKind? kind;
}

/// حالة تحليل الصورة المختارة
enum ChartStatus {
  idle,
  analyzing,

  /// فشل (Try again)
  failed,

  /// ما في اتصال: ما انبعت شي
  offline,
}

@immutable
final class AssistantState {
  const AssistantState({
    this.messages = const [],
    this.contextSymbol = defaultSymbol,
    this.replying = false,
    this.failed = false,
    this.draft,
    this.chartStatus = ChartStatus.idle,
  });

  /// الأداة الافتراضية بالسياق (أداة العرض)
  static const String defaultSymbol = 'EUR/USD';

  /// الأقدم أول
  final List<ChatMessage> messages;

  /// null = بدون أداة (أسئلة عامة)
  final String? contextSymbol;
  final bool replying;

  /// آخر سؤال فشل (بيبيّن "Try again")
  final bool failed;

  /// صورة الشارت المختارة (المعاينة)، null = ما في
  final ChartDraft? draft;
  final ChartStatus chartStatus;

  bool get analyzing => chartStatus == ChartStatus.analyzing;

  AssistantState copyWith({
    List<ChatMessage>? messages,
    String? Function()? contextSymbol,
    bool? replying,
    bool? failed,
    ChartDraft? Function()? draft,
    ChartStatus? chartStatus,
  }) =>
      AssistantState(
        messages: messages ?? this.messages,
        contextSymbol: contextSymbol == null ? this.contextSymbol : contextSymbol(),
        replying: replying ?? this.replying,
        failed: failed ?? this.failed,
        draft: draft == null ? this.draft : draft(),
        chartStatus: chartStatus ?? this.chartStatus,
      );
}

/// ViewModel المساعد: المحادثة بتضل طول ما التطبيق شغّال (بين التبويبات).
///
/// - سؤال واحد بنفس الوقت؛ "Stop" بيلغي الجواب الجاري (عدّاد أجيال: جواب
///   متأخر ما بيوصل بعد Stop أو New chat). الفشل بيترك السؤال مع "Try again".
/// - تحليل الصورة (H3): اختيار → معاينة (Remove) → Analyze → النتيجة كبطاقة
///   بالمحادثة. ضغطتين = طلب واحد، Cancel بيلغيه، وبس آخر طلب بيغيّر الشاشة
///   (عدّاد أجيال تاني + cancel token). بدون اتصال ما بينبعت شي.
/// - أي اتجاه / احتمال / مستوى بالجواب جاي من [opportunitiesProvider] (طريقة
///   الاستراتيجية المحفوظة)، فهو نفس أرقام Signals والتفاصيل والتوقّع.
class AssistantViewModel extends Notifier<AssistantState> {
  var _generation = 0;
  var _chartGeneration = 0;
  var _seq = 0;
  var _picking = false;
  _AskRequest? _last;
  ChartAnalysisCancelToken? _chartCancel;

  @override
  AssistantState build() {
    ref.onDispose(() => _chartCancel?.cancel());
    return const AssistantState();
  }

  String _id() => 'm${++_seq}';

  void setContext(String? symbol) {
    if (symbol == state.contextSymbol) return;
    state = state.copyWith(contextSymbol: () => symbol);
  }

  Future<void> send(String text, {ReplyKind? kind}) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || state.replying) return;
    state = state.copyWith(
      messages: [...state.messages, UserText(id: _id(), createdAt: DateTime.now(), text: trimmed)],
    );
    await _run(_AskRequest(trimmed, kind));
  }

  void stop() {
    if (!state.replying) return;
    _generation++;
    state = state.copyWith(replying: false);
  }

  Future<void> retry() async {
    final last = _last;
    if (last == null || state.replying || !state.failed) return;
    await _run(last);
  }

  /// محادثة جديدة - بيرجّع القديمة (لزر Undo). تحليل جاري بينلغى؛ الصورة
  /// المختارة بتضل بالمعاينة.
  List<ChatMessage> clear() {
    final previous = state.messages;
    _generation++;
    _last = null;
    cancelChart();
    state = state.copyWith(messages: const [], replying: false, failed: false);
    return previous;
  }

  void restore(List<ChatMessage> messages) {
    if (state.messages.isNotEmpty || state.replying) return;
    state = state.copyWith(messages: messages);
  }

  // ── تحليل صورة الشارت ────────────────────────────────────

  /// اختيار صورة → معاينة. null = تمام أو إلغاء، وإلا سبب الرفض لرسالة الشاشة.
  Future<ChartImageProblem?> pickChart(ChartImageSource source) async {
    if (state.analyzing || _picking) return null;
    _picking = true;
    try {
      final pick = await ref.read(chartImagePickerProvider).pick(source);
      switch (pick) {
        case ChartPickCancelled():
          return null;
        case ChartPickRejected(:final problem):
          return problem;
        case ChartPicked(:final path, :final bytes):
          if (validateChartImage(bytes) case final problem?) return problem;
          final sha = await sha256HexAsync(bytes);
          final cached = await ref.read(chartAnalysisRepositoryProvider).cached(sha) != null;
          if (state.analyzing) return null;
          state = state.copyWith(
            draft: () => ChartDraft(path: path, bytes: bytes, sha256: sha, cached: cached),
            chartStatus: ChartStatus.idle,
          );
          return null;
      }
    } finally {
      _picking = false;
    }
  }

  /// شيل الصورة المختارة (وإلغاء تحليلها إذا شغّال)
  void removeChart() {
    if (state.draft == null) return;
    _chartGeneration++;
    _chartCancel?.cancel();
    state = state.copyWith(draft: () => null, chartStatus: ChartStatus.idle);
  }

  /// إلغاء التحليل الجاري - الصورة بتضل بالمعاينة
  void cancelChart() {
    if (!state.analyzing) return;
    _chartGeneration++;
    _chartCancel?.cancel();
    state = state.copyWith(chartStatus: ChartStatus.idle);
  }

  /// تحليل الصورة المختارة (Analyze و Try again). نفس الصورة من قبل = النتيجة
  /// المحفوظة بدون ما تنحسب.
  Future<void> analyzeChart() async {
    final draft = state.draft;
    if (draft == null || state.analyzing) return;
    if (ref.read(networkStatusProvider) == NetworkStatus.offline) {
      state = state.copyWith(chartStatus: ChartStatus.offline);
      return;
    }
    _chartCancel?.cancel();
    final cancel = _chartCancel = ChartAnalysisCancelToken();
    final generation = ++_chartGeneration;
    bool current() => generation == _chartGeneration && !cancel.isCancelled;
    state = state.copyWith(chartStatus: ChartStatus.analyzing);
    try {
      final outcome = await ref.read(chartAnalysisRepositoryProvider).analyze(
            ChartImageUpload(bytes: draft.bytes, sha256: draft.sha256, fileName: draft.fileName),
            cancel: cancel,
          );
      // العدّاد بيتحدّث حتى لو انلغى بعد ما خلص (الطلب انحسب)
      ref.read(chartQuotaProvider.notifier).set(outcome.quota);
      if (!current()) return;
      final reply = await _chartReply(outcome);
      if (!current()) return;
      state = state.copyWith(
        draft: () => null,
        chartStatus: ChartStatus.idle,
        messages: [
          ...state.messages,
          UserImage(id: _id(), createdAt: DateTime.now(), path: draft.path),
          reply,
        ],
      );
    } on DailyLimitReachedException catch (e) {
      ref.read(chartQuotaProvider.notifier).reached(e.resetAt);
      if (current()) state = state.copyWith(chartStatus: ChartStatus.idle);
    } on ChartAnalysisOfflineException {
      if (current()) state = state.copyWith(chartStatus: ChartStatus.offline);
    } on ChartAnalysisCancelledException {
      // انلغى: طلب أحدث أو Cancel أخد مكانه
    } catch (_) {
      if (current()) state = state.copyWith(chartStatus: ChartStatus.failed);
    }
  }

  /// بطاقة الجواب: قراءة الصورة + إشارة الاستراتيجية المحفوظة على نفس الأداة والإطار
  Future<AssistantReply> _chartReply(ChartAnalysisOutcome outcome) async {
    final analysis = outcome.analysis;
    final language = ref.read(localeProvider).languageCode;
    final l10n = AppLocalizations(Locale(language));
    final methodId = ref.read(signalProfileProvider).methodId;
    Instrument? instrument;
    Opportunity? signal;
    if (analysis.hasInstrument) {
      final instruments = await ref.read(instrumentsProvider.future);
      instrument = instruments.where((i) => i.symbol == analysis.symbol).firstOrNull;
      if (instrument != null) {
        final opportunities = await _strategyOpportunities(instrument.symbol);
        final now = ref.read(simulatedMarketSourceProvider).now();
        signal = opportunities
            .where((o) => o.timeframe == analysis.timeframe && o.isDetected && !o.isStale(now))
            .firstOrNull;
      }
    }
    final chart = ChartAnalysisReply(
      analysis: analysis,
      instrument: instrument,
      signal: signal,
      plan: signal == null ? null : SignalPlan.of(signal, instrument!),
      methodId: methodId,
      fromCache: outcome.fromCache,
    );
    final methodName = await _methodName(methodId, language);
    return AssistantReply(
      id: _id(),
      createdAt: DateTime.now(),
      answer: AssistantAnswer(
        kind: ReplyKind.chart,
        text: chartReadingText(l10n, chart, methodName: methodName ?? l10n.chartYourStrategy),
        chart: chart,
      ),
      symbol: instrument?.symbol,
    );
  }

  Future<String?> _methodName(String methodId, String language) async {
    try {
      final methods = await ref.read(analysisMethodsRepositoryProvider).list(language: language);
      return methods.where((m) => m.id == methodId).firstOrNull?.name;
    } catch (_) {
      return null;
    }
  }

  /// آراء الاستراتيجية المحفوظة على [symbol] من نفس provider قائمة Signals
  /// وشاشة السوق ([opportunitiesProvider]) - ما في أرقام منفصلة للمساعد.
  Future<List<Opportunity>> _strategyOpportunities(String symbol) async {
    final subscription = ref.listen(opportunitiesProvider(symbol).future, (_, __) {});
    try {
      return await subscription.read();
    } finally {
      subscription.close();
    }
  }

  // ── الأسئلة ──────────────────────────────────────────────

  Future<void> _run(_AskRequest request) async {
    final generation = ++_generation;
    _last = request;
    state = state.copyWith(replying: true, failed: false);
    try {
      final context = await _context();
      final language = ref.read(localeProvider).languageCode;
      final answer = await ref
          .read(assistantRepositoryProvider)
          .ask(request.text, kind: request.kind, context: context, languageCode: language);
      if (generation != _generation) return;
      state = state.copyWith(
        replying: false,
        messages: [
          ...state.messages,
          AssistantReply(id: _id(), createdAt: DateTime.now(), answer: answer, symbol: context.instrument?.symbol),
        ],
      );
    } catch (_) {
      if (generation != _generation) return;
      state = state.copyWith(replying: false, failed: true);
    }
  }

  /// السياق من بيانات التطبيق نفسها: الأداة، آخر سعر، رأي الاستراتيجية، والحدود
  Future<AssistantContext> _context() async {
    final limits = ref.read(riskLimitsProvider);
    final symbol = state.contextSymbol;
    if (symbol == null) return AssistantContext(limits: limits);
    final instruments = await ref.read(instrumentsProvider.future);
    final instrument = instruments.where((i) => i.symbol == symbol).firstOrNull;
    if (instrument == null) return AssistantContext(limits: limits);
    final (opportunities, quotes) = await (
      // نفس طريقة الاستراتيجية المحفوظة (نفس رأي شاشة السوق وقائمة Signals)
      _strategyOpportunities(symbol),
      ref.read(liveQuotesProvider.future),
    ).wait;
    final now = ref.read(simulatedMarketSourceProvider).now();
    return AssistantContext(
      instrument: instrument,
      lastPrice: quotes[symbol]?.price,
      read: ModelRead.from(opportunities, now),
      limits: limits,
    );
  }
}

/// القراءة القصيرة تحت أرقام البطاقة (بلغة الطلب). احتمال، مش وعد: "high
/// probability" بنفس قاعدة التوقّع ([ChartAnalysisReply.isHighProbability])، وما في كلمة وعد أبدًا.
String chartReadingText(AppLocalizations l10n, ChartAnalysisReply chart, {required String methodName}) {
  final pattern = chartPatternLabel(l10n, chart.analysis.pattern);
  final instrument = chart.instrument;
  final timeframe = chart.timeframe;
  if (instrument == null || timeframe == null) {
    return l10n.chartReadNoInstrument(pattern, pictureTrendLabel(l10n, chart.analysis.trend));
  }
  final signal = chart.signal;
  if (signal == null) return l10n.chartReadNoSetup(instrument.symbol, timeframe.label, pattern, methodName);
  return [
    l10n.chartReadSignal(
      instrument.symbol,
      timeframe.label,
      pattern,
      methodName,
      signal.direction.label(l10n),
      Formatters.percent(signal.probability),
    ),
    if (chart.isHighProbability) l10n.chartReadHigh,
  ].join(' ');
}

String chartPatternLabel(AppLocalizations l10n, ChartPattern pattern) => switch (pattern) {
      ChartPattern.channel => l10n.chartPatternChannel,
      ChartPattern.triangle => l10n.chartPatternTriangle,
      ChartPattern.range => l10n.chartPatternRange,
      ChartPattern.flag => l10n.chartPatternFlag,
      ChartPattern.wedge => l10n.chartPatternWedge,
    };

String pictureTrendLabel(AppLocalizations l10n, PictureTrend trend) => switch (trend) {
      PictureTrend.rising => l10n.chartTrendRising,
      PictureTrend.falling => l10n.chartTrendFalling,
      PictureTrend.sideways => l10n.chartTrendSideways,
    };

final assistantViewModelProvider = NotifierProvider<AssistantViewModel, AssistantState>(AssistantViewModel.new);
