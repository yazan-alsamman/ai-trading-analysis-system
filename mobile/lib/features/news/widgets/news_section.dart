import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/router/app_navigator.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../core/widgets/motion.dart';
import '../../../core/widgets/source_tag.dart';
import '../../../l10n/app_localizations.dart';
import '../../../core/database/cache_support.dart';
import '../../markets/widgets/saved_data_status.dart';
import '../data/caching_news_repository.dart';
import '../data/news_repository.dart';
import '../models/news_models.dart';
import '../view_models/news_view_models.dart';
import 'news_card.dart';

/// قسم News بتبويب Community: سطر مزاج السوق (24 ساعة) وتحتو الأخبار.
/// سحب للتحديث، وتحميل / فاضي / خطأ.
class NewsSection extends ConsumerWidget {
  const NewsSection({super.key});

  Future<void> _refresh(BuildContext context, WidgetRef ref) async {
    try {
      await ref.read(newsViewModelProvider.notifier).refresh();
    } catch (error) {
      if (!context.mounted) return;
      final l10n = AppLocalizations.of(context)!;
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        // H5b: بدون اتصال الأخبار المحفوظة بتضل، وبتتحدّث لحالها لما يرجع الاتصال
        ..showSnackBar(SnackBar(
          content: Text(error is NoSavedDataException ? l10n.newsRefreshOffline : l10n.newsLoadError),
        ));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    final feed = ref.watch(newsViewModelProvider);
    final language = Localizations.localeOf(context).languageCode;
    final savedAt = ref.watch(newsSavedAtProvider(CachingNewsRepository.articlesKey(language)));

    Widget scroll(List<Widget> children) => RefreshIndicator(
          color: context.colors.accent,
          onRefresh: () => _refresh(context, ref),
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: EdgeInsets.fromLTRB(gutter, AppSpacing.xs, gutter, AppSpacing.xxl),
            children: children,
          ),
        );

    return feed.when(
      skipLoadingOnRefresh: true,
      loading: () => scroll([
        const LoadingRegion(child: Skeleton(height: AppSpacing.huge, radius: AppRadii.card)),
        for (var i = 0; i < 3; i++) ...[
          const SizedBox(height: AppSpacing.md),
          const Skeleton(height: AppSpacing.huge * 3, radius: AppRadii.card),
        ],
      ]),
      // H5b: بدون اتصال وما في أخبار محفوظة → السبب (بتتحمّل لحالها لما يرجع الاتصال)
      error: (error, __) => scroll([
        if (error is NoSavedDataException)
          EmptyState(
            illustrated: true,
            icon: Icons.cloud_off_outlined,
            title: l10n.offlineBannerTitle,
            message: l10n.newsOfflineNoCache,
          )
        else
          ErrorState(message: l10n.newsLoadError, onRetry: () => ref.invalidate(newsViewModelProvider)),
      ]),
      data: (data) => data.articles.isEmpty
          ? scroll([
              SavedDataStatus(updatedAt: savedAt),
              EmptyState(icon: Icons.newspaper_rounded, title: l10n.newsEmpty, message: l10n.newsEmptyBody),
            ])
          : scroll([
              // H5b: أخبار محفوظة (بدون اتصال / المصدر فشل) → الشارة + "Last updated"
              SavedDataStatus(updatedAt: savedAt),
              MoodLine(mood: data.mood),
              for (final (i, article) in data.articles.indexed) ...[
                const SizedBox(height: AppSpacing.md),
                FadeRise(
                  index: i,
                  child: NewsCard(
                    article: article,
                    onTap: () => context.pushNewsDetail(article.id),
                  ),
                ),
              ],
            ]),
    );
  }
}

/// مزاج السوق بسطر واحد: "Market mood · 24h  Mixed · 2 positive, 1 neutral,
/// 1 negative" + شارة "Simulated"
class MoodLine extends StatelessWidget {
  const MoodLine({super.key, required this.mood});

  final MarketMood mood;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;
    final leaning = switch (mood.leaning) {
      Sentiment.positive => l10n.moodPositive,
      Sentiment.negative => l10n.moodNegative,
      Sentiment.neutral => l10n.moodMixed,
      null => l10n.moodNone,
    };
    final counts = l10n.moodCounts('${mood.positive}', '${mood.neutral}', '${mood.negative}');

    return Semantics(
      container: true,
      label: '${l10n.moodTitle}: $leaning. ${mood.scored > 0 ? '$counts. ' : ''}${l10n.sourceDemo}',
      excludeSemantics: true,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: c.card,
          borderRadius: AppRadii.card,
          border: Border.all(color: c.hairline),
        ),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.sm),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Icon(Icons.auto_awesome_rounded, size: AppSizes.iconMd, color: c.forecast),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Text.rich(
                  TextSpan(children: [
                    TextSpan(text: '${l10n.moodTitle}  ', style: text.bodySmall),
                    TextSpan(text: leaning, style: text.titleSmall),
                    if (mood.scored > 0) TextSpan(text: ' · $counts', style: text.bodyMedium!.copyWith(color: c.fg2)),
                  ]),
                ),
              ),
              const SizedBox(width: AppSpacing.xs),
              const SourceTag(SourceKind.demo),
            ],
          ),
        ),
      ),
    );
  }
}
