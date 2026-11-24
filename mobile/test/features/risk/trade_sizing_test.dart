// اختبارات حساب حجم الصفقة وحدود المخاطرة (دوال صافية، نفس منطق الويب).

import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/core/data/json.dart';
import 'package:trading_app/core/widgets/direction_badge.dart';
import 'package:trading_app/features/markets/models/market_models.dart';
import 'package:trading_app/features/risk/models/risk_limits.dart';
import 'package:trading_app/features/risk/models/trade_sizing.dart';

const eurUsd = Instrument(symbol: 'EUR/USD', kind: MarketKind.forex, precision: 5);
const usdJpy = Instrument(symbol: 'USD/JPY', kind: MarketKind.forex, precision: 3);
const gold = Instrument(symbol: 'XAU/USD', kind: MarketKind.commodity, precision: 2);

SizingResult size(
  Instrument instrument, {
  double? capital = 10000,
  double? riskPct = 1,
  double? entry,
  double? stop,
  double? target,
  double limit = 1,
}) =>
    computeTradeSize(
      instrument: instrument,
      capital: capital,
      riskPct: riskPct,
      entry: entry,
      stop: stop,
      target: target,
      maxRiskPerTradePct: limit,
    );

void main() {
  group('computeTradeSize', () {
    test('EUR/USD long: 1% of 10,000 over a 25-pip stop', () {
      final r = size(eurUsd, entry: 1.08750, stop: 1.08500, target: 1.09250) as TradeSize;
      expect(r.direction, SignalDirection.long);
      expect(r.moneyAtRisk, closeTo(100, 1e-9));
      expect(r.pips, closeTo(25, 1e-6));
      expect(r.units, closeTo(40000, 1e-3)); // 100 / 0.0025
      expect(r.potentialReward, closeTo(200, 1e-6));
      expect(r.riskReward, closeTo(2, 1e-9));
    });

    test('USD/JPY short: P/L in yen converted to USD at the exit price', () {
      final r = size(usdJpy, entry: 150.000, stop: 150.500) as TradeSize;
      expect(r.direction, SignalDirection.short);
      expect(r.pips, closeTo(50, 1e-6));
      // الخسارة بالدولار عند الوقف = units × 0.5 / 150.5 = 100
      expect(r.units * 0.5 / 150.5, closeTo(100, 1e-6));
      expect(r.potentialReward, isNull);
    });

    test('gold: size in ounces, pip = 0.1', () {
      final r = size(gold, entry: 2045.30, stop: 2035.30) as TradeSize;
      expect(r.units, closeTo(10, 1e-9)); // 100 / 10
      expect(r.pips, closeTo(100, 1e-6));
    });

    test('missing inputs, equal stop, wrong-side target, risk above 100%', () {
      expect((size(eurUsd, capital: null, entry: 1.1, stop: 1.09) as SizingProblem).issue, SizingIssue.incomplete);
      expect((size(eurUsd, entry: 1.1, stop: null) as SizingProblem).issue, SizingIssue.incomplete);
      expect((size(eurUsd, entry: 1.1, stop: 1.1) as SizingProblem).issue, SizingIssue.stopEqualsEntry);
      expect(
        (size(eurUsd, entry: 1.1, stop: 1.09, target: 1.08) as SizingProblem).issue,
        SizingIssue.targetWrongSide,
      );
      expect((size(eurUsd, riskPct: 150, entry: 1.1, stop: 1.09) as SizingProblem).issue, SizingIssue.riskTooHigh);
    });

    test('limit status: within / near / breach against the per-trade limit', () {
      LimitStatus at(double pct) => (size(eurUsd, riskPct: pct, entry: 1.1, stop: 1.09, limit: 1) as TradeSize).limitStatus;
      expect(at(0.5), LimitStatus.within);
      expect(at(0.8), LimitStatus.near);
      expect(at(1), LimitStatus.near);
      expect(at(1.5), LimitStatus.breach);
    });
  });

  group('RiskLimits', () {
    test('defaults: no capital, 1% per trade, 3% a day (like the web)', () {
      expect(RiskLimits.defaults.capital, isNull);
      expect(RiskLimits.defaults.maxRiskPerTradePct, 1);
      expect(RiskLimits.defaults.dailyLossLimitPct, 3);
      expect(RiskLimits.defaults.riskBudgetPerTrade, isNull);
      expect(const RiskLimits(capital: 20000).riskBudgetPerTrade, 200);
    });

    test('validation', () {
      expect(validateRiskLimits(RiskLimits.defaults), isEmpty);
      expect(validateRiskLimits(const RiskLimits(capital: 0)), {RiskLimitsField.capital: RiskLimitsError.capitalInvalid});
      expect(validateRiskLimits(const RiskLimits(maxRiskPerTradePct: 11)),
          {RiskLimitsField.perTrade: RiskLimitsError.perTradeOutOfRange});
      expect(validateRiskLimits(const RiskLimits(maxRiskPerTradePct: 2, dailyLossLimitPct: 1)),
          {RiskLimitsField.daily: RiskLimitsError.dailyBelowPerTrade});
    });

    test('json round trip; corrupt or out-of-range values fall back safely', () {
      const limits = RiskLimits(capital: 12500.5, maxRiskPerTradePct: 0.75, dailyLossLimitPct: 4);
      expect(RiskLimits.fromJson(Json(limits.toJson())), limits);
      expect(RiskLimits.fromJson(const Json({'capital': 'abc', 'max_risk_per_trade_pct': 99})), RiskLimits.defaults);
      expect(RiskLimits.fromJson(const Json({'capital': -5})), RiskLimits.defaults);
    });

    test('parseUserNumber accepts the Arabic decimal separator', () {
      expect(parseUserNumber('1٫5'), 1.5);
      expect(parseUserNumber('10,000'), 10000);
      expect(parseUserNumber(' '), isNull);
      expect(parseUserNumber('x'), isNull);
    });
  });
}
