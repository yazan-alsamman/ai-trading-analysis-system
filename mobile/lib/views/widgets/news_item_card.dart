import 'package:flutter/material.dart';
import '../../models/news_item_model.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_text_styles.dart';
import 'news_impact_badge.dart';

// ═══════════════════════════════════════════════════════════
// News Item Card - بطاقة خبر واحد
// ═══════════════════════════════════════════════════════════

/// بطاقة عرض خبر من السوق
///
/// الدور المعماري: **View (واجهة) - Widget قابل لإعادة الاستخدام**
/// تُستخدم بمعاينة الأخبار المصغّرة في [HomeScreen] وبقائمة
/// [MarketNewsScreen] الكاملة، لضمان نفس اللغة البصرية بكل مكان.
///
/// التخطيط (من فوق لتحت):
/// 1. شارة التأثير (High/Medium/Low) + الوقت
/// 2. العنوان
/// 3. الوصف
/// 4. خط فاصل رفيع
/// 5. تعليقات + زر "حلّل بالـ AI" (يسار) + المصدر (يمين)
class NewsItemCard extends StatelessWidget {
  const NewsItemCard({
    super.key,
    required this.news,
    required this.onReadMore,
    this.onAnalyzeWithAi,
    this.onShowComments,
  });

  /// بيانات الخبر
  final NewsItemModel news;

  /// يُستدعى عند الضغط على الكارد ككل (فتح تفاصيل الخبر)
  final VoidCallback onReadMore;

  /// يُستدعى عند الضغط على أيقونة الدماغ (تحليل الخبر بالـ AI)
  /// اختياري: إذا ما تم تمريره، ما تُعرض الأيقونة كعنصر تفاعلي مستقل
  /// (بتبقى معروضة بصريًا بس بدون Handler خاص فيها، فبتاخد سلوك الكارد).
  final VoidCallback? onAnalyzeWithAi;

  /// يُستدعى عند الضغط على عدّاد التعليقات (لفتح قائمة التعليقات)
  /// اختياري: إذا ما تم تمريره، عدّاد التعليقات بياخد سلوك الكارد العادي.
  final VoidCallback? onShowComments;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onReadMore,
      child: Container(
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: AppColors.bgSurface.withOpacity(0.92),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: AppColors.fieldBorder.withOpacity(0.35),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildTopRow(),
            const SizedBox(height: 16),
            Text(news.title, style: AppTextStyles.heading3),
            const SizedBox(height: 10),
            Text(
              news.description,
              style: AppTextStyles.bodySmall.copyWith(
                color: AppColors.textSecondary,
                height: 1.5,
              ),
            ),
            const SizedBox(height: 16),
            Divider(
              height: 1,
              color: AppColors.fieldBorder.withOpacity(0.35),
            ),
            const SizedBox(height: 14),
            _buildFooterRow(),
          ],
        ),
      ),
    );
  }

  /// شارة التأثير + الوقت منذ النشر
  Widget _buildTopRow() {
    return Row(
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
    );
  }

  /// عدد التعليقات (قابل للضغط) + زر تحليل AI (يسار) والمصدر (يمين)
  Widget _buildFooterRow() {
    return Row(
      children: [
        GestureDetector(
          onTap: onShowComments,
          behavior: HitTestBehavior.opaque,
          child: Row(
            children: [
              const Icon(
                Icons.mode_comment_outlined,
                size: 18,
                color: AppColors.textSecondary,
              ),
              const SizedBox(width: 6),
              Text(
                '${news.commentsCount}',
                style: AppTextStyles.bodySmall.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: 18),
        GestureDetector(
          onTap: onAnalyzeWithAi,
          child: Image.asset(
            'assets/images/strategy_assistant.png',
            width: 20,
            height: 20,
            color: AppColors.accentGreen,
          ),
        ),
        const Spacer(),
        Text(
          news.source,
          style: AppTextStyles.bodySmall.copyWith(
            color: AppColors.textSecondary,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}
