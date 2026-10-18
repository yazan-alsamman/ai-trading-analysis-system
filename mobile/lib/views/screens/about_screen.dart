import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_text_styles.dart';
import '../widgets/auth_background.dart';

/// شاشة "About TradeX" - معلومات عن التطبيق ونسخته والوثائق القانونية
///
/// الدور المعماري: **View (واجهة)**
///
/// تُفتح من "About TradeX" بـ [ProfileScreen]
class AboutScreen extends StatelessWidget {
  const AboutScreen({super.key});

  /// رقم نسخة التطبيق - مطابق لـ `version` بملف pubspec.yaml
  static const String _appVersion = '1.0.0';
  static const String _buildNumber = '1';

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
                    const SizedBox(height: 16),
                    _buildAppBadge(),
                    const SizedBox(height: 28),
                    _buildInfoRow(l10n.version, _appVersion),
                    _buildInfoRow(l10n.buildNumber, _buildNumber),
                    _buildInfoRow(l10n.platform, 'Flutter'),
                    const SizedBox(height: 24),
                    _buildSectionLabel(l10n.aboutThisApp),
                    const SizedBox(height: 12),
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: AppColors.bgSurface.withOpacity(0.7),
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(
                          color: AppColors.fieldBorder.withOpacity(0.3),
                        ),
                      ),
                      child: Text(
                        l10n.aboutBody,
                        style: AppTextStyles.bodySmall.copyWith(
                          color: AppColors.textSecondary,
                          height: 1.6,
                        ),
                      ),
                    ),
                    const SizedBox(height: 24),
                    _buildSectionLabel(l10n.legal),
                    const SizedBox(height: 12),
                    _buildLegalTile(
                      icon: Icons.description_outlined,
                      title: l10n.termsOfService,
                    ),
                    _buildLegalTile(
                      icon: Icons.privacy_tip_outlined,
                      title: l10n.privacyPolicy,
                    ),
                    _buildLegalTile(
                      icon: Icons.gavel_rounded,
                      title: l10n.riskDisclosure,
                    ),
                    const SizedBox(height: 24),
                    Center(
                      child: Text(
                        '© ${DateTime.now().year} TradeX. All rights reserved.',
                        style: AppTextStyles.bodySmall.copyWith(
                          color: AppColors.textHint,
                        ),
                      ),
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
          Text(l10n.aboutTradeX, style: AppTextStyles.heading2),
        ],
      ),
    );
  }

  /// شعار التطبيق + الاسم، بأعلى الشاشة
  Widget _buildAppBadge() {
    return Center(
      child: Column(
        children: [
          Container(
            width: 88,
            height: 88,
            decoration: BoxDecoration(
              gradient: AppColors.brandGradient,
              borderRadius: BorderRadius.circular(24),
              boxShadow: [
                BoxShadow(
                  color: AppColors.gradientEnd.withOpacity(0.3),
                  blurRadius: 20,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            child: const Icon(
              Icons.candlestick_chart_rounded,
              color: AppColors.buttonText,
              size: 44,
            ),
          ),
          const SizedBox(height: 16),
          Text('TradeX', style: AppTextStyles.heading1.copyWith(fontSize: 24)),
        ],
      ),
    );
  }

  /// صف معلومة بسيطة (تسمية + قيمة)
  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: AppTextStyles.bodyMedium.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          Text(
            value,
            style: AppTextStyles.bodyMedium.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
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

  /// صف وثيقة قانونية (بدون إجراء فعلي حاليًا - محتوى نصي فقط لحين
  /// وجود صفحات قانونية حقيقية)
  Widget _buildLegalTile({required IconData icon, required String title}) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.bgSurface.withOpacity(0.7),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.fieldBorder.withOpacity(0.3)),
      ),
      child: Row(
        children: [
          Icon(icon, color: AppColors.accentCyan, size: 20),
          const SizedBox(width: 14),
          Expanded(
            child: Text(
              title,
              style: AppTextStyles.bodyMedium.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          const Icon(
            Icons.chevron_right_rounded,
            color: AppColors.textHint,
            size: 22,
          ),
        ],
      ),
    );
  }
}
