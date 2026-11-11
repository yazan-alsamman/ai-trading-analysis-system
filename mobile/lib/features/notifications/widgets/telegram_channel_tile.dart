import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../core/widgets/settings_group.dart';
import '../../../l10n/app_localizations.dart';
import '../data/notification_preferences_repository.dart';
import '../models/notification_preferences.dart';
import '../models/telegram_link.dart';
import '../view_models/telegram_link_view_model.dart';
import 'telegram_connect_sheet.dart';

/// قناة Telegram بتفضيلات الإشعارات (H4b): المفتاح معطّل لحد ما ينربط (مع
/// السبب)، وتحتو حالة الربط + "Connect Telegram" أو "Disconnect" (Undo).
class TelegramChannelTile extends ConsumerStatefulWidget {
  const TelegramChannelTile({super.key});

  @override
  ConsumerState<TelegramChannelTile> createState() => _TelegramChannelTileState();
}

class _TelegramChannelTileState extends ConsumerState<TelegramChannelTile> {
  var _opening = false;

  Future<void> _connect() async {
    if (_opening) return;
    _opening = true;
    try {
      await showTelegramConnectSheet(context);
    } finally {
      _opening = false;
    }
  }

  Future<void> _disconnect() async {
    final l10n = AppLocalizations.of(context)!;
    final messenger = ScaffoldMessenger.of(context);
    final vm = ref.read(telegramLinkProvider.notifier);
    void show(String message, {SnackBarAction? action}) => messenger
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message), action: action));
    try {
      final undo = await vm.disconnect();
      if (undo == null || !mounted) return;
      show(
        l10n.telegramDisconnectedSnack,
        action: SnackBarAction(
          label: l10n.undo,
          onPressed: () async {
            try {
              await vm.undoDisconnect(undo);
              show(l10n.telegramRestoredSnack);
            } on TelegramOfflineException {
              show(l10n.telegramOffline);
            } catch (_) {
              show(l10n.telegramFailed);
            }
          },
        ),
      );
    } on TelegramOfflineException {
      show(l10n.telegramOffline);
    } catch (_) {
      show(l10n.telegramFailed);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final text = context.textTheme;
    final link = ref.watch(telegramLinkProvider);
    final active = ref.watch(telegramChannelActiveProvider);
    final status = link.valueOrNull;

    // انقطع الربط من مكان تاني (فك الربط) → إعلان للقارئ
    ref.listen<AsyncValue<TelegramLinkStatus>>(telegramLinkProvider, (previous, next) {
      final was = previous?.valueOrNull?.isLinked;
      final now = next.valueOrNull?.isLinked;
      if (was == true && now == false && mounted) {
        SemanticsService.sendAnnouncement(View.of(context), l10n.telegramNotConnected, Directionality.of(context));
      }
    });

    final subtitle = switch (status) {
      TelegramLinked(:final handle?) => l10n.telegramConnectedAs(handle),
      TelegramLinked() => l10n.telegramConnected,
      _ => l10n.telegramConnectFirst,
    };

    final Widget footer;
    if (link.isLoading && status == null) {
      footer = LoadingRegion(
        child: Semantics(label: l10n.telegramStatusLoading, child: const Skeleton(width: 160, height: AppSpacing.xl)),
      );
    } else if (link.hasError && status == null) {
      footer = Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Semantics(
            liveRegion: true,
            child: Text(l10n.telegramStatusError, style: text.bodySmall!.copyWith(color: c.fg)),
          ),
          AppButton.ghost(
            label: l10n.tryAgain,
            icon: Icons.refresh_rounded,
            compact: true,
            onPressed: () => ref.read(telegramLinkProvider.notifier).retry(),
          ),
        ],
      );
    } else if (status is TelegramLinked) {
      footer = Semantics(
        label: l10n.telegramDisconnectLabel,
        button: true,
        excludeSemantics: true,
        onTap: _disconnect,
        child: AppButton.ghost(
          label: l10n.telegramDisconnect,
          icon: Icons.link_off_rounded,
          compact: true,
          onPressed: _disconnect,
        ),
      );
    } else {
      footer = AppButton.secondary(
        label: l10n.telegramConnect,
        icon: Icons.link_rounded,
        compact: true,
        onPressed: _connect,
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SettingsSwitchTile(
          icon: Icons.send_rounded,
          title: l10n.channelTelegram,
          subtitle: subtitle,
          value: active,
          onChanged: status is TelegramLinked
              ? (on) => ref.read(notificationPreferencesProvider.notifier).setChannel(NotificationChannel.telegram, on)
              : null,
        ),
        Padding(
          padding: const EdgeInsetsDirectional.fromSTEB(SettingsGroup.textIndent, 0, AppSpacing.md, AppSpacing.sm),
          child: Align(alignment: AlignmentDirectional.centerStart, child: footer),
        ),
      ],
    );
  }
}
