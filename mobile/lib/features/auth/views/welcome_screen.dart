import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/router/app_navigator.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/brand_mark.dart';
import '../../../core/widgets/headings.dart';
import '../../../core/widgets/motion.dart';
import '../../../l10n/app_localizations.dart';
import '../../../providers/locale_provider.dart';
import '../widgets/auth_backdrop.dart';
import '../widgets/auth_scaffold.dart';

/// Welcome: شاشة وحدة قبل الدخول - الشعار لحالو (بينبني مرة وحدة)،
/// العنوان بلون واحد، جملة وحدة، زرّين، وسطر التنبيه القصير.
///
/// اللغة قابلة للتبديل من هون (زر صغير فوق) لأنو الإعدادات ورا الدخول.
/// الشعار Hero بيطير لراس Log in / Create account.
class WelcomeScreen extends ConsumerWidget {
  const WelcomeScreen({super.key});

  /// حجم الشعار (بهالة ناعمة بس، بدون أي حلقة أو قوس حواليه)
  static const double glyphSize = 112;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final gutter = AppSpacing.gutter(context);
    final arabic = l10n.isArabic;

    final glyph = context.reduceMotion
        ? const BrandGlyph(size: glyphSize, glow: true)
        : TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: 1),
            duration: AppMotion.emphasis,
            curve: AppMotion.out,
            builder: (context, progress, _) => BrandGlyph(size: glyphSize, progress: progress, glow: true),
          );

    return Scaffold(
      body: AuthBackdrop(
        child: SafeArea(
          child: LayoutBuilder(
            builder: (context, constraints) => SingleChildScrollView(
              padding: EdgeInsets.symmetric(horizontal: gutter),
              child: ConstrainedBox(
                constraints: BoxConstraints(minHeight: constraints.maxHeight),
                child: IntrinsicHeight(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const SizedBox(height: AppSpacing.xs),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.end,
                        children: [
                          TextButton.icon(
                            onPressed: () {
                              AppHaptics.selection();
                              ref.read(localeProvider.notifier).setLocale(Locale(arabic ? 'en' : 'ar'));
                            },
                            style: TextButton.styleFrom(
                              minimumSize: const Size(AppSizes.minTap, AppSizes.minTap),
                              foregroundColor: c.fg2,
                            ),
                            icon: const Icon(Icons.translate_rounded, size: AppSizes.iconMd),
                            label: Text(
                              arabic ? l10n.english : l10n.arabic,
                              semanticsLabel: '${l10n.language}: ${arabic ? l10n.english : l10n.arabic}',
                            ),
                          ),
                        ],
                      ),
                      const Spacer(),
                      const SizedBox(height: AppSpacing.xl),
                      Center(child: AuthBrandHero(child: glyph)),
                      const SizedBox(height: AppSpacing.xxl),
                      FadeRise(
                        index: 1,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Semantics(label: l10n.appName, excludeSemantics: true, child: Eyebrow(l10n.appName)),
                            const SizedBox(height: AppSpacing.sm),
                            Semantics(
                              header: true,
                              child: Text(
                                l10n.welcomeTitle,
                                style: context.textTheme.displayLarge!.copyWith(color: c.fg),
                              ),
                            ),
                            const SizedBox(height: AppSpacing.md),
                            Text(l10n.welcomeBody, style: context.textTheme.bodyLarge!.copyWith(color: c.fg2)),
                          ],
                        ),
                      ),
                      const Spacer(),
                      const SizedBox(height: AppSpacing.xxl),
                      FadeRise(
                        index: 2,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            AppButton(
                              label: l10n.createAccountAction,
                              trailingIcon: Icons.arrow_forward_rounded,
                              expand: true,
                              onPressed: context.pushRegistration,
                            ),
                            const SizedBox(height: AppSpacing.sm),
                            AppButton.secondary(
                              label: l10n.logIn,
                              expand: true,
                              onPressed: context.pushLogin,
                            ),
                            const SizedBox(height: AppSpacing.lg),
                            const AuthDisclaimer(),
                          ],
                        ),
                      ),
                      const SizedBox(height: AppSpacing.lg),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
