import 'package:flutter/material.dart';

import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_card.dart';
import '../../../l10n/app_localizations.dart';
import '../../insights/models/track_record.dart';
import '../models/backtest.dart';
import 'equity_chart.dart';

/// الأرقام الأربعة: عدد الإشارات، نسبة الإصابة، متوسط العائد : المخاطرة، أقصى
/// تراجع - كل رقم وتحته عيّنته. عمودين على الشاشة العادية، عمود واحد مع خط كبير.
class BacktestFigures extends StatelessWidget {
  const BacktestFigures({super.key, required this.result});

  final BacktestResult result;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final count = '${result.signals}';
    final small = result.accuracy.isSmallSample;
    String withSample(String caption) => small ? '$caption · ${l10n.insightsSmallSample}' : caption;

    final figures = [
      _Figure(name: l10n.backtestSignals, value: count, caption: withSample(l10n.backtestSignalsCaption)),
      _Figure(
        name: l10n.backtestHitRate,
        value: Formatters.percent(result.accuracy.hitRate ?? 0),
        caption: withSample(l10n.backtestHitRateCaption('${result.hits}', count)),
      ),
      _Figure(
        name: l10n.backtestAvgRiskReward,
        value: '1 : ${(result.avgRiskReward ?? 0).toStringAsFixed(1)}',
        caption: withSample(l10n.backtestAvgRiskRewardCaption(count)),
      ),
      _Figure(
        name: l10n.backtestMaxDrawdown,
        value: formatR(l10n, -result.maxDrawdown, signed: result.maxDrawdown > 0),
        caption: withSample(l10n.backtestMaxDrawdownCaption(count)),
      ),
    ];

    return LayoutBuilder(
      builder: (context, constraints) {
        // خط كبير أو شاشة ضيقة → عمود واحد (ولا رقم بينقص)
        final twoColumns = MediaQuery.textScalerOf(context).scale(1) <= 1.3 && constraints.maxWidth >= 300;
        final width = twoColumns ? (constraints.maxWidth - AppSpacing.sm) / 2 : constraints.maxWidth;
        return Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: [for (final figure in figures) SizedBox(width: width, child: figure)],
        );
      },
    );
  }
}

class _Figure extends StatelessWidget {
  const _Figure({required this.name, required this.value, required this.caption});

  final String name;
  final String value;
  final String caption;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    return AppCard(
      child: Semantics(
        container: true,
        excludeSemantics: true,
        label: l10n.backtestFigureLabel(name, value, caption),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(name, style: context.textTheme.labelMedium!.copyWith(color: c.fg2)),
            const SizedBox(height: AppSpacing.xxs),
            Text(value, style: context.type.numLarge.copyWith(color: c.fg), textDirection: TextDirection.ltr),
            const SizedBox(height: AppSpacing.xxs),
            Text(caption, style: context.textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}
