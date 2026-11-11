import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:syncfusion_flutter_charts/charts.dart';

import '../../../core/theme/theme_context.dart';
import '../../../l10n/app_localizations.dart';
import '../models/backtest.dart';

/// "+1.5 R" / "−3.0 R" / "0.0 R" (الأرقام دايمًا LTR)
String formatR(AppLocalizations l10n, double r, {bool signed = true}) {
  final sign = !signed || r == 0 ? '' : (r > 0 ? '+' : '−');
  return l10n.backtestR('$sign${r.abs().toStringAsFixed(1)}');
}

/// منحنى النتيجة بوحدات R (Syncfusion، بنفس شكل `AccuracyChart` بـ Insights:
/// نفس الشبكة والمحاور والـ trackball). نقطة لكل يوم فيه إشارات، أولها 0؛ لو
/// كتار (فترات بالسنين) بينرسم [downsampleEquity] منها (أول وآخر وأدنى وأعلى
/// بيضلوا). الملخص الصوتي من النقاط كاملة. بالسنين المحور بيبيّن السنة.
///
/// لون محايد (مش صعود / هبوط: هاد مش اتجاه). الحركة بس لما تجي نتيجة جديدة
/// (350ms)، ومع تقليل الحركة بدون حركة. الضغط على نقطة بيبيّن مجموعها وعدد إشاراتها.
class EquityChart extends StatelessWidget {
  const EquityChart({super.key, required this.result});

  final BacktestResult result;

  static const double height = 200;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final all = result.equity;
    if (all.length < 2) return const SizedBox.shrink();
    final points = downsampleEquity(all);
    final years = result.period.isMultiYear;

    final values = [for (final p in all) p.r];
    final low = values.reduce(math.min);
    final high = values.reduce(math.max);
    final labelStyle = context.textTheme.labelSmall;
    final dates = MaterialLocalizations.of(context);
    return Semantics(
      label: l10n.backtestEquityLabel(
        '${result.signals}',
        formatR(l10n, all.last.r),
        formatR(l10n, low),
        formatR(l10n, high),
      ),
      child: RepaintBoundary(
        child: SizedBox(
          height: height,
          child: SfCartesianChart(
            // نتيجة جديدة = رسم جديد بحركته
            key: ObjectKey(result),
            plotAreaBorderWidth: 0,
            margin: EdgeInsets.zero,
            trackballBehavior: _trackball(context, points),
            primaryXAxis: DateTimeAxis(
              majorGridLines: const MajorGridLines(width: 0),
              axisLine: AxisLine(width: 0.5, color: c.chart.grid),
              majorTickLines: const MajorTickLines(size: 0),
              edgeLabelPlacement: EdgeLabelPlacement.shift,
              labelStyle: labelStyle,
              intervalType: years ? DateTimeIntervalType.years : DateTimeIntervalType.auto,
              interval: years ? 1 : null,
              axisLabelFormatter: (d) {
                final date = DateTime.fromMillisecondsSinceEpoch(d.value.toInt(), isUtc: true);
                return ChartAxisLabel(years ? '${date.year}' : dates.formatShortMonthDay(date), labelStyle);
              },
            ),
            primaryYAxis: NumericAxis(
              opposedPosition: true,
              majorGridLines: MajorGridLines(width: 0.5, color: c.chart.grid),
              axisLine: const AxisLine(width: 0),
              majorTickLines: const MajorTickLines(size: 0),
              // خط الصفر (نقطة البداية) أوضح من باقي الشبكة
              plotBands: [PlotBand(start: 0, end: 0, borderWidth: 1, borderColor: c.chart.crosshair)],
              axisLabelFormatter: (d) => ChartAxisLabel(formatR(l10n, d.value.toDouble()), context.type.numSmall),
            ),
            series: [
              LineSeries<EquityPoint, DateTime>(
                dataSource: points,
                xValueMapper: (p, _) => p.time,
                yValueMapper: (p, _) => p.r,
                color: c.fg,
                width: 2,
                animationDuration: context.reduceMotion ? 0 : 350,
              ),
            ],
          ),
        ),
      ),
    );
  }

  TrackballBehavior _trackball(BuildContext context, List<EquityPoint> points) {
    final c = context.colors;
    return TrackballBehavior(
      enable: true,
      activationMode: ActivationMode.singleTap,
      lineColor: c.chart.crosshair,
      lineDashArray: const [4, 4],
      builder: (context, details) {
        final index = details.pointIndex;
        if (index == null || index < 0 || index >= points.length) return const SizedBox.shrink();
        return _PointReadout(point: points[index], withYear: result.period.isMultiYear);
      },
    );
  }
}

/// قراءة نقطة: اليوم (مع السنة بالفترات الطويلة) + المجموع + عدد الإشارات لحدّه
class _PointReadout extends StatelessWidget {
  const _PointReadout({required this.point, required this.withYear});

  final EquityPoint point;
  final bool withYear;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
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
            Text(
              withYear
                  ? MaterialLocalizations.of(context).formatShortDate(point.time)
                  : MaterialLocalizations.of(context).formatShortMonthDay(point.time),
              style: context.textTheme.labelSmall,
            ),
            Text(
              l10n.backtestEquityPoint(formatR(l10n, point.r), '${point.signals}'),
              style: context.type.numSmall.copyWith(color: c.fg),
            ),
          ],
        ),
      ),
    );
  }
}
