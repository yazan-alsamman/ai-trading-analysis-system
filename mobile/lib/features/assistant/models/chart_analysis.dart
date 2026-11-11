import 'package:flutter/foundation.dart';

import '../../forecast/models/forecast_path.dart';
import '../../markets/models/market_models.dart';
import '../../signals/models/opportunity.dart';
import '../../signals/models/signal_plan.dart';

/// الشكل الفني يلي بالصورة (أسماء محايدة: ما بتعطي اتجاه لحالها)
enum ChartPattern {
  channel('channel'),
  triangle('triangle'),
  range('range'),
  flag('flag'),
  wedge('wedge');

  const ChartPattern(this.apiValue);

  final String apiValue;

  static ChartPattern? fromApi(String? value) {
    for (final p in values) {
      if (p.apiValue == value) return p;
    }
    return null;
  }
}

/// حركة السعر بالصورة نفسها (الماضي المرسوم، مش رأي) - بتنعرض بس لما ما
/// انقرأت الأداة، لأن مع أداة الاتجاه بيجي من الاستراتيجية المحفوظة
enum PictureTrend {
  rising('rising'),
  falling('falling'),
  sideways('sideways');

  const PictureTrend(this.apiValue);

  final String apiValue;

  static PictureTrend? fromApi(String? value) {
    for (final t in values) {
      if (t.apiValue == value) return t;
    }
    return null;
  }
}

/// شو انقرا من الصورة (ناتج الخادم، محفوظ ببصمة الصورة). ما فيه احتمال ولا
/// مستويات: هدول دايمًا من الاستراتيجية المحفوظة (نفس أرقام Signals).
@immutable
final class ChartImageAnalysis {
  const ChartImageAnalysis({
    required this.imageSha256,
    required this.pattern,
    required this.trend,
    required this.analysedAt,
    this.symbol,
    this.timeframe,
  });

  final String imageSha256;

  /// null = الرمز ما بيّن بالصورة
  final String? symbol;

  /// null = الإطار ما بيّن بالصورة
  final Timeframe? timeframe;
  final ChartPattern pattern;
  final PictureTrend trend;
  final DateTime analysedAt;

  bool get hasInstrument => symbol != null && timeframe != null;

  @override
  bool operator ==(Object other) =>
      other is ChartImageAnalysis &&
      other.imageSha256 == imageSha256 &&
      other.symbol == symbol &&
      other.timeframe == timeframe &&
      other.pattern == pattern &&
      other.trend == trend &&
      other.analysedAt == analysedAt;

  @override
  int get hashCode => Object.hash(imageSha256, symbol, timeframe, pattern, trend, analysedAt);
}

/// أول لحظة باليوم الجاي (توقيت الجهاز) - حدّ اليوم للعدّاد
DateTime nextLocalMidnight(DateTime now) {
  final local = now.toLocal();
  return DateTime(local.year, local.month, local.day + 1);
}

/// الحد اليومي لتحليل الصور، لكل مستخدم
@immutable
final class ChartAnalysisQuota {
  const ChartAnalysisQuota({required this.used, required this.limit, required this.resetAt});

  /// الحد بالمحاكاة (الخادم بيقرّر الحقيقي)
  static const int simulatedDailyLimit = 5;

  /// يوم جديد: صفر من [limit]
  factory ChartAnalysisQuota.fresh(DateTime now, {int limit = simulatedDailyLimit}) =>
      ChartAnalysisQuota(used: 0, limit: limit, resetAt: nextLocalMidnight(now));

  final int used;
  final int limit;

  /// إيمتى بيرجع العدّاد صفر
  final DateTime resetAt;

  int get remaining => used >= limit ? 0 : limit - used;

  bool get reached => used >= limit;

  /// نفس الحد بوقت [now]: بعد [resetAt] يوم جديد (العدّاد صفر)
  ChartAnalysisQuota at(DateTime now) => now.isBefore(resetAt) ? this : ChartAnalysisQuota.fresh(now, limit: limit);

  @override
  bool operator ==(Object other) =>
      other is ChartAnalysisQuota && other.used == used && other.limit == limit && other.resetAt == resetAt;

  @override
  int get hashCode => Object.hash(used, limit, resetAt);
}

/// وصلت للحد اليومي - الـ repository بيرميه (والـ 429 تبع الـ API بيتحوّل له)
final class DailyLimitReachedException implements Exception {
  const DailyLimitReachedException(this.resetAt);

  final DateTime resetAt;

  @override
  String toString() => 'DailyLimitReachedException(resetAt: $resetAt)';
}

/// ما في اتصال: ما انبعت شي
final class ChartAnalysisOfflineException implements Exception {
  const ChartAnalysisOfflineException();
}

/// الطلب انلغى قبل ما يخلص (ما بيتحسب من الحد بالمحاكاة)
final class ChartAnalysisCancelledException implements Exception {
  const ChartAnalysisCancelledException();
}

/// إلغاء تحليل جاري
final class ChartAnalysisCancelToken {
  bool _cancelled = false;

  bool get isCancelled => _cancelled;

  void cancel() => _cancelled = true;
}

/// الصورة يلي رح تنبعت (بعد التحقق)
@immutable
final class ChartImageUpload {
  const ChartImageUpload({required this.bytes, required this.sha256, required this.fileName});

  final Uint8List bytes;
  final String sha256;
  final String fileName;
}

/// نتيجة طلب التحليل: [fromCache] = نفس الصورة من قبل، ما انحسبت من الحد
@immutable
final class ChartAnalysisOutcome {
  const ChartAnalysisOutcome({required this.analysis, required this.quota, required this.fromCache});

  final ChartImageAnalysis analysis;
  final ChartAnalysisQuota quota;
  final bool fromCache;
}

/// صورة مختارة وجاهزة للتحليل (المعاينة)
@immutable
final class ChartDraft {
  const ChartDraft({required this.path, required this.bytes, required this.sha256, this.cached = false});

  final String path;
  final Uint8List bytes;
  final String sha256;

  /// نفس الصورة انحلّلت قبل: النتيجة محفوظة وما بتنحسب (حتى لو الحد خلص)
  final bool cached;

  int get sizeBytes => bytes.length;

  String get fileName {
    final slash = path.replaceAll(r'\', '/').lastIndexOf('/');
    return slash < 0 ? path : path.substring(slash + 1);
  }

  /// "PNG" / "JPG" من أول بايتات الملف
  String get typeLabel => isPng(bytes) ? 'PNG' : 'JPG';
}

bool isPng(List<int> b) =>
    b.length >= 8 &&
    b[0] == 0x89 &&
    b[1] == 0x50 &&
    b[2] == 0x4E &&
    b[3] == 0x47 &&
    b[4] == 0x0D &&
    b[5] == 0x0A &&
    b[6] == 0x1A &&
    b[7] == 0x0A;

bool isJpeg(List<int> b) => b.length >= 3 && b[0] == 0xFF && b[1] == 0xD8 && b[2] == 0xFF;

/// جواب تحليل الصورة كما بينعرض ببطاقة الجواب: قراءة الصورة + رأي الاستراتيجية
/// المحفوظة على نفس الأداة والإطار ([signal] من نفس مصدر قائمة Signals).
@immutable
final class ChartAnalysisReply {
  const ChartAnalysisReply({
    required this.analysis,
    required this.methodId,
    required this.fromCache,
    this.instrument,
    this.signal,
    this.plan,
  });

  final ChartImageAnalysis analysis;

  /// الأداة إذا انقرأت من الصورة وهي من أدوات المنتج
  final Instrument? instrument;

  /// إشارة الاستراتيجية على نفس الإطار (null = ما في إعداد)
  final Opportunity? signal;

  /// مستويات [signal] بنفس حساب شاشة التفاصيل
  final SignalPlan? plan;
  final String methodId;
  final bool fromCache;

  Timeframe? get timeframe => analysis.timeframe;

  /// "High probability" بنفس قاعدة التوقّع على الرسم ([ForecastLikelihood.high]، ≥ 70%)
  bool get isHighProbability => signal != null && ForecastLikelihood.of(signal!.probability) == ForecastLikelihood.high;
}
