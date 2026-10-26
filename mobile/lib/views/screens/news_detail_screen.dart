import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';
import '../../models/news_item_model.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_text_styles.dart';
import '../../utils/routes/app_navigator.dart';
import '../widgets/auth_background.dart';
import '../widgets/news_impact_badge.dart';

// ═══════════════════════════════════════════════════════════
// News Detail Screen - شاشة تفاصيل خبر واحد
// ═══════════════════════════════════════════════════════════

/// شاشة تفاصيل خبر واحد بالكامل
///
/// الدور المعماري: **View (واجهة)**
///
/// نقاط الوصول لهذه الشاشة:
/// - من [HomeScreen]: الضغط على أي [NewsItemCard] بمعاينة الأخبار المصغّرة
/// - من [MarketNewsScreen]: الضغط على أي [NewsItemCard] بالقائمة الكاملة
///
/// تعرض: شارة التأثير + الوقت، العنوان، النص الكامل، زر "AI Analyze"،
/// وعدّاد التعليقات (يفتح نفس شاشة [DiscussionScreen] المستخدمة بباقي
/// الشاشات، بنفس بيانات الخبر وبنفس سلوك الإضافة/الحذف - وعدد
/// التعليقات هون بينعكس مباشرة على [NewsRepository] المشترك عبر
/// [onCommentsCountChanged]، فبيبقى متطابق مع الهوم وMarket News).
class NewsDetailScreen extends StatefulWidget {
  const NewsDetailScreen({
    super.key,
    required this.news,
    this.onAnalyzeWithAi,
    this.onCommentsCountChanged,
  });

  /// بيانات الخبر الكاملة
  final NewsItemModel news;

  /// يُستدعى عند الضغط على زر "AI Analyze"
  final VoidCallback? onAnalyzeWithAi;

  /// يُستدعى كل مرة يتغيّر فيها عدد التعليقات (إضافة/حذف) من الـ Bottom
  /// Sheet، حتى الشاشة الأصلية (Home / Market News) تحدّث العدّاد المعروض
  /// عندها لنفس الخبر
  final ValueChanged<int>? onCommentsCountChanged;

  @override
  State<NewsDetailScreen> createState() => _NewsDetailScreenState();
}

class _NewsDetailScreenState extends State<NewsDetailScreen> {
  late int _commentsCount = widget.news.commentsCount;

  void _handleShowComments() {
    context.pushDiscussion(
      newsId: widget.news.id,
      newsTitle: widget.news.title,
      commentsCount: _commentsCount,
      onCommentsCountChanged: (newCount) {
        setState(() => _commentsCount = newCount);
        widget.onCommentsCountChanged?.call(newCount);
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return Scaffold(
      body: AuthBackground(
        child: SafeArea(
          child: Column(
            children: [
              _buildTopBar(l10n),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _buildCard(),
                      const SizedBox(height: 20),
                      _buildActionsRow(l10n),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// شريط علوي: سهم رجوع + "Back to News"
  Widget _buildTopBar(AppLocalizations l10n) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 6, 10, 0),
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
          const SizedBox(width: 2),
          Text(l10n.backToNews, style: AppTextStyles.heading2),
        ],
      ),
    );
  }

  /// كرت تفاصيل الخبر: شارة التأثير + الوقت، العنوان، النص الكامل
  Widget _buildCard() {
    final news = widget.news;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: AppColors.bgSurface.withOpacity(0.75),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: AppColors.fieldBorder.withOpacity(0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              NewsImpactBadge(impact: news.impact),
              Text(
                news.timeAgo,
                style: AppTextStyles.bodySmall.copyWith(
                  color: AppColors.textHint,
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          Text(news.title, style: AppTextStyles.heading2),
          const SizedBox(height: 16),
          Text(
            news.content,
            style: AppTextStyles.bodyMedium.copyWith(
              color: AppColors.textSecondary,
              height: 1.6,
            ),
          ),
        ],
      ),
    );
  }

  /// صف الأزرار: "AI Analyze" (يسار) + عدّاد التعليقات (يمين)
  Widget _buildActionsRow(AppLocalizations l10n) {
    return Row(
      children: [
        Expanded(child: _buildAnalyzeButton(l10n)),
        const SizedBox(width: 14),
        Expanded(child: _buildCommentsButton(l10n)),
      ],
    );
  }

  Widget _buildAnalyzeButton(AppLocalizations l10n) {
    return InkWell(
      onTap: widget.onAnalyzeWithAi,
      borderRadius: BorderRadius.circular(26),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          color: AppColors.accentGreen,
          borderRadius: BorderRadius.circular(26),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Image.asset(
              'assets/images/strategy_assistant.png',
              width: 20,
              height: 20,
            ),
            const SizedBox(width: 8),
            Text(l10n.aiAnalyze, style: AppTextStyles.buttonSmall),
          ],
        ),
      ),
    );
  }

  Widget _buildCommentsButton(AppLocalizations l10n) {
    return InkWell(
      onTap: _handleShowComments,
      borderRadius: BorderRadius.circular(26),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          color: AppColors.bgSurface,
          borderRadius: BorderRadius.circular(26),
          border: Border.all(color: AppColors.fieldBorder.withOpacity(0.5)),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.mode_comment_outlined,
              size: 18,
              color: AppColors.textSecondary,
            ),
            const SizedBox(width: 8),
            Text(
              l10n.commentsCount(_commentsCount),
              style: AppTextStyles.bodyMedium.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
