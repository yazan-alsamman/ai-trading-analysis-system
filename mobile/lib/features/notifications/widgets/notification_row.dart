import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/clock.dart';
import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../l10n/app_localizations.dart';
import '../models/app_notification.dart';

/// صف إشعار: أيقونة النوع، العنوان، النص (سطرين)، الوقت ونقطة "غير مقروء".
///
/// السحب: من البداية = مقروء / غير مقروء (الصف بيضل مكانه)، من النهاية =
/// حذف. نفس الإجراءين متاحين للقارئ الصوتي كـ custom actions.
class NotificationRow extends ConsumerWidget {
  const NotificationRow({
    super.key,
    required this.notification,
    required this.onTap,
    required this.onToggleRead,
    required this.onDelete,
  });

  final AppNotification notification;
  final VoidCallback onTap;
  final VoidCallback onToggleRead;
  final VoidCallback onDelete;

  static const double _iconBox = 36;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;
    final now = ref.watch(clockProvider).valueOrNull ?? DateTime.now();
    final n = notification;
    final time = relativeTime(l10n, n.createdAt, now);
    final readLabel = n.isRead ? l10n.notifMarkUnread : l10n.notifMarkRead;
    final iconColor = n.kind == NotificationKind.opportunity ? c.forecast : (n.isRead ? c.fg3 : c.accent);

    Widget swipeBackground({required bool delete}) => ColoredBox(
          color: delete ? c.dangerSoft : c.accentSoft,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
            child: Align(
              alignment: delete ? AlignmentDirectional.centerEnd : AlignmentDirectional.centerStart,
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    delete
                        ? Icons.delete_outline_rounded
                        : (n.isRead ? Icons.mark_email_unread_outlined : Icons.mark_email_read_outlined),
                    color: delete ? c.danger : c.accent,
                  ),
                  const SizedBox(width: AppSpacing.xs),
                  Text(
                    delete ? l10n.notifDelete : readLabel,
                    style: text.labelLarge!.copyWith(color: delete ? c.danger : c.accent),
                  ),
                ],
              ),
            ),
          ),
        );

    return Dismissible(
      key: ValueKey('dismiss-${n.id}'),
      background: swipeBackground(delete: false),
      secondaryBackground: swipeBackground(delete: true),
      confirmDismiss: (direction) async {
        if (direction == DismissDirection.startToEnd) {
          onToggleRead();
          return false;
        }
        return true;
      },
      onDismissed: (_) => onDelete(),
      child: Semantics(
        button: true,
        onTap: onTap,
        label: [
          if (!n.isRead) l10n.notifUnread,
          n.kind.label(l10n),
          n.title,
          n.body,
          time,
        ].join(', '),
        customSemanticsActions: {
          CustomSemanticsAction(label: readLabel): onToggleRead,
          CustomSemanticsAction(label: l10n.notifDelete): onDelete,
        },
        excludeSemantics: true,
        child: InkWell(
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: _iconBox,
                  height: _iconBox,
                  decoration: BoxDecoration(
                    color: n.kind == NotificationKind.opportunity ? c.forecastSoft : c.inset,
                    borderRadius: AppRadii.field,
                    border: Border.all(color: c.hairline),
                  ),
                  child: Icon(n.kind.icon, size: AppSizes.iconMd, color: iconColor),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            child: Text(
                              n.title,
                              style: text.titleSmall!.copyWith(
                                fontWeight: n.isRead ? FontWeight.w500 : FontWeight.w600,
                              ),
                            ),
                          ),
                          const SizedBox(width: AppSpacing.xs),
                          Text(time, style: text.bodySmall),
                          if (!n.isRead) ...[
                            const SizedBox(width: AppSpacing.xs),
                            Padding(
                              padding: const EdgeInsets.only(top: AppSpacing.xxs),
                              child: Container(
                                width: AppSpacing.xs,
                                height: AppSpacing.xs,
                                decoration: BoxDecoration(color: c.accent, shape: BoxShape.circle),
                              ),
                            ),
                          ],
                        ],
                      ),
                      if (n.body.isNotEmpty) ...[
                        const SizedBox(height: AppSpacing.xxs),
                        Text(
                          n.body,
                          style: text.bodyMedium!.copyWith(color: c.fg2),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
