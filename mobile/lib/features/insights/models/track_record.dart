import 'package:flutter/foundation.dart';

import '../../markets/models/market_models.dart';
import '../../signals/models/model_accuracy.dart';

/// فترات شاشة Insights (شرائح 7 / 30 / 90 يوم)
enum InsightsPeriod {
  d7(7),
  d30(30),
  d90(90);

  const InsightsPeriod(this.days);

  final int days;

  /// من عدد أيام (سطر الدقة أو الـ API) - غير المعروف → null
  static InsightsPeriod? fromDays(int? days) {
    for (final p in values) {
      if (p.days == days) return p;
    }
    return null;
  }
}

/// أقل من هيك إشارات، الرقم بينعلّم "عيّنة صغيرة" (نسبة من 3 إشارات ما بتعني شي)
const int kMinTrackSample = 10;

extension TrackSample on ModelAccuracy {
  bool get isSmallSample => resolved < kMinTrackSample;
}

/// دقة أداة وحدة بالفترة
@immutable
final class InstrumentAccuracy {
  const InstrumentAccuracy({required this.symbol, required this.accuracy});

  final String symbol;
  final ModelAccuracy accuracy;
}

/// دقة إطار واحد بالفترة
@immutable
final class TimeframeAccuracy {
  const TimeframeAccuracy({required this.timeframe, required this.accuracy});

  final Timeframe timeframe;
  final ModelAccuracy accuracy;
}

/// نقطة بالرسم: الإشارات يلي خلصت بين [start] و [start] + [days]
@immutable
final class AccuracyPoint {
  const AccuracyPoint({required this.start, required this.days, required this.accuracy});

  /// بداية المدة (UTC، أول اليوم)
  final DateTime start;
  final int days;
  final ModelAccuracy accuracy;

  /// آخر يوم بالمدة (مع الطرفين)
  DateTime get end => start.add(Duration(days: days - 1));
}

/// سجل النموذج لفترة: الإجمالي + حسب الأداة + حسب الإطار + عبر الزمن.
///
/// كل رقم معه عدد إشاراته ([ModelAccuracy.resolved])، والنسبة null لما ما في نتائج.
@immutable
final class TrackRecord {
  const TrackRecord({
    required this.period,
    required this.overall,
    required this.byInstrument,
    required this.byTimeframe,
    required this.series,
  });

  final InsightsPeriod period;
  final ModelAccuracy overall;

  /// بترتيب [kProductSymbols] (مش حسب النسبة: ترتيب بعيّنات صغيرة بيضلّل)
  final List<InstrumentAccuracy> byInstrument;

  /// بترتيب [Timeframe.modelTimeframes]
  final List<TimeframeAccuracy> byTimeframe;

  /// من الأقدم للأحدث
  final List<AccuracyPoint> series;

  /// ما في ولا إشارة مكتملة بالفترة
  bool get isEmpty => overall.resolved == 0;
}
