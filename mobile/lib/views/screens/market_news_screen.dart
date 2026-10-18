import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../controllers/news_repository.dart';
import '../../l10n/app_localizations.dart';
import '../../models/news_item_model.dart';
import '../../providers/app_providers.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_navigation.dart';
import '../../utils/app_text_styles.dart';
import '../../utils/routes/app_navigator.dart';
import '../widgets/app_bottom_nav.dart';
import '../widgets/auth_background.dart';
import '../widgets/news_item_card.dart';

/// شاشة "Market News" - تعرض كل أخبار السوق (مو بس معاينة مصغّرة)
///
/// الدور المعماري: **View (واجهة)**
/// - صورة ترويجية أعلى الشاشة (نفس لغة [AiAssistantScreen])
/// - قائمة كاملة بأخبار السوق، كل خبر ببطاقة [NewsItemCard]
/// - كل البيانات تجي من [NewsRepository] المشترك (نفس المصدر يلي
///   [HomeScreen] و[DiscussionScreen] عم يقرأوا منه)، حتى عدد
///   التعليقات يبقى متطابق بكل شاشة بأي وقت
///
/// نقاط الوصول لهذه الشاشة:
/// - من [HomeScreen]: زر "Read More" بقسم "Market Intel"
/// - من شريط التنقل السفلي: أيقونة الصفحات (index == 4، ثاني عنصر
///   من الآخر) بأي شاشة رئيسية بالتطبيق
class MarketNewsScreen extends ConsumerStatefulWidget {
  const MarketNewsScreen({super.key});

  @override
  ConsumerState<MarketNewsScreen> createState() => _MarketNewsScreenState();
}

class _MarketNewsScreenState extends ConsumerState<MarketNewsScreen> {
  /// فهرس تبويب "News" (أيقونة الصفحات) بشريط التنقل السفلي
  static const int _ownIndex = 3;

  int _selectedBottomIndex = _ownIndex;

  // ═══════════════════════════════════════════════════════════
  // Event Handlers - معالجات الأحداث
  // ═══════════════════════════════════════════════════════════

  /// معالج ضغطات شريط التنقل السفلي - مفوّض بالكامل للمعالج المشترك
  /// [handleGlobalBottomNavTap] حتى تشتغل كل الأزرار (Markets/AI/News)
  /// من هون كمان، مش بس زر Home يلي كان مفعّل لحاله.
  void _handleBottomNavTap(int index) => handleGlobalBottomNavTap(index);

  void _handleReadMore(NewsItemModel news) {
    final repository = ref.read(newsRepositoryProvider);
    context.pushNewsDetail(
      news: news,
      onAnalyzeWithAi: () => _handleAnalyzeWithAi(news),
      onCommentsCountChanged: (newCount) =>
          repository.updateCommentsCount(news.id, newCount),
    );
  }

  /// فتح "AI News Analyzer" مع تحديد هالخبر تلقائيًا (Preselect) —
  /// يُستدعى من أيقونة الدماغ بكرت الخبر، ومن زر "AI Analyze" بشاشة
  /// تفاصيل الخبر
  void _handleAnalyzeWithAi(NewsItemModel news) {
    context.pushAiNewsAnalyzer(initialNewsId: news.id);
  }

  /// فتح شاشة "Discussion" الكاملة عند الضغط على عدّاد التعليقات
  void _handleShowComments(NewsItemModel news) {
    final repository = ref.read(newsRepositoryProvider);
    context.pushDiscussion(
      newsId: news.id,
      newsTitle: news.title,
      commentsCount: news.commentsCount,
      onCommentsCountChanged: (newCount) =>
          repository.updateCommentsCount(news.id, newCount),
    );
  }

  // ═══════════════════════════════════════════════════════════
  // Build Methods - دوال البناء
  // ═══════════════════════════════════════════════════════════

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final repository = ref.watch(newsRepositoryProvider);

    return Scaffold(
      body: AuthBackground(
        child: SafeArea(
          bottom: false,
          child: Column(
            children: [
              _buildTopBar(),
              Expanded(child: _buildBody(repository, l10n)),
            ],
          ),
        ),
      ),
      bottomNavigationBar: AppBottomNav(
        selectedIndex: _selectedBottomIndex,
        onTap: _handleBottomNavTap,
      ),
    );
  }

  /// شريط علوي: سهم رجوع بسيط
  Widget _buildTopBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(10, 6, 10, 0),
      child: Row(
        children: [
          InkWell(
            onTap: () => Navigator.of(context).maybePop(),
            borderRadius: BorderRadius.circular(14),
            child: const Padding(
              padding: EdgeInsets.all(12),
              child: Icon(
                Icons.arrow_back_rounded,
                color: AppColors.textPrimary,
                size: 22,
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// محتوى الشاشة: صورة ترويجية + عنوان + قائمة الأخبار
  Widget _buildBody(NewsRepository repository, AppLocalizations l10n) {
    if (repository.isLoading) {
      return const Center(
        child: CircularProgressIndicator(color: AppColors.accentGreen),
      );
    }

    return RefreshIndicator(
      color: AppColors.accentGreen,
      backgroundColor: AppColors.bgSurface,
      onRefresh: repository.refresh,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
        children: [
          _buildHero(),
          const SizedBox(height: 4),
          Text(
            l10n.marketNews,
            style: AppTextStyles.heading1.copyWith(fontSize: 30),
          ),
          const SizedBox(height: 20),
          for (final news in repository.newsItems)
            NewsItemCard(
              news: news,
              onReadMore: () => _handleReadMore(news),
              onAnalyzeWithAi: () => _handleAnalyzeWithAi(news),
              onShowComments: () => _handleShowComments(news),
            ),
        ],
      ),
    );
  }

  /// الصورة الترويجية أعلى الشاشة (شارت صاعد + كرة أرضية)
  Widget _buildHero() {
    return Image.asset(
      'assets/images/market_news_hero.png',
      width: double.infinity,
      height: 320,
      fit: BoxFit.contain,
    );
  }
}
