import 'dart:math' as math;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/json.dart';
import '../../markets/data/market_providers.dart';
import '../../markets/data/simulated_market_source.dart';
import '../../signals/data/simulated_outcomes.dart';
import '../models/backtest.dart';
import 'backtest_dto.dart';
import 'backtest_engine.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';

/// إلغاء اختبار شغّال (تغيير الأدوات أو الفترة، أو سكّرت الشاشة)
final class BacktestCancelToken {
  bool _cancelled = false;

  bool get isCancelled => _cancelled;

  void cancel() => _cancelled = true;
}

/// الاختبار انلغى قبل ما يخلص (ما في نتيجة)
final class BacktestCancelledException implements Exception {
  const BacktestCancelledException();
}

/// مصدر اختبار الاستراتيجية على بيانات سابقة - بيتبدّل بتنفيذ API
abstract interface class BacktestRepository {
  /// بيانات محاكاة؟ (الشاشة بتبيّن "Simulated")
  /// API: ما في endpoint، تنفيذ الـ API بيرجّع false.
  /// TODO(API): بيروح مع المصدر المحاكى لما ينربط `POST /backtests`.
  bool get isSimulated;

  /// بيشغّل [request] وبيرجّع النتيجة. [onProgress] بين 0 و 1 أثناء الشغل؛
  /// [cancel] بيوقفه ([BacktestCancelledException]).
  /// API: `POST /backtests` بجسم [BacktestRequest.toJson] → شكل [backtestResultFromJson]
  /// (والتقدّم من `GET /backtests/{id}` لو الشغل طويل). `window_days` = 30 / 90 /
  /// 365 / 730 / 1095 / 1825: الـ API لازم يكون عندو تاريخ إشارات لـ 5 سنين لورا
  /// (ونتايجها)، وإلا بيرجّع الأيام يلي عندو بس وما بيخترع.
  /// TODO(API): الـ endpoint مش موجود بالـ backend لسّا (ولا routes للاختبار).
  Future<BacktestResult> run(
    BacktestRequest request, {
    BacktestCancelToken? cancel,
    void Function(double progress)? onProgress,
  });
}

/// اختبار محاكى من [SimulatedBacktestEngine]: الأيام المكتملة بس (لحد مبارح)،
/// على دفعات مع تقدّم بينها حتى الشاشة تبيّن الشغل وتقدر تلغيه.
///
/// [chunks] دفعات عالأقل، وكل دفعة [maxChunkDays] يوم عالأكتر: الفترات الطويلة
/// (لحد 5 سنين) بتنقسم لدفعات أكتر مش أتقل، فما في دفعة بتعلّق الشاشة؛ والاستراحة
/// بتنقسم عليها فالمدة الكلية تقريبًا متل سنة.
final class SimulatedBacktestRepository implements BacktestRepository {
  SimulatedBacktestRepository({required this.source, this.step = const Duration(milliseconds: 90)});

  final SimulatedMarketSource source;

  /// استراحة بين الدفعات (Duration.zero بالاختبارات)
  final Duration step;

  static const int chunks = 8;

  static const int maxChunkDays = 46;

  /// كم دفعة لفترة [days] يوم
  static int chunkCount(int days) => (days / chunkDays(days)).ceil();

  static int chunkDays(int days) => math.min((days / chunks).ceil(), maxChunkDays);

  @override
  bool get isSimulated => true;

  @override
  Future<BacktestResult> run(
    BacktestRequest request, {
    BacktestCancelToken? cancel,
    void Function(double progress)? onProgress,
  }) async {
    if (!request.isValid) throw ArgumentError.value(request, 'request', 'invalid backtest request');
    final outcomes = SimulatedOutcomes(source);
    final engine = SimulatedBacktestEngine(outcomes);
    final last = outcomes.lastFullDay;
    final first = last - request.period.days + 1;
    final size = chunkDays(request.period.days);
    final pause = step * (chunks / chunkCount(request.period.days));
    final found = <PastSignal>[];

    for (var from = first; from <= last; from += size) {
      if (cancel?.isCancelled ?? false) throw const BacktestCancelledException();
      final to = math.min(from + size - 1, last);
      found.addAll(engine.signals(request, from, to));
      onProgress?.call((to - first + 1) / request.period.days);
      await (pause > Duration.zero ? Future<void>.delayed(pause) : Future<void>.value());
    }
    if (cancel?.isCancelled ?? false) throw const BacktestCancelledException();

    final parsed = backtestResultFromJson(Json(SimulatedBacktestEngine.resultJson(request.period, first, found)));
    if (parsed == null) throw StateError('invalid backtest payload');
    return parsed;
  }
}

final backtestRepositoryProvider = Provider<BacktestRepository>(
  (ref) => apiSource(
    ref,
    ApiFeature.backtest,
    simulated: () => SimulatedBacktestRepository(source: ref.watch(simulatedMarketSourceProvider)),
  ),
);
