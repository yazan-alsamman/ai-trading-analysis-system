import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/json.dart';
import '../../markets/data/market_providers.dart';
import '../../markets/data/simulated_market_source.dart';
import '../../markets/models/market_models.dart';
import '../../signals/data/simulated_outcomes.dart';
import '../models/track_record.dart';
import 'track_record_dto.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';

/// مصدر سجل النموذج لشاشة Insights - بيتبدّل بتنفيذ API
abstract interface class InsightsRepository {
  /// بيانات محاكاة؟ (الشاشة بتبيّن "Simulated")
  /// API: ما في endpoint، تنفيذ الـ API بيرجّع false.
  /// TODO(API): بيروح مع المصدر المحاكى لما ينربط `GET /insights/track-record`.
  bool get isSimulated;

  /// سجل النموذج لـ [period]: الإجمالي + حسب الأداة + حسب الإطار + عبر الزمن.
  /// API: `GET /insights/track-record?window_days=7|30|90` → شكل [trackRecordFromJson].
  /// TODO(API): الـ endpoint مش موجود بالـ backend لسّا (ولا `/insights/accuracy`).
  Future<TrackRecord> trackRecord(InsightsPeriod period);
}

/// سجل محاكى من [SimulatedOutcomes] (نفس أرقام سطر الدقة بـ Signals لـ 90 يوم)
final class SimulatedInsightsRepository implements InsightsRepository {
  SimulatedInsightsRepository({required this.source});

  final SimulatedMarketSource source;

  /// طول كل نقطة بالرسم: يوم (7)، 3 أيام (30)، 9 أيام (90) → 7 / 10 / 10 نقاط
  static int bucketDays(InsightsPeriod period) => switch (period) {
        InsightsPeriod.d7 => 1,
        InsightsPeriod.d30 => 3,
        InsightsPeriod.d90 => 9,
      };

  @override
  bool get isSimulated => true;

  @override
  Future<TrackRecord> trackRecord(InsightsPeriod period) async {
    final parsed = trackRecordFromJson(Json(trackRecordJson(period)));
    if (parsed == null) throw StateError('invalid track record payload');
    return parsed;
  }

  Map<String, Object?> trackRecordJson(InsightsPeriod period) {
    final outcomes = SimulatedOutcomes(source);
    final last = outcomes.lastFullDay;
    final first = last - period.days + 1;
    Map<String, Object?> counts(({int resolved, int hits}) t) => {'resolved': t.resolved, 'hits': t.hits};
    final step = bucketDays(period);

    return {
      'window_days': period.days,
      ...counts(outcomes.total(first, last)),
      'by_symbol': [
        for (final symbol in kProductSymbols) {'symbol': symbol, ...counts(outcomes.total(first, last, symbol: symbol))},
      ],
      'by_timeframe': [
        for (final tf in Timeframe.modelTimeframes)
          {'timeframe': tf.apiValue, ...counts(outcomes.total(first, last, timeframe: tf))},
      ],
      'series': [
        for (var day = first; day <= last; day += step)
          {
            'start': day * Duration.millisecondsPerDay,
            'days': step,
            ...counts(outcomes.total(day, day + step - 1)),
          },
      ],
    };
  }
}

final insightsRepositoryProvider = Provider<InsightsRepository>(
  (ref) => apiSource(
    ref,
    ApiFeature.insights,
    simulated: () => SimulatedInsightsRepository(source: ref.watch(simulatedMarketSourceProvider)),
  ),
);
