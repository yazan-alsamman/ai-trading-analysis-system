import 'dart:math' as math;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/json.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';
import '../../../core/widgets/direction_badge.dart';
import '../../markets/data/market_providers.dart';
import '../../markets/data/simulated_market_source.dart';
import '../../markets/models/market_models.dart';
import '../../signals/data/opportunity_dto.dart';
import '../../signals/data/signals_repository.dart';
import '../../signals/models/opportunity.dart';
import '../models/forecast_config.dart';
import '../models/forecast_path.dart';
import 'forecast_dto.dart';

/// إلغاء طلب توقّع (تبديل إطار / أداة، إطفاء المفتاح، أو سكّرت الشاشة)
final class ForecastCancelToken {
  bool _cancelled = false;

  bool get isCancelled => _cancelled;

  void cancel() => _cancelled = true;
}

/// الطلب انلغى قبل ما يخلص (النتيجة ما بتنرسم)
final class ForecastCancelledException implements Exception {
  const ForecastCancelledException();
}

/// مصدر توقّع النموذج على رسم الأداة - بيتبدّل بتنفيذ API
abstract interface class ForecastRepository {
  /// بيانات محاكاة؟ (شارة "Simulated" جنب التوقّع)
  bool get isSimulated;

  /// توقّع [symbol] على [timeframe] لطريقة الاستراتيجية المحفوظة [methodId]:
  /// مبني من نفس الإشارة (نفس الاتجاه والاحتمال، وبيخلص عند هدفها).
  /// على إطار ما عليه إشارة بيلحق اتجاه أقوى إشارة للاستراتيجية باحتمال أقل.
  /// null = ما في توقّع هلّق (الاستراتيجية محايدة). الأطر المدعومة بتنقرّر
  /// بـ [forecastSupportedTimeframes] قبل الطلب. [cancel] بيوقفه ([ForecastCancelledException]).
  /// API: `GET /forecasts?symbol=&timeframe=&method_id=` → `ForecastSchema`
  /// (الشكل المقترح بـ [ForecastDto])، و204 / 404 = ما في توقّع.
  /// TODO(API): الـ endpoint مش موجود بالـ backend، وشكل البيانات سؤال مفتوح
  /// عند صاحب الـ backend (§8)؛ التحويل معزول بـ [ForecastDto].
  Future<ForecastPath?> forecast(
    String symbol,
    Timeframe timeframe, {
    required String methodId,
    ForecastCancelToken? cancel,
  });
}

/// توقّع محاكى حتمي من نفس آراء [SimulatedSignalsRepository] (نفس المحرّك،
/// نفس الشمعة، نفس الطريقة)، على **كل** إطار:
///
/// - الإطار إلو إشارة مكتشفة للاستراتيجية (15m / 1h / 4h): نفس [ForecastPath.signalId]
///   والاتجاه والاحتمال والصلاحية، والمسار من منتصف منطقة الدخول لمنتصف الهدف.
/// - ما إلو إشارة (1m، 1D، أو إطار محايد): بيلحق أقوى إشارة للاستراتيجية (نفس
///   خلاصة الرأي بشاشة السوق، [ModelRead.best]): نفس الاتجاه، احتمال أقل
///   ([forecastFollowPenalty])، والهدف على بعد خطة بحجم شمعة هالإطار.
/// - الاستراتيجية محايدة على كل الأطر = null ("No forecast right now").
///
/// عدد الشموع والصلاحية من [forecastHorizon]، والنطاق بيتوسّع مع الوقت ومع
/// حجم الشمعة (تذبذب الأداة). بيطلع بشكل الـ API عبر [ForecastDto].
final class SimulatedForecastRepository implements ForecastRepository {
  SimulatedForecastRepository({required this.source, this.latency = Duration.zero});

  final SimulatedMarketSource source;

  /// تأخير الطلب المحاكى (حتى حالة التحميل تبيّن)
  final Duration latency;

  @override
  bool get isSimulated => true;

  @override
  Future<ForecastPath?> forecast(
    String symbol,
    Timeframe timeframe, {
    required String methodId,
    ForecastCancelToken? cancel,
  }) async {
    if (latency > Duration.zero) await Future<void>.delayed(latency);
    if (cancel?.isCancelled ?? false) throw const ForecastCancelledException();
    final json = forecastJson(symbol, timeframe, methodId: methodId);
    return json == null ? null : ForecastDto.fromJson(Json(json)).toDomain();
  }

  /// شكل الـ API (null = ما في توقّع: الاستراتيجية محايدة، أو أداة / طريقة مش معروفة)
  Map<String, Object?>? forecastJson(String symbol, Timeframe timeframe, {required String methodId}) {
    final spec = source.spec(symbol);
    if (spec == null) return null;
    final now = source.now();
    final signals = [
      for (final json in SimulatedSignalsRepository(source: source).opportunitiesJson(symbol, methodId: methodId))
        if (OpportunityDto.fromJson(Json(json)).toDomain() case final o?) o,
    ];
    final horizon = forecastHorizon(timeframe);

    // 1) خطة الاستراتيجية على إطار الرسم نفسه
    final own = signals.where((o) => o.timeframe == timeframe && o.isDetected && !o.isStale(now)).firstOrNull;
    if (own != null) {
      return _json(
        spec,
        timeframe,
        signal: own,
        probability: own.probability,
        anchorTime: own.generatedAt,
        anchor: own.entryZone.mid,
        target: own.takeProfitZone.mid,
        validUntil: own.validUntil,
        steps: horizon.candles,
      );
    }

    // 2) ما في خطة هون: بيلحق أقوى إشارة (نفس خلاصة الرأي) باحتمال أقل
    final best = ModelRead.from(signals, now).best;
    if (best == null) return null;
    final anchorTime = timeframe.bucketStart(now);
    final anchor = source.priceAt(spec.symbol, anchorTime);
    final sign = best.direction == SignalDirection.long ? 1 : -1;
    // نفس حجم الخطة (ATR × العائد) بس بشمعة هالإطار
    final atr = anchor * spec.dailyVol * math.sqrt(timeframe.duration.inMinutes / 1440) * 1.2;
    final probability = math.max(forecastMinProbability, best.probability - forecastFollowPenalty);
    return _json(
      spec,
      timeframe,
      signal: best,
      probability: double.parse(probability.toStringAsFixed(2)),
      anchorTime: anchorTime,
      anchor: anchor,
      target: anchor + sign * atr * best.riskReward,
      validUntil: anchorTime.add(timeframe.duration * horizon.validCandles),
      steps: horizon.candles,
    );
  }

  /// المسار: من [anchor] لـ [target] على [steps] شمعة (ease-out + تموّج صغير
  /// حتمي بيصفر بالآخر)، ونطاق بيتوسّع مع √الشموع وتذبذب شمعة [timeframe].
  Map<String, Object?> _json(
    SimulatedInstrumentSpec spec,
    Timeframe timeframe, {
    required Opportunity signal,
    required double probability,
    required DateTime anchorTime,
    required double anchor,
    required double target,
    required DateTime validUntil,
    required int steps,
  }) {
    final size = timeframe.duration;
    final bucket = anchorTime.millisecondsSinceEpoch ~/ size.inMilliseconds;
    // تذبذب شمعة وحدة بالسعر
    final sigma = anchor * spec.dailyVol * math.sqrt(size.inMinutes / 1440);
    double r(double v) => double.parse(v.toStringAsFixed(spec.precision));

    final points = <Map<String, Object?>>[];
    for (var i = 1; i <= steps; i++) {
      final t = i / steps;
      final wiggle = (SimulatedMarketSource.hash01(spec.seed, 410, bucket * 31 + i) - 0.5) * sigma * 0.5;
      final expected = anchor + (target - anchor) * t * (2 - t) + wiggle * math.sin(math.pi * t);
      final half = sigma * (0.5 + 0.8 * math.sqrt(i));
      points.add({
        'time': anchorTime.add(size * i).millisecondsSinceEpoch,
        'expected': r(expected),
        'low': r(expected - half),
        'high': r(expected + half),
      });
    }

    return {
      'symbol': spec.symbol,
      'timeframe': timeframe.apiValue,
      'method_id': signal.methodId,
      'signal_id': signal.id,
      'basis_timeframe': signal.timeframe.apiValue,
      'direction': signal.direction == SignalDirection.long ? 'long' : 'short',
      'probability': probability,
      'anchor': {'time': anchorTime.millisecondsSinceEpoch, 'price': r(anchor)},
      'target': r(target),
      'generated_at': anchorTime.millisecondsSinceEpoch,
      'valid_until': validUntil.millisecondsSinceEpoch,
      'points': points,
    };
  }
}

/// المصدر الوحيد يلي بيتبدّل بالـ API (`USE_REAL_API=forecast`)
final forecastRepositoryProvider = Provider<ForecastRepository>(
  (ref) => apiSource(
    ref,
    ApiFeature.forecast,
    simulated: () => SimulatedForecastRepository(
      source: ref.watch(simulatedMarketSourceProvider),
      latency: const Duration(milliseconds: 450),
    ),
  ),
);
