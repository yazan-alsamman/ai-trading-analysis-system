import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/router/app_navigator.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/settings_group.dart';
import '../../../l10n/app_localizations.dart';
import '../data/notification_permission_service.dart';
import '../view_models/push_permission_view_model.dart';

/// قناة Push (H4b): أول تشغيل بيعرض "Why we ask" قبل سؤال النظام. مرفوض =
/// حالة قصيرة + تلميح الإعدادات (فينا نسأل كمان مرة)؛ محظور = التلميح بس
/// والمفتاح معطّل (من إعدادات الهاتف بس).
class PushChannelTile extends ConsumerWidget {
  const PushChannelTile({super.key});

  Future<void> _turnOn(BuildContext context, WidgetRef ref) async {
    final l10n = AppLocalizations.of(context)!;
    final view = View.of(context);
    final direction = Directionality.of(context);
    final result = await ref.read(pushPermissionProvider.notifier).enable(
          explain: () async => context.mounted && await showPushExplanationSheet(context),
        );
    if (result == PushPermission.granted) {
      SemanticsService.sendAnnouncement(view, l10n.pushTurnedOn, direction);
    } else if (result == PushPermission.denied || result == PushPermission.blocked) {
      SemanticsService.sendAnnouncement(view, l10n.pushNotAllowed, direction);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final text = context.textTheme;
    final permission = ref.watch(pushPermissionProvider).valueOrNull;
    final active = ref.watch(pushChannelActiveProvider);

    final subtitle = switch (permission) {
      PushPermission.denied => l10n.pushNotAllowed,
      PushPermission.blocked => l10n.pushSettingsHint,
      _ => l10n.channelPushHint,
    };

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SettingsSwitchTile(
          icon: Icons.phone_iphone_rounded,
          title: l10n.channelPush,
          subtitle: subtitle,
          value: active,
          // لسّا ما انقرأ الإذن، أو محظور: ما في شي نعملو من هون
          onChanged: permission == null || permission == PushPermission.blocked
              ? null
              : (on) => on ? _turnOn(context, ref) : ref.read(pushPermissionProvider.notifier).disable(),
        ),
        if (permission == PushPermission.denied)
          Padding(
            padding: const EdgeInsetsDirectional.fromSTEB(SettingsGroup.textIndent, 0, AppSpacing.md, AppSpacing.sm),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.settings_outlined, size: AppSizes.iconSm, color: c.fg2),
                const SizedBox(width: AppSpacing.xxs),
                Expanded(child: Text(l10n.pushSettingsHint, style: text.bodySmall!.copyWith(color: c.fg2))),
              ],
            ),
          ),
      ],
    );
  }
}

/// "Why we ask": قبل أول سؤال من النظام. true = Continue (بعدها النظام بيسأل).
Future<bool> showPushExplanationSheet(BuildContext context) async {
  if (!context.isTopmostRoute) return false;
  final ok = await showModalBottomSheet<bool>(
    useRootNavigator: true,
    context: context,
    sheetAnimationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
    isScrollControlled: true,
    useSafeArea: true,
    showDragHandle: true,
    builder: (_) => const PushExplanationSheet(),
  );
  return ok ?? false;
}

class PushExplanationSheet extends StatelessWidget {
  const PushExplanationSheet({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final text = context.textTheme;
    final gutter = AppSpacing.gutter(context);

    Widget point(IconData icon, String label) => Padding(
          padding: const EdgeInsets.only(top: AppSpacing.sm),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, size: AppSizes.iconMd, color: c.accent),
              const SizedBox(width: AppSpacing.sm),
              Expanded(child: Text(label, style: text.bodyMedium!.copyWith(color: c.fg))),
            ],
          ),
        );

    return SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(gutter, 0, gutter, AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Semantics(header: true, child: Text(l10n.pushWhyTitle, style: text.titleLarge)),
          const SizedBox(height: AppSpacing.sm),
          Text(l10n.pushWhyBody, style: text.bodyMedium!.copyWith(color: c.fg2)),
          point(Icons.notifications_active_outlined, l10n.pushWhyAlerts),
          point(Icons.auto_awesome_outlined, l10n.pushWhyOpportunities),
          point(Icons.tune_rounded, l10n.pushWhyControl),
          const SizedBox(height: AppSpacing.md),
          Text(l10n.pushWhyNote, style: text.bodySmall),
          const SizedBox(height: AppSpacing.lg),
          AppButton(label: l10n.pushWhyContinue, expand: true, onPressed: () => Navigator.of(context).pop(true)),
          const SizedBox(height: AppSpacing.xs),
          AppButton.ghost(label: l10n.pushWhyNotNow, expand: true, onPressed: () => Navigator.of(context).pop(false)),
        ],
      ),
    );
  }
}
