import 'package:flutter/foundation.dart';

import '../l10n/app_localizations.dart';
import '../models/news_analysis_model.dart';
import '../models/news_item_model.dart';

// ═══════════════════════════════════════════════════════════
// AI News Analyzer Controller - متحكم شاشة تحليل الأخبار بالـ AI
// ═══════════════════════════════════════════════════════════

/// متحكم إدارة حالة شاشة AI News Analyzer
///
/// مسؤوليات هذا الكلاس:
/// - إدارة اختيار خبر واحد من قائمة الأخبار (Single Selection - نفس
///   منطق زر Radio: خبر واحد محدد بأي لحظة، والضغط عليه تاني بيلغي
///   تحديده)
/// - دعم "تحديد مسبق" (Preselect) لما تُفتح الشاشة من زر "AI Analyze"
///   بكرت خبر أو بشاشة تفاصيل الخبر، حتى يطلع الخبر محدد فورًا
///   (بالإطار الأخضر) بدون ما يضطر المستخدم يدوس عليه من جديد
/// - إدارة حالة التحليل (idle / analyzing / success)
/// - توليد نتيجة التحليل (حاليًا محاكاة مبنية على بيانات الخبر، لحين
///   ربط API حقيقي)
///
/// ⚠️ IMPORTANT: الواجهة (View) ما بتبني منطق الاختيار أو التحليل
/// بنفسها، كل شي بيمر من هون، بنفس نمط [AiChartAnalyzerController]
final class AiNewsAnalyzerController extends ChangeNotifier {
  AiNewsAnalyzerController({
    required List<NewsItemModel> newsItems,
    required AppLocalizations l10n,
    String? initialSelectedNewsId,
  })  : _newsItems = newsItems,
        _l10n = l10n,
        _selectedNewsId = initialSelectedNewsId,
        _isLocked = initialSelectedNewsId != null;

  // ═══════════════════════════════════════════════════════════
  // Private State - الحالة الخاصة
  // ═══════════════════════════════════════════════════════════

  final List<NewsItemModel> _newsItems;
  final AppLocalizations _l10n;
  String? _selectedNewsId;

  /// true لما تكون الشاشة انفتحت بخبر محدد مسبقًا (من أيقونة الدماغ
  /// بكرت الخبر، أو زر "AI Analyze" بشاشة تفاصيل الخبر) - بهاي الحالة
  /// المستخدم ما بينقدر يغيّر الخبر المحدد، وكل يلي بده يعمله هو
  /// يضغط "Analyze" مباشرة. لما تُفتح الشاشة بدون خبر محدد مسبقًا
  /// (من AI Hub مثلًا)، القائمة الكاملة بتضل قابلة للاختيار كالمعتاد.
  bool _isLocked;
  NewsAnalysisStatus _status = NewsAnalysisStatus.idle;
  NewsAnalysisResultModel? _result;

  // ═══════════════════════════════════════════════════════════
  // Public Getters - القيم العامة (للقراءة فقط)
  // ═══════════════════════════════════════════════════════════

  /// كل الأخبار المعروضة بالشاشة
  List<NewsItemModel> get newsItems => List.unmodifiable(_newsItems);

  /// معرّف الخبر المحدد حاليًا (null لو ما في خبر محدد)
  String? get selectedNewsId => _selectedNewsId;

  /// كائن الخبر المحدد حاليًا بالكامل (null لو ما في خبر محدد، أو
  /// إذا معرّفه ما عاد موجود بالقائمة)
  NewsItemModel? get selectedNews =>
      _newsItems.where((n) => n.id == _selectedNewsId).firstOrNull;

  /// هل في خبر محدد حاليًا؟
  bool get hasSelection => _selectedNewsId != null;

  /// هل الاختيار مقفول على خبر محدد مسبقًا؟ (راجع توثيق [_isLocked])
  bool get isLocked => _isLocked;

  /// حالة عملية التحليل الحالية
  NewsAnalysisStatus get status => _status;

  /// نتيجة آخر تحليل ناجح (null قبل التحليل)
  NewsAnalysisResultModel? get result => _result;

  // ═══════════════════════════════════════════════════════════
  // Public Actions - العمليات العامة
  // ═══════════════════════════════════════════════════════════

  /// تحديد/إلغاء تحديد خبر معيّن (Single Selection):
  /// - إذا الخبر المضغوط مو المحدد حاليًا → يصير هو المحدد (والإطار
  ///   الأخضر بينتقل له)
  /// - إذا الخبر المضغوط هو نفسه المحدد أصلًا → يلغى تحديده
  ///
  /// لا تأثير للدالة إذا كانت الشاشة [isLocked] (خبر محدد مسبقًا) -
  /// المستخدم ما بينقدر يبدّل الخبر بهاي الحالة.
  ///
  /// أي تغيير بالاختيار بيمسح نتيجة التحليل السابقة (لأنها كانت
  /// لخبر تاني) ويرجّع الحالة idle.
  void selectNews(String newsId) {
    if (_isLocked) return;
    _selectedNewsId = _selectedNewsId == newsId ? null : newsId;
    _result = null;
    _status = NewsAnalysisStatus.idle;
    notifyListeners();
  }

  /// بدء تحليل الخبر المحدد حاليًا
  Future<void> analyzeSelected() async {
    final newsId = _selectedNewsId;
    if (newsId == null || _status.isAnalyzing) return;

    _status = NewsAnalysisStatus.analyzing;
    notifyListeners();

    final news = _newsItems.where((n) => n.id == newsId).firstOrNull;
    if (news == null) {
      _status = NewsAnalysisStatus.idle;
      notifyListeners();
      return;
    }

    // TODO: استبدال هذا بـ API call حقيقي عبر NewsAnalysisService
    // (تمرير نص الخبر لنموذج AI والحصول على تحليل فعلي)
    await Future.delayed(const Duration(seconds: 2));

    _result = _mockResultFor(news);
    _status = NewsAnalysisStatus.success;
    notifyListeners();
  }

  /// إعادة الشاشة لحالتها الأولية، لتحليل خبر جديد من الصفر.
  ///
  /// بتفك القفل (لو كانت الشاشة انفتحت بخبر محدد مسبقًا) حتى يقدر
  /// المستخدم يتصفح ويختار أي خبر تاني من القائمة الكاملة.
  void reset() {
    _selectedNewsId = null;
    _isLocked = false;
    _result = null;
    _status = NewsAnalysisStatus.idle;
    notifyListeners();
  }

  // ═══════════════════════════════════════════════════════════
  // Private Helper Methods - دوال مساعدة خاصة
  // ═══════════════════════════════════════════════════════════

  /// توليد نتيجة تحليل تجريبية مبنية على بيانات الخبر (بديل مؤقت لحين
  /// ربط نموذج AI حقيقي) - لكل خبر معروف من [NewsRepository] تحليل
  /// مخصص واقعي، ولأي خبر تاني بيتولّد تحليل عام بالاعتماد على مستوى
  /// تأثيره (impact)
  NewsAnalysisResultModel _mockResultFor(NewsItemModel news) {
    return _knownResultFor(news.id) ?? _genericResultFor(news);
  }

  /// تحليلات مخصصة لأخبار [NewsRepository] المعروفة، لتجربة أقرب
  /// لواقع الأداة الفعلية
  NewsAnalysisResultModel? _knownResultFor(String newsId) {
    switch (newsId) {
      case 'fed-rate-decision':
        return NewsAnalysisResultModel(
          newsId: newsId,
          sentiment: MarketSentiment.bullish,
          confidencePercent: 87,
          impact: NewsImpactLevel.high,
          summary: _l10n.newsAnalysisFedSummary,
          affectedAssets: const ['EUR/USD', 'GOLD', 'US30'],
          recommendation: _l10n.newsAnalysisFedRecommendation,
        );
      case 'ecb-rate-cuts':
        return NewsAnalysisResultModel(
          newsId: newsId,
          sentiment: MarketSentiment.bullish,
          confidencePercent: 71,
          impact: NewsImpactLevel.medium,
          summary: _l10n.newsAnalysisEcbSummary,
          affectedAssets: const ['EUR/USD', 'EUR/GBP'],
          recommendation: _l10n.newsAnalysisEcbRecommendation,
        );
      case 'gold-prices-steady':
        return NewsAnalysisResultModel(
          newsId: newsId,
          sentiment: MarketSentiment.neutral,
          confidencePercent: 54,
          impact: NewsImpactLevel.low,
          summary: _l10n.newsAnalysisGoldSummary,
          affectedAssets: const ['GOLD'],
          recommendation: _l10n.newsAnalysisGoldRecommendation,
        );
      case 'uk-retail-sales':
        return NewsAnalysisResultModel(
          newsId: newsId,
          sentiment: MarketSentiment.bullish,
          confidencePercent: 58,
          impact: NewsImpactLevel.low,
          summary: _l10n.newsAnalysisUkSummary,
          affectedAssets: const ['GBP/USD', 'GBP/JPY'],
          recommendation: _l10n.newsAnalysisUkRecommendation,
        );
      default:
        return null;
    }
  }

  /// تحليل عام (Fallback) لأي خبر ما إله تحليل مخصص جاهز، مبني على
  /// مستوى تأثيره فقط
  NewsAnalysisResultModel _genericResultFor(NewsItemModel news) {
    final MarketSentiment sentiment;
    final double confidence;
    switch (news.impact) {
      case NewsImpactLevel.high:
        sentiment = MarketSentiment.bullish;
        confidence = 80;
      case NewsImpactLevel.medium:
        sentiment = MarketSentiment.neutral;
        confidence = 62;
      case NewsImpactLevel.low:
        sentiment = MarketSentiment.neutral;
        confidence = 48;
    }

    final impactLabel = switch (news.impact) {
      NewsImpactLevel.high => _l10n.impactLevelHigh,
      NewsImpactLevel.medium => _l10n.impactLevelMedium,
      NewsImpactLevel.low => _l10n.impactLevelLow,
    };
    final volatilityLabel = news.impact == NewsImpactLevel.high
        ? _l10n.volatilitySignificant
        : _l10n.volatilityLimited;

    return NewsAnalysisResultModel(
      newsId: news.id,
      sentiment: sentiment,
      confidencePercent: confidence,
      impact: news.impact,
      summary: _l10n.newsAnalysisGenericSummary(impactLabel, volatilityLabel),
      affectedAssets: [_l10n.relatedMarketPairs],
      recommendation: _l10n.newsAnalysisGenericRecommendation,
    );
  }
}

/// مساعدة صغيرة: أول عنصر مطابق أو null (بديل محلي عن حزمة collection)
extension _FirstOrNull<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
