import '../../../core/data/json.dart';
import '../../../core/network/api_exception.dart';
import '../../markets/models/market_models.dart';
import '../models/chart_analysis.dart';

/// تحويل JSON تحليل الصورة (الشكل المقترح للـ API، ونفسه للتخزين المحلي) ↔ domain.
///
/// API (مقترح): `ChartAnalysisRead` = `{image_sha256, symbol, timeframe,
/// pattern, trend, analysed_at}` و `quota` = `{limit, used, reset_at}`.
/// TODO(API): الشكل مش موجود بالـ backend لسّا؛ إذا اختلف بيتغيّر هالملف بس.
abstract final class ChartAnalysisDto {
  /// null لو ناقص أو قيمة مش معروفة (ما منعرض تحليل نص مفهوم)
  static ChartImageAnalysis? fromJson(Json json) {
    final sha = json.string('image_sha256');
    final pattern = ChartPattern.fromApi(json.string('pattern'));
    final trend = PictureTrend.fromApi(json.string('trend'));
    final analysedAt = json.dateTime('analysed_at');
    if (sha == null || sha.isEmpty || pattern == null || trend == null || analysedAt == null) return null;
    final symbol = json.string('symbol');
    final timeframe = Timeframe.fromApi(json.string('timeframe'));
    // رمز بدون إطار (أو العكس) ما بيكفي لنقارن مع الاستراتيجية
    final known = symbol != null && kProductSymbols.contains(symbol) && timeframe != null;
    return ChartImageAnalysis(
      imageSha256: sha,
      symbol: known ? symbol : null,
      timeframe: known ? timeframe : null,
      pattern: pattern,
      trend: trend,
      analysedAt: analysedAt,
    );
  }

  static Map<String, Object?> toJson(ChartImageAnalysis a) => {
        'image_sha256': a.imageSha256,
        'symbol': a.symbol,
        'timeframe': a.timeframe?.apiValue,
        'pattern': a.pattern.apiValue,
        'trend': a.trend.apiValue,
        'analysed_at': a.analysedAt.toUtc().toIso8601String(),
      };

  /// `{limit, used, reset_at}` → الحد (null لو ناقص)
  static ChartAnalysisQuota? quotaFromJson(Json json) {
    final limit = json.integer('limit');
    final used = json.integer('used');
    final resetAt = json.dateTime('reset_at');
    if (limit == null || limit <= 0 || used == null || used < 0 || resetAt == null) return null;
    // وقت الجهاز (العرض والمقارنة مع حدّ اليوم المحلي)
    return ChartAnalysisQuota(used: used, limit: limit, resetAt: resetAt.toLocal());
  }

  static Map<String, Object?> quotaToJson(ChartAnalysisQuota q) => {
        'limit': q.limit,
        'used': q.used,
        'reset_at': q.resetAt.toUtc().toIso8601String(),
      };
}

/// أخطاء الـ API → أخطاء الميزة (طبقة الـ repository / DTO):
/// - 429 `rateLimited` → [DailyLimitReachedException] بوقت `resetAt` (من
///   `Retry-After` / `RateLimit-Reset`، E1)، وإذا الخادم ما بعت وقت: أول اليوم الجاي.
/// - ما في اتصال / طوّل → [ChartAnalysisOfflineException].
/// - غير هيك: نفس الخطأ.
/// TODO(API): الـ repository الحقيقي بيلفّ كل طلب بـ [mapChartAnalysisErrors].
Object mapChartAnalysisError(Object error, {required DateTime now}) {
  if (error is! ApiException) return error;
  if (error.kind == ApiErrorKind.rateLimited) {
    return DailyLimitReachedException(error.resetAt ?? nextLocalMidnight(now));
  }
  if (error.isOffline) return const ChartAnalysisOfflineException();
  return error;
}

extension ChartAnalysisErrorMapping<T> on Future<T> {
  /// `repo.post(...).mapChartAnalysisErrors(clock)`
  Future<T> mapChartAnalysisErrors(DateTime Function() clock) =>
      catchError((Object error) => throw mapChartAnalysisError(error, now: clock()));
}
