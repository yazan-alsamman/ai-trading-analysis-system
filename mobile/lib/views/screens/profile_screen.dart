import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../controllers/auth_controller.dart';
import '../../l10n/app_localizations.dart';
import '../../models/user_model.dart';
import '../../providers/app_providers.dart';
import '../../providers/locale_provider.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_navigation.dart';
import '../../utils/app_text_styles.dart';
import '../../utils/routes/app_navigator.dart';
import '../widgets/app_bottom_nav.dart';
import '../widgets/auth_background.dart';
import '../widgets/screen_back_button.dart';

/// شاشة "Profile Settings" - تعرض بيانات المستخدم الحالي وخيارات الإعدادات
///
/// الدور المعماري: **View (واجهة)**
/// - رأس فيه صورة رمزية (Avatar) + اسم/بريد المستخدم من [AuthController]
/// - قائمة إعدادات (Account / Notifications / Security / Help / Language)
/// - زر "Log Out" بالأسفل
///
/// تُفتح من شريط التنقل السفلي (آخر أيقونة، index == 4) بأي شاشة
/// رئيسية بالتطبيق - راجع [AppNavIndex.profile] و[handleGlobalBottomNavTap].
class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  /// فهرس تبويب Profile بشريط التنقل السفلي
  static const int _ownIndex = AppNavIndex.profile;

  int _selectedBottomIndex = _ownIndex;

  // ═══════════════════════════════════════════════════════════
  // Event Handlers - معالجات الأحداث
  // ═══════════════════════════════════════════════════════════

  /// معالج ضغطات شريط التنقل السفلي - مفوّض بالكامل للمعالج المشترك
  void _handleBottomNavTap(int index) => handleGlobalBottomNavTap(index);

  /// فتح شاشة تعديل بيانات البروفايل (الاسم/البريد/الصورة)
  void _openEditProfile() {
    context.pushEditProfile();
  }

  /// فتح شاشة الأمان (كلمة المرور وخيارات الحماية)
  void _openSecurity() {
    context.pushSecurity();
  }

  /// فتح شاشة تفضيلات الإشعارات
  void _openNotificationPreferences() {
    context.pushNotificationPreferences();
  }

  /// فتح شاشة المساعدة والدعم
  void _openHelpSupport() {
    context.pushHelpSupport();
  }

  /// فتح شاشة "حول التطبيق"
  void _openAbout() {
    context.pushAbout();
  }

  /// فتح Bottom Sheet لاختيار لغة التطبيق (عربي/إنجليزي)
  void _openLanguagePicker() {
    final l10n = AppLocalizations.of(context)!;
    final currentLocale = ref.read(localeProvider);

    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) => Container(
        margin: const EdgeInsets.all(12),
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
        decoration: BoxDecoration(
          color: AppColors.bgSurface,
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: AppColors.fieldBorder.withOpacity(0.3)),
        ),
        child: SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  margin: const EdgeInsets.only(bottom: 16),
                  decoration: BoxDecoration(
                    color: AppColors.fieldBorder.withOpacity(0.5),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              Text(l10n.language, style: AppTextStyles.heading3),
              const SizedBox(height: 4),
              Text(
                l10n.chooseAppLanguage,
                style: AppTextStyles.bodySmall.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
              const SizedBox(height: 16),
              _LanguageOptionTile(
                label: l10n.english,
                isSelected: currentLocale.languageCode == 'en',
                onTap: () {
                  ref.read(localeProvider.notifier).setLocale(const Locale('en'));
                  ref
                      .read(newsRepositoryProvider)
                      .relocalize(AppLocalizations(const Locale('en')));
                  ref
                      .read(notificationsRepositoryProvider)
                      .relocalize(AppLocalizations(const Locale('en')));
                  Navigator.of(sheetContext).pop();
                },
              ),
              _LanguageOptionTile(
                label: l10n.arabic,
                isSelected: currentLocale.languageCode == 'ar',
                onTap: () {
                  ref.read(localeProvider.notifier).setLocale(const Locale('ar'));
                  ref
                      .read(newsRepositoryProvider)
                      .relocalize(AppLocalizations(const Locale('ar')));
                  ref
                      .read(notificationsRepositoryProvider)
                      .relocalize(AppLocalizations(const Locale('ar')));
                  Navigator.of(sheetContext).pop();
                },
              ),
              const SizedBox(height: 8),
            ],
          ),
        ),
      ),
    );
  }

  /// تسجيل الخروج: يمسح المستخدم الحالي من [AuthController] ثم يرجع
  /// لشاشة التسجيل (ومسح كل شجرة التنقل، بنفس نمط [LoginScreen] و
  /// [OtpVerificationScreen] عند الدخول)
  Future<void> _handleLogout() async {
    final confirmed = await _confirmLogout();
    if (confirmed != true || !mounted) return;

    await ref.read(authControllerProvider).logout();
    if (!mounted) return;

    context.pushRegistrationAndClearStack();
  }

  /// نافذة تأكيد بسيطة قبل تسجيل الخروج فعليًا
  Future<bool?> _confirmLogout() {
    final l10n = AppLocalizations.of(context)!;

    return showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: AppColors.bgSurface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
        title: Text(l10n.logOut, style: AppTextStyles.heading3),
        content: Text(
          l10n.confirmLogOut,
          style: AppTextStyles.bodyMedium.copyWith(
            color: AppColors.textSecondary,
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: Text(l10n.cancel),
          ),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: Text(
              l10n.logOut,
              style: TextStyle(color: AppColors.error),
            ),
          ),
        ],
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════
  // Build Methods - دوال البناء
  // ═══════════════════════════════════════════════════════════

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final user = ref.watch(authControllerProvider).currentUser;

    return Scaffold(
      body: AuthBackground(
        child: SafeArea(
          bottom: false,
          child: Column(
            children: [
              const ScreenBackButton(),
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
                  children: [
                    Text(l10n.profileSettings, style: AppTextStyles.heading1.copyWith(fontSize: 26)),
                    const SizedBox(height: 24),
                    _buildUserHeader(user, l10n),
                    const SizedBox(height: 28),
                    _buildSectionLabel(l10n.account),
                    const SizedBox(height: 12),
                    _SettingsTile(
                      icon: Icons.person_outline_rounded,
                      title: l10n.accountSettings,
                      subtitle: l10n.updatePersonalInfo,
                      onTap: _openEditProfile,
                    ),
                    _SettingsTile(
                      icon: Icons.lock_outline_rounded,
                      title: l10n.security,
                      subtitle: l10n.passwordAndLoginPrefs,
                      onTap: _openSecurity,
                    ),
                    _SettingsTile(
                      icon: Icons.notifications_none_rounded,
                      title: l10n.notificationPreferences,
                      subtitle: l10n.chooseAlerts,
                      onTap: _openNotificationPreferences,
                    ),
                    _SettingsTile(
                      icon: Icons.language_rounded,
                      title: l10n.language,
                      subtitle: l10n.isArabic ? l10n.arabic : l10n.english,
                      onTap: _openLanguagePicker,
                    ),
                    const SizedBox(height: 20),
                    _buildSectionLabel(l10n.support),
                    const SizedBox(height: 12),
                    _SettingsTile(
                      icon: Icons.help_outline_rounded,
                      title: l10n.helpAndSupport,
                      subtitle: l10n.faqsAndContact,
                      onTap: _openHelpSupport,
                    ),
                    _SettingsTile(
                      icon: Icons.info_outline_rounded,
                      title: l10n.aboutTradeX,
                      subtitle: l10n.appVersionAndLegal,
                      onTap: _openAbout,
                    ),
                    const SizedBox(height: 28),
                    _buildLogoutButton(l10n),
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

  /// رأس الشاشة: صورة رمزية + الاسم المعروض + البريد الإلكتروني
  ///
  /// قابل للضغط بالكامل - بيفتح مباشرة شاشة تعديل البروفايل
  /// [EditProfileScreen]، بالإضافة لسهم ظاهر بالنهاية كتلميح بصري
  Widget _buildUserHeader(UserModel? user, AppLocalizations l10n) {
    final displayName = user?.displayName?.trim().isNotEmpty == true
        ? user!.displayName!
        : l10n.trader;
    final email = user?.email ?? l10n.guestEmail;
    final initial = displayName.isNotEmpty ? displayName[0].toUpperCase() : 'T';
    final avatarPath = user?.avatarUrl;

    return InkWell(
      onTap: _openEditProfile,
      borderRadius: BorderRadius.circular(20),
      child: Container(
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: AppColors.bgSurface.withOpacity(0.85),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: AppColors.fieldBorder.withOpacity(0.35)),
        ),
        child: Row(
          children: [
            Container(
              width: 56,
              height: 56,
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
                        style: AppTextStyles.heading2.copyWith(
                          color: AppColors.buttonText,
                        ),
                      ),
                    )
                  : null,
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    displayName,
                    style: AppTextStyles.bodyLarge.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    email,
                    style: AppTextStyles.bodySmall.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(
              Icons.chevron_right_rounded,
              color: AppColors.textHint,
              size: 22,
            ),
          ],
        ),
      ),
    );
  }

  /// عنوان قسم صغير (Account / Support)
  Widget _buildSectionLabel(String label) {
    return Text(
      label,
      style: AppTextStyles.label.copyWith(
        color: AppColors.textHint,
        letterSpacing: 0.6,
      ),
    );
  }

  /// زر تسجيل الخروج
  Widget _buildLogoutButton(AppLocalizations l10n) {
    return InkWell(
      onTap: _handleLogout,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: 16),
        decoration: BoxDecoration(
          color: AppColors.error.withOpacity(0.12),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.error.withOpacity(0.4)),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.logout_rounded, color: AppColors.error, size: 20),
            const SizedBox(width: 8),
            Text(
              l10n.logOut,
              style: AppTextStyles.button.copyWith(color: AppColors.error),
            ),
          ],
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════
// Sub-widgets - مكونات فرعية
// ═══════════════════════════════════════════════════════════

/// عنصر واحد بقائمة الإعدادات: أيقونة + عنوان + وصف + سهم
class _SettingsTile extends StatelessWidget {
  const _SettingsTile({
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
            Icon(
              Icons.chevron_right_rounded,
              color: AppColors.textHint,
              size: 22,
            ),
          ],
        ),
      ),
    );
  }
}

/// خيار لغة واحد داخل Bottom Sheet اختيار اللغة
class _LanguageOptionTile extends StatelessWidget {
  const _LanguageOptionTile({
    required this.label,
    required this.isSelected,
    required this.onTap,
  });

  final String label;
  final bool isSelected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          color: isSelected
              ? AppColors.accentCyan.withOpacity(0.15)
              : AppColors.bgSurface.withOpacity(0.7),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: isSelected
                ? AppColors.accentCyan
                : AppColors.fieldBorder.withOpacity(0.3),
          ),
        ),
        child: Row(
          children: [
            Expanded(
              child: Text(
                label,
                style: AppTextStyles.bodyMedium.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            if (isSelected)
              const Icon(
                Icons.check_circle_rounded,
                color: AppColors.accentCyan,
                size: 20,
              ),
          ],
        ),
      ),
    );
  }
}
