// H5b: كاش الميزات (Drift بالذاكرة، بدون zone تبع testWidgets): ترحيل v1 → v2
// (بيانات السوق بتضل)، الكتابة عبر الطبقة والقراءة لما ما في اتصال أو المصدر
// فشل لكل ميزة، التقليم، مسح الصفوف الخاصة بالمستخدم مع تسجيل الخروج، وآثار
// الـ Low data mode (الإعداد، الاقتراح، التبويب المخفي، نافذة الشموع).

import 'dart:async';

import 'package:dio/dio.dart';
import 'package:drift/drift.dart' show driftRuntimeOptions;
import 'package:drift/native.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:trading_app/app/shell/shell_tab.dart';
import 'package:trading_app/core/data/low_data_mode.dart';
import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/database/app_database.dart';
import 'package:trading_app/core/database/app_database_holder.dart';
import 'package:trading_app/core/database/cache_support.dart';
import 'package:trading_app/core/database/database_providers.dart';
import 'package:trading_app/core/database/user_cache_guard.dart';
import 'package:trading_app/core/network/latency_interceptor.dart';
import 'package:trading_app/core/storage/preferences_provider.dart';
import 'package:trading_app/features/auth/auth_state.dart';
import 'package:trading_app/features/forecast/models/forecast_config.dart';
import 'package:trading_app/features/markets/data/market_cache.dart';
import 'package:trading_app/features/markets/data/market_data_repository.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/markets/data/simulated_market_source.dart';
import 'package:trading_app/features/markets/models/market_models.dart';
import 'package:trading_app/features/news/data/caching_news_repository.dart';
import 'package:trading_app/features/news/data/news_repository.dart';
import 'package:trading_app/features/news/models/news_models.dart';
import 'package:trading_app/features/notifications/data/caching_notifications_repository.dart';
import 'package:trading_app/features/notifications/data/notifications_repository.dart';
import 'package:trading_app/features/notifications/models/app_notification.dart';
import 'package:trading_app/features/signals/data/caching_signals_repository.dart';
import 'package:trading_app/features/signals/data/opportunity_dto.dart';
import 'package:trading_app/features/signals/data/signals_repository.dart';
import 'package:trading_app/features/signals/models/analysis_method.dart';
import 'package:trading_app/features/signals/models/analysis_request.dart';
import 'package:trading_app/features/signals/models/model_accuracy.dart';
import 'package:trading_app/features/signals/models/opportunity.dart';
import 'package:trading_app/features/signals/models/signal_profile.dart';
import 'package:trading_app/models/user_model.dart';

import '../../helpers/test_app.dart';

/// مصدر إشارات بيقدر "يوقع" (الخادم ما بيرد)
final class _SwitchableSignals implements SignalsRepository {
  _SwitchableSignals(this.inner);

  final SignalsRepository inner;
  bool failing = false;
  int calls = 0;

  Future<T> _go<T>(Future<T> Function() call) {
    calls++;
    return failing ? Future.error(StateError('server down')) : call();
  }

  @override
  bool get isSimulated => true;
  @override
  Future<ModelAccuracy> accuracy() => _go(inner.accuracy);
  @override
  Future<List<Opportunity>> feed(SignalProfile profile) => _go(() => inner.feed(profile));
  @override
  Future<Opportunity?> opportunity(String id) => _go(() => inner.opportunity(id));
  @override
  Future<List<Opportunity>> opportunities(String symbol, {String methodId = AnalysisMethod.defaultId}) =>
      _go(() => inner.opportunities(symbol, methodId: methodId));
  @override
  Future<Opportunity> requestAnalysis(AnalysisRequest request,
          {AnalysisCancelToken? cancel, void Function(AnalysisStage stage)? onStage}) =>
      _go(() => inner.requestAnalysis(request, cancel: cancel, onStage: onStage));
}

final class _SwitchableNews implements NewsRepository {
  _SwitchableNews(this.inner);

  final NewsRepository inner;
  bool failing = false;

  Future<T> _go<T>(Future<T> Function() call) => failing ? Future.error(StateError('server down')) : call();

  @override
  Future<List<NewsArticle>> articles({required String languageCode}) =>
      _go(() => inner.articles(languageCode: languageCode));
  @override
  Future<MarketMood> mood() => _go(inner.mood);
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

final class _SwitchableNotifications implements NotificationsRepository {
  _SwitchableNotifications(this.inner);

  final NotificationsRepository inner;
  bool failing = false;

  @override
  Future<List<AppNotification>> list({required String languageCode}) =>
      failing ? Future.error(StateError('server down')) : inner.list(languageCode: languageCode);
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

AppDatabaseHolder memoryDb() {
  final db = AppDatabaseHolder.memory();
  addTearDown(db.close);
  return db;
}

SimulatedSignalsRepository simulatedSignals() =>
    SimulatedSignalsRepository(source: SimulatedMarketSource(clock: () => kTestNow), requestLatencyScale: 0);

/// إشارة "requested by you" (نفس الأرقام، معرّف `req-`)
Opportunity requested(Opportunity o) => opportunitiesFromJson([
      {...opportunityToJson(o), 'id': 'req-${o.id}', 'requestedByYou': true},
    ]).single;

void main() {
  // appActiveProvider (LiveQuotes) بدو binding
  TestWidgetsFlutterBinding.ensureInitialized();
  // كل اختبار بيفتح قاعدة بالذاكرة لحالها (مش نفس الـ executor)
  driftRuntimeOptions.dontWarnAboutMultipleDatabases = true;

  group('migration v1 → v2', () {
    /// قاعدة v1 (H5a): نفس جداول السوق + سعر وشمعة محفوظين، user_version = 1
    AppDatabaseHolder v1Database({int version = 1}) {
      final holder = AppDatabaseHolder(
        open: () => AppDatabase(NativeDatabase.memory(setup: (raw) {
          raw.execute('CREATE TABLE cached_quotes (symbol TEXT NOT NULL, price REAL NOT NULL, change REAL NOT NULL, '
              'updated_at INTEGER NOT NULL, PRIMARY KEY (symbol))');
          raw.execute('CREATE TABLE cached_candles (id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, '
              'timeframe TEXT NOT NULL, open_time INTEGER NOT NULL, open REAL NOT NULL, high REAL NOT NULL, '
              'low REAL NOT NULL, close REAL NOT NULL, volume REAL NOT NULL)');
          raw.execute('CREATE UNIQUE INDEX idx_cached_candles_series ON cached_candles (symbol, timeframe, open_time)');
          raw.execute('CREATE TABLE cache_meta ("key" TEXT NOT NULL, updated_at INTEGER NOT NULL, PRIMARY KEY ("key"))');
          final at = kTestNow.millisecondsSinceEpoch;
          raw.execute("INSERT INTO cached_quotes VALUES ('EUR/USD', 1.0845, 0.0012, $at)");
          raw.execute("INSERT INTO cached_candles (symbol, timeframe, open_time, open, high, low, close, volume) "
              "VALUES ('EUR/USD', '1h', $at, 1.08, 1.09, 1.07, 1.0845, 10)");
          raw.execute("INSERT INTO cache_meta VALUES ('quotes', $at)");
          raw.execute('PRAGMA user_version = $version');
        })),
      );
      addTearDown(holder.close);
      return holder;
    }

    test('market data saved by v1 survives, and the new tables work', () async {
      final db = v1Database();
      final market = MarketCache(db);
      final quotes = await market.readQuotes();
      expect(quotes!.value.single.symbol, 'EUR/USD');
      expect(quotes.value.single.price, 1.0845);
      expect(quotes.updatedAt, kTestNow);
      expect((await market.readCandles('EUR/USD', Timeframe.h1))!.value.single.close, 1.0845);
      expect(await db.run((d) async => (await d.customSelect('PRAGMA user_version').getSingle()).data.values.first), 2);

      // الجداول الجديدة موجودة وشغّالة
      final signals = await simulatedSignals().feed(SignalProfile.defaults);
      await SignalsCache(db).saveList(SignalsCache.feedScope, 'u1', signals, kTestNow);
      expect((await SignalsCache(db).readList(SignalsCache.feedScope, 'u1'))!.value.length, signals.length);
      final articles = await SimulatedNewsRepository(clock: () => kTestNow).articles(languageCode: 'en');
      await NewsCache(db).saveArticles('en', articles, kTestNow);
      expect((await NewsCache(db).readArticles('en'))!.value.length, articles.length);
      expect(db.recoveries, 0);
    });

    test('an unknown (newer) version is rebuilt empty instead of crashing', () async {
      final db = v1Database(version: 7);
      expect(await MarketCache(db).readQuotes(), isNull);
      expect(await SignalsCache(db).count(), 0);
    });
  });

  group('signals cache', () {
    late AppDatabaseHolder db;
    late _SwitchableSignals source;
    var offline = false;

    CachingSignalsRepository repo({String owner = 'u1'}) => CachingSignalsRepository(
          source: source,
          cache: SignalsCache(db),
          isOffline: () => offline,
          owner: owner,
          clock: () => kTestNow,
        );

    setUp(() {
      db = memoryDb();
      source = _SwitchableSignals(simulatedSignals());
      offline = false;
    });

    test('feed: written through online, read back offline with its time; the source is not asked', () async {
      final online = repo();
      final live = await online.feed(SignalProfile.defaults);
      expect(live, isNotEmpty);
      expect(online.savedAt[CachingSignalsRepository.feedKey], isNull);
      await online.flushWrites();

      offline = true;
      final calls = source.calls;
      final again = repo();
      final saved = await again.feed(SignalProfile.defaults);
      expect([for (final o in saved) o.id], [for (final o in live) o.id]);
      expect(saved.first.probability, live.first.probability);
      expect(saved.first.entryZone, live.first.entryZone);
      expect(again.savedAt[CachingSignalsRepository.feedKey], kTestNow);
      expect(again.savedAt[CachingSignalsRepository.itemKey(saved.first.id)], kTestNow);
      expect(source.calls, calls, reason: 'offline never asks the source');
    });

    test('feed: the source fails online → the saved list; nothing saved → the original error', () async {
      final first = repo();
      await first.feed(SignalProfile.defaults);
      await first.flushWrites();
      source.failing = true;
      expect(await repo().feed(SignalProfile.defaults), isNotEmpty);

      final empty = CachingSignalsRepository(
        source: source,
        cache: SignalsCache(memoryDb()),
        isOffline: () => false,
        owner: 'u1',
      );
      await expectLater(empty.feed(SignalProfile.defaults), throwsA(isA<StateError>()));
    });

    test('feed offline with nothing saved → NoSavedDataException', () async {
      offline = true;
      await expectLater(repo().feed(SignalProfile.defaults), throwsA(isA<NoSavedDataException>()));
    });

    test('a strategy changed offline only narrows the saved list', () async {
      final first = repo();
      final live = await first.feed(SignalProfile.defaults);
      await first.flushWrites();
      offline = true;
      final symbol = live.first.symbol;
      final narrowed = await repo().feed(SignalProfile.defaults.copyWith(symbols: {symbol}));
      expect(narrowed, isNotEmpty);
      expect(narrowed.every((o) => o.symbol == symbol), isTrue);
    });

    test('the feed and requested signals belong to the account: never read by another one', () async {
      final mine = repo();
      final live = await mine.feed(SignalProfile.defaults);
      mine.writeInBackground(() => SignalsCache(db).saveItem(requested(live.first), 'u1', kTestNow));
      await mine.flushWrites();

      offline = true;
      await expectLater(repo(owner: 'u2').feed(SignalProfile.defaults), throwsA(isA<NoSavedDataException>()));
      await expectLater(repo(owner: 'u2').opportunity('req-${live.first.id}'), throwsA(isA<NoSavedDataException>()));
      expect((await repo().opportunity('req-${live.first.id}'))!.requestedByYou, isTrue);
    });

    test('signed out: nothing personal is saved', () async {
      final anonymous = repo(owner: '');
      await anonymous.feed(SignalProfile.defaults);
      await anonymous.flushWrites();
      expect(await SignalsCache(db).count(scope: SignalsCache.feedScope), 0);
    });

    test('signal detail: opened online → readable offline; also found inside a saved list', () async {
      final online = repo();
      final live = await online.feed(SignalProfile.defaults);
      final opened = await online.opportunity(live.last.id);
      await online.flushWrites();
      expect(opened, isNotNull);

      offline = true;
      final again = repo();
      expect((await again.opportunity(live.last.id))!.id, live.last.id);
      expect(again.savedAt[CachingSignalsRepository.itemKey(live.last.id)], kTestNow);
      // من القائمة المحفوظة (ما انفتحت لحالها)
      expect((await again.opportunity(live.first.id))!.id, live.first.id);
    });

    test('model read per instrument: written through, read offline, shared by every account', () async {
      final online = repo();
      final live = await online.opportunities('EUR/USD');
      expect(live, hasLength(Timeframe.modelTimeframes.length));
      await online.flushWrites();

      offline = true;
      final other = repo(owner: 'u2');
      final saved = await other.opportunities('EUR/USD');
      expect([for (final o in saved) o.id], [for (final o in live) o.id]);
      expect(other.savedAt[CachingSignalsRepository.readKey('EUR/USD', AnalysisMethod.defaultId)], kTestNow);
      await expectLater(other.opportunities('XAU/USD'), throwsA(isA<NoSavedDataException>()));
    });

    test('a detected requested analysis is saved for the account', () async {
      final online = repo();
      final result = await online.requestAnalysis(const AnalysisRequest(
        symbol: 'EUR/USD',
        timeframe: Timeframe.h1,
        methodId: AnalysisMethod.defaultId,
      ));
      await online.flushWrites();
      if (result.isDetected) {
        offline = true;
        expect((await repo().opportunity(result.id))!.requestedByYou, isTrue);
        await expectLater(repo(owner: 'u2').opportunity(result.id), throwsA(isA<NoSavedDataException>()));
      } else {
        expect(await SignalsCache(db).count(scope: SignalsCache.itemScope), 0);
      }
    });

    test('pruning: lists replace the old rows, single signals keep the newest only, long-expired rows go', () async {
      final cache = SignalsCache(db, maxItems: 3);
      final list = await simulatedSignals().feed(SignalProfile.defaults);
      await cache.saveList(SignalsCache.feedScope, 'u1', list, kTestNow);
      await cache.saveList(SignalsCache.feedScope, 'u1', list.take(2).toList(), kTestNow);
      expect(await cache.count(scope: SignalsCache.feedScope), 2);

      final reads = await simulatedSignals().opportunities('EUR/USD');
      for (final (i, o) in reads.indexed) {
        await cache.saveItem(o, '', kTestNow.add(Duration(minutes: i)));
      }
      final more = await simulatedSignals().opportunities('XAU/USD');
      await cache.saveItem(more.first, '', kTestNow.add(const Duration(minutes: 10)));
      expect(await cache.count(scope: SignalsCache.itemScope), 3);
      expect(await cache.readItem(reads.first.id, ''), isNull, reason: 'oldest single signal pruned');

      // بعد 8 أيام كل شي صلاحيته خلصت من أكتر من 7 أيام بينشال (إشارة لسّا
      // صالحة بتضل)
      final fresh = opportunitiesFromJson([
        {
          ...opportunityToJson(more.last),
          'validUntil': kTestNow.add(const Duration(days: 30)).millisecondsSinceEpoch,
        },
      ]).single;
      await cache.saveItem(fresh, '', kTestNow.add(const Duration(days: 8)));
      expect(await cache.count(scope: SignalsCache.feedScope), 0);
      expect(await cache.count(scope: SignalsCache.itemScope), 1);
      expect((await cache.readItem(fresh.id, ''))!.value.validUntil, kTestNow.add(const Duration(days: 30)));
    });
  });

  group('news cache', () {
    test('articles + mood: written through, read offline / when the source fails; per language', () async {
      final db = memoryDb();
      final source = _SwitchableNews(SimulatedNewsRepository(clock: () => kTestNow));
      var offline = false;
      CachingNewsRepository repo() =>
          CachingNewsRepository(source: source, cache: NewsCache(db), isOffline: () => offline, clock: () => kTestNow);

      final online = repo();
      final live = await online.articles(languageCode: 'en');
      final mood = await online.mood();
      await online.flushWrites();

      offline = true;
      final again = repo();
      final saved = await again.articles(languageCode: 'en');
      expect([for (final a in saved) a.id], [for (final a in live) a.id]);
      expect(saved.first.title, live.first.title);
      expect(saved.first.sentiment, live.first.sentiment);
      expect(saved.first.symbols, live.first.symbols);
      expect((await again.mood()).positive, mood.positive);
      expect(again.savedAt[CachingNewsRepository.articlesKey('en')], kTestNow);
      await expectLater(again.articles(languageCode: 'ar'), throwsA(isA<NoSavedDataException>()));

      offline = false;
      source.failing = true;
      expect(await repo().articles(languageCode: 'en'), hasLength(live.length));
    });

    test('pruning: a new list replaces the old one and stays bounded', () async {
      final db = memoryDb();
      final cache = NewsCache(db, maxArticles: 2);
      final articles = await SimulatedNewsRepository(clock: () => kTestNow).articles(languageCode: 'en');
      await cache.saveArticles('en', articles, kTestNow);
      await cache.saveArticles('en', articles, kTestNow);
      expect(await cache.count('en'), 2);
    });
  });

  group('notifications cache', () {
    test('the inbox is per account: written through, read offline, never by another account', () async {
      final db = memoryDb();
      final source = _SwitchableNotifications(SimulatedNotificationsRepository(clock: () => kTestNow));
      var offline = false;
      CachingNotificationsRepository repo(String owner) => CachingNotificationsRepository(
          source: source, cache: NotificationsCache(db), isOffline: () => offline, owner: owner, clock: () => kTestNow);

      final online = repo('u1');
      final live = await online.list(languageCode: 'en');
      await online.flushWrites();

      offline = true;
      final saved = await repo('u1').list(languageCode: 'en');
      expect([for (final n in saved) n.id], [for (final n in live) n.id]);
      expect(saved.first.kind, live.first.kind);
      expect([for (final n in saved) n.isRead], [for (final n in live) n.isRead]);
      await expectLater(repo('u2').list(languageCode: 'en'), throwsA(isA<NoSavedDataException>()));

      offline = false;
      source.failing = true;
      expect(await repo('u1').list(languageCode: 'en'), hasLength(live.length));
    });
  });

  group('sign-out', () {
    test('clears every personal row and keeps market data, news and public model reads', () async {
      final db = memoryDb();
      final signals = await simulatedSignals().feed(SignalProfile.defaults);
      final reads = await simulatedSignals().opportunities('EUR/USD');
      final quotes = await SimulatedMarketDataRepository(source: SimulatedMarketSource(clock: () => kTestNow)).quotes();
      await MarketCache(db).saveQuotes(quotes, kTestNow);
      await SignalsCache(db).saveList(SignalsCache.feedScope, 'u1', signals, kTestNow);
      await SignalsCache(db).saveItem(requested(signals.first), 'u1', kTestNow);
      await SignalsCache(db).saveList(SignalsCache.readScope('EUR/USD', AnalysisMethod.defaultId), '', reads, kTestNow);
      await NewsCache(db).saveArticles(
          'en', await SimulatedNewsRepository(clock: () => kTestNow).articles(languageCode: 'en'), kTestNow);
      await NotificationsCache(db).save(
          'u1', 'en', await SimulatedNotificationsRepository(clock: () => kTestNow).list(languageCode: 'en'), kTestNow);

      final auth = StateProvider<AuthState>(
        (ref) => const SignedIn(UserModel(id: 'u1', email: 'trader@example.com')),
      );
      final container = ProviderContainer(overrides: [
        authStateProvider.overrideWith((ref) => ref.watch(auth)),
        appDatabaseProvider.overrideWithValue(db),
      ]);
      addTearDown(container.dispose);
      container.listen(userCacheGuardProvider, (_, __) {});
      expect(container.read(cacheOwnerProvider), 'u1');

      container.read(auth.notifier).state = const SignedOut();
      container.read(userCacheGuardProvider);
      await Future<void>.delayed(const Duration(milliseconds: 50));

      expect(container.read(cacheOwnerProvider), '');
      expect(await SignalsCache(db).readList(SignalsCache.feedScope, 'u1'), isNull);
      expect(await SignalsCache(db).count(owner: 'u1'), 0);
      expect(await NotificationsCache(db).count(), 0);
      expect(await NotificationsCache(db).read('u1', 'en'), isNull);
      // العام بيضل
      expect((await MarketCache(db).readQuotes())!.value, hasLength(quotes.length));
      expect((await NewsCache(db).readArticles('en'))!.value, isNotEmpty);
      expect(
        (await SignalsCache(db).readList(SignalsCache.readScope('EUR/USD', AnalysisMethod.defaultId), ''))!.value,
        hasLength(reads.length),
      );
    });
  });

  group('low data mode', () {
    Future<ProviderContainer> container({
      Map<String, Object> prefs = const {},
      FakeConnectivitySource? connection,
      List<Override> overrides = const [],
    }) async {
      SharedPreferences.setMockInitialValues(prefs);
      final shared = await SharedPreferences.getInstance();
      final c = ProviderContainer(overrides: [
        sharedPreferencesProvider.overrideWithValue(shared),
        connectivityOverride(connection),
        ...overrides,
      ]);
      addTearDown(c.dispose);
      return c;
    }

    test('off by default; on persists across a restart; off restores every value at once', () async {
      final first = await container();
      expect(first.read(lowDataModeProvider), isFalse);
      expect(first.read(quoteUpdateIntervalProvider), Duration.zero);
      expect(first.read(candleWindowProvider), LiveCandlesNotifier.limit);
      expect(first.read(lowDataImageScaleProvider), 1);

      await first.read(lowDataModeProvider.notifier).set(true);
      expect(first.read(quoteUpdateIntervalProvider), const Duration(seconds: 5));
      expect(first.read(candleWindowProvider), kLowDataCandleWindow);
      expect(first.read(lowDataImageScaleProvider), kLowDataImageScale);
      expect(imageDecodeSize(100, 3, first.read(lowDataImageScaleProvider)), 150);

      final saved = (await SharedPreferences.getInstance()).getBool(kLowDataModeKey);
      expect(saved, isTrue);
      final restarted = await container(prefs: {kLowDataModeKey: true});
      expect(restarted.read(lowDataModeProvider), isTrue);

      await restarted.read(lowDataModeProvider.notifier).set(false);
      expect(restarted.read(quoteUpdateIntervalProvider), Duration.zero);
      expect(restarted.read(candleWindowProvider), LiveCandlesNotifier.limit);
    });

    test('candle window: the chart asks for (and keeps) fewer candles, back to the full window when off', () async {
      final c = await container(overrides: simulatedMarketOverrides());
      const key = ('EUR/USD', Timeframe.h1);
      c.listen(liveCandlesProvider(key), (_, __) {});
      expect(await c.read(liveCandlesProvider(key).future), hasLength(LiveCandlesNotifier.limit));

      await c.read(lowDataModeProvider.notifier).set(true);
      expect(await c.read(liveCandlesProvider(key).future), hasLength(kLowDataCandleWindow));

      await c.read(lowDataModeProvider.notifier).set(false);
      expect(await c.read(liveCandlesProvider(key).future), hasLength(LiveCandlesNotifier.limit));
    });

    test('forecast refresh: with low data only on the chart candle close', () {
      final now = DateTime.utc(2026, 10, 21, 14, 5);
      // عادي: إشارات 15m أسرع من شمعة الساعة
      expect(forecastRefreshAt(Timeframe.h1, now, follows: true), DateTime.utc(2026, 10, 21, 14, 15));
      // Low data: `follows` بيتطفى → سكرة شمعة الساعة بس
      expect(forecastRefreshAt(Timeframe.h1, now, follows: false), DateTime.utc(2026, 10, 21, 15));
    });

    test('suggestion: on mobile data or a slow connection, never auto-enabled, dismissible and remembered', () async {
      final connection = FakeConnectivitySource(NetworkStatus.online, true);
      final c = await container(connection: connection);
      c.listen(lowDataSuggestionProvider, (_, __) {});
      await pumpEventQueue();
      expect(c.read(lowDataSuggestionProvider), LowDataReason.mobileData);
      expect(c.read(lowDataModeProvider), isFalse, reason: 'only suggested');

      connection.emitMobileData(false);
      await pumpEventQueue();
      expect(c.read(lowDataSuggestionProvider), isNull);

      for (var i = 0; i < kSlowSamples; i++) {
        c.read(slowConnectionProvider.notifier).record(const Duration(seconds: 3));
      }
      expect(c.read(lowDataSuggestionProvider), LowDataReason.slowConnection);
      c.read(slowConnectionProvider.notifier).record(const Duration(milliseconds: 200));
      expect(c.read(lowDataSuggestionProvider), isNull, reason: 'one fast request clears "slow"');

      connection.emitMobileData(true);
      await pumpEventQueue();
      connection.emit(NetworkStatus.offline);
      await pumpEventQueue();
      expect(c.read(lowDataSuggestionProvider), isNull, reason: 'no suggestion while offline');
      connection.emit(NetworkStatus.online);
      await pumpEventQueue();
      expect(c.read(lowDataSuggestionProvider), LowDataReason.mobileData);

      await c.read(lowDataSuggestionDismissedProvider.notifier).dismiss();
      expect(c.read(lowDataSuggestionProvider), isNull);
      final restarted = await container(prefs: {kLowDataSuggestionDismissedKey: true}, connection: connection);
      expect(restarted.read(lowDataSuggestionProvider), isNull);
    });

    test('the latency interceptor measures each answered request', () {
      final clock = FakeClock();
      final samples = <Duration>[];
      final interceptor = LatencyInterceptor(samples.add, clock: clock.call);
      final options = RequestOptions(path: '/x');
      interceptor.onRequest(options, RequestInterceptorHandler());
      clock.advance(const Duration(seconds: 3));
      interceptor.onResponse(Response<Object?>(requestOptions: options), ResponseInterceptorHandler());
      expect(samples, [const Duration(seconds: 3)]);
      // انقطع بدون جواب: ما بينحسب (هيداك offline)
      interceptor.onRequest(options, RequestInterceptorHandler());
      // الـ handler بيكمّل الخطأ لقدّام (مستقبل فاشل ما حدا بيسمعله هون)
      runZonedGuarded(
        () => interceptor.onError(DioException(requestOptions: options), ErrorInterceptorHandler()),
        (_, __) {},
      );
      expect(samples, hasLength(1));
    });

    test('hidden tabs do not reload by themselves; they catch up when shown (or when the mode is off)', () async {
      final connection = FakeConnectivitySource();
      var reloads = 0;
      final probe = Provider<int>((ref) {
        reloadWhenBackOnline(ref, tab: ShellTab.signals, needed: () => true, reload: () => reloads++);
        return 0;
      });
      final c = await container(connection: connection);
      c.listen(probe, (_, __) {});
      c.listen(networkStatusProvider, (_, __) {});

      // عادي: رجع الاتصال → تحميل فورًا حتى لو التبويب مخفي
      connection.emit(NetworkStatus.offline);
      await pumpEventQueue();
      connection.emit(NetworkStatus.online);
      await pumpEventQueue();
      expect(reloads, 1);

      await c.read(lowDataModeProvider.notifier).set(true);
      connection.emit(NetworkStatus.offline);
      await pumpEventQueue();
      connection.emit(NetworkStatus.online);
      await pumpEventQueue();
      expect(reloads, 1, reason: 'Signals tab hidden: waits');

      c.read(currentShellTabProvider.notifier).state = ShellTab.signals;
      await pumpEventQueue();
      expect(reloads, 2, reason: 'shown → catches up once');

      c.read(currentShellTabProvider.notifier).state = ShellTab.home;
      connection.emit(NetworkStatus.offline);
      await pumpEventQueue();
      connection.emit(NetworkStatus.online);
      await pumpEventQueue();
      expect(reloads, 2);
      await c.read(lowDataModeProvider.notifier).set(false);
      await pumpEventQueue();
      expect(reloads, 3, reason: 'turning the mode off restores the normal reload at once');
    });
  });
}
