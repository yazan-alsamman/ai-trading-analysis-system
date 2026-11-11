import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/direction_text.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../core/widgets/page_header.dart';
import '../../../core/widgets/price_flash.dart';
import '../../../core/widgets/source_tag.dart';
import '../../../l10n/app_localizations.dart';
import '../../alerts/widgets/alerts_section.dart';
import '../../alerts/widgets/set_alert_sheet.dart';
import '../../forecast/view_models/forecast_view_model.dart';
import '../../forecast/widgets/forecast_legend.dart';
import '../../forecast/widgets/forecast_toggle.dart';
import '../../risk/widgets/size_trade_sheet.dart';
import '../../signals/models/opportunity.dart';
import '../../signals/widgets/request_analysis_sheet.dart';
import '../data/market_providers.dart';
import '../models/market_models.dart';
import '../view_models/market_view_model.dart';
import '../widgets/feed_status_pill.dart';
import '../widgets/indicators_sheet.dart';
import '../widgets/market_hero.dart';
import '../widgets/price_chart.dart';
import '../widgets/signal_summary.dart';

/// شاشة الأداة: السعر الحي، الرسم (نوع + إطار + مؤشرات + مناطق النموذج)،
/// خلاصة رأي النموذج، وتنبيهات الأداة. "Set alert" زر عائم تحت (سهل للإبهام).
class MarketScreen extends ConsumerWidget {
  const MarketScreen({super.key, required this.symbol});

  final String symbol;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final instruments = ref.watch(instrumentsProvider);
    final instrument = ref.watch(instrumentProvider(symbol));
    final gutter = AppSpacing.gutter(context);

    final Widget body;
    if (instrument == null) {
      body = instruments.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => Center(child: ErrorState(onRetry: () => ref.invalidate(instrumentsProvider))),
        // رمز مش موجود (رابط قديم مثلًا)
        data: (_) => Center(child: EmptyState(icon: Icons.search_off_rounded, title: l10n.chartEmpty)),
      );
    } else {
      body = ListView(
        padding: EdgeInsets.fromLTRB(gutter, AppSpacing.xs, gutter, AppSpacing.huge * 2),
        children: [
          _PriceBlock(instrument: instrument),
          const SizedBox(height: AppSpacing.md),
          _ChartCard(instrument: instrument),
          const SizedBox(height: AppSpacing.md),
          _ModelReadCard(instrument: instrument),
          const SizedBox(height: AppSpacing.lg),
          AlertsSection(instrument: instrument),
        ],
      );
    }

    return Scaffold(
      floatingActionButton: instrument == null
          ? null
          : FloatingActionButton.extended(
              onPressed: () => setAlertAndConfirm(context, instrument: instrument),
              icon: const Icon(Icons.add_alert_outlined),
              label: Text(l10n.setAlert),
            ),
      body: SafeArea(
        bottom: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _Header(symbol: symbol),
            Expanded(child: body),
          ],
        ),
      ),
    );
  }
}

/// سهم الرجوع + الرمز (Hero من قائمة المتابعة) + الاسم الكامل
class _Header extends StatelessWidget {
  const _Header({required this.symbol});

  final String symbol;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    return Padding(
      padding: EdgeInsetsDirectional.fromSTEB(gutter - AppSpacing.sm, AppSpacing.xs, gutter, AppSpacing.xs),
      child: Row(
        children: [
          const PageBackButton(),
          const SizedBox(width: AppSpacing.xxs),
          Expanded(
            child: Semantics(
              header: true,
              label: '$symbol, ${l10n.instrumentName(symbol)}',
              excludeSemantics: true,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  MarketSymbolHero(symbol: symbol, style: context.textTheme.titleLarge!),
                  Text(l10n.instrumentName(symbol), style: context.textTheme.bodySmall),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// السعر الحي الكبير + تغيّر 24س + حالة التدفّق + شارة المحاكاة
class _PriceBlock extends ConsumerWidget {
  const _PriceBlock({required this.instrument});

  final Instrument instrument;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final quote = ref.watch(quoteProvider(instrument.symbol));
    final feed = ref.watch(feedStatusProvider);
    final simulated = ref.watch(marketDataRepositoryProvider).isSimulated;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (quote == null)
          const LoadingRegion(child: Skeleton(width: AppSpacing.huge * 4, height: AppSpacing.xxxl))
        else
          Semantics(
            liveRegion: false,
            label: '${instrument.format(quote.price)}, '
                '${DirectionText.semanticLabel(l10n, quote.changePercent)} ${l10n.change24h}',
            excludeSemantics: true,
            child: Wrap(
              crossAxisAlignment: WrapCrossAlignment.end,
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.xxs,
              children: [
                PriceFlash(
                  price: quote.price,
                  text: instrument.format(quote.price),
                  style: context.type.numHero,
                ),
                Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.xxs),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      DirectionText(value: quote.changePercent),
                      const SizedBox(width: AppSpacing.xxs),
                      Text(l10n.change24h, style: context.textTheme.labelSmall),
                    ],
                  ),
                ),
              ],
            ),
          ),
        const SizedBox(height: AppSpacing.xs),
        Wrap(
          spacing: AppSpacing.xs,
          runSpacing: AppSpacing.xs,
          children: [
            FeedStatusPill(status: feed),
            if (simulated) const SourceTag(SourceKind.demo),
          ],
        ),
      ],
    );
  }
}

/// الرسم: شريط الأدوات (النوع + المؤشرات)، الرسم نفسه، وشرائح الإطار
class _ChartCard extends ConsumerWidget {
  const _ChartCard({required this.instrument});

  final Instrument instrument;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final symbol = instrument.symbol;
    final view = ref.watch(marketViewModelProvider(symbol));
    final vm = ref.read(marketViewModelProvider(symbol).notifier);
    final candles = ref.watch(liveCandlesProvider((symbol, view.timeframe)));
    final shown = ref.watch(_shownReadProvider(symbol));
    final forecast = ref.watch(forecastViewModelProvider(symbol));

    return AppCard(
      padding: const EdgeInsets.fromLTRB(AppSpacing.sm, AppSpacing.sm, AppSpacing.xs, AppSpacing.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Wrap: بالخط الكبير زر المؤشرات بينزل لسطر تاني بدل ما يعصر أزرار النوع.
          // "Forecast" هون بس (مش بـ sheet المؤشرات): مخرجات نموذج، مش مؤشر
          Wrap(
            alignment: WrapAlignment.spaceBetween,
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: AppSpacing.xs,
            runSpacing: AppSpacing.xs,
            children: [
              SegmentedButton<ChartType>(
                showSelectedIcon: false,
                style: const ButtonStyle(tapTargetSize: MaterialTapTargetSize.padded),
                segments: [
                  ButtonSegment(
                    value: ChartType.candles,
                    icon: const Icon(Icons.candlestick_chart_outlined),
                    tooltip: l10n.chartCandles,
                  ),
                  ButtonSegment(
                    value: ChartType.line,
                    icon: const Icon(Icons.show_chart_rounded),
                    tooltip: l10n.chartLine,
                  ),
                  ButtonSegment(
                    value: ChartType.area,
                    icon: const Icon(Icons.area_chart_outlined),
                    tooltip: l10n.chartArea,
                  ),
                ],
                selected: {view.chartType},
                onSelectionChanged: (s) {
                  AppHaptics.selection();
                  vm.setChartType(s.first);
                },
              ),
              Wrap(
                spacing: AppSpacing.xs,
                runSpacing: AppSpacing.xs,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  ForecastToggle(symbol: symbol),
                  _IndicatorsButton(symbol: symbol, count: view.indicators.length),
                ],
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          AnimatedSwitcher(
            duration: context.motion(AppMotion.base),
            child: candles.when(
              skipLoadingOnRefresh: true,
              loading: () => const LoadingRegion(
                key: ValueKey('loading'),
                child: Skeleton(height: PriceChart.mainHeight, radius: AppRadii.card),
              ),
              // ارتفاع أدنى بدل ثابت: بالخط الكبير الرسالة بتطوّل الكرت بدل ما تفيض
              error: (_, __) => ConstrainedBox(
                key: const ValueKey('error'),
                constraints: const BoxConstraints(minHeight: PriceChart.mainHeight),
                child: Center(
                  child: ErrorState(
                    message: l10n.chartError,
                    onRetry: () => ref.invalidate(liveCandlesProvider((symbol, view.timeframe))),
                  ),
                ),
              ),
              data: (list) => list.isEmpty
                  ? ConstrainedBox(
                      key: const ValueKey('empty'),
                      constraints: const BoxConstraints(minHeight: PriceChart.mainHeight),
                      child: Center(
                        child: EmptyState(icon: Icons.candlestick_chart_outlined, title: l10n.chartEmpty),
                      ),
                    )
                  : PriceChart(
                      key: const ValueKey('chart'),
                      candles: list,
                      instrument: instrument,
                      timeframe: view.timeframe,
                      chartType: view.chartType,
                      indicators: view.indicators,
                      read: shown,
                      forecast: forecast is ForecastReady ? forecast.path : null,
                    ),
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          Semantics(
            label: l10n.timeframe,
            child: Wrap(
              spacing: AppSpacing.xs,
              runSpacing: AppSpacing.xs,
              children: [
                for (final tf in Timeframe.values)
                  ChoiceChip(
                    label: Text(tf.label, style: context.type.numSmall),
                    selected: view.timeframe == tf,
                    showCheckmark: false,
                    materialTapTargetSize: MaterialTapTargetSize.padded,
                    onSelected: (_) {
                      AppHaptics.selection();
                      vm.setTimeframe(tf);
                    },
                  ),
              ],
            ),
          ),
          // تحت شرائح الإطار: ظهوره ما بيزيح أدوات الرسم
          ForecastLegend(instrument: instrument),
        ],
      ),
    );
  }
}

class _IndicatorsButton extends StatelessWidget {
  const _IndicatorsButton({required this.symbol, required this.count});

  final String symbol;
  final int count;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return Semantics(
      container: true,
      button: true,
      label: count == 0 ? l10n.indicators : l10n.indicatorsCount('$count'),
      onTap: () => showIndicatorsSheet(context, symbol: symbol),
      excludeSemantics: true,
      child: TextButton.icon(
        style: TextButton.styleFrom(minimumSize: const Size(AppSizes.minTap, AppSizes.minTap)),
        onPressed: () => showIndicatorsSheet(context, symbol: symbol),
        icon: Badge(
          isLabelVisible: count > 0,
          label: Text('$count'),
          backgroundColor: context.colors.accent,
          textColor: context.colors.onAccent,
          child: const Icon(Icons.tune_rounded),
        ),
        label: Text(l10n.indicators),
      ),
    );
  }
}

/// الرأي المرسوم: يلي اختاره المستخدم من الشرائح؛ وإلا (والتوقّع شغّال) رأي
/// إطار الرسم، يعني نفس الإشارة يلي التوقّع مبني عليها، فالمناطق وخلاصة الرأي
/// والتوقّع ما بيتناقضوا؛ وإلا الأقوى
final _shownReadProvider = Provider.autoDispose.family<Opportunity?, String>((ref, symbol) {
  final read = ref.watch(modelReadProvider(symbol)).valueOrNull;
  final (picked, forecastOn, chartTimeframe) = ref.watch(
    marketViewModelProvider(symbol).select((s) => (s.readTimeframe, s.showForecast, s.timeframe)),
  );
  if (read == null) return null;
  final selected = picked ?? (forecastOn ? chartTimeframe : null);
  if (selected != null) {
    final list = ref.watch(opportunitiesProvider(symbol)).valueOrNull ?? const [];
    for (final o in list) {
      if (o.timeframe == selected && o.isDetected) return o;
    }
  }
  return read.best;
});

class _ModelReadCard extends ConsumerWidget {
  const _ModelReadCard({required this.instrument});

  final Instrument instrument;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final symbol = instrument.symbol;
    final opportunities = ref.watch(opportunitiesProvider(symbol));
    final shown = ref.watch(_shownReadProvider(symbol));
    final simulated = ref.watch(marketDataRepositoryProvider).isSimulated;

    return opportunities.when(
      skipLoadingOnRefresh: true,
      loading: () => const LoadingRegion(child: Skeleton(height: AppSpacing.huge * 4, radius: AppRadii.card)),
      error: (_, __) => AppCard(child: ErrorState(onRetry: () => ref.invalidate(opportunitiesProvider(symbol)))),
      data: (list) => SignalSummary(
        instrument: instrument,
        opportunities: list,
        shown: shown,
        agreeing: shown == null ? 0 : list.where((o) => o.isDetected && o.direction == shown.direction).length,
        simulated: simulated,
        onShowRead: (tf) {
          AppHaptics.selection();
          ref.read(marketViewModelProvider(symbol).notifier).showRead(tf);
        },
        onSizeTrade: (read) => showSizeTradeSheet(context, instrument: instrument, read: read),
        onRequestAnalysis: () => showRequestAnalysisSheet(context, symbol: symbol, timeframe: shown?.timeframe),
      ),
    );
  }
}
