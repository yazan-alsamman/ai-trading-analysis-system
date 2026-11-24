import 'package:flutter/material.dart';
import 'package:syncfusion_flutter_charts/charts.dart';

import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/direction_text.dart';
import '../../../l10n/app_localizations.dart';
import '../../forecast/models/forecast_path.dart';
import '../../forecast/widgets/forecast_legend.dart';
import '../../signals/models/opportunity.dart';
import '../models/market_models.dart';
import '../view_models/market_view_model.dart';

/// رسم الأسعار (Syncfusion): شموع / خط / مساحة + المؤشرات + مناطق النموذج.
///
/// - السحب أفقيًا للتاريخ، القرص للتكبير، والضغط المطوّل لقراءة شمعة.
/// - الحركة بتصير بس لما يتغيّر الإطار أو النوع (350ms)؛ النبضات الحيّة
///   بتحدّث آخر شمعة بدون حركة.
/// - RSI و MACD بلوحات تحت الرسم ومحاذاة محورها مع الرسم الرئيسي.
/// - توقّع النموذج ([forecast]): خط متقطّع بنفسجي على المسار المتوقّع + نطاق
///   ناعم (low / high) من آخر شمعة، بيلحق آخر شمعة مع النبضات بدون طلب
///   ([ForecastPath.followFrom])، بدون حركة رسم، والقراءة بالضغط المطوّل بتقراه.
class PriceChart extends StatefulWidget {
  const PriceChart({
    super.key,
    required this.candles,
    required this.instrument,
    required this.timeframe,
    required this.chartType,
    required this.indicators,
    this.read,
    this.forecast,
    this.height = mainHeight,
    this.animated = true,
  });

  final List<Candle> candles;
  final Instrument instrument;
  final Timeframe timeframe;
  final ChartType chartType;
  final Set<ChartIndicator> indicators;

  /// رأي النموذج المرسوم (مناطق) - null = بدون مناطق
  final Opportunity? read;

  /// توقّع النموذج المرسوم بعد آخر شمعة - null = بدون توقّع
  final ForecastPath? forecast;

  /// ارتفاع الرسم الرئيسي ([compactHeight] بتفاصيل الإشارة)
  final double height;

  /// H5b: false = ولا حركة (Low data mode)، متل "إزالة الحركة"
  final bool animated;

  static const double mainHeight = 300;
  static const double compactHeight = 220;
  static const double oscillatorHeight = 110;

  /// كم شمعة بتبيّن بأول فتحة (الباقي بالسحب)
  static const int visibleCandles = 80;

  @override
  State<PriceChart> createState() => _PriceChartState();
}

class _PriceChartState extends State<PriceChart> {
  late final ZoomPanBehavior _zoom = ZoomPanBehavior(
    enablePinching: true,
    enablePanning: true,
    zoomMode: ZoomMode.x,
  );
  final Map<ChartIndicator, DateTimeAxisController> _oscillatorAxes = {};
  bool _animate = true;

  /// فهرس الشموع بالوقت - للقراءة بالضغط المطوّل بس، فبينبنى أول ما ينطلب
  /// (مش مع كل نبضة)
  Map<int, Candle>? _byTimeCache;
  Map<int, Candle> get _byTime =>
      _byTimeCache ??= {for (final c in widget.candles) c.time.millisecondsSinceEpoch: c};

  /// نقاط التوقّع من آخر شمعة: بتنحسب من جديد بس لما يتغيّر التوقّع أو آخر شمعة
  /// (≤ 11 نقطة)، وفهرسها بالوقت للقراءة بالضغط المطوّل
  (ForecastPath, DateTime, double)? _forecastKey;
  List<ForecastPoint> _forecastCache = const [];
  Map<int, ForecastPoint>? _forecastByTimeCache;

  List<ForecastPoint> get _forecastPoints {
    final forecast = widget.forecast;
    if (forecast == null || widget.candles.isEmpty) return const [];
    final last = widget.candles.last;
    final key = (forecast, last.time, last.close);
    if (_forecastKey != key) {
      _forecastKey = key;
      _forecastCache = forecast.followFrom(last.time, last.close);
      _forecastByTimeCache = null;
    }
    return _forecastCache;
  }

  Map<int, ForecastPoint> get _forecastByTime => _forecastByTimeCache ??= {
        // أول نقطة = آخر شمعة نفسها (قراءتها قراءة الشمعة)
        for (final p in _forecastPoints.skip(1)) p.time.millisecondsSinceEpoch: p,
      };

  /// نفس الـ instance بين النبضات (instance جديد كل build كان يصفّر القراءة المفتوحة)
  late TrackballBehavior _trackballBehavior;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _trackballBehavior = _trackball(context);
  }

  @override
  void didUpdateWidget(PriceChart old) {
    super.didUpdateWidget(old);
    if (old.timeframe != widget.timeframe || old.chartType != widget.chartType) {
      _animate = true;
      _oscillatorAxes.clear();
    }
    if (!identical(old.candles, widget.candles)) _byTimeCache = null;
  }

  int get _animationMs => !_animate || !widget.animated || context.reduceMotion ? 0 : 350;

  /// اللوحات تحت الرسم بتلحق مدى المحور الأفقي للرسم الرئيسي
  void _syncOscillators(ActualRangeChangedArgs args) {
    if (args.orientation != AxisOrientation.horizontal || _oscillatorAxes.isEmpty) return;
    final min = args.visibleMin;
    final max = args.visibleMax;
    if (min is! num || max is! num) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      for (final axis in _oscillatorAxes.values) {
        axis
          ..visibleMinimum = DateTime.fromMillisecondsSinceEpoch(min.toInt(), isUtc: true)
          ..visibleMaximum = DateTime.fromMillisecondsSinceEpoch(max.toInt(), isUtc: true);
      }
    });
  }

  (DateTimeIntervalType, int) get _autoScroll => switch (widget.timeframe) {
        Timeframe.d1 => (DateTimeIntervalType.days, PriceChart.visibleCandles),
        final tf => (DateTimeIntervalType.minutes, PriceChart.visibleCandles * tf.duration.inMinutes),
      };

  DateTimeAxis _xAxis({required bool visible, ValueChanged<DateTimeAxisController>? onCreated}) {
    final c = context.colors;
    final (type, delta) = _autoScroll;
    return DateTimeAxis(
      isVisible: visible,
      autoScrollingDelta: delta,
      autoScrollingDeltaType: type,
      autoScrollingMode: AutoScrollingMode.end,
      majorGridLines: MajorGridLines(width: 0.5, color: c.chart.grid),
      axisLine: const AxisLine(width: 0),
      majorTickLines: const MajorTickLines(size: 0),
      edgeLabelPlacement: EdgeLabelPlacement.shift,
      labelStyle: context.textTheme.labelSmall,
      onRendererCreated: onCreated,
    );
  }

  /// ملخّص نصي للرسم (للقارئ الصوتي): آخر سعر + التغيّر بكلمة الاتجاه + أعلى/أدنى
  /// على الشموع الظاهرة
  String _summary(AppLocalizations l10n) {
    final candles = widget.candles;
    if (candles.isEmpty) return '';
    final visible = candles.length > PriceChart.visibleCandles
        ? candles.sublist(candles.length - PriceChart.visibleCandles)
        : candles;
    final first = visible.first.open;
    final last = visible.last.close;
    var high = visible.first.high, low = visible.first.low;
    for (final c in visible) {
      if (c.high > high) high = c.high;
      if (c.low < low) low = c.low;
    }
    final format = widget.instrument.format;
    final chart = l10n.chartLabel(
      widget.instrument.symbol,
      widget.timeframe.label,
      format(last),
      DirectionText.semanticLabel(l10n, first == 0 ? 0 : (last - first) / first * 100),
      format(high),
      format(low),
    );
    final forecast = widget.forecast;
    final points = _forecastPoints;
    if (forecast == null || points.isEmpty) return chart;
    return '$chart ${forecastSummary(context, forecast, widget.instrument, level: points.last.expected)}';
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final precision = widget.instrument.precision;
    final oscillators = [for (final i in ChartIndicator.values) if (i.isOscillator && widget.indicators.contains(i)) i];
    final animationMs = _animationMs;
    // بعد أول رسم، النبضات ما بتعيد الحركة
    if (_animate) WidgetsBinding.instance.addPostFrameCallback((_) => _animate = false);

    return Semantics(
      label: _summary(l10n),
      child: RepaintBoundary(
        child: Column(
          children: [
            SizedBox(
              height: widget.height,
              child: SfCartesianChart(
                key: ValueKey((widget.timeframe, widget.chartType)),
                plotAreaBorderWidth: 0,
                margin: EdgeInsets.zero,
                zoomPanBehavior: _zoom,
                trackballBehavior: _trackballBehavior,
                onActualRangeChanged: _syncOscillators,
                primaryXAxis: _xAxis(visible: oscillators.isEmpty),
                primaryYAxis: NumericAxis(
                  opposedPosition: true,
                  anchorRangeToVisiblePoints: true,
                  majorGridLines: MajorGridLines(width: 0.5, color: c.chart.grid),
                  axisLine: const AxisLine(width: 0),
                  majorTickLines: const MajorTickLines(size: 0),
                  labelStyle: context.type.numSmall,
                  axisLabelFormatter: (d) =>
                      ChartAxisLabel(d.value.toStringAsFixed(precision), context.type.numSmall),
                  plotBands: _zones(context),
                ),
                series: <CartesianSeries<dynamic, DateTime>>[
                  _series(context, animationMs),
                  ..._forecastSeries(context),
                ],
                indicators: _overlayIndicators(context, animationMs),
              ),
            ),
            for (final indicator in oscillators)
              SizedBox(
                height: PriceChart.oscillatorHeight,
                child: _oscillator(context, indicator, isLast: indicator == oscillators.last),
              ),
          ],
        ),
      ),
    );
  }

  CartesianSeries<Candle, DateTime> _series(BuildContext context, int animationMs) {
    final c = context.colors;
    final candles = widget.candles;
    DateTime x(Candle k, int _) => k.time;
    return switch (widget.chartType) {
      ChartType.candles => CandleSeries<Candle, DateTime>(
          dataSource: candles,
          xValueMapper: x,
          openValueMapper: (k, _) => k.open,
          highValueMapper: (k, _) => k.high,
          lowValueMapper: (k, _) => k.low,
          closeValueMapper: (k, _) => k.close,
          bullColor: c.up,
          bearColor: c.down,
          // صاعدة مفرّغة وهابطة معبّاة: الاتجاه بالشكل كمان، مش باللون بس
          enableSolidCandles: false,
          animationDuration: animationMs.toDouble(),
          name: widget.instrument.symbol,
        ),
      ChartType.line => LineSeries<Candle, DateTime>(
          dataSource: candles,
          xValueMapper: x,
          yValueMapper: (k, _) => k.close,
          color: c.fg,
          width: 1.5,
          animationDuration: animationMs.toDouble(),
          name: widget.instrument.symbol,
        ),
      ChartType.area => AreaSeries<Candle, DateTime>(
          dataSource: candles,
          xValueMapper: x,
          yValueMapper: (k, _) => k.close,
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [c.fg.withValues(alpha: 0.18), c.fg.withValues(alpha: 0)],
          ),
          borderColor: c.fg,
          borderWidth: 1.5,
          animationDuration: animationMs.toDouble(),
          name: widget.instrument.symbol,
        ),
    };
  }

  /// التوقّع: نطاق ناعم + خط متقطّع (الشكل مش اللون بس). بدون حركة رسم أبدًا
  /// (ما بيعيد يرسم نفسه مع النبضات، ومع تقليل الحركة كمان).
  List<CartesianSeries<ForecastPoint, DateTime>> _forecastSeries(BuildContext context) {
    final points = _forecastPoints;
    if (points.length < 2) return const [];
    final c = context.colors;
    DateTime x(ForecastPoint p, int _) => p.time;
    return [
      RangeAreaSeries<ForecastPoint, DateTime>(
        key: const ValueKey('forecast-band'),
        dataSource: points,
        xValueMapper: x,
        highValueMapper: (p, _) => p.high,
        lowValueMapper: (p, _) => p.low,
        color: c.chart.forecastRegion,
        borderWidth: 0,
        animationDuration: 0,
        name: 'forecast-band',
      ),
      LineSeries<ForecastPoint, DateTime>(
        key: const ValueKey('forecast-line'),
        dataSource: points,
        xValueMapper: x,
        yValueMapper: (p, _) => p.expected,
        color: c.forecast,
        width: 2,
        dashArray: const [6, 4],
        animationDuration: 0,
        name: 'forecast',
      ),
    ];
  }

  List<TechnicalIndicator<Candle, DateTime>> _overlayIndicators(BuildContext context, int animationMs) {
    final chart = context.colors.chart;
    final data = widget.candles;
    final on = widget.indicators;
    DateTime x(Candle k, int _) => k.time;
    num close(Candle k, int _) => k.close;
    return [
      if (on.contains(ChartIndicator.sma))
        SmaIndicator<Candle, DateTime>(
          dataSource: data,
          xValueMapper: x,
          closeValueMapper: close,
          period: 20,
          signalLineColor: chart.indicator1,
          signalLineWidth: 1.5,
          animationDuration: animationMs.toDouble(),
        ),
      if (on.contains(ChartIndicator.ema))
        EmaIndicator<Candle, DateTime>(
          dataSource: data,
          xValueMapper: x,
          closeValueMapper: close,
          period: 50,
          signalLineColor: chart.indicator2,
          signalLineWidth: 1.5,
          animationDuration: animationMs.toDouble(),
        ),
      if (on.contains(ChartIndicator.bollinger))
        BollingerBandIndicator<Candle, DateTime>(
          dataSource: data,
          xValueMapper: x,
          closeValueMapper: close,
          period: 20,
          standardDeviation: 2,
          signalLineColor: chart.indicator3,
          signalLineWidth: 1,
          upperLineColor: chart.indicator3,
          upperLineWidth: 1,
          lowerLineColor: chart.indicator3,
          lowerLineWidth: 1,
          bandColor: chart.indicator3.withValues(alpha: 0.08),
          animationDuration: animationMs.toDouble(),
        ),
    ];
  }

  Widget _oscillator(BuildContext context, ChartIndicator indicator, {required bool isLast}) {
    final c = context.colors;
    final data = widget.candles;
    DateTime x(Candle k, int _) => k.time;
    num close(Candle k, int _) => k.close;
    final technical = switch (indicator) {
      ChartIndicator.rsi => RsiIndicator<Candle, DateTime>(
          dataSource: data,
          xValueMapper: x,
          closeValueMapper: close,
          highValueMapper: (k, _) => k.high,
          lowValueMapper: (k, _) => k.low,
          period: 14,
          overbought: 70,
          oversold: 30,
          signalLineColor: c.chart.indicator1,
          signalLineWidth: 1.5,
          upperLineColor: c.chart.crosshair,
          upperLineWidth: 1,
          lowerLineColor: c.chart.crosshair,
          lowerLineWidth: 1,
          animationDuration: 0,
        ) as TechnicalIndicator<Candle, DateTime>,
      _ => MacdIndicator<Candle, DateTime>(
          dataSource: data,
          xValueMapper: x,
          closeValueMapper: close,
          shortPeriod: 12,
          longPeriod: 26,
          period: 9,
          macdLineColor: c.chart.indicator1,
          macdLineWidth: 1.5,
          signalLineColor: c.chart.indicator2,
          signalLineWidth: 1.5,
          histogramPositiveColor: c.up.withValues(alpha: 0.5),
          histogramNegativeColor: c.down.withValues(alpha: 0.5),
          animationDuration: 0,
        ),
    };
    return Stack(
      children: [
        SfCartesianChart(
          key: ValueKey((indicator, widget.timeframe, widget.chartType)),
          plotAreaBorderWidth: 0,
          margin: const EdgeInsets.only(top: AppSpacing.xs),
          primaryXAxis: _xAxis(
            visible: isLast,
            onCreated: (controller) => _oscillatorAxes[indicator] = controller,
          ),
          primaryYAxis: NumericAxis(
            opposedPosition: true,
            majorGridLines: MajorGridLines(width: 0.5, color: c.chart.grid),
            axisLine: const AxisLine(width: 0),
            majorTickLines: const MajorTickLines(size: 0),
            labelStyle: context.type.numSmall,
            minimum: indicator == ChartIndicator.rsi ? 0 : null,
            maximum: indicator == ChartIndicator.rsi ? 100 : null,
            interval: indicator == ChartIndicator.rsi ? 50 : null,
            axisLabelFormatter: indicator == ChartIndicator.macd
                ? (d) => ChartAxisLabel(d.value.toStringAsFixed(widget.instrument.precision), context.type.numSmall)
                : null,
          ),
          // سلسلة مخفية على محور مخفي: بتعطي المحور الأفقي مداه بدون ما تأثر بالرأسي
          axes: const [NumericAxis(name: 'hidden', isVisible: false)],
          series: [
            LineSeries<Candle, DateTime>(
              dataSource: data,
              xValueMapper: x,
              yValueMapper: (k, _) => k.close,
              yAxisName: 'hidden',
              width: 0,
              color: Colors.transparent,
              enableTooltip: false,
              enableTrackball: false,
              animationDuration: 0,
            ),
          ],
          indicators: [technical],
        ),
        PositionedDirectional(
          start: AppSpacing.xs,
          top: AppSpacing.xs,
          child: Text(
            indicator == ChartIndicator.rsi ? 'RSI 14' : 'MACD 12 26 9',
            style: context.textTheme.labelSmall,
          ),
        ),
      ],
    );
  }

  List<PlotBand> _zones(BuildContext context) {
    final read = widget.read;
    if (read == null) return const [];
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    PlotBand band(PriceZone z, Color fill, Color text, String label) => PlotBand(
          start: z.low,
          end: z.high,
          color: fill,
          borderColor: text.withValues(alpha: 0.5),
          borderWidth: 1,
          text: label,
          textStyle: context.textTheme.labelSmall!.copyWith(color: text),
          horizontalTextAlignment: TextAnchor.start,
          verticalTextAlignment: TextAnchor.middle,
        );
    return [
      band(read.takeProfitZone, c.chart.zoneTarget, c.up, l10n.zoneTarget),
      band(read.entryZone, c.chart.zoneEntry, c.accent, l10n.zoneEntry),
      band(read.stopLossZone, c.chart.zoneStop, c.down, l10n.zoneStop),
    ];
  }

  TrackballBehavior _trackball(BuildContext context) {
    final c = context.colors;
    return TrackballBehavior(
      enable: true,
      activationMode: ActivationMode.longPress,
      tooltipDisplayMode: TrackballDisplayMode.groupAllPoints,
      lineColor: c.chart.crosshair,
      lineDashArray: const [4, 4],
      builder: (context, details) {
        final x = details.groupingModeInfo?.points.firstOrNull?.x ?? details.point?.x;
        if (x is! DateTime) return const SizedBox.shrink();
        final candle = _byTime[x.millisecondsSinceEpoch];
        if (candle != null) return _CandleReadout(candle: candle, instrument: widget.instrument);
        // بعد آخر شمعة: قراءة التوقّع (المتوقّع + النطاق)
        final point = _forecastByTime[x.millisecondsSinceEpoch];
        return point == null ? const SizedBox.shrink() : _ForecastReadout(point: point, instrument: widget.instrument);
      },
    );
  }
}

/// قراءة شمعة (الضغط المطوّل): الوقت + O/H/L/C بالتسميات المترجمة
class _CandleReadout extends StatelessWidget {
  const _CandleReadout({required this.candle, required this.instrument});

  final Candle candle;
  final Instrument instrument;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final local = candle.time.toLocal();
    final when = '${MaterialLocalizations.of(context).formatShortDate(local)} ${Formatters.clock(local)}';
    Widget row(String label, double value) => Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('$label ', style: context.textTheme.labelSmall),
            Text(instrument.format(value), style: context.type.numSmall.copyWith(color: c.fg)),
          ],
        );
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
            Text(when, style: context.textTheme.labelSmall),
            row(l10n.ohlcOpen, candle.open),
            row(l10n.ohlcHigh, candle.high),
            row(l10n.ohlcLow, candle.low),
            row(l10n.ohlcClose, candle.close),
          ],
        ),
      ),
    );
  }
}

/// قراءة نقطة من التوقّع (الضغط المطوّل بعد آخر شمعة): الوقت + المتوقّع + النطاق
class _ForecastReadout extends StatelessWidget {
  const _ForecastReadout({required this.point, required this.instrument});

  final ForecastPoint point;
  final Instrument instrument;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final local = point.time.toLocal();
    final when = '${MaterialLocalizations.of(context).formatShortDate(local)} ${Formatters.clock(local)}';
    return DecoratedBox(
      decoration: BoxDecoration(
        color: c.raised,
        borderRadius: AppRadii.card,
        border: Border.all(color: c.forecast.withValues(alpha: 0.6)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xs),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l10n.forecastReadout, style: context.textTheme.labelSmall!.copyWith(color: c.forecast)),
            Text(when, style: context.textTheme.labelSmall),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('${l10n.forecastExpected} ', style: context.textTheme.labelSmall),
                Text(instrument.format(point.expected), style: context.type.numSmall.copyWith(color: c.fg)),
              ],
            ),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('${l10n.forecastRange} ', style: context.textTheme.labelSmall),
                Text(
                  '${instrument.format(point.low)} – ${instrument.format(point.high)}',
                  style: context.type.numSmall.copyWith(color: c.fg),
                  textDirection: TextDirection.ltr,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
