// اختبارات آراء النموذج: تحويل الـ DTO بأمان (العناصر الغلط بتنشال)، خلاصة
// الرأي (الأقوى + الاتفاق + القديم)، فلترة "Strategy" والترتيب، تفاصيل
// الإشارة، والمصدر المحاكى (منطقي مع اتجاه السعر ونفس أرقام رأي النموذج).

import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/core/data/json.dart';
import 'package:trading_app/core/widgets/direction_badge.dart';
import 'package:trading_app/features/markets/data/simulated_market_source.dart';
import 'package:trading_app/features/markets/models/market_models.dart';
import 'package:trading_app/features/signals/data/opportunity_dto.dart';
import 'package:trading_app/features/signals/data/signals_repository.dart';
import 'package:trading_app/features/signals/models/opportunity.dart';
import 'package:trading_app/features/signals/models/signal_detail.dart';
import 'package:trading_app/features/signals/models/signal_feed.dart';
import 'package:trading_app/features/signals/models/signal_profile.dart';
import 'package:trading_app/features/signals/models/signal_rationale.dart';

final _now = DateTime.utc(2026, 10, 21, 14, 5);

Map<String, Object?> raw({
  String? id,
  String symbol = 'EUR/USD',
  String tf = '1h',
  String direction = 'long',
  String? status,
  double probability = 0.7,
  double riskReward = 2,
  Duration age = Duration.zero,
  DateTime? validUntil,
}) =>
    {
      'id': id ?? 'o-$tf',
      'symbol': symbol,
      'timeframe': tf,
      'status': status ?? (direction == 'neutral' ? 'not_detected' : 'detected'),
      'direction': direction,
      'setupType': 'breakout',
      'riskLevel': 'low',
      'probability': probability,
      'entryZone': {'low': 1.08, 'high': 1.09},
      'stopLossZone': {'low': 1.07, 'high': 1.071},
      'takeProfitZone': {'high': 1.10, 'low': 1.11}, // مقلوبة: بتتصحّح
      'riskReward': riskReward,
      'generatedAt': _now.subtract(age).millisecondsSinceEpoch,
      'validUntil': (validUntil ?? _now.add(const Duration(hours: 1))).millisecondsSinceEpoch,
    };

/// كل الأدوات والأطر، بدون حدود دنيا
final _everything = SignalProfile.defaults.copyWith(
  symbols: kProductSymbols.toSet(),
  minProbability: 0,
  minRiskReward: 0,
);

Opportunity opp(Map<String, Object?> m) => OpportunityDto.fromJson(Json(m)).toDomain()!;

void main() {
  group('OpportunityDto', () {
    test('parses the web contract and fixes a reversed zone', () {
      final o = opp(raw());
      expect(o.timeframe, Timeframe.h1);
      expect(o.direction, SignalDirection.long);
      expect(o.setupType, SetupType.breakout);
      expect(o.takeProfitZone, const PriceZone(1.10, 1.11));
      expect(o.isDetected, isTrue);
    });

    test('invalid probability, unknown timeframe or missing zone is dropped', () {
      Opportunity? parse(Map<String, Object?> m) => OpportunityDto.fromJson(Json(m)).toDomain();
      expect(parse(raw(probability: 1.4)), isNull);
      expect(parse(raw(tf: '3h')), isNull);
      expect(parse({...raw()}..remove('entryZone')), isNull);
      expect(parse({...raw(), 'riskReward': 0}), isNull);
      expect(parse({...raw(), 'direction': 'up'}), isNull);
    });

    test('unknown setup / risk fall back instead of failing', () {
      final o = opp({...raw(), 'setupType': 'new_kind', 'riskLevel': '??'});
      expect(o.setupType, SetupType.trendFollowing);
      expect(o.riskLevel, RiskLevel.medium);
    });

    test('keeps valid items and drops invalid ones', () {
      final list = opportunitiesFromJson([
        raw(id: 'a'),
        'junk',
        null,
        {...raw(id: 'b'), 'probability': 1.5},
        {...raw(id: 'c')}..remove('validUntil'),
        {...raw(id: 'd'), 'timeframe': '3h'},
        raw(id: 'e', tf: '4h'),
      ]);
      expect(list.map((o) => o.id), ['a', 'e']);
    });

    test('a body that is not a list gives no opportunities', () {
      expect(opportunitiesFromJson({'items': []}), isEmpty);
      expect(opportunitiesFromJson(null), isEmpty);
    });
  });

  group('ModelRead', () {
    test('picks the highest probability and counts timeframes that agree', () {
      final read = ModelRead.from([
        opp(raw(tf: '15m', probability: 0.61)),
        opp(raw(tf: '1h', probability: 0.72)),
        opp(raw(tf: '4h', direction: 'short', probability: 0.65)),
      ], _now);
      expect(read.best!.timeframe, Timeframe.h1);
      expect(read.agreeing, 2);
      expect(read.analysed, 3);
    });

    test('stale and not-detected analyses are never the current read', () {
      final read = ModelRead.from([
        opp(raw(tf: '15m', validUntil: _now.subtract(const Duration(minutes: 1)))),
        opp(raw(tf: '1h', status: 'not_detected', direction: 'neutral')),
      ], _now);
      expect(read.best, isNull);
      expect(read.agreeing, 0);
      expect(read.analysed, 1);
    });
  });

  group('SimulatedSignalsRepository', () {
    final source = SimulatedMarketSource(clock: () => _now);
    final repo = SimulatedSignalsRepository(source: source);

    test('one analysis per model timeframe, deterministic, fresh', () async {
      final a = await repo.opportunities('XAU/USD');
      final b = await SimulatedSignalsRepository(source: SimulatedMarketSource(clock: () => _now))
          .opportunities('XAU/USD');
      expect(a.map((o) => o.timeframe), Timeframe.modelTimeframes);
      expect(a.map((o) => o.id), b.map((o) => o.id));
      expect(a.every((o) => !o.isStale(_now)), isTrue);
    });

    test('zones are on the right side of entry for the direction', () async {
      for (final spec in SimulatedMarketSource.specs) {
        for (final o in await repo.opportunities(spec.symbol)) {
          if (!o.isDetected) continue;
          if (o.direction == SignalDirection.long) {
            expect(o.takeProfitZone.low, greaterThan(o.entryZone.high), reason: o.id);
            expect(o.stopLossZone.high, lessThan(o.entryZone.low), reason: o.id);
          } else {
            expect(o.takeProfitZone.high, lessThan(o.entryZone.low), reason: o.id);
            expect(o.stopLossZone.low, greaterThan(o.entryZone.high), reason: o.id);
          }
          expect(o.probability, inInclusiveRange(0.5, 0.8));
        }
      }
    });

    test('unknown symbol gives no analyses', () async {
      expect(await repo.opportunities('BTC/USD'), isEmpty);
    });

    test('is simulated', () => expect(repo.isSimulated, isTrue));

    test('only the saved strategy, ranked by probability then freshness', () async {
      final feed = await repo.feed(_everything);
      expect(feed, isNotEmpty);
      expect(feed.every((o) => o.isDetected && !o.isStale(_now)), isTrue);
      for (var i = 1; i < feed.length; i++) {
        final a = feed[i - 1], b = feed[i];
        expect(
          a.probability > b.probability ||
              (a.probability == b.probability && !a.generatedAt.isBefore(b.generatedAt)),
          isTrue,
          reason: '${a.id} before ${b.id}',
        );
      }

      final gold = await repo.feed(_everything.copyWith(symbols: {'XAU/USD'}));
      expect(gold.every((o) => o.symbol == 'XAU/USD'), isTrue);
    });

    test('same numbers as the Home / Market model read', () async {
      final feed = await repo.feed(_everything);
      for (final o in feed) {
        final read = await repo.opportunities(o.symbol);
        final same = read.singleWhere((r) => r.id == o.id);
        expect(same.probability, o.probability);
        expect(same.entryZone, o.entryZone);
        expect(same.direction, o.direction);
      }
    });

    test('one signal by id gives the same signal; bad or future ids give null', () async {
      final first = (await repo.feed(_everything)).first;
      final one = await repo.opportunity(first.id);
      expect(one?.id, first.id);
      expect(one?.probability, first.probability);
      expect(one?.takeProfitZone, first.takeProfitZone);
      expect(one?.validUntil, first.validUntil);

      expect(await repo.opportunity('nonsense'), isNull);
      expect(await repo.opportunity('BTC/USD-1h-1'), isNull);
      expect(await repo.opportunity('EUR/USD-1d-1'), isNull);
      final future = _now.add(const Duration(days: 1)).millisecondsSinceEpoch ~/ Duration.millisecondsPerHour;
      expect(await repo.opportunity('EUR/USD-1h-$future'), isNull);
    });
  });

  group('rankSignals', () {
    test('highest probability first, then the fresher one', () {
      final ranked = rankSignals([
        opp(raw(id: 'low', probability: 0.62)),
        opp(raw(id: 'old', probability: 0.75, age: const Duration(hours: 2), validUntil: _now.add(const Duration(hours: 2)))),
        opp(raw(id: 'new', probability: 0.75, age: const Duration(minutes: 10))),
      ], _everything, _now);
      expect(ranked.map((o) => o.id), ['new', 'old', 'low']);
    });

    test('drops what the strategy filters out, neutral reads and stale signals', () {
      final ranked = rankSignals([
        opp(raw(id: 'keep')),
        opp(raw(id: 'other-symbol', symbol: 'NZD/USD')),
        opp(raw(id: 'other-tf', tf: '15m')),
        opp(raw(id: 'short', direction: 'short')),
        opp(raw(id: 'weak', probability: 0.55)),
        opp(raw(id: 'low-rr', riskReward: 1.2)),
        opp(raw(id: 'neutral', direction: 'neutral')),
        opp(raw(id: 'stale', validUntil: _now.add(const Duration(minutes: -1)))),
      ], SignalProfile.defaults.copyWith(
        symbols: {'EUR/USD'},
        timeframes: {Timeframe.h1, Timeframe.h4},
        directions: {SignalDirection.long},
      ), _now);
      expect(ranked.map((o) => o.id), ['keep']);
    });

    test('equal minimum risk/reward passes (no rounding loss)', () {
      final o = opp(raw(riskReward: 1.5));
      expect(matchesSignalProfile(o, SignalProfile.defaults.copyWith(symbols: {'EUR/USD'})), isTrue);
    });
  });

  group('SignalDetail', () {
    const eurusd = Instrument(symbol: 'EUR/USD', kind: MarketKind.forex, precision: 5);

    test('plan distances in pips, risk/reward and the plain-language reasons', () {
      final signal = opp(raw());
      final detail = SignalDetail.of(
        signal,
        instrument: eurusd,
        siblings: [signal, opp(raw(tf: '4h')), opp(raw(tf: '15m', direction: 'short'))],
        now: _now,
      );
      expect(detail.expired, isFalse);
      expect(detail.plan.targetPips, closeTo(200, 1e-6));
      expect(detail.plan.stopPips, closeTo(145, 1e-6));
      expect(detail.plan.riskReward, 2);
      final agreement = detail.rationale.whereType<AgreementReason>().single;
      expect((agreement.agreeing, agreement.analysed), (2, 3));
      expect(detail.rationale.whereType<ChanceReason>().single.outOfTen, 7);
    });

    test('expired at open and markExpired', () {
      final stale = opp(raw(validUntil: _now.add(const Duration(minutes: -1))));
      expect(SignalDetail.of(stale, instrument: eurusd, siblings: null, now: _now).expired, isTrue);

      final fresh = SignalDetail.of(opp(raw()), instrument: eurusd, siblings: null, now: _now);
      expect(fresh.rationale.whereType<AgreementReason>(), isEmpty);
      expect(fresh.markExpired().expired, isTrue);
      expect(fresh.markExpired().validUntil, fresh.validUntil);
    });
  });
}
