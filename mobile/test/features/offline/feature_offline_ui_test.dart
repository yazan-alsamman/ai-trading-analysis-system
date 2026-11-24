// H5b: الواجهة فوق كاش الميزات (Drift بالذاكرة جوّا الوقت الوهمي): Signals
// والتفاصيل والأخبار والإشعارات من النسخة المحفوظة بدون اتصال ("Last updated"
// + شارة Offline)، حالة الـ offline بسببها لما ما في شي محفوظ، الأفعال بتقول
// إنها بدها اتصال والمسودة بتضل، والـ Low data mode (الإعداد، الشارة، الاقتراح،
// فترة تحديث الأسعار بالساعة الوهمية، الرسم بدون حركة ونافذة أصغر).

import 'dart:async';

import 'package:drift/drift.dart' show driftRuntimeOptions;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:trading_app/core/data/low_data_mode.dart';
import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/database/app_database_holder.dart';
import 'package:trading_app/core/database/cache_support.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/core/widgets/low_data_pill.dart';
import 'package:trading_app/core/widgets/settings_group.dart';
import 'package:trading_app/features/alerts/view_models/alerts_view_model.dart';
import 'package:trading_app/features/comments/models/comment.dart';
import 'package:trading_app/features/comments/widgets/comments_sheet.dart';
import 'package:trading_app/features/home/views/home_screen.dart';
import 'package:trading_app/features/markets/data/market_cache.dart';
import 'package:trading_app/features/markets/data/market_data_repository.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/markets/data/simulated_market_source.dart';
import 'package:trading_app/features/markets/models/market_models.dart';
import 'package:trading_app/features/markets/views/market_screen.dart';
import 'package:trading_app/features/markets/widgets/last_updated_line.dart';
import 'package:trading_app/features/markets/widgets/price_chart.dart';
import 'package:trading_app/features/news/data/caching_news_repository.dart';
import 'package:trading_app/features/news/data/news_repository.dart';
import 'package:trading_app/features/news/view_models/news_view_models.dart';
import 'package:trading_app/features/news/widgets/news_card.dart';
import 'package:trading_app/features/news/widgets/news_section.dart';
import 'package:trading_app/features/notifications/data/caching_notifications_repository.dart';
import 'package:trading_app/features/notifications/data/notifications_repository.dart';
import 'package:trading_app/features/notifications/views/notifications_screen.dart';
import 'package:trading_app/features/notifications/widgets/notification_row.dart';
import 'package:trading_app/features/settings/views/settings_screen.dart';
import 'package:trading_app/features/signals/data/caching_signals_repository.dart';
import 'package:trading_app/features/signals/data/signals_repository.dart';
import 'package:trading_app/features/signals/models/signal_profile.dart';
import 'package:trading_app/features/signals/views/signal_detail_screen.dart';
import 'package:trading_app/features/signals/views/signals_screen.dart';
import 'package:trading_app/features/signals/widgets/signal_row.dart';

import '../../helpers/test_app.dart';

/// عملية Drift جوّا الوقت الوهمي تبع testWidgets: منقدّم الوقت لحد ما تخلص
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
  addTearDown(() => unawaited(db.close()));
  return db;
}

/// صاحب الصفوف بـ testScope (المستخدم الداخل)
const owner = 'test-user';

/// كاش فيه: أسعار + شموع ساعة، قائمة Signals للحساب، الأخبار (en)، الإشعارات (en)
Future<AppDatabaseHolder> savedCache(
  WidgetTester tester, {
  bool signals = true,
  bool news = true,
  bool notifications = true,
}) async {
  final db = emptyCache();
  final source = SimulatedMarketSource(clock: () => kTestNow);
  final market = SimulatedMarketDataRepository(source: source);
  await settle(tester, MarketCache(db).saveQuotes(await market.quotes(), kTestNow));
  for (final symbol in kProductSymbols) {
    for (final tf in Timeframe.modelTimeframes) {
      await settle(tester, MarketCache(db).saveCandles(symbol, tf, await market.candles(symbol, tf), kTestNow));
    }
  }
  if (signals) {
    final feed = await SimulatedSignalsRepository(source: source).feed(SignalProfile.defaults);
    await settle(tester, SignalsCache(db).saveList(SignalsCache.feedScope, owner, feed, kTestNow));
  }
  if (news) {
    final repo = SimulatedNewsRepository(clock: () => kTestNow);
    await settle(tester, NewsCache(db).saveArticles('en', await repo.articles(languageCode: 'en'), kTestNow));
    await settle(tester, NewsCache(db).saveMood(await repo.mood(), kTestNow));
  }
  if (notifications) {
    final list = await SimulatedNotificationsRepository(clock: () => kTestNow).list(languageCode: 'en');
    await settle(tester, NotificationsCache(db).save(owner, 'en', list, kTestNow));
  }
  return db;
}

Future<ProviderContainer> pumpScreen(
  WidgetTester tester,
  Widget screen, {
  required AppDatabaseHolder db,
  bool offline = true,
  String locale = 'en',
  String theme = 'light',
  Map<String, Object> prefs = const {},
  FakeConnectivitySource? connection,
  List<Override> overrides = const [],
  double height = 1400,
}) async {
  usePhoneSize(tester, height: height);
  // شاشة تانية بنفس الاختبار = ProviderScope جديد (الـ overrides ما بتتغيّر بمكانها)
  await tester.pumpWidget(const SizedBox());
  await tester.pumpWidget(await testScope(
    TestApp(home: screen),
    locale: locale,
    prefs: {themeModeStorageKey: theme, ...prefs},
    overrides: [
      ...cachedMarketOverrides(db: db),
      ...cachedFeatureOverrides(),
      if (connection != null) connectivityOverride(connection),
      if (offline) simulatedOfflineProvider.overrideWith((ref) => true),
      ...overrides,
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

Future<void> goOffline(WidgetTester tester, ProviderContainer container) async {
  container.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
  await tester.pumpAndSettle();
}

/// يفتح sheet التعليقات لخبر
class _CommentsLauncher extends StatelessWidget {
  const _CommentsLauncher();

  @override
  Widget build(BuildContext context) => Scaffold(
        body: Center(
          child: TextButton(
            onPressed: () => showCommentsSheet(context, thread: (target: CommentTarget.article, id: 'fed-rate-decision')),
            child: const Text('open comments'),
          ),
        ),
      );
}

/// repository أسعار بنبضات يدوية (فترة التحديث بالساعة الوهمية)
final class _ManualTicks implements MarketDataRepository {
  final controller = StreamController<List<Quote>>.broadcast();

  @override
  bool get isSimulated => true;
  @override
  Future<List<Instrument>> instruments() async => const [];
  @override
  Future<List<Candle>> candles(String symbol, Timeframe timeframe, {int limit = 300}) async => const [];
  @override
  Future<List<Quote>> quotes() async => [Quote(symbol: 'EUR/USD', price: 1, reference: 1, time: kTestNow)];
  @override
  Stream<List<Quote>> ticks() => controller.stream;
}

void main() {
  driftRuntimeOptions.dontWarnAboutMultipleDatabases = true;

  group('Signals', () {
    testWidgets('offline with a saved list: rows, Offline pill, polite "Last updated"', (tester) async {
      final handle = tester.ensureSemantics();
      final container = await pumpScreen(tester, const SignalsScreen(), db: await savedCache(tester), height: 2600);
      final saved = await settle(tester, SignalsCache(emptyCache()).readList(SignalsCache.feedScope, owner));
      expect(saved, isNull, reason: 'another database has nothing');

      expect(find.byType(SignalRow), findsWidgets);
      expect(find.text('Offline'), findsOneWidget);
      final line = tester.getSemantics(find.byType(LastUpdatedLine));
      expect(line.label, startsWith('Last updated '));
      expect(line.getSemanticsData().flagsCollection.isLiveRegion, isTrue);
      expect(container.read(signalsSavedAtProvider(CachingSignalsRepository.feedKey)), kTestNow);
      expect(tester.takeException(), isNull);
      handle.dispose();
    });

    testWidgets('pull to refresh offline says why; the saved list stays', (tester) async {
      await pumpScreen(tester, const SignalsScreen(), db: await savedCache(tester), height: 2600);
      final rows = find.byType(SignalRow).evaluate().length;
      unawaited(tester.state<RefreshIndicatorState>(find.byType(RefreshIndicator)).show());
      await tester.pumpAndSettle();
      expect(find.textContaining('You’re offline, so signals can’t refresh'), findsOneWidget);
      expect(find.byType(SignalRow), findsNWidgets(rows));
    });

    testWidgets('nothing saved + offline: the offline state with its reason, then loads online', (tester) async {
      final container = await pumpScreen(tester, const SignalsScreen(), db: await savedCache(tester, signals: false));
      expect(find.byType(SignalRow), findsNothing);
      expect(find.text('Signals will load when you’re back online.'), findsOneWidget);
      await goOnline(tester, container);
      expect(find.byType(SignalRow), findsWidgets);
      expect(find.textContaining('Last updated'), findsNothing);
    });

    testWidgets('signal detail opens from the saved list offline with "Last updated"', (tester) async {
      final db = await savedCache(tester);
      final feed = (await settle(tester, SignalsCache(db).readList(SignalsCache.feedScope, owner)))!.value;
      final signal = feed.first;
      await pumpScreen(tester, SignalDetailScreen(signalId: signal.id, symbol: signal.symbol), db: db, height: 2600);
      expect(find.textContaining('Last updated'), findsOneWidget);
      expect(find.text('Offline'), findsOneWidget);
      expect(find.byType(PriceChart), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });

  group('News', () {
    testWidgets('offline with saved news: articles + "Last updated"; back online refreshes by itself', (tester) async {
      final container = await pumpScreen(tester, const Scaffold(body: NewsSection()), db: await savedCache(tester));
      expect(find.byType(NewsCard), findsWidgets);
      expect(find.textContaining('Last updated'), findsOneWidget);
      expect(container.read(newsSavedAtProvider(CachingNewsRepository.articlesKey('en'))), kTestNow);

      await goOnline(tester, container);
      expect(find.byType(NewsCard), findsWidgets);
      expect(find.textContaining('Last updated'), findsNothing);
    });

    testWidgets('nothing saved + offline: the offline state with its reason', (tester) async {
      final container =
          await pumpScreen(tester, const Scaffold(body: NewsSection()), db: await savedCache(tester, news: false));
      expect(container.read(newsViewModelProvider).error, isA<NoSavedDataException>());
      expect(find.byType(NewsCard), findsNothing);
      expect(find.textContaining('News hasn’t been saved on this phone yet'), findsOneWidget);
    });

    testWidgets('pull to refresh offline says why', (tester) async {
      await pumpScreen(tester, const Scaffold(body: NewsSection()), db: await savedCache(tester));
      unawaited(tester.state<RefreshIndicatorState>(find.byType(RefreshIndicator)).show());
      await tester.pumpAndSettle();
      expect(find.textContaining('You’re offline, so news can’t refresh'), findsOneWidget);
    });
  });

  group('Notifications', () {
    testWidgets('offline with a saved inbox: rows + "Last updated"', (tester) async {
      final container = await pumpScreen(tester, const NotificationsScreen(), db: await savedCache(tester));
      expect(find.byType(NotificationRow), findsWidgets);
      expect(find.textContaining('Last updated'), findsOneWidget);
      expect(container.read(notificationsSavedAtProvider(CachingNotificationsRepository.inboxKey('en'))), kTestNow);
    });

    testWidgets('nothing saved + offline: the offline state with its reason', (tester) async {
      await pumpScreen(tester, const NotificationsScreen(), db: await savedCache(tester, notifications: false));
      expect(find.byType(NotificationRow), findsNothing);
      expect(find.textContaining('Notifications haven’t been saved on this phone yet'), findsOneWidget);
    });
  });

  group('actions that need the server', () {
    testWidgets('a comment offline says it needs a connection and the draft stays', (tester) async {
      final container =
          await pumpScreen(tester, const _CommentsLauncher(), db: await savedCache(tester), offline: false);
      await tester.tap(find.text('open comments'));
      await tester.pumpAndSettle();
      await goOffline(tester, container);

      await tester.enterText(find.byType(TextField).last, 'Rates hold, gold up');
      await tester.pump();
      await tester.tap(find.byIcon(Icons.send_rounded));
      await tester.pumpAndSettle();
      expect(find.textContaining('your comment wasn’t sent'), findsOneWidget);
      expect(find.text('Rates hold, gold up'), findsOneWidget, reason: 'draft kept');
    });

    testWidgets('comments opened offline explain why they are not shown', (tester) async {
      await pumpScreen(tester, const _CommentsLauncher(), db: await savedCache(tester));
      await tester.tap(find.text('open comments'));
      await tester.pumpAndSettle();
      expect(find.text('Comments need a connection. They load by themselves when you’re back online.'), findsOneWidget);
    });

    testWidgets('an alert on a real API offline: needs a connection, the sheet and the price stay', (tester) async {
      await pumpScreen(
        tester,
        const MarketScreen(symbol: 'EUR/USD'),
        db: await savedCache(tester),
        overrides: [alertsNeedConnectionProvider.overrideWithValue(true)],
        height: 2400,
      );
      await scrollTo(tester, find.text('Set alert'));
      await tester.tap(find.text('Set alert'));
      await tester.pumpAndSettle();
      await tester.enterText(find.widgetWithText(TextField, 'Target price'), '1.5');
      await tester.pump();
      await tester.tap(find.text('Create alert'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Alerts are saved on the server, so this needs a connection'), findsOneWidget);
      expect(find.text('Create alert'), findsOneWidget, reason: 'sheet still open');
      expect(find.text('1.5'), findsOneWidget, reason: 'draft kept');
    });
  });

  group('Low data mode', () {
    testWidgets('off by default: no pill, chart animates with the full window', (tester) async {
      await pumpScreen(tester, const MarketScreen(symbol: 'EUR/USD'), db: emptyCache(), offline: false);
      expect(find.byType(LowDataPill), findsNothing);
      final chart = tester.widget<PriceChart>(find.byType(PriceChart));
      expect(chart.animated, isTrue);
      expect(chart.candles, hasLength(LiveCandlesNotifier.limit));
    });

    testWidgets('on: "Low data mode" pill (polite), chart without animation and a smaller window', (tester) async {
      final handle = tester.ensureSemantics();
      final container = await pumpScreen(tester, const MarketScreen(symbol: 'EUR/USD'),
          db: emptyCache(), offline: false, prefs: {kLowDataModeKey: true});
      expect(find.text('Low data mode'), findsOneWidget);
      final pill = tester.getSemantics(find.byType(LowDataPill));
      expect(pill.label, contains('Prices update every 5 seconds'));
      expect(pill.getSemanticsData().flagsCollection.isLiveRegion, isTrue);
      var chart = tester.widget<PriceChart>(find.byType(PriceChart));
      expect(chart.animated, isFalse);
      expect(chart.candles, hasLength(kLowDataCandleWindow));

      // الإطفاء بيرجّع كل شي فورًا
      await container.read(lowDataModeProvider.notifier).set(false);
      await tester.pumpAndSettle();
      expect(find.byType(LowDataPill), findsNothing);
      chart = tester.widget<PriceChart>(find.byType(PriceChart));
      expect(chart.animated, isTrue);
      expect(chart.candles, hasLength(LiveCandlesNotifier.limit));
      handle.dispose();
    });

    testWidgets('Home shows the pill when on', (tester) async {
      await pumpScreen(tester, const HomeScreen(), db: emptyCache(), offline: false, prefs: {kLowDataModeKey: true});
      expect(find.byType(LowDataPill), findsOneWidget);
      expect(find.text('Low data mode'), findsOneWidget);
    });

    testWidgets('suggestion on mobile data: "Turn on" enables it (never by itself)', (tester) async {
      final container = await pumpScreen(tester, const HomeScreen(),
          db: emptyCache(), offline: false, connection: FakeConnectivitySource(NetworkStatus.online, true));
      expect(find.text('Use less data?'), findsOneWidget);
      expect(find.textContaining('You’re on mobile data'), findsOneWidget);
      expect(container.read(lowDataModeProvider), isFalse);
      final turnOn = find.widgetWithText(TextButton, 'Turn on');
      expect(tester.getSize(turnOn).height, greaterThanOrEqualTo(48));

      await tester.tap(turnOn);
      await tester.pumpAndSettle();
      expect(container.read(lowDataModeProvider), isTrue);
      expect(find.text('Use less data?'), findsNothing);
      expect(find.byType(LowDataPill), findsOneWidget);
      expect(find.textContaining('You can turn it off in Settings'), findsOneWidget);
    });

    testWidgets('suggestion: "Not now" dismisses it for good, the mode stays off', (tester) async {
      final container = await pumpScreen(tester, const HomeScreen(),
          db: emptyCache(), offline: false, connection: FakeConnectivitySource(NetworkStatus.online, true));
      await tester.tap(find.widgetWithText(TextButton, 'Not now'));
      await tester.pumpAndSettle();
      expect(find.text('Use less data?'), findsNothing);
      expect(container.read(lowDataModeProvider), isFalse);
      expect((await SharedPreferences.getInstance()).getBool(kLowDataSuggestionDismissedKey), isTrue);
    });

    testWidgets('Settings: off by default with an explanation; the switch persists', (tester) async {
      await pumpScreen(tester, const SettingsScreen(), db: emptyCache(), offline: false);
      expect(find.text('Low data mode'), findsOneWidget);
      expect(find.textContaining('prices update every 5 seconds'), findsOneWidget);
      final tile = find.ancestor(of: find.text('Low data mode'), matching: find.byType(SettingsSwitchTile));
      expect(tester.getSize(tile).height, greaterThanOrEqualTo(48));
      expect(find.descendant(of: tile, matching: find.byType(Switch)), findsOneWidget);
      await tester.tap(find.text('Low data mode'));
      await tester.pumpAndSettle();
      expect((await SharedPreferences.getInstance()).getBool(kLowDataModeKey), isTrue);
      await tester.tap(find.text('Low data mode'));
      await tester.pumpAndSettle();
      expect((await SharedPreferences.getInstance()).getBool(kLowDataModeKey), isFalse);
    });

    testWidgets('price updates: every tick normally, at most one per 5 s with low data (fake clock)', (tester) async {
      Future<int> count({required bool lowData}) async {
        final repo = _ManualTicks();
        final container = ProviderContainer(overrides: [
          ...(await testScopeOverridesForContainer(prefs: {kLowDataModeKey: lowData})),
          marketDataRepositoryProvider.overrideWithValue(repo),
        ]);
        var updates = 0;
        container.listen(liveQuotesProvider, (_, __) => updates++);
        await tester.pump();
        await tester.pump();
        updates = 0;
        // نبضة كل 1.5 ثانية لمدة 15 ثانية (10 نبضات، كل وحدة بسعر جديد)
        for (var i = 1; i <= 10; i++) {
          await tester.pump(const Duration(milliseconds: 1500));
          repo.controller.add([
            Quote(symbol: 'EUR/USD', price: 1 + i / 1000, reference: 1, time: kTestNow.add(Duration(milliseconds: 1500 * i))),
          ]);
          await tester.pump();
        }
        await tester.pump(const Duration(seconds: 5));
        final last = container.read(liveQuotesProvider).value!['EUR/USD']!.price;
        expect(last, 1.010, reason: 'the newest price is never lost');
        container.dispose();
        await repo.controller.close();
        return updates;
      }

      expect(await count(lowData: false), 10);
      final slow = await count(lowData: true);
      // أول نبضة فورًا، بعدين مرة كل 5 ثواني: 15 ثانية → 4 تحديثات (الأخيرة بعد آخر نبضة)
      expect(slow, inInclusiveRange(3, 4));
    });
  });

  group('a11y: EN/AR, light/dark, text scale 2.0', () {
    for (final locale in ['en', 'ar']) {
      for (final theme in ['light', 'dark']) {
        testWidgets('$locale $theme: Home suggestion + Settings switch fit', (tester) async {
          useLargeText(tester);
          await pumpScreen(tester, const HomeScreen(),
              db: emptyCache(),
              offline: false,
              locale: locale,
              theme: theme,
              connection: FakeConnectivitySource(NetworkStatus.online, true),
              height: 2400);
          expect(find.byType(TextButton), findsWidgets);
          expect(tester.takeException(), isNull);

          await pumpScreen(tester, const SettingsScreen(),
              db: emptyCache(), offline: false, locale: locale, theme: theme, height: 2400);
          expect(tester.takeException(), isNull);
        });

        testWidgets('$locale $theme: offline Signals + Notifications + Market pill fit', (tester) async {
          useLargeText(tester);
          final db = await savedCache(tester);
          await pumpScreen(tester, const SignalsScreen(), db: db, locale: locale, theme: theme, height: 3200);
          expect(find.byType(LastUpdatedLine), findsOneWidget);
          expect(tester.takeException(), isNull);
          await pumpScreen(tester, const MarketScreen(symbol: 'EUR/USD'),
              db: db, locale: locale, theme: theme, prefs: {kLowDataModeKey: true}, height: 3200);
          expect(find.byType(LowDataPill), findsOneWidget);
          expect(tester.takeException(), isNull);
        });
      }
    }

    testWidgets('reduced motion: the suggestion appears without animating', (tester) async {
      tester.platformDispatcher.accessibilityFeaturesTestValue = const FakeAccessibilityFeatures(disableAnimations: true);
      addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
      await pumpScreen(tester, const HomeScreen(),
          db: emptyCache(), offline: false, connection: FakeConnectivitySource(NetworkStatus.online, true));
      expect(find.text('Use less data?'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });
}

/// نفس أساس testScope لـ ProviderContainer مباشر (تخزين وهمي + اتصال وهمي)
Future<List<Override>> testScopeOverridesForContainer({Map<String, Object> prefs = const {}}) async {
  final scope = await testScope(const SizedBox(), prefs: prefs);
  return scope.overrides;
}
