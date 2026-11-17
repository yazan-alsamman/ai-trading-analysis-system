import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/clock.dart';
import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../l10n/app_localizations.dart';
import '../models/comment.dart';
import '../view_models/comments_view_model.dart';

/// تعليقات خبر أو منشور بـ bottom sheet: القائمة بتسكرول، وحقل الكتابة ثابت
/// تحت (بيطلع فوق الكيبورد). حذف تعليقك بيعطي Undo.
Future<void> showCommentsSheet(BuildContext context, {required CommentThread thread}) {
  AppHaptics.light();
  return showModalBottomSheet<void>(
    useRootNavigator: true,
    context: context,
    sheetAnimationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
    isScrollControlled: true,
    useSafeArea: true,
    showDragHandle: true,
    builder: (context) => Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.75,
        minChildSize: 0.4,
        maxChildSize: 1,
        builder: (context, controller) => _CommentsSheet(thread: thread, controller: controller),
      ),
    ),
  );
}

class _CommentsSheet extends ConsumerWidget {
  const _CommentsSheet({required this.thread, required this.controller});

  final CommentThread thread;
  final ScrollController controller;

  Future<void> _delete(BuildContext context, WidgetRef ref, Comment comment) async {
    final messenger = ScaffoldMessenger.of(context);
    final l10n = AppLocalizations.of(context)!;
    final vm = ref.read(commentsViewModelProvider(thread).notifier);
    try {
      final removed = await vm.remove(comment.id);
      if (removed == null) return;
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(
          content: Text(l10n.commentDeleted),
          action: SnackBarAction(label: l10n.undo, onPressed: () => vm.undoRemove(removed)),
        ));
    } catch (error) {
      messenger.showSnackBar(SnackBar(
        content: Text(error is CommentsOfflineException ? l10n.commentsOfflineAction : l10n.commentActionFailed),
      ));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    final comments = ref.watch(commentsViewModelProvider(thread));
    final count = comments.valueOrNull?.length;

    return ScaffoldMessenger(
      child: Builder(
        builder: (context) => Scaffold(
          backgroundColor: Colors.transparent,
          // الـ padding تبع الكيبورد برا الـ sheet - ما منضاعفه
          resizeToAvoidBottomInset: false,
          body: Column(
            children: [
              Expanded(
                child: ListView(
                  controller: controller,
                  padding: EdgeInsets.fromLTRB(gutter, 0, gutter, AppSpacing.md),
                  children: [
                    Semantics(
                      header: true,
                      child: Text(
                        count == null ? l10n.comments : l10n.commentsTitle('$count'),
                        style: context.textTheme.titleLarge,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.md),
                    ...comments.when(
                      loading: () => [
                        LoadingRegion(
                          child: Column(children: [for (var i = 0; i < 3; i++) const _SkeletonComment()]),
                        ),
                      ],
                      // H5b: بدون اتصال → السبب (بيتحمّل لحالو لما يرجع الاتصال)
                      error: (error, __) => [
                        if (error is CommentsOfflineException)
                          EmptyState(
                            icon: Icons.cloud_off_outlined,
                            title: l10n.offlineBannerTitle,
                            message: l10n.commentsOffline,
                          )
                        else
                          ErrorState(onRetry: () => ref.invalidate(commentsViewModelProvider(thread))),
                      ],
                      data: (list) => list.isEmpty
                          ? [
                              EmptyState(
                                  icon: Icons.forum_outlined,
                                  title: l10n.commentsEmpty,
                                  message: l10n.commentsEmptyBody)
                            ]
                          : [
                              for (final comment in list)
                                _CommentTile(
                                  key: ValueKey(comment.id),
                                  comment: comment,
                                  onDelete: comment.isOwn ? () => _delete(context, ref, comment) : null,
                                ),
                            ],
                    ),
                  ],
                ),
              ),
              _Composer(thread: thread),
            ],
          ),
        ),
      ),
    );
  }
}

class _CommentTile extends ConsumerWidget {
  const _CommentTile({super.key, required this.comment, this.onDelete});

  final Comment comment;
  final VoidCallback? onDelete;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;
    final now = ref.watch(clockProvider).valueOrNull ?? DateTime.now();
    final author = comment.isOwn ? l10n.commentAuthorYou : comment.author;
    final time = relativeTime(l10n, comment.createdAt, now);

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(
            radius: AppSpacing.md,
            backgroundColor: comment.isOwn ? c.accentSoft : c.inset,
            child: ExcludeSemantics(
              child: Text(
                author.characters.first.toUpperCase(),
                style: text.labelLarge!.copyWith(color: comment.isOwn ? c.accent : c.fg2),
              ),
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: AppSpacing.xs,
                  runSpacing: AppSpacing.xxs,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Text(author, style: text.titleSmall),
                    Text(time, style: text.bodySmall),
                  ],
                ),
                const SizedBox(height: 2),
                Text(comment.body, style: text.bodyMedium!.copyWith(color: c.fg)),
              ],
            ),
          ),
          if (onDelete != null)
            IconButton(
              tooltip: l10n.commentDelete,
              constraints: const BoxConstraints(minWidth: AppSizes.minTap, minHeight: AppSizes.minTap),
              icon: Icon(Icons.delete_outline_rounded, color: c.fg3, size: AppSizes.iconMd),
              onPressed: onDelete,
            ),
        ],
      ),
    );
  }
}

/// حقل كتابة التعليق + زر الإرسال (معطّل وهو فاضي أو عم يبعت)
class _Composer extends ConsumerStatefulWidget {
  const _Composer({required this.thread});

  final CommentThread thread;

  @override
  ConsumerState<_Composer> createState() => _ComposerState();
}

class _ComposerState extends ConsumerState<_Composer> {
  final _controller = TextEditingController();
  bool _sending = false;

  static const int maxLength = 1000;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    if (_sending || _controller.text.trim().isEmpty) return;
    setState(() => _sending = true);
    try {
      final ok = await ref.read(commentsViewModelProvider(widget.thread).notifier).add(_controller.text);
      if (ok) {
        AppHaptics.confirm();
        _controller.clear();
      }
    } catch (error) {
      // المسودة بتضل بالخانة (بتنمسح بس لما ينبعت)
      if (mounted) {
        final l10n = AppLocalizations.of(context)!;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error is CommentsOfflineException ? l10n.commentsOfflineAction : l10n.commentActionFailed)),
        );
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    final canSend = !_sending && _controller.text.trim().isNotEmpty;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: c.sheet,
        border: Border(top: BorderSide(color: c.hairline)),
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: EdgeInsetsDirectional.fromSTEB(gutter, AppSpacing.xs, gutter - AppSpacing.xs, AppSpacing.xs),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: TextField(
                  controller: _controller,
                  enabled: !_sending,
                  minLines: 1,
                  maxLines: 4,
                  maxLength: maxLength,
                  textCapitalization: TextCapitalization.sentences,
                  decoration: InputDecoration(hintText: l10n.commentHint, hintMaxLines: 3, counterText: ''),
                  onChanged: (_) => setState(() {}),
                ),
              ),
              const SizedBox(width: AppSpacing.xxs),
              IconButton(
                tooltip: l10n.commentSend,
                constraints: const BoxConstraints(minWidth: AppSizes.minTap, minHeight: AppSizes.minTap),
                onPressed: canSend ? _send : null,
                icon: _sending
                    ? SizedBox.square(
                        dimension: AppSizes.iconMd,
                        child: CircularProgressIndicator(strokeWidth: 2, color: c.fg2),
                      )
                    : Icon(Icons.send_rounded, color: canSend ? c.accent : c.fgDisabled),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SkeletonComment extends StatelessWidget {
  const _SkeletonComment();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.only(bottom: AppSpacing.md),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Skeleton(width: AppSpacing.xxl, height: AppSpacing.xxl, radius: AppRadii.pillAll),
          SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Skeleton(width: AppSpacing.huge * 2),
                SizedBox(height: AppSpacing.xs),
                Skeleton(height: AppSpacing.sm),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
