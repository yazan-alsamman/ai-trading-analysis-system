import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/router/app_navigator.dart';
import '../../../app/shell/widgets/back_to_home_button.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/motion.dart';
import '../../../core/widgets/settings_group.dart';
import '../../../l10n/app_localizations.dart';
import '../view_models/profile_view_model.dart';
import '../widgets/profile_identity_card.dart';

/// تبويب Profile: بطاقة الهوية + أربع وجهات (الخطة، كلمة المرور والأمان،
/// الإعدادات، المساعدة وحول) + تسجيل الخروج. كل التفاصيل بشاشاتها الفرعية،
/// فالتبويب بينقرا بنظرة وحدة بدون سكرول.
///
/// الدور المعماري: **View** - بترسم [ProfileState] بس، وكل فعل بيروح
/// لـ [ProfileViewModel] أو لشاشة فرعية.
class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  Future<void> _logout(BuildContext context, WidgetRef ref) async {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final confirmed = await showDialog<bool>(
      context: context,
      animationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
      builder: (dialogContext) => AlertDialog(
        title: Text(l10n.logOut),
        content: Text(l10n.confirmLogOut),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: Text(l10n.cancel),
          ),
          TextButton(
            style: TextButton.styleFrom(foregroundColor: c.danger),
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: Text(l10n.logOut),
          ),
        ],
      ),
    );
    if (confirmed != true || !context.mounted) return;

    // الرجوع لـ Welcome بيصير تلقائيًا لما الجلسة تنتهي (TradingApp)
    await ref.read(profileViewModelProvider.notifier).logout();
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(profileViewModelProvider);
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final gutter = AppSpacing.gutter(context);

    final sections = <Widget>[
      ProfileIdentityCard(
        name: state.displayName ?? l10n.trader,
        email: state.email ?? l10n.guestEmail,
        avatarPath: state.avatarPath,
        role: state.role,
        onTap: context.pushEditProfile,
      ),
      SettingsGroup(
        children: [
          SettingsTile(
            icon: Icons.workspace_premium_outlined,
            title: l10n.profilePlan,
            subtitle: l10n.toolPlansSubtitle,
            onTap: context.pushPlans,
          ),
          SettingsTile(
            icon: Icons.lock_outline_rounded,
            title: l10n.passwordAndSecurity,
            subtitle: l10n.passwordAndSecuritySubtitle,
            onTap: context.pushSecurity,
          ),
          SettingsTile(
            icon: Icons.settings_outlined,
            title: l10n.settings,
            subtitle: l10n.settingsSubtitle,
            onTap: context.pushSettings,
          ),
          SettingsTile(
            icon: Icons.help_outline_rounded,
            title: l10n.helpAndAbout,
            subtitle: l10n.helpAndAboutSubtitle,
            onTap: context.pushHelpAbout,
          ),
        ],
      ),
      SettingsGroup(
        children: [
          SettingsTile(
            // نفس Icons.logout_rounded بس بتنعكس بالعربي (السهم طالع من الباب)
            icon: const IconData(0xf88b, fontFamily: 'MaterialIcons', matchTextDirection: true),
            iconColor: c.danger,
            titleColor: c.danger,
            title: state.isLoggingOut ? l10n.loggingOut : l10n.logOut,
            onTap: state.isLoggingOut ? null : () => _logout(context, ref),
            trailing: state.isLoggingOut
                ? SizedBox.square(
                    dimension: AppSizes.iconMd,
                    child: CircularProgressIndicator(strokeWidth: 2, color: c.danger),
                  )
                : const SizedBox.shrink(),
          ),
        ],
      ),
    ];

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: CustomScrollView(
          slivers: [
            SliverToBoxAdapter(child: TabHeader(title: l10n.navProfile)),
            SliverPadding(
              padding: EdgeInsets.fromLTRB(gutter, AppSpacing.lg, gutter, AppSpacing.xxl),
              sliver: SliverList.separated(
                itemCount: sections.length,
                separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.xl),
                itemBuilder: (_, i) => FadeRise(index: i, child: sections[i]),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
