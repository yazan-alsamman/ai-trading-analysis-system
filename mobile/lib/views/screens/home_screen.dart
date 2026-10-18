import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'dart:io';
import '../../controllers/auth_controller.dart';
import '../../controllers/news_repository.dart';
import '../../controllers/notifications_repository.dart';
import '../../l10n/app_localizations.dart';
import '../../models/portfolio_model.dart';
import '../../models/market_item_model.dart';
import '../../models/news_item_model.dart';
import '../../providers/app_providers.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_navigation.dart';
import '../../utils/app_text_styles.dart';
import '../../utils/mock_market_items.dart';
import '../../utils/routes/app_navigator.dart';
import '../widgets/app_bottom_nav.dart';
import '../widgets/market_picker_sheet.dart';
import '../widgets/portfolio_card.dart';
import '../widgets/market_overview_carousel.dart';
import '../widgets/news_item_card.dart';
import '../widgets/registration_background.dart';

/// الصفحة الرئيسية - Home Screen
/// 
/// الدور المعماري: **View (واجهة)**
/// - عرض معلومات المحفظة
/// - عرض نظرة على السوق
/// - عرض الأخبار
/// - التنقل لشاشات أخرى
class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});
  
  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  // ═══════════════════════════════════════════════════════════
  // Mock Data - بيانات تجريبية
  // ═══════════════════════════════════════════════════════════
  
  final _portfolio = const PortfolioModel(
    name: 'Main Portfolio',
    totalEquity: 124583.50,
    dailyChange: 1107.30,
    dailyChangePercent: 0.88,
    availableBalance: 124583.50,
    marginUsed: 45000.00,
    profitLoss: 25690.80,
    profitLossPercent: 279.31,
  );
  
  // القائمة نفسها صارت مشتركة بملف utils/mock_market_items.dart حتى
  // يقدر زر "Markets" بالـ navbar يفتحها من أي شاشة بالتطبيق، مش بس
  // من الـ Home. راجع _marketItems getter تحت.
  List<MarketItemModel> get _marketItems => kDefaultMarketItems;
  
  /// معرّفات الخبرين المعروضين بمعاينة الأخبار المصغّرة هون (بنفس ترتيبهم
  /// الأصلي) - البيانات الفعلية (وعدد التعليقات الحيّ) بتجي من
  /// [NewsRepository] المشترك مع باقي شاشات التطبيق
  static const _previewNewsIds = ['fed-rate-decision', 'gold-prices-steady'];

  int _selectedBottomIndex = 0;
  
  // ═══════════════════════════════════════════════════════════
  // Event Handlers - معالجات الأحداث
  // ═══════════════════════════════════════════════════════════
  
  void _handleTrade(MarketItemModel item) {
    context.pushTrade(item);
  }
  
  void _handleReadMore(NewsItemModel news) {
    context.pushNewsDetail(
      news: news,
      onAnalyzeWithAi: () => _handleAnalyzeWithAi(news),
      onCommentsCountChanged: (newCount) =>
          ref.read(newsRepositoryProvider).updateCommentsCount(news.id, newCount),
    );
  }

  /// فتح "AI News Analyzer" مع تحديد هالخبر تلقائيًا (Preselect) —
  /// يُستدعى من أيقونة الدماغ بكرت الخبر، ومن زر "AI Analyze" بشاشة
  /// تفاصيل الخبر
  void _handleAnalyzeWithAi(NewsItemModel news) {
    context.pushAiNewsAnalyzer(initialNewsId: news.id);
  }

  /// فتح "AI News Analyzer" بدون خبر محدد مسبقًا — من زر "News Analyzer"
  /// بقسم Quantitative Intelligence
  void _handleOpenNewsAnalyzer() {
    context.pushAiNewsAnalyzer();
  }

  /// فتح شاشة "Discussion" الكاملة عند الضغط على عدّاد التعليقات
  void _handleShowComments(NewsItemModel news) {
    context.pushDiscussion(
      newsId: news.id,
      newsTitle: news.title,
      commentsCount: news.commentsCount,
      onCommentsCountChanged: (newCount) =>
          ref.read(newsRepositoryProvider).updateCommentsCount(news.id, newCount),
    );
  }
  
  /// فتح شاشة "Market News" الكاملة من رابط "Read More" بقسم Market Intel
  void _handleReadMoreAll() {
    context.pushMarketNews();
  }

  /// فتح شاشة شات AI Strategy Assistant مباشرة من زر "AI Quick Access"
  /// (بدون المرور بصفحة AI Hub)
  void _handleOpenAiChat() {
    context.pushAiChat();
  }

  /// فتح شاشة AI Chart Analyzer مباشرة من زر "Chart Analyzer"
  /// (بدون المرور بصفحة AI Hub)
  void _handleOpenChartAnalyzer() {
    context.pushAiChartAnalyzer();
  }

  /// فتح شاشة الإشعارات من أيقونة الجرس بأعلى الهوم
  void _handleOpenNotifications() {
    context.pushNotifications();
  }

  /// فتح "Profile Settings" من الضغط على اسم المستخدم بأعلى الهوم
  void _handleOpenProfile() {
    context.pushProfile();
  }
  
  /// معالج ضغطات شريط التنقل السفلي - مفوّض بالكامل للمعالج المشترك
  /// [handleGlobalBottomNavTap] حتى يشتغل بنفس السلوك المضبوط من كل
  /// شاشات التطبيق (راجع utils/app_navigation.dart لتفاصيل ليش).
  Future<void> _handleBottomNavTap(int index) => handleGlobalBottomNavTap(index);

  /// يعرض قائمة الأسواق كـ Bottom Sheet ويرجع السوق اللي اختاره المستخدم
  /// (أو null إذا سكّر القائمة بدون اختيار)
  Future<MarketItemModel?> _pickMarket() {
    return showModalBottomSheet<MarketItemModel>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (_) => MarketPickerSheet(items: _marketItems),
    );
  }
  
  // ═══════════════════════════════════════════════════════════
  // Build Methods - دوال البناء
  // ═══════════════════════════════════════════════════════════
  
  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return Scaffold(
      body: RegistrationBackground(
        child: SafeArea(
          child: Column(
            children: [
              _buildHeader(l10n),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.only(bottom: 20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const SizedBox(height: 16),
                      PortfolioCard(portfolio: _portfolio),
                      const SizedBox(height: 24),
                      _buildMarketOverview(l10n),
                      const SizedBox(height: 24),
                      _buildQuantitativeIntelligence(l10n),
                      const SizedBox(height: 24),
                      _buildNewsSection(l10n),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
      bottomNavigationBar: _buildBottomNav(),
    );
  }
  
  /// بناء الرأس
  Widget _buildHeader(AppLocalizations l10n) {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      child: Row(
        children: [
          // بطاقة المستخدم - صورة/حرف أول + اسمه، بتفتح "Profile Settings"
          _buildUserChip(l10n),

          const Spacer(),

          // أيقونة الإشعارات
          _buildNotificationBell(),
        ],
      ),
    );
  }

  /// بطاقة صغيرة بأعلى الهوم تعرض صورة/حرف المستخدم واسمه المعروض
  /// (بدل اسم المحفظة سابقًا) - قابلة للضغط، بتفتح [ProfileScreen]
  /// ("Profile Settings") مباشرة
  Widget _buildUserChip(AppLocalizations l10n) {
    final user = ref.watch(authControllerProvider).currentUser;
    final displayName = user?.displayName?.trim().isNotEmpty == true
        ? user!.displayName!
        : l10n.trader;
    final initial = displayName.isNotEmpty ? displayName[0].toUpperCase() : 'T';
    final avatarPath = user?.avatarUrl;

    return InkWell(
      onTap: _handleOpenProfile,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: const Color(0xFF0D2539),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: AppColors.fieldBorder.withOpacity(0.3),
            width: 1,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: AppColors.accentGreen,
                shape: BoxShape.circle,
                image: avatarPath != null
                    ? DecorationImage(
                        image: FileImage(File(avatarPath)),
                        fit: BoxFit.cover,
                      )
                    : null,
              ),
              child: avatarPath == null
                  ? Center(
                      child: Text(
                        initial,
                        style: AppTextStyles.labelSmall.copyWith(
                          color: AppColors.buttonText,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    )
                  : null,
            ),
            const SizedBox(width: 10),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  l10n.welcome,
                  style: AppTextStyles.labelSmall.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  displayName,
                  style: AppTextStyles.bodyMedium.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
            const SizedBox(width: 8),
            Icon(
              Icons.keyboard_arrow_down_rounded,
              color: AppColors.textSecondary,
              size: 20,
            ),
          ],
        ),
      ),
    );
  }
  
  /// أيقونة الجرس + نقطة حمرا فوقها بعدد الإشعارات غير المقروءة
  /// (من [NotificationsRepository] المشترك) - النقطة ما بتظهر إذا
  /// العدد صفر
  Widget _buildNotificationBell() {
    final unreadCount = ref.watch(notificationsRepositoryProvider).unreadCount;

    return InkWell(
      onTap: _handleOpenNotifications,
      borderRadius: BorderRadius.circular(22),
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: const Color(0xFF0D2539),
              shape: BoxShape.circle,
              border: Border.all(
                color: AppColors.fieldBorder.withOpacity(0.3),
                width: 1,
              ),
            ),
            child: Center(
              child: Icon(
                Icons.notifications_none_rounded,
                color: AppColors.textPrimary,
                size: 24,
              ),
            ),
          ),
          if (unreadCount > 0)
            Positioned(
              top: -4,
              right: -4,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                constraints: const BoxConstraints(minWidth: 18, minHeight: 18),
                decoration: BoxDecoration(
                  color: AppColors.error,
                  borderRadius: BorderRadius.circular(9),
                  border: Border.all(color: AppColors.bgDeep, width: 1.5),
                ),
                child: Center(
                  child: Text(
                    unreadCount > 99 ? '99+' : '$unreadCount',
                    style: AppTextStyles.labelSmall.copyWith(
                      color: AppColors.textPrimary,
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                      height: 1,
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
  
  /// بناء نظرة السوق
  Widget _buildMarketOverview(AppLocalizations l10n) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Text(
            l10n.marketOverview,
            style: AppTextStyles.heading3.copyWith(
              fontSize: 16,
            ),
          ),
        ),
        const SizedBox(height: 16),
        MarketOverviewCarousel(
          items: _marketItems,
          onTrade: _handleTrade,
        ),
      ],
    );
  }
  
  /// بناء الذكاء الكمي
  Widget _buildQuantitativeIntelligence(AppLocalizations l10n) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            l10n.quantitativeIntelligence,
            style: AppTextStyles.heading3.copyWith(
              fontSize: 16,
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _QuickAccessButton(
                  imagePath: 'assets/images/strategy_assistant.png',
                  label: l10n.aiQuickAccess,
                  onTap: _handleOpenAiChat,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _QuickAccessButton(
                  imagePath: 'assets/images/chart_analyzer_icon.png',
                  label: l10n.chartAnalyzer,
                  onTap: _handleOpenChartAnalyzer,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _QuickAccessButton(
                  imagePath: 'assets/images/nav_pages.png',
                  label: l10n.newsAnalyzer,
                  onTap: _handleOpenNewsAnalyzer,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
  
  /// بناء قسم الأخبار
  Widget _buildNewsSection(AppLocalizations l10n) {
    final previewNews = ref.watch(newsRepositoryProvider).byIds(_previewNewsIds);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // رأس القسم: Market Intel + Read More
          Row(
            children: [
              Text(
                l10n.marketIntel,
                style: AppTextStyles.heading3.copyWith(
                  fontSize: 16,
                ),
              ),
              const Spacer(),
              GestureDetector(
                onTap: _handleReadMoreAll,
                child: Text(
                  l10n.readMore,
                  style: AppTextStyles.link.copyWith(
                    fontSize: 13,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          ...previewNews.map(
            (news) => NewsItemCard(
              news: news,
              onReadMore: () => _handleReadMore(news),
              onAnalyzeWithAi: () => _handleAnalyzeWithAi(news),
              onShowComments: () => _handleShowComments(news),
            ),
          ),
        ],
      ),
    );
  }
  
  /// بناء شريط التنقل السفلي
  Widget _buildBottomNav() {
    return AppBottomNav(
      selectedIndex: _selectedBottomIndex,
      onTap: _handleBottomNavTap,
    );
  }
}

// ═══════════════════════════════════════════════════════════
// Sub-widgets - مكونات فرعية
// ═══════════════════════════════════════════════════════════

/// زر الوصول السريع
class _QuickAccessButton extends StatelessWidget {
  const _QuickAccessButton({
    required this.imagePath,
    required this.label,
    required this.onTap,
  });
  
  final String imagePath;
  final String label;
  final VoidCallback onTap;
  
  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 16),
        decoration: BoxDecoration(
          color: const Color(0xFF0D2539),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: AppColors.fieldBorder.withOpacity(0.3),
            width: 1,
          ),
        ),
        child: Column(
          children: [
            Image.asset(
              imagePath,
              width: 32,
              height: 32,
              color: AppColors.accentCyan,
            ),
            const SizedBox(height: 8),
            Text(
              label,
              style: AppTextStyles.labelSmall.copyWith(
                color: AppColors.textSecondary,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

