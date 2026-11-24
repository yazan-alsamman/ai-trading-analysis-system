import 'package:flutter/material.dart';

import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../l10n/app_localizations.dart';
import '../models/chat_message.dart';

/// فقاعة رسالة بمحادثة خبير: رسالتك بآخر السطر، رسالة الخبير بأولو (بالعربي
/// بينعكسوا). تحت النص الوقت، وحالة رسالتك (أيقونة + كلمة: Sending / Sent /
/// Not sent)؛ رد الخبير مكتوب "Simulated reply". القارئ الصوتي بيقرأ كل رسالة
/// مع المرسل والوقت. رسالة ما انبعتت: زر "Try again" تحتها.
class ChatBubble extends StatelessWidget {
  const ChatBubble({super.key, required this.message, required this.expertName, this.onRetry});

  final ChatMessage message;
  final String expertName;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;
    final mine = message.fromMe;
    final time = Formatters.clock(message.createdAt.toLocal());
    final failed = message.status == ChatMessageStatus.failed;
    final (statusIcon, statusWord, statusColor) = switch (message.status) {
      ChatMessageStatus.sending => (Icons.schedule_rounded, l10n.chatSending, c.fg3),
      ChatMessageStatus.sent => (Icons.done_rounded, l10n.chatSent, c.fg3),
      ChatMessageStatus.failed => (Icons.error_outline_rounded, l10n.chatNotSent, c.danger),
    };
    const big = Radius.circular(AppRadii.lg);
    const small = Radius.circular(AppRadii.xs);

    final bubble = Semantics(
      container: true,
      label: mine
          ? l10n.chatMessageMine(time, message.body, statusWord)
          : l10n.chatMessageTheirs(expertName, time, message.body),
      excludeSemantics: true,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: mine ? c.selected : c.card,
          borderRadius: BorderRadiusDirectional.only(
            topStart: big,
            topEnd: big,
            bottomStart: mine ? big : small,
            bottomEnd: mine ? small : big,
          ),
          border: Border.all(color: failed ? c.danger : c.hairline),
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(message.body, style: text.bodyLarge),
              const SizedBox(height: AppSpacing.xxs),
              Wrap(
                spacing: AppSpacing.xxs,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Text(mine ? time : '$time · ${l10n.chatSimulatedReply}', style: text.bodySmall),
                  if (mine) ...[
                    Icon(statusIcon, size: AppSizes.iconSm, color: statusColor),
                    Text(statusWord, style: text.bodySmall!.copyWith(color: failed ? c.danger : null)),
                  ],
                ],
              ),
            ],
          ),
        ),
      ),
    );

    return Align(
      alignment: mine ? AlignmentDirectional.centerEnd : AlignmentDirectional.centerStart,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: MediaQuery.sizeOf(context).width * 0.82),
        child: Column(
          crossAxisAlignment: mine ? CrossAxisAlignment.end : CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            bubble,
            if (failed && onRetry != null)
              AppButton.ghost(label: l10n.tryAgain, icon: Icons.refresh_rounded, compact: true, onPressed: onRetry),
          ],
        ),
      ),
    );
  }
}
