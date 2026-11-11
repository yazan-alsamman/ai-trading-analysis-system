import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/clock.dart';
import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_card.dart';
import '../../../l10n/app_localizations.dart';
import '../models/news_models.dart';

/// شارة النبرة: أيقونة + كلمة بالبنفسجي (ناتج نموذج، مش اتجاه سعر)
class SentimentTag extends StatelessWidget {
  const SentimentTag(this.sentiment, {super.key});

  final Sentiment sentiment;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final label = sentiment.label(l10n);
    return Semantics(
      label: l10n.sentimentLabel(label),
      excludeSemantics: true,
      child: DecoratedBox(
        decoration: BoxDecoration(color: c.forecastSoft, borderRadius: AppRadii.badge),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xs, vertical: AppSpacing.xxs / 2),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(sentiment.icon, size: AppSizes.iconSm - 2, color: c.forecast),
              const SizedBox(width: AppSpacing.xxs),
              Text(label, style: context.textTheme.labelSmall!.copyWith(color: c.forecast)),
            ],
          ),
        ),
      ),
    );
  }
}

/// رمز أداة صغير (مش قابل للضغط - البطاقة كلها هي الزر)
class SymbolTag extends StatelessWidget {
  const SymbolTag(this.symbol, {super.key});

  final String symbol;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: c.inset,
        borderRadius: AppRadii.badge,
        border: Border.all(color: c.hairline),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xs, vertical: AppSpacing.xxs / 2),
        child: Text(symbol, style: context.type.numSmall.copyWith(color: c.fg2), textDirection: TextDirection.ltr),
      ),
    );
  }
}

/// "ForexLive · 2h ago"
String newsByline(AppLocalizations l10n, NewsArticle article, DateTime now) =>
    '${article.source} · ${relativeTime(l10n, article.publishedAt, now)}';

/// بطاقة خبر بالقائمة: المصدر والوقت، العنوان، الملخص (سطرين)، وتحت
/// النبرة + الأدوات + عدد التعليقات. الضغط بيفتح الخبر كامل.
class NewsCard extends ConsumerWidget {
  const NewsCard({super.key, required this.article, required this.onTap});

  final NewsArticle article;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;
    final now = ref.watch(clockProvider).valueOrNull ?? DateTime.now();

    return AppCard(
      onTap: onTap,
      semanticLabel: [
        article.title,
        newsByline(l10n, article, now),
        if (article.sentiment case final s?) l10n.sentimentLabel(s.label(l10n)),
        l10n.commentsTitle('${article.commentsCount}'),
      ].join(', '),
      child: ExcludeSemantics(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(newsByline(l10n, article, now), style: text.bodySmall),
            const SizedBox(height: AppSpacing.xxs),
            Text(article.title, style: text.titleMedium),
            if (article.summary.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.xxs),
              Text(
                article.summary,
                style: text.bodyMedium!.copyWith(color: c.fg2),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
            const SizedBox(height: AppSpacing.sm),
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Expanded(
                  child: Wrap(
                    spacing: AppSpacing.xs,
                    runSpacing: AppSpacing.xs,
                    children: [
                      if (article.sentiment case final s?) SentimentTag(s),
                      for (final symbol in article.symbols) SymbolTag(symbol),
                    ],
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Icon(Icons.mode_comment_outlined, size: AppSizes.iconSm, color: c.fg3),
                const SizedBox(width: AppSpacing.xxs),
                Text('${article.commentsCount}', style: context.type.numSmall.copyWith(color: c.fg2)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
