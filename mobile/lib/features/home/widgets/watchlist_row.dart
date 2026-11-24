import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:syncfusion_flutter_charts/sparkcharts.dart';

import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/direction_badge.dart';
import '../../../core/widgets/direction_text.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../core/widgets/price_flash.dart';
import '../../../l10n/app_localizations.dart';
import '../../markets/data/market_providers.dart';
import '../../markets/models/market_models.dart';
import '../../markets/widgets/market_hero.dart';
import '../../signals/models/opportunity.dart';

/// صف أداة بقائمة المتابعة: الرمز + رأي النموذج | sparkline 24س | السعر + التغيّر
///
/// كل جزء بيقرأ provider خاص فيه (السعر، الرسم، الرأي)، فنبضة سعر بتعيد
/// بناء هالصف بس. الضغط بيفتح شاشة الأداة (Hero على الرمز).
class WatchlistRow extends ConsumerWidget {
  const WatchlistRow({super.key, required this.instrument, required this.onTap});

  /// ارتفاع الصف بالخط العادي (بيكبر مع الخط)
  static const double minHeight = 72;

  /// حجم الـ sparkline
  static const Size _spark = Size(64, 28);

  /// فوق هالحجم للخط الـ sparkline بيختفي حتى يضل مكان للأرقام
  static const double _sparkMaxTextScale = 1.4;

  final Instrument instrument;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;
    final symbol = instrument.symbol;
    // تبويب Home مخفي (IndexedStack) أو شاشة فوقه: TickerMode مطفي، فالصف
    // ما بيعيد البناء مع كل نبضة. لما يرجع يبيّن بيعيد البناء وبيرجع يتابع.
    final quote = TickerMode.valuesOf(context).enabled
        ? ref.watch(quoteProvider(symbol))
        : ref.read(quoteProvider(symbol));
    final read = ref.watch(modelReadProvider(symbol));
    final showSpark = MediaQuery.textScalerOf(context).scale(1) <= _sparkMaxTextScale;

    final readLabel = switch (read.valueOrNull?.best) {
      final Opportunity o => l10n.modelReadLabel(
          o.direction.label(l10n),
          Formatters.percent(o.probability),
          o.timeframe.label,
        ),
      null when read.hasValue => l10n.noSetupLabel,
      null => '',
    };
    final semantics = [
      symbol,
      l10n.instrumentName(symbol),
      if (quote != null) ...[
        instrument.format(quote.price),
        DirectionText.semanticLabel(l10n, quote.changePercent),
      ],
      if (readLabel.isNotEmpty) readLabel,
    ].join(', ');

    return Semantics(
      container: true,
      button: true,
      label: semantics,
      hint: l10n.openChartHint,
      onTap: onTap,
      excludeSemantics: true,
      child: InkWell(
        onTap: onTap,
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: minHeight),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      MarketSymbolHero(symbol: symbol, style: text.titleSmall!),
                      const SizedBox(height: AppSpacing.xxs),
                      _ModelReadLine(read: read),
                    ],
                  ),
                ),
                if (showSpark) ...[
                  const SizedBox(width: AppSpacing.sm),
                  SizedBox.fromSize(size: _spark, child: _Sparkline(symbol: symbol)),
                ],
                const SizedBox(width: AppSpacing.sm),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (quote == null)
                      const Skeleton(width: AppSpacing.huge * 1.5)
                    else
                      PriceFlash(
                        price: quote.price,
                        text: instrument.format(quote.price),
                        style: context.type.num.copyWith(color: c.fg),
                      ),
                    const SizedBox(height: AppSpacing.xxs),
                    if (quote != null)
                      DirectionText(value: quote.changePercent, style: context.type.numSmall),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// "↑ Long 72% · 1h" (الاتجاه بلونه + سهم، الاحتمال بنفسجي = مخرجات النموذج)
class _ModelReadLine extends StatelessWidget {
  const _ModelReadLine({required this.read});

  final AsyncValue<ModelRead> read;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final style = context.textTheme.labelMedium!;
    return read.when(
      skipLoadingOnRefresh: true,
      loading: () => const Skeleton(width: AppSpacing.huge * 2, height: AppSpacing.sm),
      error: (_, __) => const SizedBox.shrink(),
      data: (r) {
        final best = r.best;
        if (best == null) return Text(l10n.noSetup, style: style.copyWith(color: c.fg3));
        final up = best.direction == SignalDirection.long;
        final dirColor = up ? c.up : c.down;
        return Text.rich(
          TextSpan(children: [
            WidgetSpan(
              alignment: PlaceholderAlignment.middle,
              child: Icon(
                up ? Icons.arrow_upward_rounded : Icons.arrow_downward_rounded,
                size: AppSizes.iconSm - 2,
                color: dirColor,
              ),
            ),
            TextSpan(text: ' ${best.direction.label(l10n)} ', style: style.copyWith(color: dirColor)),
            TextSpan(
              text: Formatters.percent(best.probability),
              style: context.type.numSmall.copyWith(color: c.forecast),
            ),
            TextSpan(text: ' · ${best.timeframe.label}', style: style.copyWith(color: c.fg3)),
          ]),
        );
      },
    );
  }
}

/// sparkline آخر 24 ساعة - لونه حسب اتجاه الفترة (والتغيّر بسهم جنبه)
class _Sparkline extends ConsumerWidget {
  const _Sparkline({required this.symbol});

  final String symbol;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    return ExcludeSemantics(
      child: ref.watch(sparklineProvider(symbol)).when(
            skipLoadingOnRefresh: true,
            loading: () => const Skeleton(radius: AppRadii.badge),
            error: (_, __) => const SizedBox.shrink(),
            data: (closes) => closes.length < 2
                ? const SizedBox.shrink()
                : RepaintBoundary(
                    child: SfSparkLineChart(
                      data: closes,
                      width: 1.5,
                      color: closes.last >= closes.first ? c.up : c.down,
                      axisLineWidth: 0,
                    ),
                  ),
          ),
    );
  }
}
