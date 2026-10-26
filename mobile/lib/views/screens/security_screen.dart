import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../controllers/auth_controller.dart';
import '../../l10n/app_localizations.dart';
import '../../providers/app_providers.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_text_styles.dart';
import '../../utils/validators.dart';
import '../widgets/auth_background.dart';
import '../widgets/custom_text_field.dart';
import '../widgets/gradient_button.dart';

/// شاشة "Security" - تغيير كلمة المرور وضبط خيارات الحماية
/// (بصمة/Face ID، تحقق بخطوتين، تنبيهات تسجيل دخول)
///
/// الدور المعماري: **View (واجهة)**
/// - تغيير كلمة المرور يمر عبر [AuthController.changePassword]
/// - مفاتيح التبديل (Switches) حالة عرض محلية بسيطة لحين ربط
///   إعدادات الحساب الحقيقية بـ API
///
/// تُفتح من "Security" بـ [ProfileScreen]
class SecurityScreen extends ConsumerStatefulWidget {
  const SecurityScreen({super.key});

  @override
  ConsumerState<SecurityScreen> createState() => _SecurityScreenState();
}

class _SecurityScreenState extends ConsumerState<SecurityScreen> {
  final _formKey = GlobalKey<FormState>();
  final _currentPasswordController = TextEditingController();
  final _newPasswordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();

  bool _biometricEnabled = false;
  bool _twoFactorEnabled = false;
  bool _loginAlertsEnabled = true;

  @override
  void dispose() {
    _currentPasswordController.dispose();
    _newPasswordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  // ═══════════════════════════════════════════════════════════
  // Event Handlers - معالجات الأحداث
  // ═══════════════════════════════════════════════════════════

  /// تحقق من صحة النموذج ثم استدعاء [AuthController.changePassword]
  Future<void> _handleChangePassword() async {
    final l10n = AppLocalizations.of(context)!;
    FocusScope.of(context).unfocus();
    if (!(_formKey.currentState?.validate() ?? false)) return;

    final controller = ref.read(authControllerProvider);
    final success = await controller.changePassword(
      currentPassword: _currentPasswordController.text,
      newPassword: _newPasswordController.text,
    );

    if (!mounted) return;

    if (success) {
      _currentPasswordController.clear();
      _newPasswordController.clear();
      _confirmPasswordController.clear();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(l10n.passwordUpdatedSuccessfully),
          backgroundColor: AppColors.bgSurface,
          behavior: SnackBarBehavior.floating,
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(controller.passwordError ?? l10n.couldNotUpdatePassword),
          backgroundColor: AppColors.error,
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  // ═══════════════════════════════════════════════════════════
  // Build Methods - دوال البناء
  // ═══════════════════════════════════════════════════════════

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final isChangingPassword =
        ref.watch(authControllerProvider).isChangingPassword;

    return Scaffold(
      body: AuthBackground(
        child: SafeArea(
          bottom: false,
          child: Column(
            children: [
              _buildTopBar(l10n),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const SizedBox(height: 8),
                      _buildSectionLabel(l10n.changePassword),
                      const SizedBox(height: 12),
                      Form(
                        key: _formKey,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            CustomTextField(
                              label: l10n.currentPassword,
                              hint: l10n.enterCurrentPassword,
                              controller: _currentPasswordController,
                              isPassword: true,
                              prefixIcon: Icons.lock_outline_rounded,
                              validator: (value) => Validators.required(
                                value,
                                l10n,
                                fieldName: l10n.currentPassword,
                              ),
                            ),
                            const SizedBox(height: 20),
                            CustomTextField(
                              label: l10n.newPassword,
                              hint: l10n.enterNewPassword,
                              controller: _newPasswordController,
                              isPassword: true,
                              prefixIcon: Icons.lock_reset_rounded,
                              validator: (value) => Validators.password(value, l10n),
                            ),
                            const SizedBox(height: 6),
                            Align(
                              alignment: Alignment.centerLeft,
                              child: Text(
                                l10n.passwordRequirementsHint,
                                style: AppTextStyles.labelSmall.copyWith(
                                  color: AppColors.textHint,
                                ),
                              ),
                            ),
                            const SizedBox(height: 14),
                            CustomTextField(
                              label: l10n.confirmNewPassword,
                              hint: l10n.reEnterNewPassword,
                              controller: _confirmPasswordController,
                              isPassword: true,
                              prefixIcon: Icons.lock_outline_rounded,
                              validator: (value) => Validators.confirmPassword(
                                value,
                                _newPasswordController.text,
                                l10n,
                              ),
                            ),
                            const SizedBox(height: 24),
                            GradientButton(
                              label: l10n.updatePassword,
                              isLoading: isChangingPassword,
                              onPressed:
                                  isChangingPassword ? null : _handleChangePassword,
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 32),
                      _buildSectionLabel(l10n.protection),
                      const SizedBox(height: 12),
                      _buildSwitchTile(
                        icon: Icons.fingerprint_rounded,
                        title: l10n.biometricLogin,
                        subtitle: l10n.biometricLoginSubtitle,
                        value: _biometricEnabled,
                        onChanged: (value) =>
                            setState(() => _biometricEnabled = value),
                      ),
                      _buildSwitchTile(
                        icon: Icons.verified_user_outlined,
                        title: l10n.twoFactorAuth,
                        subtitle: l10n.twoFactorAuthSubtitle,
                        value: _twoFactorEnabled,
                        onChanged: (value) =>
                            setState(() => _twoFactorEnabled = value),
                      ),
                      _buildSwitchTile(
                        icon: Icons.notifications_active_outlined,
                        title: l10n.newLoginAlerts,
                        subtitle: l10n.newLoginAlertsSubtitle,
                        value: _loginAlertsEnabled,
                        onChanged: (value) =>
                            setState(() => _loginAlertsEnabled = value),
                      ),
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

  /// شريط علوي: سهم رجوع + عنوان الشاشة
  Widget _buildTopBar(AppLocalizations l10n) {
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
          Text(l10n.security, style: AppTextStyles.heading2),
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

  /// عنصر تبديل (Switch) بنفس هوية بطاقات الإعدادات بـ [ProfileScreen]
  Widget _buildSwitchTile({
    required IconData icon,
    required String title,
    required String subtitle,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
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
          Switch(
            value: value,
            onChanged: onChanged,
            activeColor: AppColors.accentGreen,
          ),
        ],
      ),
    );
  }
}
