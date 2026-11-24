import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/router/app_navigator.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../core/widgets/motion.dart';
import '../../../core/widgets/source_tag.dart';
import '../../../l10n/app_localizations.dart';
import '../../comments/models/comment.dart';
import '../../comments/widgets/comments_sheet.dart';
import '../models/post.dart';
import '../view_models/posts_view_model.dart';
import 'new_post_sheet.dart';
import 'post_card.dart';
import 'report_sheet.dart';

/// يفتح "New post"، وبعد النشر snackbar تأكيد (من زر Community أو حالة الفراغ)
Future<void> composePost(BuildContext context) async {
  final messenger = ScaffoldMessenger.of(context);
  final l10n = AppLocalizations.of(context)!;
  final posted = await showNewPostSheet(context);
  if (posted ?? false) {
    messenger
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(l10n.postShared)));
  }
}

/// قسم Posts بتبويب Community: منشورات كل الأعضاء (الأحدث أول، نفس الشكل للكل)،
/// إعجاب، تعليقات بـ sheet (نفس تعليقات الأخبار)، وحذف منشورك مع Undo.
/// سحب للتحديث، وتحميل / فاضي / خطأ.
class PostsSection extends ConsumerWidget {
  const PostsSection({super.key});

  /// مسافة تحت القائمة حتى آخر بطاقة ما تنغطّى بزر "New post"
  static const double fabClearance = AppSpacing.huge * 2;

  Future<void> _refresh(BuildContext context, WidgetRef ref) async {
    try {
      await ref.read(postsViewModelProvider.notifier).refresh();
    } catch (error) {
      if (!context.mounted) return;
      final l10n = AppLocalizations.of(context)!;
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(
          content: Text(error is PostsOfflineException ? l10n.postsOfflineAction : l10n.postsLoadError),
        ));
    }
  }

  /// رسالة فشل إجراء: بدون اتصال أو فشل عادي
  static String _failure(AppLocalizations l10n, Object error) =>
      error is PostsOfflineException ? l10n.postsOfflineAction : l10n.postActionFailed;

  Future<void> _like(BuildContext context, WidgetRef ref, Post post) async {
    final messenger = ScaffoldMessenger.of(context);
    final l10n = AppLocalizations.of(context)!;
    try {
      await ref.read(postsViewModelProvider.notifier).toggleLike(post.id);
    } catch (error) {
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(_failure(l10n, error))));
    }
  }

  Future<void> _delete(BuildContext context, WidgetRef ref, Post post) async {
    final messenger = ScaffoldMessenger.of(context);
    final l10n = AppLocalizations.of(context)!;
    final vm = ref.read(postsViewModelProvider.notifier);
    try {
      final removed = await vm.remove(post.id);
      if (removed == null) return;
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(
          content: Text(l10n.postDeleted),
          action: SnackBarAction(label: l10n.undo, onPressed: () => vm.undoRemove(removed)),
        ));
    } catch (error) {
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(_failure(l10n, error))));
    }
  }

  Future<void> _report(BuildContext context, WidgetRef ref, Post post) async {
    final messenger = ScaffoldMessenger.of(context);
    final l10n = AppLocalizations.of(context)!;
    final reason = await showReportSheet(context);
    if (reason == null) return;
    try {
      final sent = await ref.read(postsViewModelProvider.notifier).report(post.id, reason);
      if (!sent) return;
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(l10n.reportSent)));
    } catch (error) {
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(_failure(l10n, error))));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    final posts = ref.watch(postsViewModelProvider);

    Widget scroll(List<Widget> children) => RefreshIndicator(
          color: context.colors.accent,
          onRefresh: () => _refresh(context, ref),
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: EdgeInsets.fromLTRB(gutter, AppSpacing.xs, gutter, fabClearance),
            children: children,
          ),
        );

    final intro = Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SourceTag(SourceKind.demo),
        const SizedBox(width: AppSpacing.xs),
        Expanded(child: Text(l10n.postsIntro, style: context.textTheme.bodySmall)),
      ],
    );

    return posts.when(
      skipLoadingOnRefresh: true,
      loading: () => scroll([
        intro,
        const SizedBox(height: AppSpacing.md),
        LoadingRegion(
          child: Column(children: [
            for (var i = 0; i < 3; i++) ...[
              if (i > 0) const SizedBox(height: AppSpacing.md),
              const Skeleton(height: AppSpacing.huge * 3, radius: AppRadii.card),
            ],
          ]),
        ),
      ]),
      error: (error, _) => scroll([
        if (error is PostsOfflineException)
          EmptyState(
            illustrated: true,
            icon: Icons.cloud_off_outlined,
            title: l10n.postsOfflineTitle,
            message: l10n.postsOfflineBody,
            actionLabel: l10n.tryAgain,
            onAction: () => ref.invalidate(postsViewModelProvider),
          )
        else
          ErrorState(message: l10n.postsLoadError, onRetry: () => ref.invalidate(postsViewModelProvider)),
      ]),
      data: (list) => list.isEmpty
          ? scroll([
              intro,
              EmptyState(
                illustrated: true,
                icon: Icons.forum_outlined,
                title: l10n.postsEmptyTitle,
                message: l10n.postsEmptyBody,
                actionLabel: l10n.newPost,
                onAction: () => composePost(context),
              ),
            ])
          : scroll([
              intro,
              for (final (i, post) in list.indexed) ...[
                const SizedBox(height: AppSpacing.md),
                FadeRise(
                  key: ValueKey(post.id),
                  index: i,
                  child: PostCard(
                    post: post,
                    onLike: () => _like(context, ref, post),
                    onComments: () => showCommentsSheet(context, thread: (target: CommentTarget.post, id: post.id)),
                    onSymbol: context.pushMarket,
                    onDelete: post.isOwn ? () => _delete(context, ref, post) : null,
                    onReport: post.isOwn ? null : () => _report(context, ref, post),
                  ),
                ),
              ],
            ]),
    );
  }
}
