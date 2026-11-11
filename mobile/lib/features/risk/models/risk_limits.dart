import 'package:flutter/foundation.dart';

import '../../../core/data/json.dart';

/// رأس المال وحدود المخاطرة يلي المستخدم بيكتبها بنفسه (Settings).
///
/// التطبيق ما بيشوف حساب الوسيط ولا بينفّذ صفقات، فهالأرقام "Your input"
/// دايمًا. بتنستعمل لحساب حجم الصفقة وبفلتر "بتناسب حدودي" بالإشارات.
@immutable
final class RiskLimits {
  const RiskLimits({
    this.capital,
    this.maxRiskPerTradePct = 1,
    this.dailyLossLimitPct = 3,
  });

  /// عملة الحساب - كل الأدوات الثمانية فيها USD بطرف، فما في تحويل مخمَّن
  static const String currency = 'USD';

  /// null لحد ما المستخدم يكتبه (ما منخمّن رأس مال)
  final double? capital;

  /// أقصى مخاطرة بالصفقة الوحدة (% من رأس المال)
  final double maxRiskPerTradePct;

  /// حد الخسارة اليومي (% من رأس المال)
  final double dailyLossLimitPct;

  static const RiskLimits defaults = RiskLimits();

  // حدود الإدخال المقبولة
  static const double maxCapital = 1e9;
  static const double minPerTradePct = 0.1;
  static const double maxPerTradePct = 10;
  static const double minDailyPct = 0.5;
  static const double maxDailyPct = 20;

  bool get hasCapital => capital != null && capital! > 0;

  /// المبلغ يلي بيقبل يخسره بالصفقة الوحدة (null بدون رأس مال)
  double? get riskBudgetPerTrade => hasCapital ? capital! * maxRiskPerTradePct / 100 : null;

  Map<String, Object?> toJson() => {
        'capital': capital,
        'max_risk_per_trade_pct': maxRiskPerTradePct,
        'daily_loss_limit_pct': dailyLossLimitPct,
      };

  /// قيمة محفوظة تالفة أو برا الحدود → الافتراضي (ما منرمي استثناء)
  static RiskLimits fromJson(Json json) {
    final capital = json.number('capital');
    final perTrade = json.number('max_risk_per_trade_pct');
    final daily = json.number('daily_loss_limit_pct');
    final parsed = RiskLimits(
      capital: capital != null && capital > 0 && capital <= maxCapital ? capital : null,
      maxRiskPerTradePct: perTrade ?? defaults.maxRiskPerTradePct,
      dailyLossLimitPct: daily ?? defaults.dailyLossLimitPct,
    );
    return validateRiskLimits(parsed).isEmpty ? parsed : RiskLimits(capital: parsed.capital);
  }

  @override
  bool operator ==(Object other) =>
      other is RiskLimits &&
      other.capital == capital &&
      other.maxRiskPerTradePct == maxRiskPerTradePct &&
      other.dailyLossLimitPct == dailyLossLimitPct;

  @override
  int get hashCode => Object.hash(capital, maxRiskPerTradePct, dailyLossLimitPct);
}

enum RiskLimitsField { capital, perTrade, daily }

enum RiskLimitsError {
  /// رأس المال لازم يكون أكبر من صفر (أو فاضي = مش محدد)
  capitalInvalid,
  perTradeOutOfRange,
  dailyOutOfRange,

  /// الحد اليومي أصغر من مخاطرة صفقة وحدة
  dailyBelowPerTrade,
}

/// كل الأخطاء بالقيم (فاضي = صالح). رأس المال الفاضي مقبول.
Map<RiskLimitsField, RiskLimitsError> validateRiskLimits(RiskLimits limits) {
  final errors = <RiskLimitsField, RiskLimitsError>{};
  final capital = limits.capital;
  if (capital != null && (capital <= 0 || capital > RiskLimits.maxCapital)) {
    errors[RiskLimitsField.capital] = RiskLimitsError.capitalInvalid;
  }
  final perTrade = limits.maxRiskPerTradePct;
  if (perTrade < RiskLimits.minPerTradePct || perTrade > RiskLimits.maxPerTradePct) {
    errors[RiskLimitsField.perTrade] = RiskLimitsError.perTradeOutOfRange;
  }
  final daily = limits.dailyLossLimitPct;
  if (daily < RiskLimits.minDailyPct || daily > RiskLimits.maxDailyPct) {
    errors[RiskLimitsField.daily] = RiskLimitsError.dailyOutOfRange;
  } else if (!errors.containsKey(RiskLimitsField.perTrade) && daily < perTrade) {
    errors[RiskLimitsField.daily] = RiskLimitsError.dailyBelowPerTrade;
  }
  return errors;
}

/// رقم مكتوب بإيد المستخدم ("10,000" أو "1.5") → double (null لو مش رقم)
double? parseUserNumber(String text) {
  final cleaned = text.trim().replaceAll(',', '').replaceAll('٬', '').replaceAll('٫', '.');
  if (cleaned.isEmpty) return null;
  final value = double.tryParse(cleaned);
  return value == null || value.isNaN || value.isInfinite ? null : value;
}
