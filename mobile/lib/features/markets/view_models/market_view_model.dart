import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/market_models.dart';

enum ChartType { candles, line, area }

/// مؤشرات الرسم (من مؤشرات Syncfusion الجاهزة)
enum ChartIndicator {
  sma,
  ema,
  bollinger,
  rsi,
  macd;

  /// RSI و MACD بلوحة تحت الرسم، الباقي فوق السعر
  bool get isOscillator => this == rsi || this == macd;
}

/// حالة شاشة الأداة (إعدادات العرض بس - البيانات بـ providers تانية)
@immutable
final class MarketViewState {
  const MarketViewState({
    this.timeframe = Timeframe.h1,
    this.chartType = ChartType.candles,
    this.indicators = const {},
    this.readTimeframe,
    this.showForecast = false,
  });

  final Timeframe timeframe;
  final ChartType chartType;
  final Set<ChartIndicator> indicators;

  /// أي رأي للنموذج مرسوم على الرسم (مناطق الدخول/الهدف/الوقف) - null = الأقوى
  final Timeframe? readTimeframe;

  /// مفتاح "Forecast" بشريط الرسم: توقّع النموذج (خط متقطّع + نطاق) بعد آخر شمعة
  final bool showForecast;

  MarketViewState copyWith({
    Timeframe? timeframe,
    ChartType? chartType,
    Set<ChartIndicator>? indicators,
    Timeframe? Function()? readTimeframe,
    bool? showForecast,
  }) =>
      MarketViewState(
        timeframe: timeframe ?? this.timeframe,
        chartType: chartType ?? this.chartType,
        indicators: indicators ?? this.indicators,
        readTimeframe: readTimeframe == null ? this.readTimeframe : readTimeframe(),
        showForecast: showForecast ?? this.showForecast,
      );
}

/// ViewModel شاشة الأداة (لكل رمز instance، بينحذف لما الشاشة تتسكّر)
class MarketViewModel extends AutoDisposeFamilyNotifier<MarketViewState, String> {
  @override
  MarketViewState build(String symbol) => const MarketViewState();

  void setTimeframe(Timeframe timeframe) {
    if (timeframe != state.timeframe) state = state.copyWith(timeframe: timeframe);
  }

  void setChartType(ChartType type) {
    if (type != state.chartType) state = state.copyWith(chartType: type);
  }

  void toggleIndicator(ChartIndicator indicator) {
    final next = {...state.indicators};
    if (!next.remove(indicator)) next.add(indicator);
    state = state.copyWith(indicators: Set.unmodifiable(next));
  }

  void toggleForecast() => state = state.copyWith(showForecast: !state.showForecast);

  /// نفس الإطار مرّة تانية = رجوع للأقوى
  void showRead(Timeframe timeframe) {
    state = state.copyWith(readTimeframe: () => state.readTimeframe == timeframe ? null : timeframe);
  }
}

final marketViewModelProvider =
    NotifierProvider.autoDispose.family<MarketViewModel, MarketViewState, String>(MarketViewModel.new);
