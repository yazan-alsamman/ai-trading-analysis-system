import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/direction_badge.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../core/widgets/motion.dart';
import '../../../core/widgets/page_header.dart';
import '../../../l10n/app_localizations.dart';
import '../../insights/models/track_record.dart';
import '../../markets/models/market_models.dart';
import '../../signals/data/signal_profile_repository.dart';
import '../../signals/models/signal_profile.dart';
import '../../signals/widgets/method_picker.dart';
import '../../signals/widgets/strategy_sheet.dart';
import '../data/backtest_repository.dart';
import '../models/backtest.dart';
import '../view_models/backtest_view_model.dart';
import '../widgets/backtest_figures.dart';
import '../widgets/equity_chart.dart';

extension BacktestPeriodLabel on BacktestPeriod {
  /// "30 days" / "1 year" / "5 years"
  String label(AppLocalizations l10n) => switch (this) {
        BacktestPeriod.d30 => l10n.insightsPeriod30,
        BacktestPeriod.d90 => l10n.insightsPeriod90,
        BacktestPeriod.y1 => l10n.backtestPeriod1y,
        BacktestPeriod.y2 => l10n.backtestPeriod2y,
        BacktestPeriod.y3 => l10n.backtestPeriod3y,
        BacktestPeriod.y5 => l10n.backtestPeriod5y,
      };
}

/// Backtest (من "Test on past data" بـ Strategy): الإشارات السابقة يلي
/// بتطابق الاستراتيجية المحفوظة على الأدوات والفترة المختارة - كم إشارة، نسبة
/// الإصابة، متوسط العائد : المخاطرة، أقصى تراجع ومنحنى النتيجة بوحدات R.
///
/// سطر "Simulated · past results are not a promise of future results" ثابت فوق بكل
/// الحالات. الإعدادات شغّالة دايمًا (تغييرها أثناء الشغل بيلغيه).
class BacktestScreen extends ConsumerWidget {
  const BacktestScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    final simulated = ref.watch(backtestRepositoryProvider).isSimulated;
    final state = ref.watch(backtestViewModelProvider);
    final vm = ref.read(backtestViewModelProvider.notifier);

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            PageHeader(title: l10n.backtestTitle, back: const PageBackButton()),
            Padding(
              padding: EdgeInsets.fromLTRB(gutter, 0, gutter, AppSpacing.sm),
              child: _Disclaimer(simulated: simulated),
            ),
            Expanded(
              child: ListView(
                padding: EdgeInsets.fromLTRB(gutter, AppSpacing.xs, gutter, AppSpacing.xxl),
                children: [
                  _Settings(state: state, onToggle: vm.toggleSymbol, onPeriod: vm.selectPeriod),
                  const SizedBox(height: AppSpacing.lg),
                  AppButton(
                    label: l10n.backtestRun,
                    icon: Icons.play_arrow_rounded,
                    expand: true,
                    loading: state.isRunning,
                    onPressed: state.canRun ? vm.run : null,
                  ),
                  if (state.symbols.isEmpty) ...[
                    const SizedBox(height: AppSpacing.xs),
                    Semantics(
                      liveRegion: true,
                      child: Text(
                        l10n.backtestPickInstrument,
                        style: context.textTheme.bodyMedium!.copyWith(color: context.colors.danger),
                      ),
                    ),
                  ],
                  const SizedBox(height: AppSpacing.lg),
                  _Status(state: state, onRun: vm.run, onPeriod: vm.selectPeriod),
                  const SizedBox(height: AppSpacing.lg),
                  const _Note(),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// "Simulated · past results are not a promise of future results" (دايمًا ظاهر)
class _Disclaimer extends StatelessWidget {
  const _Disclaimer({required this.simulated});

  final bool simulated;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ExcludeSemantics(
          child: Icon(simulated ? Icons.science_outlined : Icons.info_outline_rounded,
              size: AppSizes.iconSm, color: c.fg3),
        ),
        const SizedBox(width: AppSpacing.xs),
        Expanded(
          child: Text(
            simulated ? l10n.backtestDisclaimerSimulated : l10n.backtestDisclaimer,
            style: context.textTheme.bodySmall,
          ),
        ),
      ],
    );
  }
}

/// الأدوات (من الاستراتيجية) + الفترة + شو الاستراتيجية المطبّقة وفلاترها
class _Settings extends ConsumerWidget {
  const _Settings({required this.state, required this.onToggle, required this.onPeriod});

  final BacktestState state;
  final void Function(String symbol, bool on) onToggle;
  final ValueChanged<BacktestPeriod> onPeriod;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;
    final custom = ref.watch(hasCustomStrategyProvider);
    final methodName = watchMethodName(ref, context, state.methodId);
    final using = custom ? l10n.backtestUsingSaved : l10n.backtestUsingDefault;

    Widget label(String value) => Padding(
          padding: const EdgeInsets.only(top: AppSpacing.md, bottom: AppSpacing.xs),
          child: Semantics(header: true, child: Text(value, style: text.titleSmall)),
        );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(l10n.backtestIntro, style: text.bodyMedium),
        const SizedBox(height: AppSpacing.sm),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ExcludeSemantics(
              child: Icon(
                custom ? Icons.check_circle_rounded : Icons.tune_outlined,
                size: AppSizes.iconSm,
                color: custom ? c.accent : c.fg3,
              ),
            ),
            const SizedBox(width: AppSpacing.xs),
            Expanded(
              child: Text(
                // "Using your saved strategy · RSI Reversal" (بيلتف بالخط الكبير)
                methodName == null ? using : '$using · $methodName',
                style: text.labelMedium!.copyWith(color: custom ? c.fg : c.fg2),
              ),
            ),
          ],
        ),
        label(l10n.strategyInstruments),
        Wrap(
          spacing: AppSpacing.xs,
          runSpacing: AppSpacing.xs,
          children: [
            for (final symbol in kProductSymbols)
              MergeSemantics(
                child: Semantics(
                  label: l10n.instrumentName(symbol),
                  child: FilterChip(
                    label: Text(symbol, style: context.type.numSmall.copyWith(color: c.fg)),
                    selected: state.symbols.contains(symbol),
                    materialTapTargetSize: MaterialTapTargetSize.padded,
                    onSelected: (on) {
                      AppHaptics.selection();
                      onToggle(symbol, on);
                    },
                  ),
                ),
              ),
          ],
        ),
        label(l10n.insightsPeriodsLabel),
        // 6 فترات: الشرائح بتنزل لسطر تاني لما ما بتساع، وكل تسمية سطر واحد
        Wrap(
          spacing: AppSpacing.xs,
          runSpacing: AppSpacing.xs,
          children: [
            for (final period in BacktestPeriod.values)
              ChoiceChip(
                selected: period == state.period,
                showCheckmark: false,
                materialTapTargetSize: MaterialTapTargetSize.padded,
                onSelected: (_) {
                  if (period == state.period) return;
                  AppHaptics.selection();
                  onPeriod(period);
                },
                label: Text(period.label(l10n), maxLines: 1, softWrap: false),
              ),
          ],
        ),
        const SizedBox(height: AppSpacing.md),
        Text(_strategyLine(l10n, state.strategy), style: text.bodySmall),
      ],
    );
  }

  static String _strategyLine(AppLocalizations l10n, SignalProfile s) => l10n.backtestStrategyLine(
        [
          for (final tf in Timeframe.modelTimeframes)
            if (s.timeframes.contains(tf)) tf.label
        ].join(', '),
        [
          for (final d in const [SignalDirection.long, SignalDirection.short])
            if (s.directions.contains(d)) d.label(l10n),
        ].join(', '),
        minProbabilityText(l10n, s.minProbability),
        minRiskRewardText(l10n, s.minRiskReward),
      );
}

/// تحت زر Run: idle / شغّال / نتيجة / فاضي / خطأ / بدون اتصال
class _Status extends StatelessWidget {
  const _Status({required this.state, required this.onRun, required this.onPeriod});

  final BacktestState state;
  final Future<void> Function() onRun;
  final ValueChanged<BacktestPeriod> onPeriod;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return switch (state.status) {
      BacktestIdle() => Text(
          l10n.backtestIdle,
          style: context.textTheme.bodyMedium!.copyWith(color: context.colors.fg2),
          textAlign: TextAlign.center,
        ),
      BacktestRunning(:final progress) => _Running(progress: progress),
      BacktestDone(:final result) when result.isEmpty => EmptyState(
          illustrated: true,
          icon: Icons.manage_search_rounded,
          title: l10n.backtestEmptyTitle,
          message: l10n.backtestEmptyBody,
          // "جرّب سنة" بس لما الفترة أقصر من سنة (ما منقصّر فترة أطول)
          actionLabel: state.period.days >= BacktestPeriod.y1.days ? null : l10n.backtestTryYear,
          onAction: () {
            onPeriod(BacktestPeriod.y1);
            onRun();
          },
        ),
      BacktestDone(:final result) => _Results(result: result),
      BacktestFailed(offline: true) => EmptyState(
          illustrated: true,
          icon: Icons.cloud_off_outlined,
          title: l10n.offlineBannerTitle,
          message: l10n.backtestOfflineBody,
          actionLabel: l10n.tryAgain,
          onAction: onRun,
        ),
      BacktestFailed() => ErrorState(message: l10n.backtestError, onRetry: onRun),
    };
  }
}

class _Running extends StatelessWidget {
  const _Running({required this.progress});

  final double progress;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final percent = Formatters.percent(progress);
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(
                child: Semantics(
                  liveRegion: true,
                  child: Text(l10n.backtestRunning, style: context.textTheme.titleSmall),
                ),
              ),
              const SizedBox(width: AppSpacing.xs),
              ExcludeSemantics(child: Text(percent, style: context.type.numSmall.copyWith(color: context.colors.fg))),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          ClipRRect(
            borderRadius: AppRadii.badge,
            child: LinearProgressIndicator(
              value: progress,
              minHeight: 6,
              semanticsLabel: l10n.backtestRunning,
              // رقم بس (القارئ الصوتي بيضيف "بالمية")
              semanticsValue: '${(progress * 100).round()}',
            ),
          ),
        ],
      ),
    );
  }
}

class _Results extends StatelessWidget {
  const _Results({required this.result});

  final BacktestResult result;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final sections = [
      Semantics(
        header: true,
        child: Text(l10n.backtestResults(result.period.label(l10n)), style: context.textTheme.titleMedium),
      ),
      BacktestFigures(result: result),
      AppCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Semantics(header: true, child: Text(l10n.backtestEquityTitle, style: context.textTheme.titleMedium)),
            const SizedBox(height: AppSpacing.sm),
            EquityChart(result: result),
            const SizedBox(height: AppSpacing.xs),
            Text(l10n.backtestEquityCaption('${result.signals}'), style: context.textTheme.bodySmall),
          ],
        ),
      ),
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final (i, section) in sections.indexed) ...[
          if (i > 0) const SizedBox(height: AppSpacing.md),
          FadeRise(index: i, child: section),
        ],
      ],
    );
  }
}

/// كيف تنقرأ الأرقام (نفس قاعدة "عيّنة صغيرة" تبع Insights)
class _Note extends StatelessWidget {
  const _Note();

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
              Text(l10n.backtestNote('$kMinTrackSample'), style: context.textTheme.bodySmall),
            ],
          ),
        ),
      ],
    );
  }
}
