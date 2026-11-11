import 'dart:math' as math;

import '../../markets/data/simulated_market_source.dart';
import '../../markets/models/market_models.dart';
import '../models/analysis_method.dart';

/// قراءة طريقة تحليل على شمعة مسكّرة (قبل ما تنبني المناطق السعرية)
typedef MethodRead = ({
  bool detected,
  bool long,
  double probability,
  double riskReward,
  String setupType,
  double? indicator,
});

/// المحرّك المحاكى لكل طريقة - حتمي لـ (أداة، إطار، طريقة، شمعة).
///
/// النموذج دايمًا هو يلي بيطلّع الاحتمال والأسباب (محاكى هون)؛ الطريقة الفنية
/// بتحدّد شلون الإشارة بتنبني (الاتجاه، الاحتمال، العائد، المؤشر):
/// - MA Crossover: متوسط 10 شموع مقابل 30 (اتجاه).
/// - RSI Reversal: RSI (14)؛ تحت 35 = صعود محتمل، فوق 65 = هبوط محتمل (انعكاس).
///
/// كل طريقة إلها ملح hash خاص، فنفس الأداة ونفس الشمعة بتعطي اتجاه / احتمال /
/// عائد مختلفين بين الطرق.
final class SimulatedAnalysisEngine {
  const SimulatedAnalysisEngine(this.source);

  final SimulatedMarketSource source;

  static const int fastPeriod = 10;
  static const int slowPeriod = 30;
  static const int rsiPeriod = 14;
  static const double rsiOversold = 35;
  static const double rsiOverbought = 65;

  MethodRead read(SimulatedInstrumentSpec spec, Timeframe tf, int index, DateTime close, String methodId) =>
      switch (methodId) {
        AnalysisMethod.rsiReversalId => _rsiReversal(spec, tf, index, close),
        // MA Crossover (والافتراضي لأي معرّف تاني)
        _ => _maCrossover(spec, tf, index, close),
      };

  int _bucket(Timeframe tf, DateTime close) => close.millisecondsSinceEpoch ~/ tf.duration.inMilliseconds;

  double _close(SimulatedInstrumentSpec spec, Timeframe tf, DateTime close, int back) =>
      source.priceAt(spec.symbol, close.subtract(tf.duration * back));

  MethodRead _maCrossover(SimulatedInstrumentSpec spec, Timeframe tf, int index, DateTime close) {
    double mean(int n) {
      var sum = 0.0;
      for (var i = 0; i < n; i++) {
        sum += _close(spec, tf, close, i);
      }
      return sum / n;
    }

    final fast = mean(fastPeriod);
    final slow = mean(slowPeriod);
    // الفرق بوحدات تذبذب الأداة على مدى المتوسط السريع (مقارن بين الأدوات)
    final gap = (fast / slow - 1) / (spec.dailyVol * math.sqrt(tf.duration.inMinutes * fastPeriod / 1440));
    final h = SimulatedMarketSource.hash01(spec.seed, 230 + index, _bucket(tf, close));
    return (
      detected: gap.abs() > 0.2 && h > 0.2,
      long: gap >= 0,
      probability: 0.5 + math.min(gap.abs(), 2) / 2 * 0.18 + h * 0.08,
      riskReward: 1.3 + h * 1.2,
      setupType: 'trend_following',
      indicator: double.parse(gap.toStringAsFixed(2)),
    );
  }

  /// RSI (14) بمتوسط بسيط للربح والخسارة على آخر 14 شمعة
  double rsi(SimulatedInstrumentSpec spec, Timeframe tf, DateTime close) {
    var gain = 0.0;
    var loss = 0.0;
    for (var i = 0; i < rsiPeriod; i++) {
      final change = _close(spec, tf, close, i) - _close(spec, tf, close, i + 1);
      if (change >= 0) {
        gain += change;
      } else {
        loss -= change;
      }
    }
    if (loss == 0) return gain == 0 ? 50 : 100;
    return 100 - 100 / (1 + gain / loss);
  }

  MethodRead _rsiReversal(SimulatedInstrumentSpec spec, Timeframe tf, int index, DateTime close) {
    final value = rsi(spec, tf, close);
    final h = SimulatedMarketSource.hash01(spec.seed, 260 + index, _bucket(tf, close));
    final extreme = ((value - 50).abs() - 15) / 35;
    return (
      detected: (value <= rsiOversold || value >= rsiOverbought) && h > 0.15,
      // انعكاس: مبالغة بالبيع = صعود محتمل
      long: value <= 50,
      probability: 0.5 + extreme.clamp(0, 1) * 0.2 + h * 0.05,
      riskReward: 1.2 + h * 0.8,
      setupType: 'mean_reversion',
      indicator: double.parse(value.toStringAsFixed(1)),
    );
  }

  /// مدة الطلب المحاكى (1.5 لـ 3 ثواني)، حتمية لـ (أداة، إطار، طريقة، شمعة)
  static Duration requestLatency(SimulatedInstrumentSpec spec, Timeframe tf, String methodId, int bucket) {
    final salt = 300 + AnalysisMethod.knownIds.indexOf(methodId) * 7 + Timeframe.modelTimeframes.indexOf(tf);
    final h = SimulatedMarketSource.hash01(spec.seed, salt, bucket);
    return Duration(milliseconds: 1500 + (h * 1500).round());
  }
}
