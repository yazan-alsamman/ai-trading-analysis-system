import '../../../core/data/json.dart';
import '../../../core/widgets/direction_badge.dart';
import '../../markets/models/market_models.dart';
import '../../signals/models/analysis_method.dart';
import '../models/forecast_path.dart';

/// شكل الـ API للتوقّع → domain. **مقترح، مش نهائي**: شكل البيانات الحقيقي
/// سؤال مفتوح عند صاحب الـ backend (HANDOFF §8)، فالتحويل كلو هون بس؛ لو
/// تغيّر الشكل منغيّر هالملف وبس.
///
/// ```json
/// {"symbol": "EUR/USD", "timeframe": "1h", "method_id": "ma_crossover",
///  "signal_id": "EUR/USD-1h-493214@ma_crossover", "basis_timeframe": "1h",
///  "direction": "long",
///  "probability": 0.72, "anchor": {"time": 1761055200000, "price": 1.08412},
///  "target": 1.08655, "generated_at": 1761055200000, "valid_until": 1761066000000,
///  "points": [{"time": 1761058800000, "expected": 1.0844, "low": 1.0839, "high": 1.0849}]}
/// ```
///
/// `basis_timeframe` = إطار الإشارة [signal_id] (اختياري، الافتراضي = `timeframe`):
/// مختلف لما التوقّع بيلحق إشارة إطار تاني (رسم 1m بيلحق إشارة 1h مثلًا).
///
/// غلط أو ناقص → null (ولا شي بيرمي): نقطة غلط بتنشال، والتوقّع بلا نقاط صالحة،
/// أو باتجاه محايد، أو احتمال برّا 0..1 = ما في توقّع.
final class ForecastDto {
  const ForecastDto(this.json);

  final Json json;

  factory ForecastDto.fromJson(Json json) => ForecastDto(json);

  ForecastPath? toDomain() {
    final symbol = json.string('symbol')?.trim().toUpperCase();
    final timeframe = Timeframe.fromApi(json.string('timeframe'));
    final methodId = json.string('method_id') ?? AnalysisMethod.defaultId;
    final signalId = json.string('signal_id');
    final basis = Timeframe.fromApi(json.string('basis_timeframe'));
    final direction = switch (json.string('direction')) {
      'long' => SignalDirection.long,
      'short' => SignalDirection.short,
      _ => null,
    };
    final probability = json.number('probability');
    final anchor = json.object('anchor');
    final anchorTime = anchor?.epochMillis('time');
    final anchorPrice = anchor?.number('price');
    final target = json.number('target');
    final generatedAt = json.epochMillis('generated_at');
    final validUntil = json.epochMillis('valid_until');

    if (symbol == null ||
        timeframe == null ||
        !AnalysisMethod.isKnown(methodId) ||
        signalId == null ||
        direction == null ||
        probability == null ||
        probability < 0 ||
        probability > 1 ||
        anchorTime == null ||
        anchorPrice == null ||
        anchorPrice <= 0 ||
        target == null ||
        generatedAt == null ||
        validUntil == null ||
        !validUntil.isAfter(generatedAt)) {
      return null;
    }

    // بعد الـ anchor، بترتيب الوقت، بلا تكرار، و low ≤ expected ≤ high
    final points = <ForecastPoint>[];
    for (final p in json.objects('points')) {
      final time = p.epochMillis('time');
      final expected = p.number('expected');
      final low = p.number('low');
      final high = p.number('high');
      if (time == null || expected == null || low == null || high == null) continue;
      if (!time.isAfter(points.isEmpty ? anchorTime : points.last.time)) continue;
      if (low > expected || expected > high || low <= 0) continue;
      points.add(ForecastPoint(time: time, expected: expected, low: low, high: high));
    }
    if (points.isEmpty) return null;

    return ForecastPath(
      symbol: symbol,
      timeframe: timeframe,
      methodId: methodId,
      signalId: signalId,
      basisTimeframe: basis ?? timeframe,
      direction: direction,
      probability: probability,
      anchorTime: anchorTime,
      anchorPrice: anchorPrice,
      target: target,
      generatedAt: generatedAt,
      validUntil: validUntil,
      points: List.unmodifiable(points),
    );
  }
}
