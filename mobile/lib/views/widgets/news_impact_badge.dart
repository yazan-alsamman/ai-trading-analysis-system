import 'package:flutter/material.dart';
import '../../models/news_item_model.dart';
import '../../l10n/app_localizations.dart';
import '../../utils/app_colors.dart';

// ═══════════════════════════════════════════════════════════
// News Impact Badge - شارة مستوى تأثير الخبر
// ═══════════════════════════════════════════════════════════

/// شارة صغيرة (Pill) تعرض مستوى تأثير الخبر بلون مرتبط بالحالة:
/// - [NewsImpactLevel.high]   → أحمر (نفس لغة "بيع/خطر" بالتطبيق)
/// - [NewsImpactLevel.medium] → أصفر-أخضر (تحذير متوسط)
/// - [NewsImpactLevel.low]    → أخضر (نفس لغة "شراء/آمن" بالتطبيق)
///
/// الدور المعماري: **View (واجهة) - Widget قابل لإعادة الاستخدام**
class NewsImpactBadge extends StatelessWidget {
  const NewsImpactBadge({super.key, required this.impact});

  final NewsImpactLevel impact;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final color = _colorFor(impact);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color, width: 1.4),
      ),
      child: Text(
        _labelFor(impact, l10n),
        style: TextStyle(
          fontFamily: 'SF Pro Display',
          fontSize: 12,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.4,
          color: color,
        ),
      ),
    );
  }

  String _labelFor(NewsImpactLevel impact, AppLocalizations l10n) {
    switch (impact) {
      case NewsImpactLevel.high:
        return l10n.highImpact;
      case NewsImpactLevel.medium:
        return l10n.mediumImpact;
      case NewsImpactLevel.low:
        return l10n.lowImpact;
    }
  }

  Color _colorFor(NewsImpactLevel impact) {
    switch (impact) {
      case NewsImpactLevel.high:
        return AppColors.sellRed;
      case NewsImpactLevel.medium:
        return AppColors.gradientStart;
      case NewsImpactLevel.low:
        return AppColors.buyGreen;
    }
  }
}
