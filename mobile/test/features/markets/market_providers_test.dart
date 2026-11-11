// اختبارات منطق الـ providers: دمج النبضات بالشموع، دمج الأسعار (الأحدث بيربح)،
// إيقاف النبضات بدون اتصال، وحالة التدفّق.

import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/features/markets/data/market_data_repository.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/markets/models/market_models.dart';

import '../../helpers/test_app.dart';

Candle candle(DateTime t, double c) => Candle(time: t, open: c, high: c, low: c, close: c, volume: 1);
Quote quote(String s, double p, DateTime t) => Quote(symbol: s, price: p, reference: p, time: t);

/// repository وهمي بنبضات يدوية
final class ManualRepo implements MarketDataRepository {
  final controller = StreamController<List<Quote>>.broadcast();
  List<Quote> snapshot = [];
  int quoteCalls = 0;

  @override
  bool get isSimulated => true;
  @override
  Future<List<Instrument>> instruments() async => const [];
  @override
  Future<List<Candle>> candles(String symbol, Timeframe timeframe, {int limit = 300}) async => const [];
  @override
  Future<List<Quote>> quotes() async {
    quoteCalls++;
    return snapshot;
  }

  @override
  Stream<List<Quote>> ticks() => controller.stream;
}

void main() {
  // appActiveProvider بيسمع لحالة التطبيق (AppLifecycleListener) - بدها binding
  TestWidgetsFlutterBinding.ensureInitialized();

  final t0 = DateTime.utc(2026, 10, 21, 14);

  group('mergeTick', () {
    final candles = [candle(t0, 1.0), candle(t0.add(const Duration(hours: 1)), 1.1)];
    final lastStart = t0.add(const Duration(hours: 1));

    test('same bucket updates close and widens high/low', () {
      final up = mergeTick(candles, quote('X', 1.3, lastStart.add(const Duration(minutes: 5))), Timeframe.h1)!;
      expect(up.length, 2);
      expect(up.last.close, 1.3);
      expect(up.last.high, 1.3);
      final down = mergeTick(up, quote('X', 0.9, lastStart.add(const Duration(minutes: 6))), Timeframe.h1)!;
      expect(down.last.low, 0.9);
      expect(down.last.high, 1.3);
      expect(down.last.open, 1.1);
    });

    test('unchanged price or an older tick returns the same list (no rebuild)', () {
      expect(identical(mergeTick(candles, quote('X', 1.1, lastStart), Timeframe.h1), candles), isTrue);
      expect(identical(mergeTick(candles, quote('X', 5, t0.subtract(const Duration(hours: 3))), Timeframe.h1), candles),
          isTrue);
    });

    test('the next bucket appends a candle opening at the previous close', () {
      final next = mergeTick(candles, quote('X', 1.2, lastStart.add(const Duration(hours: 1))), Timeframe.h1)!;
      expect(next.length, 3);
      expect(next.last.open, 1.1);
      expect(next.last.close, 1.2);
      expect(next.last.time, lastStart.add(const Duration(hours: 1)));
    });

    test('keeps at most maxLength candles', () {
      final next = mergeTick(candles, quote('X', 1.2, lastStart.add(const Duration(hours: 1))), Timeframe.h1,
          maxLength: 2)!;
      expect(next.length, 2);
      expect(next.first.time, lastStart);
    });

    test('a gap of more than one bucket asks for a reload (null)', () {
      expect(mergeTick(candles, quote('X', 1.2, lastStart.add(const Duration(hours: 3))), Timeframe.h1), isNull);
    });
  });

  group('mergeNewerQuotes', () {
    test('newer wins, older is ignored, unchanged keeps the same map', () {
      final current = {'A': quote('A', 1, t0)};
      final newer = mergeNewerQuotes(current, [quote('A', 2, t0.add(const Duration(seconds: 1)))]);
      expect(newer['A']!.price, 2);
      final stale = mergeNewerQuotes(newer, [quote('A', 9, t0)]);
      expect(identical(stale, newer), isTrue);
      expect(identical(mergeNewerQuotes(newer, [newer['A']!]), newer), isTrue);
      expect(mergeNewerQuotes(current, [quote('B', 3, t0)]).keys, containsAll(['A', 'B']));
    });
  });

  group('liveQuotesProvider', () {
    late ManualRepo repo;
    late ProviderContainer container;

    setUp(() {
      repo = ManualRepo()..snapshot = [quote('EUR/USD', 1.0, t0)];
      container = ProviderContainer(overrides: [connectivityOverride(), marketDataRepositoryProvider.overrideWithValue(repo)]);
      addTearDown(container.dispose);
    });

    test('snapshot first, then ticks merge in', () async {
      container.listen(liveQuotesProvider, (_, __) {});
      expect(container.read(feedStatusProvider), FeedStatus.connecting);
      await container.read(liveQuotesProvider.future);
      expect(container.read(quoteProvider('EUR/USD'))!.price, 1.0);
      expect(container.read(feedStatusProvider), FeedStatus.live);

      repo.controller.add([quote('EUR/USD', 1.01, t0.add(const Duration(seconds: 2)))]);
      await Future<void>.delayed(Duration.zero);
      expect(container.read(quoteProvider('EUR/USD'))!.price, 1.01);
    });

    test('offline keeps the last prices and ignores ticks until back online', () async {
      container.listen(liveQuotesProvider, (_, __) {});
      await container.read(liveQuotesProvider.future);

      container.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      await container.read(liveQuotesProvider.future);
      expect(container.read(feedStatusProvider), FeedStatus.offline);
      repo.controller.add([quote('EUR/USD', 2.0, t0.add(const Duration(seconds: 5)))]);
      await Future<void>.delayed(Duration.zero);
      expect(container.read(quoteProvider('EUR/USD'))!.price, 1.0);
      expect(repo.quoteCalls, 1, reason: 'no new request while offline');

      container.read(networkStatusProvider.notifier).set(NetworkStatus.online);
      await container.read(liveQuotesProvider.future);
      repo.controller.add([quote('EUR/USD', 1.5, t0.add(const Duration(seconds: 9)))]);
      await Future<void>.delayed(Duration.zero);
      expect(container.read(quoteProvider('EUR/USD'))!.price, 1.5);
    });

    test('a refresh never overwrites a newer tick with an older snapshot', () async {
      container.listen(liveQuotesProvider, (_, __) {});
      await container.read(liveQuotesProvider.future);
      repo.controller.add([quote('EUR/USD', 1.2, t0.add(const Duration(seconds: 10)))]);
      await Future<void>.delayed(Duration.zero);
      repo.snapshot = [quote('EUR/USD', 0.5, t0.add(const Duration(seconds: 1)))];
      await container.read(liveQuotesProvider.notifier).refresh();
      expect(container.read(quoteProvider('EUR/USD'))!.price, 1.2);
    });

    test('a failing tick stream marks the feed as error but keeps prices', () async {
      container.listen(liveQuotesProvider, (_, __) {});
      await container.read(liveQuotesProvider.future);
      repo.controller.addError(StateError('socket closed'));
      await Future<void>.delayed(Duration.zero);
      expect(container.read(feedStatusProvider), FeedStatus.error);
      expect(container.read(quoteProvider('EUR/USD')), isNotNull);
    });

    test('in the background ticks stop and prices stay; back in front they resume', () async {
      final binding = TestWidgetsFlutterBinding.instance;
      void go(List<AppLifecycleState> states) => states.forEach(binding.handleAppLifecycleStateChanged);
      container.listen(liveQuotesProvider, (_, __) {});
      await container.read(liveQuotesProvider.future);

      go(const [AppLifecycleState.inactive, AppLifecycleState.hidden, AppLifecycleState.paused]);
      await container.read(liveQuotesProvider.future);
      expect(repo.controller.hasListener, isFalse, reason: 'no tick subscription in the background');
      repo.controller.add([quote('EUR/USD', 2.0, t0.add(const Duration(seconds: 5)))]);
      await Future<void>.delayed(Duration.zero);
      expect(container.read(quoteProvider('EUR/USD'))!.price, 1.0);
      expect(repo.quoteCalls, 1, reason: 'the last prices stay, nothing is refetched');

      // ستارة الإشعارات (inactive) ما بتوقف شي
      go(const [AppLifecycleState.hidden, AppLifecycleState.inactive]);
      await container.read(liveQuotesProvider.future);
      expect(repo.controller.hasListener, isTrue);
      repo.controller.add([quote('EUR/USD', 1.5, t0.add(const Duration(seconds: 9)))]);
      await Future<void>.delayed(Duration.zero);
      expect(container.read(quoteProvider('EUR/USD'))!.price, 1.5);
      go(const [AppLifecycleState.resumed]);
    });
  });
}
