import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../controllers/ai_news_analyzer_controller.dart';
import '../../l10n/app_localizations.dart';
import '../../models/news_analysis_model.dart';
import '../../models/news_item_model.dart';
import '../../providers/app_providers.dart';
import '../../providers/screen_providers.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_navigation.dart';
import '../../utils/app_text_styles.dart';
import '../widgets/app_bottom_nav.dart';
import '../widgets/auth_background.dart';
import '../widgets/news_impact_badge.dart';

/// شاشة "AI News Analyzer" — اختيار خبر من قائمة أخبار السوق والحصول
/// على تحليل تأثيره على السوق (Sentiment + توصية تداول)
///
/// الدور المعماري: **View (واجهة)**
/// - تعرض قائمة كل أخبار السوق (من [NewsRepository] المشترك، نفس
///   المصدر المستخدم بـ Home / Market News، فأي خبر جديد بيطلع هون
///   تلقائيًا) - فقط لما تُفتح الشاشة **بدون** خبر محدد مسبقًا
/// - اختيار خبر واحد (Single Selection): إطار أخضر حول الكرت المحدد
///   فقط، وباقي الكروت بدون أي إطار
/// - زر "Analyze Selected News" يبدأ التحليل عبر
///   [AiNewsAnalyzerController]، ونتيجة التحليل بتظهر تحت الزر
///
/// نقاط الوصول لهذه الشاشة:
/// 1. [HomeScreen]: زر "News Analyzer" بقسم Quantitative Intelligence
///    → تفتح بدون خبر محدد مسبقًا، وبتعرض القائمة الكاملة قابلة
///    للاختيار كالمعتاد.
/// 2. [AiAssistantScreen] ("AI Hub"): بطاقة "AI News Analyzer"
///    → نفس سلوك رقم 1.
/// 3. أيقونة الدماغ 🧠 على أي [NewsItemCard] (بمعاينة الهوم أو بقائمة
///    [MarketNewsScreen] الكاملة) → تفتح مع تحديد ذلك الخبر تلقائيًا
///    **ومقفولة عليه**: بيطلع كرت الخبر هو الوحيد المعروض (بدون باقي
///    القائمة)، وكل يلي المستخدم بده يعمله هو الضغط على "Analyze" -
///    بدون إمكانية تبديل الخبر. لو بدو يحلل خبر تاني، لازم يضغط
///    "Analyze Another News" بعد ما تطلع النتيجة (بيفك القفل ويرجع
///    القائمة الكاملة).
/// 4. زر "AI Analyze" بشاشة [NewsDetailScreen] (بعد الضغط على الخبر
///    نفسه ثم الزر) → نفس سلوك رقم 3، تحديد وقفل مسبق لنفس الخبر.
class AiNewsAnalyzerScreen extends ConsumerWidget {
  const AiNewsAnalyzerScreen({super.key, this.initialNewsId});

  /// معرّف خبر لتحديده تلقائيًا فور فتح الشاشة (Preselect) — بيوصل
  /// من أيقونة الدماغ بكرت الخبر أو زر "AI Analyze" بشاشة التفاصيل.
  /// null لما تُفتح الشاشة من "AI Hub" أو زر الوصول السريع بالهوم
  /// (بدون خبر محدد مسبقًا).
  final String? initialNewsId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final newsItems = ref.read(newsRepositoryProvider).newsItems;
    final l10n = AppLocalizations.of(context)!;

    return ProviderScope(
      overrides: [
        aiNewsAnalyzerControllerProvider.overrideWith(
          (ref) => AiNewsAnalyzerController(
            newsItems: newsItems,
            l10n: l10n,
            initialSelectedNewsId: initialNewsId,
          ),
        ),
      ],
      child: const _AiNewsAnalyzerView(),
    );
  }
}

// ═══════════════════════════════════════════════════════════
// Screen View - جسم الشاشة الفعلي
// ═══════════════════════════════════════════════════════════

class _AiNewsAnalyzerView extends ConsumerStatefulWidget {
  const _AiNewsAnalyzerView();

  @override
  ConsumerState<_AiNewsAnalyzerView> createState() =>
      _AiNewsAnalyzerViewState();
}

class _AiNewsAnalyzerViewState extends ConsumerState<_AiNewsAnalyzerView> {
  /// فهرس تبويب AI بشريط التنقل السفلي (نفس فهرس باقي أدوات الـ AI)
  static const int _ownIndex = 2;

  int _selectedBottomIndex = _ownIndex;

  // ═══════════════════════════════════════════════════════════
  // Event Handlers - معالجات الأحداث
  // ═══════════════════════════════════════════════════════════

  /// معالج ضغطات شريط التنقل السفلي - مفوّض بالكامل للمعالج المشترك
  /// [handleGlobalBottomNavTap] حتى يشتغل زر "Markets" (كان مو مفعّل
  /// أساسًا هون) بنفس سلوك باقي شاشات التطبيق.
  void _handleBottomNavTap(int index) => handleGlobalBottomNavTap(index);

  // ═══════════════════════════════════════════════════════════
  // Build Methods - دوال البناء
  // ═══════════════════════════════════════════════════════════

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final controller = ref.watch(aiNewsAnalyzerControllerProvider);

    return Scaffold(
      body: AuthBackground(
        child: SafeArea(
          bottom: false,
          child: Column(
            children: [
              _buildTopBar(),
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
                  children: [
                    _buildHeader(controller.isLocked, l10n),
                    const SizedBox(height: 8),
                    if (controller.isLocked)
                      _buildLockedNewsCard(controller)
                    else
                      for (final news in controller.newsItems)
                        _SelectableNewsCard(
                          news: news,
                          isSelected: controller.selectedNewsId == news.id,
                          onTap: () => controller.selectNews(news.id),
                        ),
                    const SizedBox(height: 8),
                    _buildAnalyzeButton(controller, l10n),
                    if (controller.status.isSuccess &&
                        controller.result != null) ...[
                      const SizedBox(height: 20),
                      _ResultCard(result: controller.result!),
                      const SizedBox(height: 16),
                      _buildAnalyzeAnotherButton(controller, l10n),
                    ],
                  ],
                ),
              ),
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

  /// شريط علوي: سهم رجوع فقط (بدون نص "Back to AI Hub")
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

  /// عنوان الشاشة ووصفها - الوصف بيتغيّر إذا كانت الشاشة [isLocked]
  /// (خبر محدد مسبقًا) حتى يوضّح للمستخدم إنو كل يلي بده يعمله هو
  /// الضغط على "Analyze"، مو اختيار خبر من قائمة.
  Widget _buildHeader(bool isLocked, AppLocalizations l10n) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(0, 8, 0, 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l10n.newsAnalyzerTitle, style: AppTextStyles.heading1),
          const SizedBox(height: 8),
          Text(
            isLocked
                ? l10n.newsAnalyzerSubtitleLocked
                : l10n.newsAnalyzerSubtitleUnlocked,
            style: AppTextStyles.subtitle.copyWith(fontSize: 16),
          ),
        ],
      ),
    );
  }

  /// بطاقة الخبر الوحيدة لما تكون الشاشة [AiNewsAnalyzerController.isLocked]
  /// (خبر محدد مسبقًا) - بتُعرض بشكل ثابت (مو قابلة للضغط) حتى ما
  /// يقدر المستخدم يبدّل الخبر، وبس يضغط زر "Analyze" تحتها مباشرة.
  Widget _buildLockedNewsCard(AiNewsAnalyzerController controller) {
    final news = controller.selectedNews;
    if (news == null) return const SizedBox.shrink();

    return _SelectableNewsCard(
      news: news,
      isSelected: true,
      isLocked: true,
      onTap: null,
    );
  }

  /// زر "Analyze Selected News" — معطّل لحد ما يتم تحديد خبر، وبيعرض
  /// مؤشر تحميل أثناء التحليل
  Widget _buildAnalyzeButton(AiNewsAnalyzerController controller, AppLocalizations l10n) {
    final isAnalyzing = controller.status.isAnalyzing;
    final isEnabled = controller.hasSelection && !isAnalyzing;

    return SizedBox(
      width: double.infinity,
      height: 54,
      child: ElevatedButton(
        onPressed: isEnabled ? controller.analyzeSelected : null,
        style: ElevatedButton.styleFrom(
          disabledBackgroundColor:
              AppColors.accentGreen.withOpacity(controller.hasSelection ? 1 : 0.35),
          disabledForegroundColor: AppColors.buttonText,
        ),
        child: isAnalyzing
            ? Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2.4,
                      color: AppColors.buttonText,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Text(l10n.analyzing),
                ],
              )
            : Text(l10n.analyzeSelectedNews),
      ),
    );
  }

  /// زر "تحليل خبر تاني" — بيرجع الشاشة لحالتها الأولية
  Widget _buildAnalyzeAnotherButton(AiNewsAnalyzerController controller, AppLocalizations l10n) {
    return SizedBox(
      width: double.infinity,
      height: 52,
      child: OutlinedButton(
        onPressed: controller.reset,
        style: OutlinedButton.styleFrom(
          foregroundColor: AppColors.textPrimary,
          side: BorderSide(color: AppColors.fieldBorder.withOpacity(0.6)),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(30),
          ),
        ),
        child: Text(l10n.analyzeAnotherNews),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════
// Sub-widgets - مكونات فرعية
// ═══════════════════════════════════════════════════════════

/// كرت خبر واحد قابل للاختيار داخل القائمة:
/// - غير محدد → خلفية عادية، بدون أي إطار مميّز
/// - محدد → نفس الخلفية + إطار أخضر متوهج حول الكرت بالكامل
/// - [isLocked] → نفس مظهر "محدد" (الإطار الأخضر)، بس مو قابل للضغط
///   وبدون أيقونة دائرة اختيار على الجنب - يُستخدم لما يوصل المستخدم
///   للشاشة بخبر محدد مسبقًا (من أيقونة الدماغ أو زر "AI Analyze")،
///   حتى ما يقدر يبدّل الخبر ويضل هو نفسه المطلوب تحليله.
class _SelectableNewsCard extends StatelessWidget {
  const _SelectableNewsCard({
    required this.news,
    required this.isSelected,
    required this.onTap,
    this.isLocked = false,
  });

  final NewsItemModel news;
  final bool isSelected;
  final bool isLocked;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: isLocked ? null : onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        margin: const EdgeInsets.only(bottom: 14),
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: AppColors.bgSurface.withOpacity(0.92),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isSelected
                ? AppColors.accentGreen
                : AppColors.fieldBorder.withOpacity(0.35),
            width: isSelected ? 1.8 : 1,
          ),
          boxShadow: isSelected
              ? [
                  BoxShadow(
                    color: AppColors.accentGreen.withOpacity(0.25),
                    blurRadius: 16,
                    spreadRadius: 1,
                  ),
                ]
              : null,
        ),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      NewsImpactBadge(impact: news.impact),
                      const Spacer(),
                      Text(
                        news.timeAgo,
                        style: AppTextStyles.bodySmall.copyWith(
                          color: AppColors.textHint,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Text(news.title, style: AppTextStyles.heading3),
                  const SizedBox(height: 8),
                  Text(
                    news.source,
                    style: AppTextStyles.bodySmall.copyWith(
                      color: AppColors.textSecondary,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            if (!isLocked)
              Icon(
                isSelected
                    ? Icons.check_circle_rounded
                    : Icons.radio_button_unchecked_rounded,
                color: isSelected
                    ? AppColors.accentGreen
                    : AppColors.fieldBorder,
                size: 22,
              ),
          ],
        ),
      ),
    );
  }
}

/// كرت نتيجة التحليل: الاتجاه (Sentiment) + نسبة الثقة + مستوى التأثير
/// + الملخص + الأدوات المتأثرة + التوصية
class _ResultCard extends StatelessWidget {
  const _ResultCard({required this.result});

  final NewsAnalysisResultModel result;

  Color get _sentimentColor {
    switch (result.sentiment) {
      case MarketSentiment.bullish:
        return AppColors.buyGreen;
      case MarketSentiment.bearish:
        return AppColors.sellRed;
      case MarketSentiment.neutral:
        return AppColors.accentCyan;
    }
  }

  IconData get _sentimentIcon {
    switch (result.sentiment) {
      case MarketSentiment.bullish:
        return Icons.trending_up_rounded;
      case MarketSentiment.bearish:
        return Icons.trending_down_rounded;
      case MarketSentiment.neutral:
        return Icons.trending_flat_rounded;
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.bgSurface.withOpacity(0.92),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: _sentimentColor.withOpacity(0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: _sentimentColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(30),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(_sentimentIcon, color: _sentimentColor, size: 18),
                    const SizedBox(width: 6),
                    Text(
                      result.sentiment.label(l10n),
                      style: AppTextStyles.bodyMedium.copyWith(
                        color: _sentimentColor,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 10),
              NewsImpactBadge(impact: result.impact),
              const Spacer(),
              Text(
                l10n.confidencePercent(result.confidencePercent.toStringAsFixed(0)),
                style: AppTextStyles.labelSmall.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            result.summary,
            style: AppTextStyles.bodyMedium.copyWith(height: 1.5),
          ),
          const SizedBox(height: 18),
          Divider(color: AppColors.fieldBorder.withOpacity(0.3)),
          const SizedBox(height: 14),
          Text(l10n.affectedAssets, style: AppTextStyles.label),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final asset in result.affectedAssets)
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: AppColors.accentCyan.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(
                      color: AppColors.accentCyan.withOpacity(0.35),
                    ),
                  ),
                  child: Text(
                    asset,
                    style: AppTextStyles.bodySmall.copyWith(
                      color: AppColors.accentCyan,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 18),
          Divider(color: AppColors.fieldBorder.withOpacity(0.3)),
          const SizedBox(height: 14),
          Text(l10n.tradingRecommendation, style: AppTextStyles.label),
          const SizedBox(height: 10),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.lightbulb_outline_rounded,
                  color: _sentimentColor, size: 18),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  result.recommendation,
                  style: AppTextStyles.bodyMedium.copyWith(
                    color: AppColors.textSecondary,
                    height: 1.5,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
