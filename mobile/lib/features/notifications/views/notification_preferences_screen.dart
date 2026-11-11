import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/page_header.dart';
import '../../../core/widgets/settings_group.dart';
import '../../../l10n/app_localizations.dart';
import '../data/notification_preferences_repository.dart';
import '../models/notification_preferences.dart';
import '../view_models/push_permission_view_model.dart';
import '../view_models/telegram_link_view_model.dart';
import '../widgets/push_channel_tile.dart';
import '../widgets/telegram_channel_tile.dart';

/// تفضيلات الإشعارات (من Settings): القنوات (Push، داخل التطبيق، بريد،
/// Telegram) والأنواع (تنبيه سعر، فرصة، نظام). كل مفتاح بيتطبّق فورًا.
///
/// الواجهة بس - التوصيل الفعلي (FCM / NotificationHub) شغل الـ backend.
/// H4b: Push بيمرق بإذن النظام ("Why we ask" أول مرة)، و Telegram بيشتغل بس بعد
/// الربط (كود لمرة وحدة). "كل القنوات مطفية" بيحسب القناة الفعلية (مفعّلة ومسموحة/مربوطة).
class NotificationPreferencesScreen extends ConsumerWidget {
  const NotificationPreferencesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final prefs = ref.watch(notificationPreferencesProvider);
    final vm = ref.read(notificationPreferencesProvider.notifier);
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final text = context.textTheme;
    final gutter = AppSpacing.gutter(context);

    final channels = [
      (NotificationChannel.inApp, Icons.notifications_none_rounded, l10n.channelInApp, l10n.channelInAppHint),
      (NotificationChannel.email, Icons.mail_outline_rounded, l10n.channelEmail, l10n.channelEmailHint),
    ];
    // ما في ولا قناة شغّالة فعليًا (Push بدون إذن، أو Telegram بدون ربط = مطفي)
    final muted = !ref.watch(pushChannelActiveProvider) &&
        !ref.watch(telegramChannelActiveProvider) &&
        !prefs.channels.contains(NotificationChannel.inApp) &&
        !prefs.channels.contains(NotificationChannel.email);
    final kinds = [
      (NotificationKind.priceAlert, Icons.notifications_active_outlined, l10n.kindPriceAlert, l10n.kindPriceAlertHint),
      (NotificationKind.opportunity, Icons.auto_awesome_outlined, l10n.kindOpportunity, l10n.kindOpportunityHint),
      (NotificationKind.system, Icons.info_outline_rounded, l10n.kindSystem, l10n.kindSystemHint),
    ];

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: ListView(
          padding: const EdgeInsets.only(bottom: AppSpacing.xxl),
          children: [
            PageHeader(title: l10n.notificationPreferences, back: const PageBackButton()),
            Padding(
              padding: EdgeInsets.fromLTRB(gutter, AppSpacing.md, gutter, 0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  SettingsGroup(
                    title: l10n.notifChannels,
                    children: [
                      const PushChannelTile(),
                      for (final (channel, icon, title, hint) in channels)
                        SettingsSwitchTile(
                          icon: icon,
                          title: title,
                          subtitle: hint,
                          value: prefs.channels.contains(channel),
                          onChanged: (on) => vm.setChannel(channel, on),
                        ),
                      const TelegramChannelTile(),
                    ],
                  ),
                  if (muted) ...[
                    const SizedBox(height: AppSpacing.sm),
                    Semantics(
                      liveRegion: true,
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(Icons.warning_amber_rounded, size: AppSizes.iconMd, color: c.warning),
                          const SizedBox(width: AppSpacing.xs),
                          Expanded(
                            child: Text(l10n.notifMuted, style: text.bodyMedium!.copyWith(color: c.fg)),
                          ),
                        ],
                      ),
                    ),
                  ],
                  const SizedBox(height: AppSpacing.xl),
                  SettingsGroup(
                    title: l10n.notifKinds,
                    children: [
                      for (final (kind, icon, title, hint) in kinds)
                        SettingsSwitchTile(
                          icon: icon,
                          title: title,
                          subtitle: hint,
                          value: prefs.kinds.contains(kind),
                          onChanged: (on) => vm.setKind(kind, on),
                        ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.md),
                  Text(l10n.notifPrefsNote, style: text.bodySmall),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
