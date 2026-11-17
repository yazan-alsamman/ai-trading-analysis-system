// H5c: انحدارات من المحاكي.
// 1) شريط "You’re offline" مرتين على Notifications وخبر News (الشاشة نفسها
//    كانت تحط شريط تحت شريط الـ shell). شريط واحد وsnackbar واحد لكل حدث
//    offline على كل الشاشات، والتعليق بدون اتصال: رسالة وحدة والمسودة بتضل.
// 2) تبديل الحساب: كل إيميل كان ياخد نفس المعرّف (`uid_mock`)، والقائمة
//    والصندوق بالذاكرة كانوا يضلّوا. لازم يتمسحوا (الكاش والذاكرة) مع الخروج،
//    نهاية الجلسة، ودخول حساب تاني؛ بيانات السوق بتضل.

import 'dart:async';

import 'package:drift/drift.dart' show driftRuntimeOptions;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/app/router/app_router.dart';
import 'package:trading_app/app/router/app_routes.dart';
import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/database/app_database_holder.dart';
import 'package:trading_app/core/database/user_cache_guard.dart';
import 'package:trading_app/features/auth/auth_state.dart';
import 'package:trading_app/features/markets/data/market_cache.dart';
import 'package:trading_app/features/markets/data/market_data_repository.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/markets/data/simulated_market_source.dart';
import 'package:trading_app/features/news/data/caching_news_repository.dart';
import 'package:trading_app/features/news/data/news_repository.dart';
import 'package:trading_app/features/notifications/data/caching_notifications_repository.dart';
import 'package:trading_app/features/notifications/data/notifications_repository.dart';
import 'package:trading_app/features/notifications/view_models/notifications_view_model.dart';
import 'package:trading_app/features/signals/data/caching_signals_repository.dart';
import 'package:trading_app/features/signals/data/signals_repository.dart';
import 'package:trading_app/features/signals/models/analysis_method.dart';
import 'package:trading_app/features/signals/models/analysis_request.dart';
import 'package:trading_app/features/signals/models/model_accuracy.dart';
import 'package:trading_app/features/signals/models/opportunity.dart';
import 'package:trading_app/features/signals/models/signal_profile.dart';
import 'package:trading_app/features/signals/view_models/signals_feed_view_model.dart';
import 'package:trading_app/features/signals/widgets/signal_row.dart';
import 'package:trading_app/features/workspaces/widgets/workspace_chip.dart';
import 'package:trading_app/models/user_model.dart';
import 'package:trading_app/providers/app_providers.dart';

import '../../helpers/test_app.dart';

/// عملية async جوّا الوقت الوهمي: منقدّم الوقت لحد ما تخلص
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
  for (var i = 0; i < 300 && !done; i++) {
    await tester.pump(const Duration(milliseconds: 10));
  }
  if (!done) fail('async call did not finish');
  if (error != null) throw error!;
  return value;
}

AppDatabaseHolder emptyCache() {
  final db = AppDatabaseHolder.memory();
  addTearDown(() => unawaited(db.close()));
  return db;
}

/// أسعار + أخبار محفوظين (عامين، مش لحساب)
Future<AppDatabaseHolder> publicCache(WidgetTester tester) async {
  final db = emptyCache();
  final market = SimulatedMarketDataRepository(source: SimulatedMarketSource(clock: () => kTestNow));
  await settle(tester, MarketCache(db).saveQuotes(await market.quotes(), kTestNow));
  final news = SimulatedNewsRepository(clock: () => kTestNow);
  await settle(tester, NewsCache(db).saveArticles('en', await news.articles(languageCode: 'en'), kTestNow));
  await settle(tester, NewsCache(db).saveMood(await news.mood(), kTestNow));
  return db;
}

final _offlineStrip = find.textContaining('Showing the last received data.', findRichText: true);

/// التطبيق الحقيقي (router + shell) على [route]، مع الكاش بالذاكرة
Future<ProviderContainer> pumpApp(
  WidgetTester tester,
  String route, {
  required AppDatabaseHolder db,
  FakeConnectivitySource? device,
}) async {
  usePhoneSize(tester, height: 1400);
  await tester.pumpWidget(await testScope(
    TestApp(initialRoute: route),
    overrides: [
      ...cachedMarketOverrides(db: db),
      ...cachedFeatureOverrides(),
      if (device != null) connectivityOverride(device),
    ],
  ));
  await tester.pumpAndSettle();
  return ProviderScope.containerOf(tester.element(find.byType(Navigator).first));
}

Future<void> setOffline(WidgetTester tester, ProviderContainer c, bool offline) async {
  c.read(networkStatusProvider.notifier).set(offline ? NetworkStatus.offline : NetworkStatus.online);
  await tester.pumpAndSettle();
}

/// سحب للتحديث على أول RefreshIndicator ظاهر
Future<void> pullToRefresh(WidgetTester tester) async {
  unawaited(tester.state<RefreshIndicatorState>(find.byType(RefreshIndicator).hitTestable().first).show());
  await tester.pumpAndSettle();
}

/// مصدر إشارات بقائمة بتوصل لما الاختبار يقرّر (طلب بالطريق وقت الخروج)
final class _GatedSignals implements SignalsRepository {
  _GatedSignals(this.inner);

  final SignalsRepository inner;
  Completer<void>? gate;

  @override
  bool get isSimulated => true;
  @override
  Future<ModelAccuracy> accuracy() => inner.accuracy();
  @override
  Future<List<Opportunity>> feed(SignalProfile profile) async {
    final wait = gate;
    if (wait != null) await wait.future;
    return inner.feed(profile);
  }

  @override
  Future<Opportunity?> opportunity(String id) => inner.opportunity(id);
  @override
  Future<List<Opportunity>> opportunities(String symbol, {String methodId = AnalysisMethod.defaultId}) =>
      inner.opportunities(symbol, methodId: methodId);
  @override
  Future<Opportunity> requestAnalysis(AnalysisRequest request,
          {AnalysisCancelToken? cancel, void Function(AnalysisStage stage)? onStage}) =>
      inner.requestAnalysis(request, cancel: cancel, onStage: onStage);
}

void main() {
  driftRuntimeOptions.dontWarnAboutMultipleDatabases = true;

  group('bug 1: one offline strip and one snackbar per offline event', () {
    for (final route in [
      AppRoutes.home,
      AppRoutes.market('EUR/USD'),
      AppRoutes.signals,
      AppRoutes.assistant,
      AppRoutes.community,
      AppRoutes.notifications,
      AppRoutes.newsDetail('fed-rate-decision'),
      AppRoutes.plans,
    ]) {
      testWidgets('$route: exactly one offline strip', (tester) async {
        final c = await pumpApp(tester, route, db: await publicCache(tester));
        expect(_offlineStrip, findsNothing);
        await setOffline(tester, c, true);
        expect(_offlineStrip, findsOneWidget);
        await setOffline(tester, c, false);
        expect(_offlineStrip, findsNothing, reason: 'never stuck after Simulate offline is off');
      });
    }

    for (final (route, text) in [
      (AppRoutes.home, 'You’re offline, so prices can’t refresh'),
      (AppRoutes.signals, 'You’re offline, so signals can’t refresh'),
      (AppRoutes.community, 'You’re offline, so news can’t refresh'),
      (AppRoutes.notifications, 'You’re offline, so notifications can’t refresh'),
    ]) {
      testWidgets('$route: pull to refresh offline = one snackbar, also when pulled twice', (tester) async {
        final c = await pumpApp(tester, route, db: await publicCache(tester));
        await setOffline(tester, c, true);
        await pullToRefresh(tester);
        expect(find.byType(SnackBar), findsOneWidget);
        expect(find.textContaining(text), findsOneWidget);
        await pullToRefresh(tester);
        expect(find.byType(SnackBar), findsOneWidget);
      });
    }

    testWidgets('Posts: refresh offline = one snackbar', (tester) async {
      final c = await pumpApp(tester, AppRoutes.community, db: await publicCache(tester));
      await tester.tap(find.text('Posts'));
      await tester.pumpAndSettle();
      await setOffline(tester, c, true);
      await pullToRefresh(tester);
      expect(find.byType(SnackBar), findsOneWidget);
    });

    testWidgets('Strategy and Workspaces sheets offline: one strip behind them', (tester) async {
      final c = await pumpApp(tester, AppRoutes.signals, db: await publicCache(tester));
      await setOffline(tester, c, true);
      await tester.tap(find.text('Strategy').first);
      await tester.pumpAndSettle();
      expect(_offlineStrip, findsOneWidget);
      Navigator.of(tester.element(find.byType(BottomSheet))).pop();
      await tester.pumpAndSettle();

      c.read(appRouterProvider).go(AppRoutes.home);
      await tester.pumpAndSettle();
      await tester.tap(find.byType(WorkspaceChip).first);
      await tester.pumpAndSettle();
      expect(_offlineStrip, findsOneWidget);
    });

    testWidgets('a comment offline: one message, the draft stays; back online it sends', (tester) async {
      final c = await pumpApp(tester, AppRoutes.newsDetail('fed-rate-decision'), db: await publicCache(tester));
      await tester.tap(find.textContaining('Comments'));
      await tester.pumpAndSettle();
      await setOffline(tester, c, true);
      await tester.enterText(find.byType(TextField).last, 'Gold holds');
      await tester.pump();
      await tester.tap(find.byIcon(Icons.send_rounded));
      await tester.pumpAndSettle();
      expect(find.byType(SnackBar), findsOneWidget);
      expect(find.textContaining('your comment wasn’t sent'), findsOneWidget);
      expect(find.text('Gold holds'), findsOneWidget);

      await setOffline(tester, c, false);
      await tester.pump(const Duration(seconds: 5)); // الـ snackbar فوق زر الإرسال بيروح
      await tester.pumpAndSettle();
      await tester.tap(find.byIcon(Icons.send_rounded));
      await tester.pumpAndSettle();
      final field = tester.widget<TextField>(find.byType(TextField).last);
      expect(field.controller!.text, isEmpty, reason: 'sent, so the field is cleared');
      expect(find.text('Gold holds'), findsOneWidget, reason: 'now in the list');
    });

    testWidgets('connectivity returns: the offline state on Signals is not stuck', (tester) async {
      final device = FakeConnectivitySource();
      final c = await pumpApp(tester, AppRoutes.home, db: emptyCache(), device: device);
      device.emit(NetworkStatus.offline);
      await tester.pumpAndSettle();
      c.read(appRouterProvider).go(AppRoutes.signals);
      await tester.pumpAndSettle();
      expect(find.byType(SignalRow), findsNothing);
      expect(find.text('Signals will load when you’re back online.'), findsOneWidget);
      device.emit(NetworkStatus.online);
      await tester.pumpAndSettle();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pumpAndSettle();
      expect(find.byType(SignalRow), findsWidgets);
      expect(_offlineStrip, findsNothing);
    });
  });

  group('bug 2: account switch', () {
    testWidgets('the mock sign-in gives each account its own id (same email = same id)', (tester) async {
      final c = ProviderContainer(overrides: (await testScope(const SizedBox(), signedIn: null)).overrides);
      addTearDown(c.dispose);
      final auth = c.read(authControllerProvider);
      Future<String> signIn(String email) async {
        unawaited(auth.login(email: email, password: 'Secret123!'));
        await tester.pump(const Duration(seconds: 3));
        final id = c.read(cacheOwnerProvider);
        await auth.endSession();
        await tester.pump();
        expect(c.read(cacheOwnerProvider), '');
        return id;
      }

      final a = await signIn('a@example.com');
      final b = await signIn('b@example.com');
      expect(a, isNotEmpty);
      expect(b, isNot(a));
      expect(await signIn(' A@Example.com '), a);
      c.dispose();
      await tester.pump(const Duration(seconds: 5));
    });

    Future<(ProviderContainer, StateController<AuthState>)> container(
      WidgetTester tester,
      AppDatabaseHolder db, {
      SignalsRepository? signals,
      String first = 'a',
    }) async {
      final auth = StateProvider<AuthState>((ref) => SignedIn(UserModel(id: first, email: '$first@example.com')));
      final base = (await testScope(const SizedBox())).overrides;
      final c = ProviderContainer(overrides: [
        ...base,
        ...cachedMarketOverrides(db: db),
        ...cachedFeatureOverrides(signals: signals),
        authStateProvider.overrideWith((ref) => ref.watch(auth)),
      ]);
      addTearDown(c.dispose);
      c.listen(userCacheGuardProvider, (_, __) {});
      c.listen(signalsFeedViewModelProvider, (_, __) {});
      c.listen(notificationsViewModelProvider, (_, __) {});
      c.listen(unreadNotificationsProvider, (_, __) {});
      await settle(tester, c.read(signalsFeedViewModelProvider.future));
      await settle(tester, c.read(notificationsViewModelProvider.future));
      return (c, c.read(auth.notifier));
    }

    Future<void> flush(WidgetTester tester, ProviderContainer c) async {
      await settle(tester, (c.read(signalsRepositoryProvider) as CachingSignalsRepository).flushWrites());
      await settle(tester, (c.read(notificationsRepositoryProvider) as CachingNotificationsRepository).flushWrites());
    }

    testWidgets('sign-out then another account (offline): no feed, inbox or badge of the first account',
        (tester) async {
      final db = await publicCache(tester);
      final (c, auth) = await container(tester, db);
      expect(c.read(signalsFeedViewModelProvider).value, isNotEmpty);
      expect(c.read(unreadNotificationsProvider), greaterThan(0));
      await flush(tester, c);
      expect(await settle(tester, SignalsCache(db).count(owner: 'a')), greaterThan(0));

      auth.state = const SignedOut();
      await tester.pump(const Duration(milliseconds: 50));
      c.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      auth.state = const SignedIn(UserModel(id: 'b', email: 'b@example.com'));
      await tester.pump(const Duration(milliseconds: 50));
      await settle(tester, c.read(signalsFeedViewModelProvider.future).then((_) {}, onError: (_) {}));
      await settle(tester, c.read(notificationsViewModelProvider.future).then((_) {}, onError: (_) {}));

      expect(c.read(signalsFeedViewModelProvider).valueOrNull ?? const [], isEmpty);
      expect(c.read(signalsFeedViewModelProvider).error, isA<SignalsOfflineException>());
      expect(c.read(notificationsViewModelProvider).valueOrNull ?? const [], isEmpty);
      expect(c.read(unreadNotificationsProvider), 0);
      expect(await settle(tester, SignalsCache(db).count(owner: 'a')), 0);
      expect(await settle(tester, NotificationsCache(db).count()), 0);
      // بيانات السوق مش لحساب: بتضل
      expect((await settle(tester, MarketCache(db).readQuotes()))!.value, isNotEmpty);
    });

    testWidgets('another account signs in without a sign-out: the first account rows go', (tester) async {
      final db = await publicCache(tester);
      final (c, auth) = await container(tester, db);
      await flush(tester, c);
      auth.state = const SignedIn(UserModel(id: 'b', email: 'b@example.com'));
      await tester.pump(const Duration(milliseconds: 50));
      expect(await settle(tester, SignalsCache(db).count(owner: 'a')), 0);
      expect(await settle(tester, NotificationsCache(db).count(owner: 'a')), 0);
    });

    testWidgets('a notification read / deleted by one account is not carried to the next one (online)',
        (tester) async {
      final db = await publicCache(tester);
      final (c, auth) = await container(tester, db);
      final first = c.read(notificationsViewModelProvider).value!.first;
      await settle(tester, c.read(notificationsViewModelProvider.notifier).remove(first.id));
      auth.state = const SignedOut();
      await tester.pump();
      auth.state = const SignedIn(UserModel(id: 'b', email: 'b@example.com'));
      await tester.pump();
      final list = await settle(tester, c.read(notificationsViewModelProvider.future));
      expect([for (final n in list) n.id], contains(first.id));
    });

    testWidgets('the same account back after sign-out (offline): nothing stale, even from a late write',
        (tester) async {
      final db = await publicCache(tester);
      final gated = _GatedSignals(SimulatedSignalsRepository(source: SimulatedMarketSource(clock: () => kTestNow)));
      final (c, auth) = await container(tester, db, signals: gated);
      await flush(tester, c);
      // تحديث بالطريق وقت الخروج: جوابه بيوصل بعد المسح
      gated.gate = Completer<void>();
      final refresh = c.read(signalsFeedViewModelProvider.notifier).refresh().then((_) {}, onError: (_) {});
      await tester.pump();
      auth.state = const SignedOut();
      await tester.pump(const Duration(milliseconds: 50));
      gated.gate!.complete();
      await settle(tester, refresh);
      await tester.pump(const Duration(milliseconds: 50));
      expect(await settle(tester, SignalsCache(db).count(owner: 'a')), 0, reason: 'late write dropped');

      c.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      auth.state = const SignedIn(UserModel(id: 'a', email: 'a@example.com'));
      await tester.pump(const Duration(milliseconds: 50));
      await settle(tester, c.read(signalsFeedViewModelProvider.future).then((_) {}, onError: (_) {}));
      expect(c.read(signalsFeedViewModelProvider).valueOrNull ?? const [], isEmpty);
      expect(c.read(signalsFeedViewModelProvider).error, isA<SignalsOfflineException>());
    });

    testWidgets('session end (refresh refused) clears like a sign-out', (tester) async {
      final db = await publicCache(tester);
      final (c, auth) = await container(tester, db);
      await flush(tester, c);
      auth.state = const SignedOut(); // endSession() = نفس الانتقال
      await tester.pump(const Duration(milliseconds: 50));
      expect(await settle(tester, SignalsCache(db).count(owner: 'a')), 0);
      expect(await settle(tester, NotificationsCache(db).count()), 0);
    });

    testWidgets('app start with a different saved account: rows of other accounts are cleared', (tester) async {
      final db = await publicCache(tester);
      final feed = await SimulatedSignalsRepository(source: SimulatedMarketSource(clock: () => kTestNow))
          .feed(SignalProfile.defaults);
      await settle(tester, SignalsCache(db).saveList(SignalsCache.feedScope, 'old', feed, kTestNow));
      await container(tester, db, first: 'new');
      await tester.pump(const Duration(milliseconds: 50));
      expect(await settle(tester, SignalsCache(db).count(owner: 'old')), 0);
    });
  });
}
