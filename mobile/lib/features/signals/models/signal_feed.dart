import '../../markets/models/market_models.dart';
import 'opportunity.dart';
import 'signal_profile.dart';

/// هل الفرصة بتمرق من فلتر "Strategy"؟ (نفس فحوص الويب `evaluateSignal`:
/// الأداة، الإطار، الاتجاه، أقل احتمال، أقل عائد : مخاطرة)
///
/// "بتناسب حدودي" ما بتنحسب هون: الويب بيحسب الحجم على حد الصفقة الوحدة،
/// والحد اليومي دايمًا ≥ حد الصفقة، فخطة صالحة ما بتخالف أبدًا. الحجم
/// الفعلي بيبيّن بـ "Size this trade".
bool matchesSignalProfile(Opportunity o, SignalProfile profile) =>
    o.isDetected &&
    profile.symbols.contains(o.symbol) &&
    profile.timeframes.contains(o.timeframe) &&
    profile.directions.contains(o.direction) &&
    o.probability >= profile.minProbability &&
    o.riskReward + 1e-9 >= profile.minRiskReward;

/// قائمة Signals: الصالحة (مش قديمة) يلي بتطابق الاستراتيجية، بالترتيب:
/// الاحتمال الأعلى، بعدين الأحدث، بعدين ترتيب الأدوات الثابت (حتمي).
List<Opportunity> rankSignals(Iterable<Opportunity> items, SignalProfile profile, DateTime now) {
  int order(String symbol) {
    final i = kProductSymbols.indexOf(symbol);
    return i < 0 ? kProductSymbols.length : i;
  }

  return [
    for (final o in items)
      if (!o.isStale(now) && matchesSignalProfile(o, profile)) o,
  ]..sort((a, b) {
      final byProbability = b.probability.compareTo(a.probability);
      if (byProbability != 0) return byProbability;
      final byFreshness = b.generatedAt.compareTo(a.generatedAt);
      if (byFreshness != 0) return byFreshness;
      final bySymbol = order(a.symbol).compareTo(order(b.symbol));
      return bySymbol != 0 ? bySymbol : a.timeframe.index.compareTo(b.timeframe.index);
    });
}
