import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/shell/widgets/back_to_home_button.dart';
import '../../../core/data/network_status.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/motion.dart';
import '../../../l10n/app_localizations.dart';
import '../models/assistant_models.dart';
import '../view_models/assistant_view_model.dart';
import '../view_models/chart_quota_view_model.dart';
import '../widgets/chart_analyze_panel.dart';
import '../widgets/chat_messages.dart';
import '../widgets/context_chip.dart';

/// تبويب Assistant: فوق شريحة السياق (الأداة). المحادثة الفاضية بتبلّش بالزر
/// الرئيسي "Analyze a chart image" (مع العدّاد اليومي)، وتحته 3 اقتراحات
/// (ثانوية). بالنص المحادثة، وتحت حقل الكتابة مع زر إرفاق صورة شارت.
class AssistantScreen extends ConsumerWidget {
  const AssistantScreen({super.key});

  void _newChat(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final vm = ref.read(assistantViewModelProvider.notifier);
    final previous = vm.clear();
    if (previous.isEmpty) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(
        content: Text(l10n.asstCleared),
        action: SnackBarAction(label: l10n.undo, onPressed: () => vm.restore(previous)),
      ));
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    final state = ref.watch(assistantViewModelProvider);
    final hasMessages = state.messages.isNotEmpty;
    // جواب جديد بينعلن للقارئ الصوتي (بطاقة الجواب نفسها مش live region)
    ref.listen(assistantViewModelProvider.select((s) => s.messages), (previous, next) {
      if (next.length <= (previous?.length ?? 0)) return;
      if (next.last case final AssistantReply reply) {
        SemanticsService.sendAnnouncement(
          View.of(context),
          l10n.asstAnswerLabel(replyKindLabel(l10n, reply.answer.kind)),
          Directionality.of(context),
        );
      }
    });

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TabHeader(
              title: l10n.navAssistant,
              icon: Icons.smart_toy_outlined,
              actions: [
                if (hasMessages)
                  IconButton(
                    tooltip: l10n.asstNewChat,
                    constraints: const BoxConstraints(minWidth: AppSizes.minTap, minHeight: AppSizes.minTap),
                    icon: Icon(Icons.add_comment_outlined, color: context.colors.fg),
                    onPressed: () => _newChat(context, ref),
                  ),
              ],
            ),
            Padding(
              padding: EdgeInsets.symmetric(horizontal: gutter),
              child: const Align(alignment: AlignmentDirectional.centerStart, child: ContextChip()),
            ),
            Expanded(
              child: hasMessages || state.replying ? _Conversation(state: state) : const _EmptyState(),
            ),
            const _Composer(),
          ],
        ),
      ),
    );
  }
}

/// المحادثة الفاضية: الزر الرئيسي (تحليل صورة شارت + العدّاد، أو المعاينة)
/// أول شي، وبعدها "أو اسأل": سطر شرح + 3 اقتراحات (كل واحد بيبعت سؤاله مباشرة)
class _EmptyState extends ConsumerWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final text = context.textTheme;
    final gutter = AppSpacing.gutter(context);
    final symbol = ref.watch(assistantViewModelProvider.select((s) => s.contextSymbol));
    final offline = ref.watch(networkStatusProvider) == NetworkStatus.offline;
    final suggestions = [
      (ReplyKind.explain, Icons.manage_search_rounded, l10n.asstSuggestExplain),
      (ReplyKind.invalidate, Icons.report_gmailerrorred_rounded, l10n.asstSuggestInvalidate),
      (ReplyKind.risk, Icons.balance_rounded, l10n.asstSuggestRisk),
    ];

    return ListView(
      padding: EdgeInsets.fromLTRB(gutter, AppSpacing.md, gutter, AppSpacing.lg),
      children: [
        const ChartAnalyzePanel(),
        const SizedBox(height: AppSpacing.lg),
        Text(l10n.chartOrAsk, style: text.labelLarge!.copyWith(color: c.fg2)),
        const SizedBox(height: AppSpacing.sm),
        Row(
          children: [
            ExcludeSemantics(
              child: Container(
                width: AppSizes.iconLg + AppSpacing.md,
                height: AppSizes.iconLg + AppSpacing.md,
                decoration: BoxDecoration(color: c.forecastSoft, shape: BoxShape.circle),
                child: Icon(Icons.smart_toy_outlined, color: c.forecast, size: AppSizes.iconMd),
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Semantics(
                header: true,
                child: Text(
                  symbol == null ? l10n.asstEmptyTitleGeneral : l10n.asstEmptyTitle(symbol),
                  style: text.titleMedium,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.xxs),
        Text(l10n.asstEmptyBody, style: text.bodyMedium),
        const SizedBox(height: AppSpacing.md),
        for (final (i, (kind, icon, label)) in suggestions.indexed) ...[
          if (i > 0) const SizedBox(height: AppSpacing.xs),
          FadeRise(
            index: i,
            child: OutlinedButton(
              onPressed: offline
                  ? null
                  : () {
                      AppHaptics.selection();
                      ref.read(assistantViewModelProvider.notifier).send(label, kind: kind);
                    },
              style: OutlinedButton.styleFrom(
                minimumSize: const Size.fromHeight(AppSizes.buttonHeight),
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
                alignment: AlignmentDirectional.centerStart,
                shape: const RoundedRectangleBorder(borderRadius: AppRadii.card),
                side: BorderSide(color: c.hairline),
                foregroundColor: c.fg,
              ),
              child: Row(
                children: [
                  Icon(icon, size: AppSizes.iconMd, color: c.forecast),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(child: Text(label, style: text.bodyLarge)),
                  Icon(Icons.arrow_forward_rounded, size: AppSizes.iconSm, color: c.fg3),
                ],
              ),
            ),
          ),
        ],
      ],
    );
  }
}

/// المحادثة: قائمة معكوسة (آخر رسالة دايمًا تحت جنب حقل الكتابة)
class _Conversation extends ConsumerWidget {
  const _Conversation({required this.state});

  final AssistantState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    final items = <Widget>[
      for (final m in state.messages)
        switch (m) {
          UserText() => UserBubble(key: ValueKey(m.id), message: m),
          UserImage() => UserImageBubble(key: ValueKey(m.id), message: m),
          AssistantReply() => FadeRise(key: ValueKey(m.id), child: ReplyCard(reply: m)),
        },
      if (state.replying) const TypingIndicator(),
      if (state.failed)
        _Failed(
          message: l10n.asstFailed,
          onRetry: () => ref.read(assistantViewModelProvider.notifier).retry(),
        ),
      // الصورة المختارة (معاينة / تحليل) أحدث شي، جنب حقل الكتابة
      if (state.draft != null) const ChartAnalyzePanel(showAction: false),
    ];
    final reversed = items.reversed.toList();

    return ListView.separated(
      reverse: true,
      keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
      padding: EdgeInsets.fromLTRB(gutter, AppSpacing.md, gutter, AppSpacing.md),
      itemCount: reversed.length,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.md),
      itemBuilder: (_, i) => reversed[i],
    );
  }
}

class _Failed extends StatelessWidget {
  const _Failed({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    return Semantics(
      liveRegion: true,
      container: true,
      child: Row(
        children: [
          Icon(Icons.error_outline_rounded, size: AppSizes.iconMd, color: c.danger),
          const SizedBox(width: AppSpacing.xs),
          Expanded(child: Text(message, style: context.textTheme.bodyMedium)),
          AppButton.ghost(label: l10n.tryAgain, icon: Icons.refresh_rounded, compact: true, onPressed: onRetry),
        ],
      ),
    );
  }
}

/// حقل الكتابة: إرفاق صورة شارت، النص، وإرسال (بيصير "Stop" وقت الجواب).
/// بدون اتصال: معطّل مع سطر شرح.
class _Composer extends ConsumerStatefulWidget {
  const _Composer();

  @override
  ConsumerState<_Composer> createState() => _ComposerState();
}

class _ComposerState extends ConsumerState<_Composer> {
  final _controller = TextEditingController();

  static const int maxLength = 2000;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _send() {
    final text = _controller.text;
    if (text.trim().isEmpty) return;
    AppHaptics.selection();
    _controller.clear();
    setState(() {});
    ref.read(assistantViewModelProvider.notifier).send(text);
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    final replying = ref.watch(assistantViewModelProvider.select((s) => s.replying));
    final hasMessages = ref.watch(assistantViewModelProvider.select((s) => s.messages.isNotEmpty));
    final offline = ref.watch(networkStatusProvider) == NetworkStatus.offline;
    final quota = ref.watch(chartQuotaNowProvider);
    final canAttach = canAttachChart(ref);
    final canSend = !offline && !replying && _controller.text.trim().isNotEmpty;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: c.canvas,
        border: Border(top: BorderSide(color: c.hairline)),
      ),
      child: Padding(
        padding: EdgeInsetsDirectional.fromSTEB(gutter - AppSpacing.sm, AppSpacing.xs, gutter - AppSpacing.sm, AppSpacing.xs),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (offline)
              Padding(
                padding: const EdgeInsetsDirectional.fromSTEB(AppSpacing.sm, 0, AppSpacing.sm, AppSpacing.xs),
                child: Text(l10n.asstOffline, style: context.textTheme.bodySmall!.copyWith(color: c.warning)),
              )
            // الحد خلص: الإرفاق معطّل بس الأسئلة شغّالة (بالمحادثة الفاضية السطر بالزر الرئيسي)
            else if (hasMessages && quota != null && quota.reached)
              Padding(
                padding: const EdgeInsetsDirectional.fromSTEB(AppSpacing.sm, 0, AppSpacing.sm, AppSpacing.xs),
                child: Semantics(
                  liveRegion: true,
                  child: Text(
                    '${chartLimitText(l10n, quota)} ${l10n.chartLimitChat}',
                    style: context.textTheme.bodySmall!.copyWith(color: c.fg2),
                  ),
                ),
              ),
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                IconButton(
                  tooltip: l10n.asstAttach,
                  constraints: const BoxConstraints(minWidth: AppSizes.minTap, minHeight: AppSizes.minTap),
                  icon: Icon(Icons.add_photo_alternate_outlined, color: canAttach ? c.fg2 : c.fgDisabled),
                  onPressed: canAttach ? () => pickChartImage(context, ref) : null,
                ),
                Expanded(
                  child: TextField(
                    controller: _controller,
                    enabled: !offline,
                    minLines: 1,
                    maxLines: 4,
                    maxLength: maxLength,
                    textCapitalization: TextCapitalization.sentences,
                    textInputAction: TextInputAction.send,
                    decoration: InputDecoration(hintText: l10n.asstHint, hintMaxLines: 8, counterText: ''),
                    onChanged: (_) => setState(() {}),
                    onSubmitted: (_) => canSend ? _send() : null,
                  ),
                ),
                const SizedBox(width: AppSpacing.xxs),
                if (replying)
                  IconButton(
                    tooltip: l10n.asstStop,
                    constraints: const BoxConstraints(minWidth: AppSizes.minTap, minHeight: AppSizes.minTap),
                    icon: Icon(Icons.stop_circle_outlined, color: c.fg),
                    onPressed: () {
                      AppHaptics.selection();
                      ref.read(assistantViewModelProvider.notifier).stop();
                    },
                  )
                else
                  IconButton.filled(
                    tooltip: l10n.asstSend,
                    constraints: const BoxConstraints(minWidth: AppSizes.minTap, minHeight: AppSizes.minTap),
                    style: IconButton.styleFrom(
                      backgroundColor: c.primaryAction,
                      foregroundColor: c.onPrimaryAction,
                      disabledBackgroundColor: c.pressed,
                      disabledForegroundColor: c.fgDisabled,
                    ),
                    icon: const Icon(Icons.arrow_upward_rounded),
                    onPressed: canSend ? _send : null,
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
