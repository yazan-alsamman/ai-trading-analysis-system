import '../l10n/app_localizations.dart';
import 'news_item_model.dart';

// ═══════════════════════════════════════════════════════════
// News Analysis Model - موديل تحليل الخبر بالـ AI
// ═══════════════════════════════════════════════════════════

/// حالة عملية تحليل الخبر بشاشة AI News Analyzer
enum NewsAnalysisStatus {
  /// لسا ما في خبر مختار، أو خبر مختار وبعدها ما انبدأ التحليل
  idle,

  /// جاري تحليل الخبر حاليًا
  analyzing,

  /// التحليل نجح والنتيجة جاهزة بـ [AiNewsAnalyzerController.result]
  success;

  bool get isAnalyzing => this == NewsAnalysisStatus.analyzing;

  bool get isSuccess => this == NewsAnalysisStatus.success;
}

/// اتجاه السوق المتوقّع نتيجة الخبر (Sentiment)
enum MarketSentiment {
  bullish,
  bearish,
  neutral;

  /// النص المعروض بالواجهة (يحتاج [AppLocalizations] لأن النص يتغيّر
  /// حسب لغة التطبيق الحالية - نفس نمط [OrderType] بملف order_type_model)
  String label(AppLocalizations l10n) {
    switch (this) {
      case MarketSentiment.bullish:
        return l10n.sentimentBullish;
      case MarketSentiment.bearish:
        return l10n.sentimentBearish;
      case MarketSentiment.neutral:
        return l10n.sentimentNeutral;
    }
  }
}

/// نتيجة تحليل خبر واحد بالـ AI (immutable)
///
/// تُبنى من [AiNewsAnalyzerController] بعد انتهاء التحليل (حاليًا محاكاة
/// مبنية على بيانات الخبر نفسه، ريثما تُربط بنموذج AI حقيقي)
final class NewsAnalysisResultModel {
  const NewsAnalysisResultModel({
    required this.newsId,
    required this.sentiment,
    required this.confidencePercent,
    required this.impact,
    required this.summary,
    required this.affectedAssets,
    required this.recommendation,
  });

  /// معرّف الخبر يلي التحليل هذا بيخصّه
  final String newsId;

  /// الاتجاه المتوقّع للسوق (صاعد/هابط/محايد)
  final MarketSentiment sentiment;

  /// نسبة ثقة الـ AI بالتحليل (0-100)
  final double confidencePercent;

  /// مستوى تأثير الخبر على السوق (نفس تصنيف [NewsItemModel.impact])
  final NewsImpactLevel impact;

  /// ملخص تحليلي عن تأثير الخبر على السوق
  final String summary;

  /// الأدوات/الأزواج المالية الأكثر تأثرًا بهذا الخبر
  final List<String> affectedAssets;

  /// توصية تداول مختصرة مبنية على التحليل
  final String recommendation;

  @override
  String toString() =>
      'NewsAnalysisResultModel(sentiment: $sentiment, confidence: $confidencePercent%)';
}
