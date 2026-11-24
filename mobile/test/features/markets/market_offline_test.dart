// H5a: الواجهة بدون اتصال فوق كاش السوق (Drift بالذاكرة): Home والـ Market
// بيانات محفوظة ("Last updated" + شارة Offline، "Old data" بعد 24س، الرسم من
// الشموع المحفوظة)، ما في كاش + بدون اتصال = حالة الـ offline، رجوع الاتصال
// بيحدّث لحالو، سحب التحديث بيقول ليش، المفتاح مطفي = متل قبل، ومسح الكاش.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/database/app_database_holder.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/core/widgets/source_tag.dart';
import 'package:trading_app/features/home/views/home_screen.dart';
import 'package:trading_app/features/home/widgets/watchlist_row.dart';
import 'package:trading_app/features/markets/data/market_cache.dart';
import 'package:trading_app/features/markets/data/market_data_repository.dart';
import 'package:trading_app/features/markets/data/simulated_market_source.dart';
import 'package:trading_app/features/markets/models/market_models.dart';
import 'package:trading_app/features/markets/views/market_screen.dart';
import 'package:trading_app/features/markets/widgets/last_updated_line.dart';
import 'package:trading_app/features/markets/widgets/price_chart.dart';
import 'package:trading_app/features/settings/views/settings_screen.dart';

import '../../helpers/test_app.dart';

/// عملية Drift جوّا الوقت الوهمي تبع testWidgets: منقدّم الوقت لحد ما تخلص.
/// (القاعدة لازم تنفتح وتنستعمل بنفس الـ zone: مفتوحة بـ runAsync بتعلق هون.)
Future<T> settle<T>(WidgetTester tester, Future<T> future) async {
  var done = false;
  late T value;
  Object? error;
  future.then((v) {
    value = v;
    done = true;
  }, onError: (Object e) {
    error = e;
    done = true;
  });
  for (var i = 0; i < 200 && !done; i++) {
    await tester.pump(const Duration(milliseconds: 10));
  }
  if (!done) fail('Drift call did not finish');
  if (error != null) throw error!;
  return value;
}

AppDatabaseHolder emptyCache() {
  final db = AppDatabaseHolder.memory();
  // ما منستنّى: بعد ما يخلص الاختبار الوقت الوهمي واقف، والإغلاق بيعلق
  addTearDown(() => unawaited(db.close()));
  return db;
}

/// كاش فيه أسعار الأدوات الـ 8 (وقتها [at]) وشموع ساعة لكل أداة
Future<AppDatabaseHolder> savedCache(WidgetTester tester, {DateTime? at}) async {
  final db = emptyCache();
  final cache = MarketCache(db);
  final sim = SimulatedMarketDataRepository(source: SimulatedMarketSource(clock: () => at ?? kTestNow));
  await settle(tester, cache.saveQuotes(await sim.quotes(), at ?? kTestNow));
  for (final symbol in kProductSymbols) {
    await settle(tester, cache.saveCandles(symbol, Timeframe.h1, await sim.candles(symbol, Timeframe.h1), at ?? kTestNow));
  }
  return db;
}

Future<ProviderContainer> pumpOffline(
  WidgetTester tester,
  Widget screen, {
  required AppDatabaseHolder db,
  bool offline = true,
  bool enabled = true,
  String locale = 'en',
  String theme = 'light',
  double height = 1000,
}) async {
  usePhoneSize(tester, height: height);
  await tester.pumpWidget(await testScope(
    TestApp(home: screen),
    locale: locale,
    prefs: {themeModeStorageKey: theme},
    overrides: [
      ...cachedMarketOverrides(db: db, enabled: enabled),
      if (offline) simulatedOfflineProvider.overrideWith((ref) => true),
    ],
  ));
  await tester.pumpAndSettle();
  return ProviderScope.containerOf(tester.element(find.byWidget(screen)));
}

Future<void> goOnline(WidgetTester tester, ProviderContainer container) async {
  container.read(networkStatusProvider.notifier).set(NetworkStatus.online);
  await tester.pumpAndSettle();
  await tester.pump(const Duration(milliseconds: 100));
  await tester.pumpAndSettle();
}

void main() {
  group('Home', () {
    testWidgets('offline with saved prices: rows, Offline pill, "Last updated", Simulated stays', (tester) async {
      await pumpOffline(tester, const HomeScreen(), db: await savedCache(tester));

      expect(find.byType(WatchlistRow), findsNWidgets(8));
      expect(find.text('Offline'), findsOneWidget);
      expect(find.textContaining('Last updated'), findsOneWidget);
      expect(find.text('Old data'), findsNothing);
      expect(find.byType(SourceTag), findsOneWidget); // "Simulated" ما بيروح
      expect(find.text('Live'), findsNothing); // المحفوظ مش حيّ أبدًا
      expect(tester.takeException(), isNull);
    });

    testWidgets('"Last updated" is a polite live region read with the time', (tester) async {
      final handle = tester.ensureSemantics();
      await pumpOffline(tester, const HomeScreen(), db: await savedCache(tester));
      final node = tester.getSemantics(find.byType(LastUpdatedLine));
      expect(node.label, startsWith('Last updated '));
      expect(node.getSemanticsData().flagsCollection.isLiveRegion, isTrue);
      handle.dispose();
    });

    testWidgets('saved data older than 24 h says "Old data"', (tester) async {
      final db = await savedCache(tester, at: kTestNow.subtract(const Duration(hours: 25)));
      await pumpOffline(tester, const HomeScreen(), db: db);
      expect(find.text('Old data'), findsOneWidget);
      expect(find.textContaining('Last updated'), findsOneWidget);
    });

    testWidgets('pull to refresh offline says why, nothing is lost', (tester) async {
      await pumpOffline(tester, const HomeScreen(), db: await savedCache(tester));
      await tester.fling(find.byType(CustomScrollView), const Offset(0, 500), 1200);
      await tester.pumpAndSettle();
      expect(find.textContaining('You’re offline, so prices can’t refresh'), findsOneWidget);
      expect(find.byType(WatchlistRow), findsNWidgets(8));
    });

    testWidgets('back online: refreshes by itself, the saved-data line goes away', (tester) async {
      final container = await pumpOffline(tester, const HomeScreen(), db: await savedCache(tester));
      expect(find.textContaining('Last updated'), findsOneWidget);
      await goOnline(tester, container);
      expect(find.textContaining('Last updated'), findsNothing);
      expect(find.text('Offline'), findsNothing);
      expect(find.byType(WatchlistRow), findsNWidgets(8));
    });

    testWidgets('no saved data + offline: the offline state (not an empty list), then loads online',
        (tester) async {
      final container = await pumpOffline(tester, const HomeScreen(), db: emptyCache());
      expect(find.byType(WatchlistRow), findsNothing);
      expect(find.text('You’re offline'), findsOneWidget);
      expect(find.textContaining('Prices haven’t been saved on this phone yet'), findsOneWidget);
      expect(find.text('Try again'), findsNothing); // بيرجع لحالو

      await goOnline(tester, container);
      expect(find.byType(WatchlistRow), findsNWidgets(8));
      expect(find.text('You’re offline'), findsNothing);
    });

    testWidgets('online but the source fails: saved prices with Stale + "Last updated"', (tester) async {
      final db = await savedCache(tester);
      usePhoneSize(tester, height: 1000);
      await tester.pumpWidget(await testScope(
        const TestApp(home: HomeScreen()),
        overrides: cachedMarketOverrides(db: db, source: _FailingSource()),
      ));
      await tester.pumpAndSettle();
      expect(find.byType(WatchlistRow), findsNWidgets(8));
      expect(find.text('Stale'), findsOneWidget);
      expect(find.textContaining('Last updated'), findsOneWidget);
    });

    for (final (locale, theme) in [('ar', 'dark'), ('en', 'dark'), ('ar', 'light')]) {
      testWidgets('offline + old data: $locale $theme, text scale 2.0, no overflow', (tester) async {
        useLargeText(tester);
        final db = await savedCache(tester, at: kTestNow.subtract(const Duration(days: 2)));
        await pumpOffline(tester, const HomeScreen(), db: db, locale: locale, theme: theme, height: 1600);
        expect(tester.takeException(), isNull);
        if (locale == 'ar') {
          expect(Directionality.of(tester.element(find.byType(LastUpdatedLine))), TextDirection.rtl);
          expect(find.textContaining('آخر تحديث'), findsOneWidget);
          expect(find.text('بيانات قديمة'), findsOneWidget);
          expect(find.text('غير متصل'), findsOneWidget);
        } else {
          expect(find.text('Old data'), findsOneWidget);
        }
      });
    }

    testWidgets('flag off: offline Home exactly as before (live source, no saved-data line)', (tester) async {
      await pumpOffline(tester, const HomeScreen(), db: emptyCache(), enabled: false);
      expect(find.byType(WatchlistRow), findsNWidgets(8));
      expect(find.textContaining('Last updated'), findsNothing);
      expect(find.text('Offline'), findsNothing);
      expect(find.textContaining('Prices haven’t been saved'), findsNothing);
      // سحب التحديث بيشتغل متل قبل (ما في رسالة offline)
      await tester.fling(find.byType(CustomScrollView), const Offset(0, 500), 1200);
      await tester.pumpAndSettle();
      expect(find.textContaining('can’t refresh'), findsNothing);
    });
  });

  group('Market screen', () {
    testWidgets('offline: chart from saved candles, Offline pill, "Last updated", forecast hidden', (tester) async {
      await pumpOffline(tester, const MarketScreen(symbol: 'EUR/USD'), db: await savedCache(tester), height: 1400);
      expect(find.byType(PriceChart), findsOneWidget);
      expect(find.text('Offline'), findsOneWidget);
      expect(find.textContaining('Last updated'), findsOneWidget);
      expect(find.text('Live'), findsNothing);
      expect(find.byType(SourceTag), findsWidgets);
      expect(tester.takeException(), isNull);
    });

    testWidgets('offline on a timeframe never saved: explains instead of an empty chart', (tester) async {
      final container =
          await pumpOffline(tester, const MarketScreen(symbol: 'EUR/USD'), db: await savedCache(tester), height: 1400);
      await tester.tap(find.widgetWithText(ChoiceChip, '1m'));
      await tester.pumpAndSettle();
      expect(find.byType(PriceChart), findsNothing);
      expect(find.textContaining('This chart hasn’t been saved for offline use yet'), findsOneWidget);

      await goOnline(tester, container); // بيتحمّل لحالو
      expect(find.byType(PriceChart), findsOneWidget);
    });

    testWidgets('no saved data + offline: the offline state', (tester) async {
      await pumpOffline(tester, const MarketScreen(symbol: 'EUR/USD'), db: emptyCache());
      expect(find.byType(PriceChart), findsNothing);
      expect(find.text('You’re offline'), findsOneWidget);
      expect(find.textContaining('Prices haven’t been saved on this phone yet'), findsOneWidget);
    });

    testWidgets('Arabic, dark, text scale 2.0: offline Market has no overflow', (tester) async {
      useLargeText(tester);
      await pumpOffline(tester, const MarketScreen(symbol: 'XAU/USD'),
          db: await savedCache(tester), locale: 'ar', theme: 'dark', height: 2400);
      expect(tester.takeException(), isNull);
      expect(find.textContaining('آخر تحديث'), findsOneWidget);
    });
  });

  group('Settings → Developer', () {
    testWidgets('"Clear saved market data" empties the cache and confirms (48 dp row)', (tester) async {
      final db = await savedCache(tester);
      await pumpOffline(tester, const SettingsScreen(), db: db, offline: false, height: 1600);
      final row = find.text('Clear saved market data');
      expect(row, findsOneWidget);
      expect(tester.getSize(find.ancestor(of: row, matching: find.byType(InkWell)).first).height,
          greaterThanOrEqualTo(48));
      await tester.tap(row);
      for (var i = 0; i < 20; i++) {
        await tester.pump(const Duration(milliseconds: 10));
      }
      await tester.pumpAndSettle();
      expect(find.text('Saved market data cleared.'), findsOneWidget);
      expect(await settle(tester, MarketCache(db).readQuotes()), isNull);
    });

    testWidgets('flag off: no cache row', (tester) async {
      await pumpOffline(tester, const SettingsScreen(), db: emptyCache(), offline: false, enabled: false, height: 1600);
      expect(find.text('Clear saved market data'), findsNothing);
    });
  });
}

/// مصدر دايمًا فاشل (السيرفر واقع وإحنا متصلين)
final class _FailingSource implements MarketDataRepository {
  @override
  bool get isSimulated => true;
  @override
  Future<List<Instrument>> instruments() => Future.error(StateError('down'));
  @override
  Future<List<Quote>> quotes() => Future.error(StateError('down'));
  @override
  Future<List<Candle>> candles(String symbol, Timeframe timeframe, {int limit = 300}) =>
      Future.error(StateError('down'));
  @override
  Stream<List<Quote>> ticks() => const Stream.empty();
}
