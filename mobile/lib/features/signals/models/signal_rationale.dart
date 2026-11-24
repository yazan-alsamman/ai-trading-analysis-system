import 'package:flutter/foundation.dart';

import '../../../core/widgets/direction_badge.dart';
import '../../markets/models/market_models.dart';
import 'analysis_method.dart';
import 'opportunity.dart';

/// قديش السبب مأثّر بالقراءة (بينعرض جنب كل سبب: High / Medium / Low)
enum ReasonInfluence { high, medium, low }

/// سبب واحد بقائمة "ليش النموذج شايف هيك" - بيانات بس، النص المترجم بالـ View.
/// كلام احتمالات دايمًا، أبدًا وعود.
@immutable
sealed class SignalReason {
  const SignalReason();

  /// قوة السبب من 0 لـ 1 (قديش بيدعم القراءة) - للترتيب، ومنها [influence]
  double get strength;

  /// ≥ 0.65 عالي، ≥ 0.45 متوسط، أقل = منخفض
  ReasonInfluence get influence => strength >= 0.65
      ? ReasonInfluence.high
      : strength >= 0.45
          ? ReasonInfluence.medium
          : ReasonInfluence.low;
}

/// MA Crossover: المتوسط السريع (10) فوق / تحت البطيء (30) على إطار الإشارة
final class MaCrossReason extends SignalReason {
  const MaCrossReason({required this.direction, required this.timeframe, required this.gap});

  final SignalDirection direction;
  final Timeframe timeframe;

  /// الفرق بين المتوسطين بوحدات التذبذب ([Opportunity.indicator])
  final double gap;

  /// 0.5 لفرق صغير لحد 0.8 لفرق كبير
  @override
  double get strength => 0.5 + (gap.abs().clamp(0, 2) / 2) * 0.3;
}

/// RSI Reversal: قيمة RSI (14) ومنطقتها (مبالغة بيع = صعود محتمل)
final class RsiReason extends SignalReason {
  const RsiReason({required this.direction, required this.timeframe, required this.value});

  final SignalDirection direction;
  final Timeframe timeframe;

  /// 0..100
  final double value;

  /// كل ما بعدت عن 50 أقوى: 0.45 عند حد المنطقة لحد 0.8
  @override
  double get strength => 0.45 + (((value - 50).abs() - 15) / 35).clamp(0, 1) * 0.35;
}

/// ما في إعداد واضح هلّق (نتيجة محايدة لطلب تحليل) - السبب حسب الطريقة
final class NoSetupReason extends SignalReason {
  const NoSetupReason({required this.methodId, required this.timeframe, this.indicator});

  final String methodId;
  final Timeframe timeframe;

  /// قراءة المؤشر (RSI أو فرق المتوسطين) لو موجودة
  final double? indicator;

  @override
  double get strength => 0.5;
}

/// كم إطار (من يلي انحلّلوا) بيأشّر لنفس الجهة
final class AgreementReason extends SignalReason {
  const AgreementReason({required this.agreeing, required this.analysed});

  final int agreeing;
  final int analysed;

  @override
  double get strength => analysed == 0 ? 0 : agreeing / analysed;
}

/// الاحتمال بكلام بسيط: "تقريبًا 7 من 10"
final class ChanceReason extends SignalReason {
  const ChanceReason(this.probability);

  final double probability;

  int get outOfTen => (probability * 10).round().clamp(0, 10);

  @override
  double get strength => probability.clamp(0, 1).toDouble();
}

/// الهدف أبعد من الوقف بكم مرة
final class RewardRiskReason extends SignalReason {
  const RewardRiskReason(this.ratio);

  final double ratio;

  /// 1 : 1 = 0.5، 2 : 1 ≈ 0.67، 3 : 1 = 0.75
  @override
  double get strength => ratio <= 0 ? 0 : ratio / (1 + ratio);
}

/// تذبذب الأداة (عالي أو هادي بس، المتوسط ما بيحتاج جملة)
final class VolatilityReason extends SignalReason {
  const VolatilityReason(this.level);

  final RiskLevel level;

  /// سياق (تحذير / صبر)، مش دعم للاتجاه: الأضعف
  @override
  double get strength => 0.3;
}

/// الأسباب مرتّبة من الأقوى للأضعف ([SignalReason.strength])؛ التساوي بيحافظ على
/// الترتيب الأصلي: سبب الطريقة (تقاطع المتوسطات أو RSI)، الاتفاق
/// بين الأطر، الاحتمال، العائد : المخاطرة، التذبذب.
/// شاشة التفاصيل بتعرض أول [kTopReasons] والباقي ورا زر "أسباب أخرى (N)".
///
/// نتيجة محايدة (مش مكتشفة) = [NoSetupReason] (+ التذبذب لو مش متوسط).
///
/// [siblings] = رأي النموذج على باقي أطر نفس الأداة (نفس أرقام الـ Home وشاشة
/// السوق)؛ null لحد ما توصل، فسبب الاتفاق بيغيب.
///
/// TODO(API): لما الـ backend يرجّع `factors` بالعقد، بتنضاف هون كأسباب.
List<SignalReason> buildSignalRationale(
  Opportunity signal, {
  required List<Opportunity>? siblings,
  required DateTime now,
}) {
  final volatility = signal.riskLevel != RiskLevel.medium ? VolatilityReason(signal.riskLevel) : null;
  if (!signal.isDetected) {
    return [
      NoSetupReason(methodId: signal.methodId, timeframe: signal.timeframe, indicator: signal.indicator),
      if (volatility != null) volatility,
    ];
  }
  final fresh = siblings?.where((o) => !o.isStale(now)).toList();
  return strongestFirst([
    // سبب الطريقة (كل إشارة إلها طريقة فنية؛ أي معرّف تاني = الافتراضي MA Crossover)
    switch (signal.methodId) {
      AnalysisMethod.rsiReversalId =>
        RsiReason(direction: signal.direction, timeframe: signal.timeframe, value: signal.indicator ?? 50),
      _ => MaCrossReason(direction: signal.direction, timeframe: signal.timeframe, gap: signal.indicator ?? 0),
    },
    if (fresh != null && fresh.isNotEmpty)
      AgreementReason(
        agreeing: fresh.where((o) => o.isDetected && o.direction == signal.direction).length,
        analysed: fresh.length,
      ),
    ChanceReason(signal.probability),
    RewardRiskReason(signal.riskReward),
    if (volatility != null) volatility,
  ]);
}

/// كم سبب بينعرض بالبداية بشاشة التفاصيل
const int kTopReasons = 3;

/// ترتيب ثابت (stable): الأقوى أول، والمتساويين بترتيبهم الأصلي
List<SignalReason> strongestFirst(List<SignalReason> reasons) {
  final indexed = reasons.indexed.toList()
    ..sort((a, b) {
      final byStrength = b.$2.strength.compareTo(a.$2.strength);
      return byStrength != 0 ? byStrength : a.$1.compareTo(b.$1);
    });
  return [for (final (_, reason) in indexed) reason];
}
