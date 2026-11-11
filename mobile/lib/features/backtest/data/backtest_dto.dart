import '../../../core/data/json.dart';
import '../models/backtest.dart';

/// شكل الـ API لنتيجة اختبار (`POST /backtests`) → domain.
///
/// ```json
/// {"window_days": 90, "signals": 42, "hits": 23, "avg_risk_reward": 1.94,
///  "max_drawdown_r": 3.0,
///  "equity": [{"time": 1760000000000, "r": 0, "signals": 0},
///             {"time": 1760086400000, "r": 1.5, "signals": 1}]}
/// ```
///
/// الإجمالي ناقص أو غير منطقي (hits > signals، فترة مش 30 / 90 / 365 / 730 / 1095 / 1825، عائد أو
/// تراجع سالب، إشارات بدون متوسط عائد) → null. نقاط المنحنى الغلط بتنشال؛
/// الوقت المكرر بينحسب أول مرة بس.
BacktestResult? backtestResultFromJson(Json json) {
  final period = BacktestPeriod.fromDays(json.integer('window_days'));
  final signals = json.integer('signals');
  final hits = json.integer('hits');
  final avg = json.number('avg_risk_reward');
  final drawdown = json.number('max_drawdown_r') ?? (signals == 0 ? 0.0 : null);
  if (period == null || signals == null || hits == null || drawdown == null) return null;
  if (signals < 0 || hits < 0 || hits > signals || drawdown < 0) return null;
  if (signals > 0 && (avg == null || avg <= 0)) return null;

  final equity = <int, EquityPoint>{};
  for (final item in json.objects('equity')) {
    final time = item.epochMillis('time');
    final r = item.number('r');
    final count = item.integer('signals');
    if (time == null || r == null || count == null || count < 0 || count > signals) continue;
    equity.putIfAbsent(time.millisecondsSinceEpoch, () => EquityPoint(time: time, r: r, signals: count));
  }

  return BacktestResult(
    period: period,
    signals: signals,
    hits: hits,
    avgRiskReward: signals == 0 ? null : avg,
    maxDrawdown: drawdown,
    equity: equity.values.toList()..sort((a, b) => a.time.compareTo(b.time)),
  );
}
