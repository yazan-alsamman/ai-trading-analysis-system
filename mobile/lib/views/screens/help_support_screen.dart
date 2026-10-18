import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../l10n/app_localizations.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_text_styles.dart';
import '../widgets/auth_background.dart';

/// شاشة "Help & Support" - أسئلة شائعة وطرق التواصل مع الدعم
///
/// الدور المعماري: **View (واجهة)**
///
/// تُفتح من "Help & Support" بـ [ProfileScreen]
class HelpSupportScreen extends StatelessWidget {
  const HelpSupportScreen({super.key});

  /// نسخ نص للحافظة وعرض تأكيد بسيط بالأسفل
  void _copyToClipboard(
    BuildContext context,
    String value,
    String label,
    AppLocalizations l10n,
  ) {
    Clipboard.setData(ClipboardData(text: value));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(l10n.copiedToClipboard(label)),
        backgroundColor: AppColors.bgSurface,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;

    return Scaffold(
      body: AuthBackground(
        child: SafeArea(
          bottom: false,
          child: Column(
            children: [
              _buildTopBar(context, l10n),
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
                  children: [
                    const SizedBox(height: 8),
                    _buildSectionLabel(l10n.contactUs),
                    const SizedBox(height: 12),
                    _ContactTile(
                      icon: Icons.email_outlined,
                      title: l10n.emailSupport,
                      subtitle: 'support@tradex.app',
                      onTap: () => _copyToClipboard(
                        context,
                        'support@tradex.app',
                        l10n.emailAddressLabel,
                        l10n,
                      ),
                    ),
                    _ContactTile(
                      icon: Icons.chat_bubble_outline_rounded,
                      title: l10n.liveChat,
                      subtitle: l10n.avgResponseTime,
                      onTap: () => _copyToClipboard(
                        context,
                        'support@tradex.app',
                        l10n.emailAddressLabel,
                        l10n,
                      ),
                    ),
                    _ContactTile(
                      icon: Icons.phone_outlined,
                      title: l10n.callUs,
                      subtitle: '+1 (800) 555-0199',
                      onTap: () => _copyToClipboard(
                        context,
                        '+18005550199',
                        l10n.phoneNumberLabel,
                        l10n,
                      ),
                    ),
                    const SizedBox(height: 24),
                    _buildSectionLabel(l10n.frequentlyAskedQuestions),
                    const SizedBox(height: 12),
                    _FaqTile(
                      question: l10n.faqFundQuestion,
                      answer: l10n.faqFundAnswer,
                    ),
                    _FaqTile(
                      question: l10n.faqFirstTradeQuestion,
                      answer: l10n.faqFirstTradeAnswer,
                    ),
                    _FaqTile(
                      question: l10n.faqProtectedQuestion,
                      answer: l10n.faqProtectedAnswer,
                    ),
                    _FaqTile(
                      question: l10n.faqAiQuestion,
                      answer: l10n.faqAiAnswer,
                    ),
                    _FaqTile(
                      question: l10n.faqWithdrawQuestion,
                      answer: l10n.faqWithdrawAnswer,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// شريط علوي: سهم رجوع + عنوان الشاشة
  Widget _buildTopBar(BuildContext context, AppLocalizations l10n) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(10, 6, 20, 0),
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
          const SizedBox(width: 4),
          Text(l10n.helpAndSupport, style: AppTextStyles.heading2),
        ],
      ),
    );
  }

  /// عنوان قسم صغير
  Widget _buildSectionLabel(String label) {
    return Text(
      label,
      style: AppTextStyles.label.copyWith(
        color: AppColors.textHint,
        letterSpacing: 0.6,
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════
// Sub-widgets - مكونات فرعية
// ═══════════════════════════════════════════════════════════

/// بطاقة طريقة تواصل واحدة (بريد / شات / اتصال)
class _ContactTile extends StatelessWidget {
  const _ContactTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppColors.bgSurface.withOpacity(0.7),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.fieldBorder.withOpacity(0.3)),
        ),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: AppColors.accentCyan.withOpacity(0.15),
                shape: BoxShape.circle,
              ),
              child: Icon(icon, color: AppColors.accentCyan, size: 20),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: AppTextStyles.bodyMedium.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    subtitle,
                    style: AppTextStyles.bodySmall.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(
              Icons.copy_rounded,
              color: AppColors.textHint,
              size: 18,
            ),
          ],
        ),
      ),
    );
  }
}

/// سؤال شائع قابل للطي/الفرد (Expandable FAQ item)
class _FaqTile extends StatefulWidget {
  const _FaqTile({required this.question, required this.answer});

  final String question;
  final String answer;

  @override
  State<_FaqTile> createState() => _FaqTileState();
}

class _FaqTileState extends State<_FaqTile> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.bgSurface.withOpacity(0.7),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.fieldBorder.withOpacity(0.3)),
      ),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          initiallyExpanded: _expanded,
          onExpansionChanged: (value) => setState(() => _expanded = value),
          tilePadding: EdgeInsets.zero,
          childrenPadding: const EdgeInsets.only(bottom: 14),
          iconColor: AppColors.accentCyan,
          collapsedIconColor: AppColors.textHint,
          title: Text(
            widget.question,
            style: AppTextStyles.bodyMedium.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          children: [
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                widget.answer,
                style: AppTextStyles.bodySmall.copyWith(
                  color: AppColors.textSecondary,
                  height: 1.5,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
