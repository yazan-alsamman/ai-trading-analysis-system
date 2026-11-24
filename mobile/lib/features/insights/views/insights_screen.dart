import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../core/widgets/motion.dart';
import '../../../core/widgets/page_header.dart';
import '../../../core/widgets/source_tag.dart';
import '../../../l10n/app_localizations.dart';
import '../data/insights_repository.dart';
import '../models/track_record.dart';
import '../view_models/insights_view_model.dart';
import '../widgets/accuracy_breakdown.dart';
import '../widgets/accuracy_chart.dart';
import '../widgets/period_chips.dart';

/// Insights (من سطر الدقة بـ Signals): سجل النموذج بصراحة - نسبة الإصابة
/// للفترة، عبر الزمن، حسب الأداة وحسب الإطار، وعدد الإشارات جنب كل رقم.
///
/// الشرائح فوق ثابتة وشغّالة بكل الحالات (تحميل، فراغ، خطأ، بدون اتصال).
class InsightsScreen extends ConsumerWidget {
  const InsightsScreen({super.key});

  /// "حاول مجددًا": الفشل بيرجع يطلع كحالة، فما في شي نعمله هون
  Future<void> _retry(WidgetRef ref) async {
    try {
      await ref.read(insightsViewModelProvider.notifier).retry();
    } on Object {
      // الحالة نفسها بتعرض الخطأ
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    final period = ref.watch(insightsPeriodProvider);
    final simulated = ref.watch(insightsRepositoryProvider).isSimulated;
    void select(InsightsPeriod p) => ref.read(insightsPeriodProvider.notifier).select(p);

    Widget centered(Widget child) => Center(child: SingleChildScrollView(child: child));

    final body = ref.watch(insightsViewModelProvider).when(
          skipLoadingOnReload: false,
          skipLoadingOnRefresh: false,
          loading: () => const _LoadingBody(),
          error: (error, _) => centered(
            error is InsightsOfflineException
                ? EmptyState(
                    illustrated: true,
                    icon: Icons.cloud_off_outlined,
                    title: l10n.offlineBannerTitle,
                    message: l10n.insightsOfflineBody,
                    actionLabel: l10n.tryAgain,
                    onAction: () => _retry(ref),
                  )
                : ErrorState(message: l10n.insightsError, onRetry: () => _retry(ref)),
          ),
          data: (record) => record.isEmpty
              ? centered(EmptyState(
                  illustrated: true,
                  icon: Icons.insights_outlined,
                  title: l10n.insightsEmptyTitle,
                  message: l10n.insightsEmptyBody,
                  actionLabel: period == InsightsPeriod.d90 ? null : l10n.insightsShowLonger,
                  onAction: () => select(InsightsPeriod.d90),
                ))
              : _RecordBody(record: record, simulated: simulated),
        );

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            PageHeader(title: l10n.insightsTitle, back: const PageBackButton()),
            // سجل النموذج نفسه، مش طريقة الاستراتيجية (A3c) - بكل الحالات
            Padding(
              padding: EdgeInsets.fromLTRB(gutter, 0, gutter, AppSpacing.sm),
              child: Text(l10n.insightsIntro, style: context.textTheme.bodyMedium),
            ),
            Padding(
              padding: EdgeInsets.fromLTRB(gutter, 0, gutter, AppSpacing.sm),
              child: Row(
                children: [
                  Expanded(child: PeriodChips(selected: period, onSelected: select)),
                  if (simulated) ...[
                    const SizedBox(width: AppSpacing.xs),
                    const SourceTag(SourceKind.demo),
                  ],
                ],
              ),
            ),
            Expanded(child: body),
          ],
        ),
      ),
    );
  }
}

class _LoadingBody extends StatelessWidget {
  const _LoadingBody();

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    return Semantics(
      label: l10n.loading,
      child: ListView(
        padding: EdgeInsets.fromLTRB(gutter, AppSpacing.xs, gutter, AppSpacing.xxl),
        children: const [
          Skeleton(height: AppSpacing.huge * 3, radius: AppRadii.heroCard),
          SizedBox(height: AppSpacing.md),
          Skeleton(height: AccuracyChart.height, radius: AppRadii.card),
          SizedBox(height: AppSpacing.md),
          Skeleton(height: AppSpacing.huge * 4, radius: AppRadii.card),
        ],
      ),
    );
  }
}

class _RecordBody extends StatelessWidget {
  const _RecordBody({required this.record, required this.simulated});

  final TrackRecord record;
  final bool simulated;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    final sections = [
      _Headline(record: record),
      _OverTimeCard(record: record),
      AccuracyBreakdownCard(
        title: l10n.insightsByInstrument,
        rows: [
          for (final row in record.byInstrument)
            AccuracyRow(
              title: row.symbol,
              semanticName: '${row.symbol}, ${l10n.instrumentName(row.symbol)}',
              accuracy: row.accuracy,
            ),
        ],
      ),
      AccuracyBreakdownCard(
        title: l10n.insightsByTimeframe,
        rows: [
          for (final row in record.byTimeframe)
            AccuracyRow(title: row.timeframe.label, semanticName: row.timeframe.label, accuracy: row.accuracy),
        ],
      ),
      _Note(simulated: simulated),
    ];
    return ListView(
      padding: EdgeInsets.fromLTRB(gutter, AppSpacing.xs, gutter, AppSpacing.xxl),
      children: [
        for (final (i, section) in sections.indexed) ...[
          if (i > 0) const SizedBox(height: AppSpacing.md),
          FadeRise(index: i, child: section),
        ],
      ],
    );
  }
}

/// الرقم الكبير: نسبة الإصابة + كم من كم + كم وصلت للوقف أولًا
class _Headline extends StatelessWidget {
  const _Headline({required this.record});

  final TrackRecord record;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final overall = record.overall;
    final rate = overall.hitRate ?? 0;
    final period = record.period.label(l10n);
    final hits = '${overall.hits}';
    final count = '${overall.resolved}';

    return AppCard(
      highlight: true,
      child: Semantics(
        container: true,
        excludeSemantics: true,
        label: [
          l10n.insightsHeadlineLabel(period, Formatters.percent(rate), hits, count),
          if (overall.isSmallSample) l10n.insightsSmallSample,
        ].join(' '),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l10n.insightsHitRate(period), style: context.textTheme.labelMedium!.copyWith(color: c.fg2)),
            const SizedBox(height: AppSpacing.xxs),
            AnimatedNumber(
              // بدون عدّ من 0: الرقم بيطلع بقيمته (الشاشة بتنعرض بعد التحميل)
              value: rate,
              animateOnFirstBuild: false,
              format: (v) => Formatters.percent(v),
              style: context.type.numHero.copyWith(color: c.fg),
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(l10n.insightsHeadlineCount(hits, count), style: context.textTheme.bodyMedium),
            const SizedBox(height: AppSpacing.xxs),
            Text(
              [
                l10n.insightsHeadlineMisses('${overall.resolved - overall.hits}'),
                if (overall.isSmallSample) l10n.insightsSmallSample,
              ].join(' · '),
              style: context.textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}

class _OverTimeCard extends StatelessWidget {
  const _OverTimeCard({required this.record});

  final TrackRecord record;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Semantics(header: true, child: Text(l10n.insightsOverTime, style: context.textTheme.titleMedium)),
          const SizedBox(height: AppSpacing.sm),
          AccuracyChart(record: record),
          const SizedBox(height: AppSpacing.xs),
          Text(l10n.insightsChartCaption, style: context.textTheme.bodySmall),
        ],
      ),
    );
  }
}

/// كيف تنقرأ الأرقام + "النتائج السابقة ما بتضمن المستقبل" (+ محاكاة)
class _Note extends StatelessWidget {
  const _Note({required this.simulated});

  final bool simulated;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ExcludeSemantics(child: Icon(Icons.info_outline_rounded, size: AppSizes.iconMd, color: c.fg3)),
        const SizedBox(width: AppSpacing.xs),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Semantics(header: true, child: Text(l10n.insightsNoteTitle, style: context.textTheme.titleSmall)),
              const SizedBox(height: AppSpacing.xxs),
              Text(l10n.insightsNoteBody('$kMinTrackSample'), style: context.textTheme.bodySmall),
              if (simulated) ...[
                const SizedBox(height: AppSpacing.xxs),
                Text(l10n.insightsSimulatedNote, style: context.textTheme.bodySmall),
              ],
            ],
          ),
        ),
      ],
    );
  }
}
