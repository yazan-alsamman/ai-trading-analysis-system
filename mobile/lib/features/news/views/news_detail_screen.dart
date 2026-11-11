import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/clock.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../core/widgets/headings.dart';
import '../../../core/widgets/offline_banner.dart';
import '../../../core/widgets/page_header.dart';
import '../../../core/widgets/source_tag.dart';
import '../../../l10n/app_localizations.dart';
import '../../comments/models/comment.dart';
import '../../comments/widgets/comments_sheet.dart';
import '../view_models/news_view_models.dart';
import '../widgets/news_card.dart';

/// صفحة الخبر: مقال كامل بقراءة مريحة (عرض أقصى، فقرات)، النبرة والأدوات
/// فوق، وزر التعليقات ثابت تحت (بيفتح sheet).
class NewsDetailScreen extends ConsumerWidget {
  const NewsDetailScreen({super.key, required this.articleId});

  final String articleId;

  /// عرض النص الأقصى - سطر مقروء على التابلت
  static const double maxTextWidth = 640;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final text = context.textTheme;
    final gutter = AppSpacing.gutter(context);
    final feed = ref.watch(newsViewModelProvider);
    final article = ref.watch(newsArticleProvider(articleId));
    final now = ref.watch(clockProvider).valueOrNull ?? DateTime.now();

    final Widget body;
    if (article == null) {
      body = feed.isLoading
          ? LoadingRegion(
              child: ListView(
                physics: const NeverScrollableScrollPhysics(),
                padding: EdgeInsets.fromLTRB(gutter, AppSpacing.xs, gutter, 0),
                children: [
                  const Skeleton(width: AppSpacing.huge * 3),
                  const SizedBox(height: AppSpacing.sm),
                  const Skeleton(height: AppSpacing.xxl),
                  const SizedBox(height: AppSpacing.lg),
                  for (var i = 0; i < 6; i++) ...[const Skeleton(), const SizedBox(height: AppSpacing.sm)],
                ],
              ),
            )
          : Center(
              child: feed.hasError
                  ? ErrorState(message: l10n.newsLoadError, onRetry: () => ref.invalidate(newsViewModelProvider))
                  : EmptyState(icon: Icons.article_outlined, title: l10n.newsNotFound),
            );
    } else {
      final paragraphs = article.body.split(RegExp(r'\n\s*\n')).where((p) => p.trim().isNotEmpty);
      body = ListView(
        padding: EdgeInsets.fromLTRB(gutter, AppSpacing.xs, gutter, AppSpacing.xxl),
        children: [
          Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: maxTextWidth),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Eyebrow(newsByline(l10n, article, now)),
                  const SizedBox(height: AppSpacing.xs),
                  Semantics(header: true, child: Text(article.title, style: text.displaySmall)),
                  const SizedBox(height: AppSpacing.md),
                  Wrap(
                    spacing: AppSpacing.xs,
                    runSpacing: AppSpacing.xs,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      if (article.sentiment case final s?) SentimentTag(s),
                      for (final symbol in article.symbols) SymbolTag(symbol),
                      const SourceTag(SourceKind.demo),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  Divider(height: 1, color: c.hairline),
                  const SizedBox(height: AppSpacing.lg),
                  for (final p in paragraphs) ...[
                    Text(p.trim(), style: text.bodyLarge!.copyWith(height: 1.6)),
                    const SizedBox(height: AppSpacing.md),
                  ],
                  if (article.sentiment != null) ...[
                    const SizedBox(height: AppSpacing.xs),
                    Text(l10n.sentimentNote, style: text.bodySmall),
                  ],
                ],
              ),
            ),
          ),
        ],
      );
    }

    return Scaffold(
      bottomNavigationBar: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (article != null)
            DecoratedBox(
              decoration: BoxDecoration(
                color: c.canvas,
                border: Border(top: BorderSide(color: c.hairline)),
              ),
              child: SafeArea(
                top: false,
                child: Padding(
                  padding: EdgeInsets.fromLTRB(gutter, AppSpacing.sm, gutter, AppSpacing.sm),
                  child: AppButton.secondary(
                    label: l10n.commentsTitle('${article.commentsCount}'),
                    icon: Icons.mode_comment_outlined,
                    expand: true,
                    onPressed: () =>
                        showCommentsSheet(context, thread: (target: CommentTarget.article, id: article.id)),
                  ),
                ),
              ),
            ),
          const OfflineBanner(),
        ],
      ),
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            PageHeader(title: l10n.communityNews, back: const PageBackButton()),
            Expanded(child: body),
          ],
        ),
      ),
    );
  }
}
