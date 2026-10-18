import '../l10n/app_localizations.dart';

/// حالة عملية تحليل الشارت بشاشة AI Chart Analyzer
enum ChartAnalysisStatus {
  /// لسا ما في صورة مختارة، أو صورة مختارة وبعدها ما انبدأ التحليل
  idle,

  /// جاري تحليل الصورة حاليًا
  analyzing,

  /// التحليل نجح والنتيجة جاهزة بـ [AiChartAnalyzerController.result]
  success,

  /// صار خطأ (نوع/حجم صورة غير صالح، أو فشل التحليل)
  failure;

  bool get isAnalyzing => this == ChartAnalysisStatus.analyzing;

  bool get isSuccess => this == ChartAnalysisStatus.success;
}

/// اتجاه السوق المستنتج من تحليل الشارت
enum ChartTrend {
  bullish,
  bearish,
  neutral;

  /// النص المعروض بالواجهة - بيتطلب [AppLocalizations] حتى يرجع
  /// بلغة التطبيق الحالية (بدل getter ثابت باللغة الإنجليزية بس)
  String label(AppLocalizations l10n) {
    switch (this) {
      case ChartTrend.bullish:
        return l10n.trendBullish;
      case ChartTrend.bearish:
        return l10n.trendBearish;
      case ChartTrend.neutral:
        return l10n.trendNeutral;
    }
  }
}

/// نتيجة تحليل شارت واحدة (immutable)
///
/// تُبنى من [AiChartAnalyzerController] بعد انتهاء التحليل (حقيقي
/// أو تجريبي، حسب ما هو مربوط حاليًا بالـ Controller)
final class ChartAnalysisResultModel {
  const ChartAnalysisResultModel({
    required this.trend,
    required this.confidencePercent,
    required this.summary,
    required this.keyLevels,
  });

  /// الاتجاه العام المستنتج (صاعد/هابط/محايد)
  final ChartTrend trend;

  /// نسبة ثقة الـ AI بالتحليل (0-100)
  final double confidencePercent;

  /// وصف تحليلي مختصر عن حالة الشارت
  final String summary;

  /// مستويات سعرية أساسية (دعم/مقاومة/هدف...) كنصوص جاهزة للعرض
  final List<String> keyLevels;

  @override
  String toString() =>
      'ChartAnalysisResultModel(trend: $trend, confidence: $confidencePercent%)';
}
