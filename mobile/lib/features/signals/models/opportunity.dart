import 'package:flutter/foundation.dart';

import '../../../core/widgets/direction_badge.dart';
import '../../markets/models/market_models.dart';
import 'analysis_method.dart';

enum OpportunityStatus { detected, notDetected }

enum SetupType { trendFollowing, meanReversion, breakout, scalping }

enum RiskLevel { low, medium, high }

/// منطقة سعرية (دخول / وقف / هدف)
@immutable
final class PriceZone {
  const PriceZone(this.low, this.high);

  final double low;
  final double high;

  double get mid => (low + high) / 2;

  @override
  bool operator ==(Object other) => other is PriceZone && other.low == low && other.high == high;

  @override
  int get hashCode => Object.hash(low, high);
}

/// رأي النموذج على أداة + إطار زمني (عقد الويب `Opportunity`). احتمال، مش أمر.
@immutable
final class Opportunity {
  const Opportunity({
    required this.id,
    required this.symbol,
    required this.timeframe,
    required this.status,
    required this.direction,
    required this.setupType,
    required this.riskLevel,
    required this.probability,
    required this.entryZone,
    required this.stopLossZone,
    required this.takeProfitZone,
    required this.riskReward,
    required this.generatedAt,
    required this.validUntil,
    this.methodId = AnalysisMethod.defaultId,
    this.indicator,
    this.requestedByYou = false,
  });

  final String id;
  final String symbol;
  final Timeframe timeframe;
  final OpportunityStatus status;
  final SignalDirection direction;
  final SetupType setupType;
  final RiskLevel riskLevel;

  /// احتمال بلوغ الهدف قبل الوقف (0..1)
  final double probability;
  final PriceZone entryZone;
  final PriceZone stopLossZone;
  final PriceZone takeProfitZone;

  /// العائد ÷ المخاطرة (2 = 1:2)
  final double riskReward;
  final DateTime generatedAt;
  final DateTime validUntil;

  /// الاستراتيجية المستعملة: طريقة التحليل يلي طلّعت الرأي ([AnalysisMethod.knownIds])
  final String methodId;

  /// قراءة المؤشر الأساسي للطريقة: RSI (0..100) لـ RSI Reversal، والفرق بين
  /// المتوسطين (بوحدات التذبذب، موجب = السريع فوق) لـ MA Crossover، و null للنموذج
  final double? indicator;

  /// انطلب من المستخدم (Request analysis)، مش من قائمة الاستراتيجية
  final bool requestedByYou;

  bool get isDetected => status == OpportunityStatus.detected && direction != SignalDirection.neutral;

  /// بعد [validUntil] التحليل قديم وما بينعرض كرأي حالي
  bool isStale(DateTime now) => now.isAfter(validUntil);
}

/// خلاصة رأي النموذج على أداة: الأقوى بين 15m / 1h / 4h + كم إطار متّفق
@immutable
final class ModelRead {
  const ModelRead({required this.best, required this.agreeing, required this.analysed});

  /// null = ما في فرصة حالية على أي إطار
  final Opportunity? best;

  /// كم إطار بيتّفق مع اتجاه [best]
  final int agreeing;

  /// كم إطار انحلّل (صالح وغير قديم)
  final int analysed;

  static ModelRead from(List<Opportunity> items, DateTime now) {
    final fresh = items.where((o) => !o.isStale(now)).toList();
    final detected = fresh.where((o) => o.isDetected).toList()..sort((a, b) => b.probability.compareTo(a.probability));
    final best = detected.isEmpty ? null : detected.first;
    return ModelRead(
      best: best,
      agreeing: best == null ? 0 : detected.where((o) => o.direction == best.direction).length,
      analysed: fresh.length,
    );
  }
}
