import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/router/app_navigator.dart';
import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/motion.dart';
import '../../../core/widgets/page_header.dart';
import '../../../core/widgets/settings_group.dart';
import '../../../l10n/app_localizations.dart';
import '../../../core/data/low_data_mode.dart';
import '../../markets/data/market_providers.dart';
import '../../risk/models/risk_limits.dart';
import '../../risk/widgets/risk_limits_sheet.dart';
import '../view_models/settings_view_model.dart';
import '../widgets/appearance_selector.dart';
import '../widgets/language_sheet.dart';

/// Settings (من Profile): المظهر، اللغة، الإشعارات، رأس المال والحدود،
/// وقسم Developer بنسخ التطوير بس.
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  Future<void> _openLanguage(BuildContext context, WidgetRef ref, String current) async {
    final code = await showLanguageSheet(context, current: current);
    if (code != null) await ref.read(settingsViewModelProvider.notifier).setLanguage(code);
  }

  Future<void> _openRiskLimits(BuildContext context, WidgetRef ref, RiskLimits current) async {
    final next = await showRiskLimitsSheet(context, current: current);
    if (next == null || next == current || !context.mounted) return;
    final l10n = AppLocalizations.of(context)!;
    final messenger = ScaffoldMessenger.of(context);
    try {
      await ref.read(settingsViewModelProvider.notifier).saveRiskLimits(next);
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(l10n.riskLimitsSaved)));
    } catch (_) {
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(l10n.couldNotSaveChanges)));
    }
  }

  Future<void> _clearMarketCache(BuildContext context, WidgetRef ref) async {
    final l10n = AppLocalizations.of(context)!;
    final messenger = ScaffoldMessenger.of(context);
    try {
      await clearMarketCache(ref);
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(l10n.marketCacheCleared)));
    } catch (_) {
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(l10n.marketCacheClearFailed)));
    }
  }

  static String riskSummary(AppLocalizations l10n, RiskLimits limits) {
    final perTrade = Formatters.plainPercent(limits.maxRiskPerTradePct);
    final daily = Formatters.plainPercent(limits.dailyLossLimitPct);
    return limits.hasCapital
        ? l10n.riskLimitsSummary(Formatters.money(limits.capital!, RiskLimits.currency), perTrade, daily)
        : l10n.riskLimitsSummaryNoCapital(perTrade, daily);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(settingsViewModelProvider);
    final vm = ref.read(settingsViewModelProvider.notifier);
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);

    final sections = <Widget>[
      SettingsGroup(
        title: l10n.preferences,
        children: [
          AppearanceSelector(mode: state.themeMode, onChanged: vm.setThemeMode),
          SettingsTile(
            icon: Icons.translate_rounded,
            title: l10n.language,
            subtitle: state.languageCode == 'ar' ? l10n.arabic : l10n.english,
            onTap: () => _openLanguage(context, ref, state.languageCode),
          ),
          SettingsTile(
            icon: Icons.notifications_none_rounded,
            title: l10n.notificationPreferences,
            subtitle: l10n.chooseAlerts,
            onTap: context.pushNotificationPreferences,
          ),
          // H5b: مطفي بالافتراضي، بينحفظ، والإطفاء بيرجّع كل شي فورًا
          SettingsSwitchTile(
            icon: Icons.data_saver_on_rounded,
            title: l10n.lowDataMode,
            subtitle: l10n.lowDataModeSubtitle,
            value: ref.watch(lowDataModeProvider),
            onChanged: (on) => ref.read(lowDataModeProvider.notifier).set(on),
          ),
        ],
      ),
      SettingsGroup(
        title: l10n.riskGroup,
        children: [
          SettingsTile(
            icon: Icons.shield_outlined,
            title: l10n.riskLimits,
            subtitle: riskSummary(l10n, state.riskLimits),
            onTap: () => _openRiskLimits(context, ref, state.riskLimits),
          ),
        ],
      ),
      // TODO(B12): "Simulate offline" (debug بس) بيفرض offline فوق مصدر الاتصال
      // الحقيقي (E1) - بينحذف بالكامل قبل ربط الـ API (راجع REQUIREMENTS.md).
      if (kDebugMode)
        SettingsGroup(
          title: l10n.developer,
          children: [
            SettingsSwitchTile(
              icon: Icons.cloud_off_rounded,
              title: l10n.simulateOffline,
              subtitle: l10n.simulateOfflineSubtitle,
              value: state.simulatingOffline,
              onChanged: vm.setSimulatedOffline,
            ),
            // H5a: بيمسح الأسعار والشموع المحفوظة للاستخدام بدون اتصال
            if (ref.watch(marketCacheEnabledProvider))
              SettingsTile(
                icon: Icons.delete_sweep_outlined,
                title: l10n.clearMarketCache,
                subtitle: l10n.clearMarketCacheSubtitle,
                onTap: () => _clearMarketCache(context, ref),
              ),
          ],
        ),
    ];

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: CustomScrollView(
          slivers: [
            SliverToBoxAdapter(child: PageHeader(title: l10n.settings, back: const PageBackButton())),
            SliverPadding(
              padding: EdgeInsets.fromLTRB(gutter, AppSpacing.md, gutter, AppSpacing.xxl),
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
