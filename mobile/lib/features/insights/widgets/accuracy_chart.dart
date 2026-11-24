import 'package:flutter/material.dart';
import 'package:syncfusion_flutter_charts/charts.dart';

import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../l10n/app_localizations.dart';
import '../models/track_record.dart';
import 'period_chips.dart';

/// نسبة الإصابة عبر الزمن (Syncfusion، بنفس شكل [PriceChart]: نفس الشبكة
/// والمحاور والـ trackball). نقطة لكل مدة؛ مدة بدون نتائج = فجوة (مش 0%).
///
/// الحركة بس لما تتغيّر الفترة (350ms)، ومع تقليل الحركة بدون حركة.
/// الضغط على نقطة بيبيّن نسبتها وعدد إشاراتها.
class AccuracyChart extends StatelessWidget {
  const AccuracyChart({super.key, required this.record});

  final TrackRecord record;

  static const double height = 200;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final rates = [for (final p in record.series) if (p.accuracy.hitRate case final r?) r];
    final period = record.period.label(l10n);

    if (rates.isEmpty) {
      return SizedBox(
        height: AccuracyChart.height / 2,
        child: Center(child: Text(l10n.insightsChartNoPoints, style: context.textTheme.bodySmall, textAlign: TextAlign.center)),
      );
    }

    rates.sort();
    final labelStyle = context.textTheme.labelSmall;
    final dates = MaterialLocalizations.of(context);
    return Semantics(
      label: l10n.insightsChartLabel(period, Formatters.percent(rates.first), Formatters.percent(rates.last)),
      child: RepaintBoundary(
        child: SizedBox(
          height: AccuracyChart.height,
          child: SfCartesianChart(
            // فترة جديدة = رسم جديد بحركته؛ نفس الفترة ما بتعيد الحركة
            key: ValueKey(record.period),
            plotAreaBorderWidth: 0,
            margin: EdgeInsets.zero,
            trackballBehavior: _trackball(context),
            primaryXAxis: DateTimeAxis(
              majorGridLines: const MajorGridLines(width: 0),
              axisLine: AxisLine(width: 0.5, color: c.chart.grid),
              majorTickLines: const MajorTickLines(size: 0),
              edgeLabelPlacement: EdgeLabelPlacement.shift,
              labelStyle: labelStyle,
              axisLabelFormatter: (d) => ChartAxisLabel(
                dates.formatShortMonthDay(DateTime.fromMillisecondsSinceEpoch(d.value.toInt(), isUtc: true)),
                labelStyle,
              ),
            ),
            primaryYAxis: NumericAxis(
              minimum: 0,
              maximum: 100,
              interval: 25,
              opposedPosition: true,
              majorGridLines: MajorGridLines(width: 0.5, color: c.chart.grid),
              axisLine: const AxisLine(width: 0),
              majorTickLines: const MajorTickLines(size: 0),
              axisLabelFormatter: (d) => ChartAxisLabel('${d.value.toInt()}%', context.type.numSmall),
            ),
            series: [
              LineSeries<AccuracyPoint, DateTime>(
                dataSource: record.series,
                xValueMapper: (p, _) => p.start,
                yValueMapper: (p, _) => p.accuracy.hitRate == null ? null : p.accuracy.hitRate! * 100,
                emptyPointSettings: const EmptyPointSettings(mode: EmptyPointMode.gap),
                color: c.fg,
                width: 2,
                markerSettings: MarkerSettings(
                  isVisible: true,
                  height: 6,
                  width: 6,
                  color: c.card,
                  borderColor: c.fg,
                  borderWidth: 2,
                ),
                animationDuration: context.reduceMotion ? 0 : 350,
              ),
            ],
          ),
        ),
      ),
    );
  }

  TrackballBehavior _trackball(BuildContext context) {
    final c = context.colors;
    return TrackballBehavior(
      enable: true,
      activationMode: ActivationMode.singleTap,
      lineColor: c.chart.crosshair,
      lineDashArray: const [4, 4],
      builder: (context, details) {
        final index = details.pointIndex;
        final series = record.series;
        if (index == null || index < 0 || index >= series.length) return const SizedBox.shrink();
        return _PointReadout(point: series[index]);
      },
    );
  }
}

/// قراءة نقطة: المدة + النسبة + عدد الإشارات
class _PointReadout extends StatelessWidget {
  const _PointReadout({required this.point});

  final AccuracyPoint point;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final dates = MaterialLocalizations.of(context);
    final range = point.days == 1
        ? dates.formatShortMonthDay(point.start)
        : '${dates.formatShortMonthDay(point.start)} – ${dates.formatShortMonthDay(point.end)}';
    final rate = point.accuracy.hitRate;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: c.raised,
        borderRadius: AppRadii.card,
        border: Border.all(color: c.lineStrong),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xs),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(range, style: context.textTheme.labelSmall),
            Text(
              l10n.insightsChartPoint(rate == null ? '—' : Formatters.percent(rate), '${point.accuracy.resolved}'),
              style: context.type.numSmall.copyWith(color: c.fg),
            ),
          ],
        ),
      ),
    );
  }
}
