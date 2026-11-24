// اختبارات طبقة بيانات السوق: تحويل DTO → domain بأمان، والمصدر المحاكى
// (حتمي، متّسق بين الأطر، بمقاييس أسعار واقعية)، والـ repository، والنبضات.

import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/core/data/json.dart';
import 'package:trading_app/features/markets/data/market_data_repository.dart';
import 'package:trading_app/features/markets/data/market_dtos.dart';
import 'package:trading_app/features/markets/data/simulated_market_source.dart';
import 'package:trading_app/features/markets/models/market_models.dart';

final _now = DateTime.utc(2026, 10, 21, 14, 5, 30);

void main() {
  group('Json safe reads', () {
    test('wrong types return null instead of throwing', () {
      const j = Json({'a': 'x', 'b': true, 'c': [1], 'n': 'NaN', 'i': 2.5});
      expect(j.number('a'), isNull);
      expect(j.number('n'), isNull);
      expect(j.integer('i'), isNull);
      expect(j.string('c'), isNull);
      expect(j.dateTime('missing'), isNull);
      expect(j.objects('a'), isEmpty);
      expect(Json.from('not a map'), isNull);
    });

    test('numbers in strings and unix seconds are accepted', () {
      const j = Json({'p': '1.5', 'i': '7', 't': 1700000000});
      expect(j.number('p'), 1.5);
      expect(j.integer('i'), 7);
      expect(j.dateTime('t'), DateTime.utc(2023, 11, 14, 22, 13, 20));
    });
  });

  group('DTO → domain', () {
    test('instrument: backend InstrumentRead shape', () {
      final i = InstrumentDto.fromJson(const Json({
        'id': 'b7c1',
        'symbol': ' eur/usd ',
        'market': 'forex',
        'price_precision': 5,
        'is_active': true,
      })).toDomain();
      expect(i, isNotNull);
      expect(i!.symbol, 'EUR/USD');
      expect(i.kind, MarketKind.forex);
      expect(i.format(1.087624), '1.08762');
    });

    test('instrument: inactive, out-of-scope market or bad symbol are dropped', () {
      Instrument? parse(Map<String, Object?> m) => InstrumentDto.fromJson(Json(m)).toDomain();
      expect(parse({'symbol': 'EUR/USD', 'market': 'forex', 'is_active': false}), isNull);
      expect(parse({'symbol': 'BTC/USDT', 'market': 'crypto'}), isNull);
      expect(parse({'symbol': 'EURUSD', 'market': 'forex'}), isNull);
      expect(parse({'market': 'forex'}), isNull);
    });

    test('instrument: missing precision falls back per symbol', () {
      Instrument parse(String s, String m) =>
          InstrumentDto.fromJson(Json({'symbol': s, 'market': m})).toDomain()!;
      expect(parse('USD/JPY', 'forex').precision, 3);
      expect(parse('XAU/USD', 'commodity').precision, 2);
      expect(parse('GBP/USD', 'forex').precision, 5);
    });

    test('candles: invalid rows are dropped, order and duplicates fixed', () {
      final candles = candlesFromJson(const Json({
        'candles': [
          {'time': 120, 'open': 1, 'high': 2, 'low': 0.5, 'close': 1.5, 'volume': 3},
          {'time': 60, 'open': 1, 'high': 2, 'low': 0.5, 'close': 1.2, 'volume': 1},
          {'time': 60, 'open': 1, 'high': 2, 'low': 0.5, 'close': 1.3, 'volume': 1}, // نفس الوقت
          {'time': 180, 'open': 1, 'high': 0.9, 'low': 0.5, 'close': 0.8}, // high < open
          {'time': 240, 'open': 1, 'high': 2, 'low': 3, 'close': 1.5}, // high < low
          {'time': 300, 'open': 'x', 'high': 2, 'low': 0.5, 'close': 1}, // نوع غلط
          {'open': 1, 'high': 2, 'low': 0.5, 'close': 1}, // بدون وقت
          'garbage',
        ],
      }));
      expect(candles.map((c) => c.time.millisecondsSinceEpoch ~/ 1000), [60, 120]);
      expect(candles.first.close, 1.3);
    });

    test('candles: missing or negative volume becomes 0', () {
      final c = CandleDto.fromJson(const Json({'time': 60, 'open': 1, 'high': 1, 'low': 1, 'close': 1, 'volume': -4}))
          .toDomain();
      expect(c!.volume, 0);
    });

    test('quote: missing reference means no change (not an invented number)', () {
      final q = QuoteDto.fromJson(const Json({'symbol': 'EUR/USD', 'price': 1.1, 'time': 100})).toDomain();
      expect(q!.changePercent, 0);
      expect(QuoteDto.fromJson(const Json({'symbol': 'EUR/USD', 'price': -1, 'time': 1})).toDomain(), isNull);
      expect(QuoteDto.fromJson(const Json({'price': 1, 'time': 1})).toDomain(), isNull);
    });
  });

  group('SimulatedMarketSource', () {
    final source = SimulatedMarketSource(clock: () => _now);

    test('deterministic: the same moment always gives the same price', () {
      final other = SimulatedMarketSource(clock: () => _now);
      for (final s in SimulatedMarketSource.specs) {
        expect(source.priceAt(s.symbol, _now), other.priceAt(s.symbol, _now));
      }
      expect(source.candlesJson('EUR/USD', Timeframe.h1), other.candlesJson('EUR/USD', Timeframe.h1));
    });

    test('realistic scale per instrument (within ±25% of the base price)', () {
      for (final s in SimulatedMarketSource.specs) {
        for (final days in [0, 30, 365]) {
          final p = source.priceAt(s.symbol, _now.subtract(Duration(days: days)));
          expect(p, inInclusiveRange(s.base * 0.75, s.base * 1.25), reason: '${s.symbol} -$days d');
        }
      }
      // 24 ساعة: تغيّر يومي معقول (< 5%)
      final q = source.quotesJson().first;
      final change = ((q['price']! as double) / (q['reference']! as double) - 1).abs();
      expect(change, lessThan(0.05));
    });

    test('candles are valid OHLC, ascending, one per bucket, last ends at now', () {
      for (final tf in Timeframe.values) {
        final candles = candlesFromJson(Json(source.candlesJson('XAU/USD', tf, limit: 120)));
        expect(candles, hasLength(120), reason: tf.label);
        for (var i = 1; i < candles.length; i++) {
          expect(candles[i].time.difference(candles[i - 1].time), tf.duration);
        }
        expect(candles.last.time, tf.bucketStart(_now));
        expect(candles.last.close, closeTo(source.priceAt('XAU/USD', _now), 0.01));
      }
    });

    test('timeframes agree: a closed 1h candle closes where the 15m candle at that time closes', () {
      final h1 = candlesFromJson(Json(source.candlesJson('EUR/USD', Timeframe.h1, limit: 5)));
      final m15 = candlesFromJson(Json(source.candlesJson('EUR/USD', Timeframe.m15, limit: 20)));
      final closedHour = h1[h1.length - 2];
      final lastQuarterOfThatHour = m15.firstWhere(
        (c) => c.time == closedHour.time.add(const Duration(minutes: 45)),
      );
      expect(lastQuarterOfThatHour.close, closedHour.close);
    });

    test('prices are rounded to the instrument precision', () {
      final candle = (source.candlesJson('USD/JPY', Timeframe.m1, limit: 1)['candles']! as List).first as Map;
      final close = candle['close']! as double;
      expect(close, double.parse(close.toStringAsFixed(3)));
    });

    test('unknown symbol gives no candles and NaN price', () {
      expect((source.candlesJson('BTC/USD', Timeframe.h1)['candles']! as List), isEmpty);
      expect(source.priceAt('BTC/USD', _now).isNaN, isTrue);
    });

    test('limit is clamped to a sane range', () {
      expect((source.candlesJson('EUR/USD', Timeframe.m1, limit: 0)['candles']! as List), hasLength(1));
      expect(
        (source.candlesJson('EUR/USD', Timeframe.m1, limit: 99999)['candles']! as List),
        hasLength(SimulatedMarketSource.maxCandles),
      );
    });
  });

  group('SimulatedMarketDataRepository', () {
    test('maps through the DTO layer: 8 instruments, gold and FX precision', () async {
      final repo = SimulatedMarketDataRepository(source: SimulatedMarketSource(clock: () => _now));
      final instruments = await repo.instruments();
      expect(instruments.map((i) => i.symbol), contains('XAU/USD'));
      expect(instruments, hasLength(8));
      expect(instruments.firstWhere((i) => i.symbol == 'XAU/USD').kind, MarketKind.commodity);
      expect(repo.isSimulated, isTrue);
      final quotes = await repo.quotes();
      expect(quotes, hasLength(8));
    });

    test('quotes match the last candle close (one source for every screen)', () async {
      final repo = SimulatedMarketDataRepository(source: SimulatedMarketSource(clock: () => _now));
      final quote = (await repo.quotes()).firstWhere((q) => q.symbol == 'GBP/USD');
      final candles = await repo.candles('GBP/USD', Timeframe.m15);
      expect(candles.last.close, quote.price);
    });

    test('ticks emit fresh prices as time moves', () async {
      var t = _now;
      final repo = SimulatedMarketDataRepository(
        source: SimulatedMarketSource(clock: () => t),
        tickInterval: const Duration(milliseconds: 10),
      );
      final first = (await repo.quotes()).first;
      t = t.add(const Duration(minutes: 3));
      final batch = await repo.ticks().first;
      final next = batch.firstWhere((q) => q.symbol == first.symbol);
      expect(next.time.isAfter(first.time), isTrue);
      expect(next.price, isNot(first.price));
    });
  });
}
