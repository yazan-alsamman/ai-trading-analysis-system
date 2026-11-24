import 'dart:math' as math;

import 'package:flutter/foundation.dart';

import '../../../core/widgets/direction_badge.dart';
import '../../markets/data/simulated_market_source.dart';
import '../../markets/models/market_models.dart';
import '../../signals/data/simulated_outcomes.dart';
import '../../signals/models/analysis_method.dart';
import '../models/backtest.dart';

/// إشارة سابقة محاكاة: خلية من [SimulatedOutcomes] مع اتجاهها واحتمالها وعائدها
@immutable
final class PastSignal {
  const PastSignal({
    required this.day,
    required this.symbol,
    required this.timeframe,
    required this.direction,
    required this.probability,
    required this.riskReward,
    required this.hit,
  });

  /// رقم اليوم من 1970 (UTC)
  final int day;
  final String symbol;
  final Timeframe timeframe;
  final SignalDirection direction;
  final double probability;
  final double riskReward;

  /// وصلت للهدف قبل الوقف
  final bool hit;

  /// نتيجتها بوحدات المخاطرة: هدف = +العائد:المخاطرة، وقف = −1
  double get r => hit ? riskReward : -1;
}

/// محرّك الاختبار المحاكى - حتمي (نفس الطلب ونفس اليوم = نفس النتيجة).
///
/// ما بيخترع نتائج جديدة: كل إشارة سابقة هي خلية من [SimulatedOutcomes] لطريقة
/// الاستراتيجية. الاتجاه من ميل السعر المحاكى ([SimulatedMarketSource.priceAt])
/// وقت الإشارة.
///
/// الطريقة ([BacktestRequest.methodId]) دايمًا فنية (A3c: النموذج مش طريقة):
/// خلاياها الخاصة ([SimulatedOutcomes.methodSalt])، والاتجاه حسب منطقها:
/// MA Crossover = ميل 10 شموع (اتجاه)، RSI Reversal = عكس ميل 14 شمعة (انعكاس).
/// القاعدة: نفس الاستراتيجية ونفس الفترة = نفس النتيجة بكل مكان (حتمي)؛ ما عاد
/// في "= Insights" (Insights = سجل النموذج، مش طريقة).
final class SimulatedBacktestEngine {
  const SimulatedBacktestEngine(this.outcomes);

  final SimulatedOutcomes outcomes;

  SimulatedMarketSource get _source => outcomes.source;

  /// الإشارة السابقة بخلية (أداة × إطار × يوم) لطريقة [methodId]، null لما ما
  /// في وحدة إلها نتيجة
  PastSignal? signal(String symbol, Timeframe timeframe, int day, {String methodId = AnalysisMethod.defaultId}) {
    final spec = _source.spec(symbol);
    final index = Timeframe.modelTimeframes.indexOf(timeframe);
    if (spec == null || index < 0) return null;
    final outcome = outcomes.cell(symbol, timeframe, day, methodId: methodId);
    if (outcome.resolved == 0) return null;
    final methodSalt = SimulatedOutcomes.methodSalt(methodId);
    double hash(int salt) => SimulatedMarketSource.hash01(spec.seed, methodSalt + salt + index, day);

    final at = DateTime.fromMillisecondsSinceEpoch(
      day * Duration.millisecondsPerDay + (hash(460) * Duration.millisecondsPerDay).floor(),
      isUtc: true,
    );
    bool rising(int lookback) =>
        _source.priceAt(symbol, at) >= _source.priceAt(symbol, at.subtract(timeframe.duration * lookback));
    final (long, probability, riskReward) = switch (methodId) {
      // انعكاس: احتمال 50..75%، عائد 1.2..2.0
      AnalysisMethod.rsiReversalId => (!rising(14), 0.5 + hash(440) * 0.25, 1.2 + hash(430) * 0.8),
      // MA Crossover (والافتراضي): احتمال 50..74%، عائد 1.3..2.5
      _ => (rising(10), 0.5 + hash(440) * 0.24, 1.3 + hash(430) * 1.2),
    };
    return PastSignal(
      day: day,
      symbol: symbol,
      timeframe: timeframe,
      direction: long ? SignalDirection.long : SignalDirection.short,
      probability: double.parse(probability.toStringAsFixed(2)),
      riskReward: double.parse(riskReward.toStringAsFixed(1)),
      hit: outcome.hits == 1,
    );
  }

  static bool matches(PastSignal s, BacktestRequest request) =>
      request.symbols.contains(s.symbol) &&
      request.timeframes.contains(s.timeframe) &&
      request.directions.contains(s.direction) &&
      s.probability >= request.minProbability &&
      s.riskReward >= request.minRiskReward;

  /// إشارات الأيام [from]..[to] (مع الطرفين) يلي بتطابق [request]،
  /// مرتبة باليوم ثم ترتيب المنتج ثم الإطار
  List<PastSignal> signals(BacktestRequest request, int from, int to) => [
        for (var day = from; day <= to; day++)
          for (final symbol in kProductSymbols)
            if (request.symbols.contains(symbol))
              for (final tf in Timeframe.modelTimeframes)
                if (signal(symbol, tf, day, methodId: request.methodId) case final s? when matches(s, request)) s,
      ];

  /// ملخص بشكل جواب `POST /backtests` من إشارات مرتبة من [firstDay]
  static Map<String, Object?> resultJson(BacktestPeriod period, int firstDay, List<PastSignal> signals) {
    double round(double v) => double.parse(v.toStringAsFixed(2));
    var total = 0.0;
    var peak = 0.0;
    var drawdown = 0.0;
    final byDay = <int, ({double r, int signals})>{};
    for (final (i, s) in signals.indexed) {
      total += s.r;
      peak = math.max(peak, total);
      drawdown = math.max(drawdown, peak - total);
      byDay[s.day] = (r: total, signals: i + 1);
    }
    final rrSum = signals.fold(0.0, (sum, s) => sum + s.riskReward);
    return {
      'window_days': period.days,
      'signals': signals.length,
      'hits': signals.where((s) => s.hit).length,
      'avg_risk_reward': signals.isEmpty ? null : round(rrSum / signals.length),
      'max_drawdown_r': round(drawdown),
      'equity': [
        if (signals.isNotEmpty) {'time': firstDay * Duration.millisecondsPerDay, 'r': 0.0, 'signals': 0},
        for (final MapEntry(key: day, value: point) in byDay.entries)
          {'time': day * Duration.millisecondsPerDay, 'r': round(point.r), 'signals': point.signals},
      ],
    };
  }
}
