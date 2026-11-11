import '../../markets/data/simulated_market_source.dart';
import '../../markets/models/market_models.dart';
import '../models/analysis_method.dart';

/// نتائج إشارات سابقة محاكاة (هدف أو وقف) لكل يوم × أداة × إطار - حتمية.
///
/// المصدر الوحيد لأرقام الدقة المحاكاة: سطر الدقة بـ Signals (آخر 90 يوم)
/// وشاشة Insights (7 / 30 / 90 + التقسيمات) بيجمعوا من نفس الخلايا، فالأرقام
/// متطابقة بين الشاشتين. الأيام المكتملة بس (لحد مبارح)، فالنتيجة ثابتة طول اليوم.
///
/// Insights وسطر الدقة = سجل النموذج دايمًا (ما بيتأثروا بطريقة الاستراتيجية).
/// الطرق الفنية إلها خلايا خاصة (ملح مختلف) بس لـ Backtest؛ Backtest دايمًا
/// بطريقة (A3c: النموذج مش طريقة)، فما عاد يساوي Insights.
final class SimulatedOutcomes {
  const SimulatedOutcomes(this.source);

  final SimulatedMarketSource source;

  /// احتمال إشارة مكتملة باليوم لكل أداة حسب الإطار (15m أكتر، 4h أقل)
  static const List<double> _dailyChance = [0.16, 0.09, 0.05];

  /// آخر يوم مكتمل (رقم اليوم من 1970، UTC)
  int get lastFullDay => source.now().millisecondsSinceEpoch ~/ Duration.millisecondsPerDay - 1;

  /// ملح كل طريقة؛ null = سجل النموذج نفسه (0 = نفس الخلايا من قبل A3، لـ
  /// Insights وسطر الدقة بس). أي معرّف تاني = الطريقة الافتراضية (MA Crossover).
  static int methodSalt(String? methodId) => switch (methodId) {
        null => 0,
        AnalysisMethod.rsiReversalId => 2000,
        _ => 1000,
      };

  /// نتيجة خلية وحدة: (كم إشارة إلها نتيجة، كم وحدة وصلت للهدف).
  /// [methodId] null = سجل النموذج (Insights)؛ طريقة = خلاياها (Backtest).
  ({int resolved, int hits}) cell(
    String symbol,
    Timeframe timeframe,
    int day, {
    String? methodId,
  }) {
    final spec = source.spec(symbol);
    final index = Timeframe.modelTimeframes.indexOf(timeframe);
    if (spec == null || index < 0) return (resolved: 0, hits: 0);
    final salt = methodSalt(methodId);
    final technical = salt != 0;
    // الطرق الفنية بتطلّع إشارات أكتر شوي، ودقتها أوطى شوي ومتغيّرة أكتر
    final chance = _dailyChance[index] * (technical ? 1.3 : 1);
    if (SimulatedMarketSource.hash01(spec.seed, salt + 400 + index, day) >= chance) {
      return (resolved: 0, hits: 0);
    }
    // كل أداة إلها مستوى دقة خاص فيها، والأطر الأطول أدق شوي
    final rate = technical
        ? 0.42 + SimulatedMarketSource.hash01(spec.seed, salt + 420, 0) * 0.16 + index * 0.02
        : 0.49 + SimulatedMarketSource.hash01(spec.seed, 420, 0) * 0.12 + index * 0.02;
    final hit = SimulatedMarketSource.hash01(spec.seed, salt + 410 + index, day) < rate;
    return (resolved: 1, hits: hit ? 1 : 0);
  }

  /// مجموع كل الأدوات والأطر على أيام [from]..[to] (مع الطرفين)
  /// [methodId] null = سجل النموذج (Insights)؛ طريقة = خلاياها (اختبار ثبات Backtest)
  ({int resolved, int hits}) total(int from, int to, {String? symbol, Timeframe? timeframe, String? methodId}) {
    var resolved = 0;
    var hits = 0;
    for (var day = from; day <= to; day++) {
      for (final s in kProductSymbols) {
        if (symbol != null && s != symbol) continue;
        for (final tf in Timeframe.modelTimeframes) {
          if (timeframe != null && tf != timeframe) continue;
          final r = cell(s, tf, day, methodId: methodId);
          resolved += r.resolved;
          hits += r.hits;
        }
      }
    }
    return (resolved: resolved, hits: hits);
  }
}
