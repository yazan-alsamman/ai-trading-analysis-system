import 'package:flutter/foundation.dart';

import '../../../core/widgets/direction_badge.dart';
import '../../markets/models/market_models.dart';
import '../../signals/models/analysis_method.dart';
import '../../signals/models/model_accuracy.dart';
import '../../signals/models/signal_profile.dart';

/// فترات الاختبار (شرائح 30 يوم / 90 يوم / سنة / سنتين / 3 / 5 سنين)
enum BacktestPeriod {
  d30(30),
  d90(90),
  y1(365),
  y2(730),
  y3(1095),
  y5(1825);

  const BacktestPeriod(this.days);

  final int days;

  /// أطول من سنة: محور المنحنى بالسنين والتاريخ بيبيّن السنة
  bool get isMultiYear => days > 365;

  /// من عدد أيام (الـ API) - غير المعروف → null
  static BacktestPeriod? fromDays(int? days) {
    for (final p in values) {
      if (p.days == days) return p;
    }
    return null;
  }
}

/// طلب اختبار: الطريقة + الأدوات المختارة + الفترة + باقي فلاتر الاستراتيجية.
///
/// "Fits my capital" ما بيدخل: بيعتمد على رأس المال اليوم، مش وقت الإشارة.
@immutable
final class BacktestRequest {
  const BacktestRequest({
    required this.symbols,
    required this.timeframes,
    required this.directions,
    required this.minProbability,
    required this.minRiskReward,
    required this.period,
    this.methodId = AnalysisMethod.defaultId,
  });

  /// الأدوات (والطريقة لو انبعتت) من الشاشة، والفلاتر التانية من الاستراتيجية المحفوظة
  factory BacktestRequest.from(
    SignalProfile profile, {
    required Set<String> symbols,
    required BacktestPeriod period,
    String? methodId,
  }) =>
      BacktestRequest(
        methodId: methodId ?? profile.methodId,
        symbols: symbols,
        timeframes: profile.timeframes,
        directions: profile.directions,
        minProbability: profile.minProbability,
        minRiskReward: profile.minRiskReward,
        period: period,
      );

  final Set<String> symbols;
  final Set<Timeframe> timeframes;
  final Set<SignalDirection> directions;
  final double minProbability;
  final double minRiskReward;
  final BacktestPeriod period;

  /// طريقة التحليل يلي بتنختبر ([AnalysisMethod.knownIds])
  final String methodId;

  bool get isValid =>
      AnalysisMethod.isKnown(methodId) && symbols.isNotEmpty && timeframes.isNotEmpty && directions.isNotEmpty;

  /// جسم `POST /backtests` (بترتيب المنتج، حتى نفس الطلب = نفس الجسم)
  Map<String, Object?> toJson() => {
        'method_id': methodId,
        'symbols': [
          for (final s in kProductSymbols)
            if (symbols.contains(s)) s
        ],
        'timeframes': [
          for (final tf in Timeframe.modelTimeframes)
            if (timeframes.contains(tf)) tf.apiValue
        ],
        'directions': [
          for (final d in const [SignalDirection.long, SignalDirection.short])
            if (directions.contains(d)) d.name,
        ],
        'min_probability': minProbability,
        'min_risk_reward': minRiskReward,
        'window_days': period.days,
      };
}

/// نقطة بمنحنى النتيجة: المجموع بوحدات المخاطرة (R) لآخر يوم [time]
@immutable
final class EquityPoint {
  const EquityPoint({required this.time, required this.r, required this.signals});

  /// أول اليوم (UTC)
  final DateTime time;

  /// المجموع لحد هاليوم: هدف = +العائد:المخاطرة، وقف = −1
  final double r;

  /// كم إشارة انحسبت لحد هاليوم
  final int signals;
}

/// نتيجة اختبار: كل رقم جاي من [signals] إشارة (العيّنة بتنعرض جنب كل رقم)
@immutable
final class BacktestResult {
  const BacktestResult({
    required this.period,
    required this.signals,
    required this.hits,
    required this.avgRiskReward,
    required this.maxDrawdown,
    required this.equity,
  });

  final BacktestPeriod period;

  /// كم إشارة سابقة طابقت الاستراتيجية وإلها نتيجة (هدف أو وقف)
  final int signals;

  /// كم وحدة وصلت للهدف قبل الوقف
  final int hits;

  /// متوسط العائد : المخاطرة المخطط (null لما ما في إشارات)
  final double? avgRiskReward;

  /// أكبر تراجع من قمة لقاع، بوحدات R (موجب، 0 = ما في تراجع)
  final double maxDrawdown;

  /// من الأقدم للأحدث، أول نقطة = بداية الفترة على 0. كل الأرقام محسوبة من
  /// النقاط كاملة؛ الرسم بس بياخد [downsampleEquity] منها.
  final List<EquityPoint> equity;

  bool get isEmpty => signals == 0;

  /// نفس شكل دقة Insights (نسبة الإصابة + "عيّنة صغيرة")
  ModelAccuracy get accuracy => ModelAccuracy(resolved: signals, hits: hits, windowDays: period.days);
}

/// أقصى نقاط بمنحنى الرسم (5 سنين ≈ 1800 يوم بتضل مقروءة وخفيفة)
const int kMaxChartPoints = 240;

/// بيقلّل نقاط المنحنى للرسم بدون ما يغيّر شكله: أول وآخر نقطة بيضلوا، والباقي
/// بينقسم لدفعات متساوية وكل دفعة بتحتفظ بأدنى وأعلى نقطة فيها (بترتيب الوقت)،
/// فالقاع والقمة الحقيقيين بيبيّنوا عالرسم. [maxPoints] نقطة أو أقل → نفس القائمة.
List<EquityPoint> downsampleEquity(List<EquityPoint> points, {int maxPoints = kMaxChartPoints}) {
  if (points.length <= maxPoints || maxPoints < 4) return points;
  final inner = points.length - 2;
  final buckets = (maxPoints - 2) ~/ 2;
  final kept = [points.first];
  for (var b = 0; b < buckets; b++) {
    final start = 1 + b * inner ~/ buckets;
    final end = 1 + (b + 1) * inner ~/ buckets;
    if (start >= end) continue;
    var low = start;
    var high = start;
    for (var i = start + 1; i < end; i++) {
      if (points[i].r < points[low].r) low = i;
      if (points[i].r > points[high].r) high = i;
    }
    if (low == high) {
      kept.add(points[low]);
    } else {
      kept
        ..add(points[low < high ? low : high])
        ..add(points[low < high ? high : low]);
    }
  }
  return kept..add(points.last);
}
