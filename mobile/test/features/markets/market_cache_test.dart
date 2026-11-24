// H5a: كاش السوق بـ Drift (بالذاكرة): الكتابة مع القراءة، الرجوع للكاش لما
// المصدر يفشل أو ما في اتصال، التقليم، كتابة النبضات المحدودة، إصلاح الملف
// المضروب، حدّ "Old data"، والمفتاح مطفي = متل قبل.

import 'dart:async';
import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/database/app_database.dart';
import 'package:trading_app/core/database/app_database_holder.dart';
import 'package:trading_app/features/markets/data/caching_market_data_repository.dart';
import 'package:trading_app/features/markets/data/market_cache.dart';
import 'package:trading_app/features/markets/data/market_data_repository.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/markets/data/simulated_market_source.dart';
import 'package:trading_app/features/markets/models/market_models.dart';

import '../../helpers/test_app.dart';

/// مصدر بنتحكّم فيه: بيعدّ الطلبات، بيفشل لما [fail]، ونبضات يدوية
final class ControlledSource implements MarketDataRepository {
  ControlledSource() : _sim = SimulatedMarketDataRepository(source: SimulatedMarketSource(clock: () => kTestNow));

  final SimulatedMarketDataRepository _sim;
  final ticksController = StreamController<List<Quote>>.broadcast();
  bool fail = false;
  int calls = 0;

  Future<T> _call<T>(Future<T> Function() f) {
    calls++;
    if (fail) return Future.error(const SocketException('down'));
    return f();
  }

  @override
  bool get isSimulated => true;
  @override
  Future<List<Instrument>> instruments() => _call(_sim.instruments);
  @override
  Future<List<Quote>> quotes() => _call(_sim.quotes);
  @override
  Future<List<Candle>> candles(String symbol, Timeframe timeframe, {int limit = 300}) =>
      _call(() => _sim.candles(symbol, timeframe, limit: limit));
  @override
  Stream<List<Quote>> ticks() => ticksController.stream;
}

Candle candleAt(DateTime t, double c) => Candle(time: t, open: c, high: c, low: c, close: c, volume: 1);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late AppDatabaseHolder db;
  late MarketCache cache;
  late ControlledSource source;
  late FakeClock clock;
  var offline = false;

  CachingMarketDataRepository repo({Duration tickWriteInterval = const Duration(seconds: 5)}) =>
      CachingMarketDataRepository(
        source: source,
        cache: cache,
        isOffline: () => offline,
        clock: clock.call,
        tickWriteInterval: tickWriteInterval,
      );

  setUp(() {
    db = AppDatabaseHolder.memory();
    cache = MarketCache(db);
    source = ControlledSource();
    clock = FakeClock();
    offline = false;
  });
  tearDown(() => db.close());

  group('write-through', () {
    test('quotes and candles from the source are saved with the write time', () async {
      final r = repo();
      final quotes = await r.quotes();
      final candles = await r.candles('EUR/USD', Timeframe.h1, limit: 50);
      await r.flushWrites();

      final savedQuotes = (await cache.readQuotes())!;
      expect(savedQuotes.value.map((q) => q.symbol), unorderedEquals(quotes.map((q) => q.symbol)));
      expect(savedQuotes.value.firstWhere((q) => q.symbol == 'EUR/USD').price,
          quotes.firstWhere((q) => q.symbol == 'EUR/USD').price);
      expect(savedQuotes.updatedAt, kTestNow);

      final savedCandles = (await cache.readCandles('EUR/USD', Timeframe.h1))!;
      expect(savedCandles.value.length, candles.length);
      expect(savedCandles.value.last.time, candles.last.time);
      expect(savedCandles.value.last.close, candles.last.close);
      expect(r.servingCache.value, isFalse);
    });

    test('24h change survives the round trip', () async {
      final r = repo();
      final quotes = await r.quotes();
      await r.flushWrites();
      final saved = (await cache.readQuotes())!.value;
      for (final q in quotes) {
        final s = saved.firstWhere((x) => x.symbol == q.symbol);
        expect(s.changePercent, closeTo(q.changePercent, 1e-9));
        expect(s.time, q.time);
      }
    });
  });

  group('read when the source fails', () {
    test('online + source error → saved data, marked as serving cache', () async {
      final r = repo();
      final fresh = await r.quotes();
      await r.candles('XAU/USD', Timeframe.m15);
      await r.flushWrites();

      source.fail = true;
      final fromCache = await r.quotes();
      expect(fromCache.map((q) => q.price), unorderedEquals(fresh.map((q) => q.price)));
      expect(r.servingCache.value, isTrue);
      expect(await r.candles('XAU/USD', Timeframe.m15), isNotEmpty);

      // المصدر رجع: مش من الكاش
      source.fail = false;
      await r.quotes();
      expect(r.servingCache.value, isFalse);
    });

    test('source error and nothing saved → the original error', () async {
      source.fail = true;
      await expectLater(repo().quotes(), throwsA(isA<SocketException>()));
      await expectLater(repo().candles('EUR/USD', Timeframe.h1), throwsA(isA<SocketException>()));
    });

    test('offline: the source is never asked; saved data or MarketOfflineException', () async {
      final r = repo();
      await r.quotes();
      await r.flushWrites();
      final before = source.calls;

      offline = true;
      expect(await r.quotes(), hasLength(8));
      final instruments = await r.instruments();
      expect(instruments.map((i) => i.symbol).toList(), kProductSymbols);
      expect(instruments.firstWhere((i) => i.symbol == 'USD/JPY').precision, 3);
      await expectLater(r.candles('EUR/USD', Timeframe.d1), throwsA(isA<MarketOfflineException>()));
      expect(source.calls, before);
    });

    test('offline with an empty cache → MarketOfflineException everywhere', () async {
      offline = true;
      final r = repo();
      await expectLater(r.quotes(), throwsA(isA<MarketOfflineException>()));
      await expectLater(r.instruments(), throwsA(isA<MarketOfflineException>()));
      expect(source.calls, 0);
    });
  });

  group('pruning', () {
    test('keeps only the newest candles per series, upserts without duplicates', () async {
      final small = MarketCache(db, maxCandlesPerSeries: 5);
      final t0 = DateTime.utc(2026, 10, 21);
      List<Candle> series(int from, int to) => [
            for (var i = from; i < to; i++) candleAt(t0.add(Duration(hours: i)), 1 + i / 100),
          ];

      await small.saveCandles('EUR/USD', Timeframe.h1, series(0, 8), kTestNow);
      expect(await small.candleCount('EUR/USD', Timeframe.h1), 5);
      final kept = (await small.readCandles('EUR/USD', Timeframe.h1))!.value;
      expect(kept.first.time, t0.add(const Duration(hours: 3)));
      expect(kept.last.time, t0.add(const Duration(hours: 7)));

      // نفس الشموع (آخر وحدة تغيّرت) + وحدة جديدة
      await small.saveCandles('EUR/USD', Timeframe.h1, [...series(6, 8), candleAt(t0.add(const Duration(hours: 8)), 9)],
          kTestNow);
      expect(await small.candleCount('EUR/USD', Timeframe.h1), 5);
      expect((await small.readCandles('EUR/USD', Timeframe.h1))!.value.last.close, 9);

      // سلسلة تانية ما بتتأثّر
      await small.saveCandles('EUR/USD', Timeframe.m15, series(0, 2), kTestNow);
      expect(await small.candleCount('EUR/USD', Timeframe.m15), 2);
      expect(await small.candleCount('EUR/USD', Timeframe.h1), 5);
    });

    test('the app keeps as many candles as the chart loads', () {
      final container = ProviderContainer(overrides: cachedMarketOverrides(db: db));
      addTearDown(container.dispose);
      expect(container.read(marketCacheProvider).maxCandlesPerSeries, LiveCandlesNotifier.limit);
    });
  });

  group('throttled tick writes', () {
    test('at most one write per interval, the rest on cancel', () async {
      final r = repo();
      final received = <List<Quote>>[];
      final sub = r.ticks().listen(received.add);
      Quote q(String s, double p) => Quote(symbol: s, price: p, reference: p, time: clock.now);

      source.ticksController.add([q('EUR/USD', 1.1)]);
      await pumpEventQueue();
      expect(r.tickWrites, 1); // أول نبضة بتنكتب فورًا

      for (var i = 0; i < 10; i++) {
        clock.advance(const Duration(milliseconds: 400));
        source.ticksController.add([q('EUR/USD', 1.1 + i / 1000), q('XAU/USD', 2400.0 + i)]);
        await pumpEventQueue();
      }
      expect(received, hasLength(11)); // كل النبضات وصلت للشاشة
      expect(r.tickWrites, 1); // 4 ثواني بس

      clock.advance(const Duration(seconds: 1));
      source.ticksController.add([q('GBP/USD', 1.3)]);
      await pumpEventQueue();
      expect(r.tickWrites, 2);

      clock.advance(const Duration(seconds: 1));
      source.ticksController.add([q('EUR/USD', 1.2)]);
      await pumpEventQueue();
      expect(r.tickWrites, 2);

      await sub.cancel();
      await r.flushWrites();
      expect(r.tickWrites, 3); // الباقي انكتب لما الاشتراك تسكّر
      final saved = (await cache.readQuotes())!.value;
      expect(saved.firstWhere((x) => x.symbol == 'EUR/USD').price, 1.2);
      expect(saved.firstWhere((x) => x.symbol == 'XAU/USD').price, 2409.0);
    });
  });

  group('corruption recovery', () {
    late Directory dir;
    setUp(() async => dir = await Directory.systemTemp.createTemp('market_cache_test'));
    tearDown(() async {
      if (await dir.exists()) await dir.delete(recursive: true);
    });

    AppDatabaseHolder fileHolder(File file) => AppDatabaseHolder(
          open: () => AppDatabase(NativeDatabase(file)),
          deleteStorage: () async {
            if (await file.exists()) await file.delete();
          },
        );

    test('a file that is not a database is deleted and rebuilt once', () async {
      final file = File('${dir.path}/cache.sqlite');
      await file.writeAsString('this is not a database ' * 400);
      final holder = fileHolder(file);
      addTearDown(holder.close);
      final c = MarketCache(holder);

      await c.saveQuotes([Quote(symbol: 'EUR/USD', price: 1.1, reference: 1.0, time: kTestNow)], kTestNow);
      expect(holder.recoveries, 1);
      expect((await c.readQuotes())!.value.single.price, 1.1);
    });

    test('still broken after a rebuild → cache off for the session, the app keeps working', () async {
      final holder = AppDatabaseHolder(open: () => throw const CorruptDatabaseException('bad'));
      addTearDown(holder.close);
      final r = CachingMarketDataRepository(source: source, cache: MarketCache(holder), isOffline: () => false);

      expect(await r.quotes(), hasLength(8)); // من المصدر، الكتابة فشلت بصمت
      await r.flushWrites();
      await expectLater(MarketCache(holder).readQuotes(), throwsA(isA<CacheUnavailableException>()));
      source.fail = true;
      await expectLater(r.quotes(), throwsA(isA<SocketException>())); // ما في كاش = الخطأ الأصلي
    });

    test('isCorruptionError: malformed / not a database only', () {
      expect(isCorruptionError(const CorruptDatabaseException('x')), isTrue);
      expect(isCorruptionError(Exception('database disk image is malformed')), isTrue);
      expect(isCorruptionError(Exception('file is not a database')), isTrue);
      expect(isCorruptionError(Exception('disk full')), isFalse);
    });
  });

  group('"Old data" threshold (24 h)', () {
    test('exactly 24 h is not old, a millisecond later is', () {
      expect(isOldData(kTestNow, kTestNow.add(const Duration(hours: 23))), isFalse);
      expect(isOldData(kTestNow, kTestNow.add(kCacheOldAfter)), isFalse);
      expect(isOldData(kTestNow, kTestNow.add(kCacheOldAfter + const Duration(milliseconds: 1))), isTrue);
      expect(kCacheOldAfter, const Duration(hours: 24));
    });
  });

  test('clear empties quotes and candles', () async {
    final r = repo();
    await r.quotes();
    await r.candles('EUR/USD', Timeframe.h1);
    await r.flushWrites();
    await cache.clear();
    expect(await cache.readQuotes(), isNull);
    expect(await cache.readCandles('EUR/USD', Timeframe.h1), isNull);
  });

  group('providers', () {
    ProviderContainer containerWith({required bool enabled, required bool offlineAtStart}) {
      final container = ProviderContainer(overrides: [
        connectivityOverride(),
        ...cachedMarketOverrides(db: db, source: source, enabled: enabled),
        if (offlineAtStart) simulatedOfflineProvider.overrideWith((ref) => true),
      ]);
      addTearDown(container.dispose);
      return container;
    }

    test('flag on: the repository is the caching layer', () {
      expect(kMarketOfflineCache, isTrue);
      final c = containerWith(enabled: true, offlineAtStart: false);
      expect(c.read(marketDataRepositoryProvider), isA<CachingMarketDataRepository>());
    });

    test('flag off: the source itself, no saved-data state, offline keeps working as before', () async {
      final c = containerWith(enabled: false, offlineAtStart: true);
      expect(c.read(marketDataRepositoryProvider), same(source));
      expect(c.read(marketShowingSavedProvider), isFalse);
      // بدون اتصال المصدر بينطلب متل قبل (المحاكاة بتشتغل)
      expect(await c.read(liveQuotesProvider.future), hasLength(8));
      expect(c.read(feedStatusProvider), FeedStatus.offline);
      // رجوع الاتصال ما بيجيب لقطة جديدة (متل قبل H5a)
      final calls = source.calls;
      c.read(networkStatusProvider.notifier).set(NetworkStatus.online);
      await c.read(liveQuotesProvider.future);
      await pumpEventQueue();
      expect(source.calls, calls);
    });

    test('flag on: offline from saved data, back online fetches a fresh snapshot by itself', () async {
      await cache.saveQuotes(await source.quotes(), kTestNow.subtract(const Duration(hours: 2)));
      final c = containerWith(enabled: true, offlineAtStart: true);
      final sub = c.listen(liveQuotesProvider, (_, __) {});
      addTearDown(sub.close);
      final calls = source.calls;

      expect(await c.read(liveQuotesProvider.future), hasLength(8));
      expect(source.calls, calls);
      expect(c.read(marketShowingSavedProvider), isTrue);
      expect(c.read(latestQuoteTimeProvider), isNotNull);

      c.read(networkStatusProvider.notifier).set(NetworkStatus.online);
      await pumpEventQueue();
      await c.read(liveQuotesProvider.future);
      await pumpEventQueue();
      expect(source.calls, greaterThan(calls));
      expect(c.read(marketShowingSavedProvider), isFalse);
    });

    test('online but the source fails → feed says Stale, never Live', () async {
      await cache.saveQuotes(await source.quotes(), kTestNow);
      source.fail = true;
      final c = containerWith(enabled: true, offlineAtStart: false);
      final sub = c.listen(feedStatusProvider, (_, __) {});
      addTearDown(sub.close);
      await c.read(liveQuotesProvider.future);
      await pumpEventQueue();
      expect(c.read(feedStatusProvider), FeedStatus.stale);
      expect(c.read(marketShowingSavedProvider), isTrue);
    });
  });
}
