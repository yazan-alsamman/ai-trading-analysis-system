import '../../../core/data/json.dart';
import '../../../core/widgets/direction_badge.dart';
import '../../markets/models/market_models.dart';
import '../models/analysis_method.dart';
import '../models/opportunity.dart';

/// شكل الـ API لفرصة النموذج (عقد `OpportunitySchema` بـ web/src/services/schemas.ts،
/// لسّا مش نهائي بالـ backend). الحقول الغلط أو الناقصة → null (بتنشال).
final class OpportunityDto {
  const OpportunityDto(this.json);

  final Json json;

  factory OpportunityDto.fromJson(Json json) => OpportunityDto(json);

  Opportunity? toDomain() {
    final id = json.string('id');
    final symbol = json.string('symbol')?.trim().toUpperCase();
    final timeframe = Timeframe.fromApi(json.string('timeframe'));
    final status = switch (json.string('status')) {
      'detected' => OpportunityStatus.detected,
      'not_detected' => OpportunityStatus.notDetected,
      _ => null,
    };
    final direction = switch (json.string('direction')) {
      'long' => SignalDirection.long,
      'short' => SignalDirection.short,
      'neutral' => SignalDirection.neutral,
      _ => null,
    };
    final probability = json.number('probability');
    final entry = _zone(json.object('entryZone'));
    final stop = _zone(json.object('stopLossZone'));
    final target = _zone(json.object('takeProfitZone'));
    final riskReward = json.number('riskReward');
    final generatedAt = json.epochMillis('generatedAt');
    final validUntil = json.epochMillis('validUntil');
    // بدون طريقة (عقد الويب القديم) = الطريقة الافتراضية؛ طريقة مش معروفة
    // (`ai_model` كمان، A3c) = الفرصة بتنشال: كل إشارة إلها طريقة فنية
    final methodId = json.string('methodId') ?? AnalysisMethod.defaultId;

    if (id == null ||
        symbol == null ||
        timeframe == null ||
        status == null ||
        direction == null ||
        probability == null ||
        probability < 0 ||
        probability > 1 ||
        entry == null ||
        stop == null ||
        target == null ||
        riskReward == null ||
        riskReward <= 0 ||
        generatedAt == null ||
        validUntil == null ||
        !AnalysisMethod.isKnown(methodId)) {
      return null;
    }
    return Opportunity(
      id: id,
      symbol: symbol,
      timeframe: timeframe,
      status: status,
      direction: direction,
      setupType: switch (json.string('setupType')) {
        'mean_reversion' => SetupType.meanReversion,
        'breakout' => SetupType.breakout,
        'scalping' => SetupType.scalping,
        _ => SetupType.trendFollowing,
      },
      riskLevel: switch (json.string('riskLevel')) {
        'low' => RiskLevel.low,
        'high' => RiskLevel.high,
        _ => RiskLevel.medium,
      },
      probability: probability,
      entryZone: entry,
      stopLossZone: stop,
      takeProfitZone: target,
      riskReward: riskReward,
      generatedAt: generatedAt,
      validUntil: validUntil,
      methodId: methodId,
      indicator: json.number('indicator'),
      requestedByYou: json.boolean('requestedByYou') ?? false,
    );
  }

  static PriceZone? _zone(Json? json) {
    final low = json?.number('low');
    final high = json?.number('high');
    if (low == null || high == null || low <= 0 || high <= 0) return null;
    return low <= high ? PriceZone(low, high) : PriceZone(high, low);
  }
}

/// قائمة `OpportunitySchema[]` من الـ API → فرص صالحة بس (أي عنصر مش Map أو
/// ناقص بينتشال بهدوء، وجسم مش قائمة = ولا فرصة)
List<Opportunity> opportunitiesFromJson(Object? body) => body is List
    ? mapValid(
        body,
        (Object? item) => switch (Json.from(item)) {
              final json? => OpportunityDto.fromJson(json).toDomain(),
              null => null,
            })
    : const [];
