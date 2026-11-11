import 'package:flutter/foundation.dart';

import '../../../core/widgets/direction_badge.dart';
import '../../markets/models/market_models.dart';
import 'risk_limits.dart';

/// حجم المخاطرة بالنسبة لحد المستخدم بالصفقة الوحدة
enum LimitStatus {
  /// ≤ 80% من الحد
  within,

  /// بين 80% والحد نفسه
  near,

  /// فوق الحد
  breach;

  static LimitStatus of({required double riskPct, required double limitPct}) {
    if (riskPct > limitPct + 1e-9) return breach;
    if (riskPct >= limitPct * 0.8 - 1e-9) return near;
    return within;
  }
}

/// ليش ما في نتيجة
enum SizingIssue {
  /// ناقص رأس مال / نسبة / دخول / وقف
  incomplete,

  /// الوقف نفس الدخول
  stopEqualsEntry,

  /// الهدف بنفس جهة الوقف (أو مش موجب)
  targetWrongSide,

  /// نسبة المخاطرة أكبر من 100%
  riskTooHigh,
}

/// نتيجة حساب الحجم: إما [TradeSize] أو [SizingProblem]
sealed class SizingResult {
  const SizingResult();
}

@immutable
final class SizingProblem extends SizingResult {
  const SizingProblem(this.issue);

  final SizingIssue issue;
}

/// حجم صفقة مخطّطة - للقرار بس، التطبيق ما بينفّذ شي.
///
/// الحجم بوحدات الأصل الأساسي (يورو، أونصة ذهب...) لأنو ما بيحتاج غير
/// الأسعار وعملة الحساب. اللوتات بتعتمد على عقد الوسيط فما منخمّنها.
@immutable
final class TradeSize extends SizingResult {
  const TradeSize({
    required this.direction,
    required this.stopDistance,
    required this.pips,
    required this.units,
    required this.moneyAtRisk,
    required this.riskPct,
    required this.potentialReward,
    required this.riskReward,
    required this.limitStatus,
  });

  final SignalDirection direction;

  /// |دخول − وقف| بوحدة السعر
  final double stopDistance;
  final double pips;

  /// الحجم بوحدات الأصل الأساسي
  final double units;

  /// الخسارة لو ضرب الوقف (USD)
  final double moneyAtRisk;
  final double riskPct;

  /// الربح لو وصل الهدف (USD) - null بدون هدف
  final double? potentialReward;
  final double? riskReward;
  final LimitStatus limitStatus;
}

/// حجم النقطة (pip): 0.01 للين، 0.1 للذهب، 0.0001 لباقي الأزواج
double pipSize(Instrument instrument) {
  if (instrument.quote == 'JPY') return 0.01;
  if (instrument.base == 'XAU') return 0.1;
  return 0.0001;
}

/// قيمة وحدة وحدة من عملة التسعير بالـ USD عند [price]:
/// التسعير بالـ USD → 1، الأساس USD → 1 / السعر (عند سعر الخروج، دقيق).
double? _usdPerQuoteUnit(Instrument instrument, double price) {
  if (instrument.quote == RiskLimits.currency) return 1;
  if (instrument.base == RiskLimits.currency) return 1 / price;
  return null;
}

/// حساب الحجم (دالة صافية، نفس منطق `computeTradeRisk` بالويب)
SizingResult computeTradeSize({
  required Instrument instrument,
  required double? capital,
  required double? riskPct,
  required double? entry,
  required double? stop,
  double? target,
  required double maxRiskPerTradePct,
}) {
  bool positive(double? v) => v != null && v.isFinite && v > 0;
  if (!positive(capital) || !positive(riskPct) || !positive(entry) || !positive(stop)) {
    return const SizingProblem(SizingIssue.incomplete);
  }
  if (riskPct! > 100) return const SizingProblem(SizingIssue.riskTooHigh);
  if (stop == entry) return const SizingProblem(SizingIssue.stopEqualsEntry);

  final long = stop! < entry!;
  if (target != null) {
    final wrongSide = !positive(target) || (long ? target <= entry : target >= entry);
    if (wrongSide) return const SizingProblem(SizingIssue.targetWrongSide);
  }

  final riskRate = _usdPerQuoteUnit(instrument, stop);
  if (riskRate == null) return const SizingProblem(SizingIssue.incomplete);

  final stopDistance = (entry - stop).abs();
  final riskBudget = capital! * riskPct / 100;
  final units = riskBudget / (stopDistance * riskRate);
  final targetDistance = target == null ? null : (target - entry).abs();
  final reward = target == null ? null : units * targetDistance! * _usdPerQuoteUnit(instrument, target)!;

  return TradeSize(
    direction: long ? SignalDirection.long : SignalDirection.short,
    stopDistance: stopDistance,
    pips: stopDistance / pipSize(instrument),
    units: units,
    moneyAtRisk: riskBudget,
    riskPct: riskPct,
    potentialReward: reward,
    riskReward: targetDistance == null ? null : targetDistance / stopDistance,
    limitStatus: LimitStatus.of(riskPct: riskPct, limitPct: maxRiskPerTradePct),
  );
}
