// H5d: تبديل الحساب عبر المسار الحقيقي بالظبط: TradingApp (يلي بيشغّل الـ
// guard)، الـ splash، Welcome → Log in (AuthController الوهمي الحقيقي)، الـ
// providers الحقيقية تبع الكاش والمصادر المحاكاة (بس القاعدة بالذاكرة)، و
// Profile → Log out. a@x.com بيحمّل Signals و News والصندوق والعدّاد وبيغيّر
// شي خاص فيه، بعدين بيطلع وبيدخل b@x.com: ولا شي خاص بـ a لازم يبيّن.

import 'dart:async';

import 'package:drift/drift.dart' show driftRuntimeOptions;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:trading_app/models/user_model.dart';
import 'package:trading_app/features/workspaces/data/workspaces_repository.dart';
import 'package:trading_app/features/auth/auth_state.dart';
import 'package:trading_app/features/alerts/data/alerts_repository.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:trading_app/app/app.dart';
import 'package:trading_app/app/shell/app_shell.dart';
import 'package:trading_app/app/shell/shell_tab.dart';
import 'package:trading_app/core/database/app_database_holder.dart';
import 'package:trading_app/core/database/database_providers.dart';
import 'package:trading_app/core/database/user_cache_guard.dart';
import 'package:trading_app/core/storage/preferences_provider.dart';
import 'package:trading_app/features/alerts/models/price_alert.dart';
import 'package:trading_app/features/alerts/view_models/alerts_view_model.dart';
import 'package:trading_app/features/assistant/data/chart_analysis_repository.dart';
import 'package:trading_app/features/assistant/view_models/assistant_view_model.dart';
import 'package:trading_app/features/auth/views/welcome_screen.dart';
import 'package:trading_app/features/markets/data/caching_market_data_repository.dart';
import 'package:trading_app/features/markets/data/market_cache.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/news/data/news_repository.dart';
import 'package:trading_app/features/news/view_models/news_view_models.dart';
import 'package:trading_app/features/notifications/data/caching_notifications_repository.dart';
import 'package:trading_app/features/notifications/data/notifications_repository.dart';
import 'package:trading_app/features/notifications/view_models/notifications_view_model.dart';
import 'package:trading_app/features/signals/data/caching_signals_repository.dart';
import 'package:trading_app/features/signals/data/signal_profile_repository.dart';
import 'package:trading_app/features/signals/models/analysis_request.dart';
import 'package:trading_app/features/signals/models/signal_profile.dart';
import 'package:trading_app/features/signals/view_models/signals_feed_view_model.dart';
import 'package:trading_app/features/markets/models/market_models.dart';
import 'package:trading_app/features/workspaces/view_models/workspaces_view_model.dart';
import 'package:trading_app/providers/app_providers.dart';

import '../../helpers/test_app.dart';

ProviderContainer _container(WidgetTester tester) =>
    ProviderScope.containerOf(tester.element(find.byType(Navigator).first));

Finder _field(String label) => find.ancestor(of: find.text(label), matching: find.byType(Column)).first;

Future<void> _type(WidgetTester tester, String label, String value) async {
  await tester.enterText(find.descendant(of: _field(label), matching: find.byType(TextField)), value);
  await tester.pump();
}

/// وقت وهمي لحد ما الـ Future يخلص (طلبات المحاكاة إلها تأخير)
Future<T> _wait<T>(WidgetTester tester, Future<T> future) async {
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
  for (var i = 0; i < 400 && !done; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
  if (!done) fail('did not finish');
  if (error != null) throw error!;
  return value;
}

/// Welcome → Log in → Home عبر الشاشات
Future<void> _logIn(WidgetTester tester, String email) async {
  expect(find.byType(WelcomeScreen), findsOneWidget);
  await tester.tap(find.text('Log in').hitTestable().first);
  await tester.pumpAndSettle();
  await _type(tester, 'Email', email);
  await _type(tester, 'Password', 'research42');
  await tester.tap(find.widgetWithText(FilledButton, 'Log in'));
  await tester.pump(const Duration(seconds: 3));
  await settleMocks(tester);
  expect(find.byType(AppShell), findsOneWidget);
}

Future<void> _openTab(WidgetTester tester, ShellTab tab) async {
  await tester.tap(find.descendant(of: find.byType(NavigationBar), matching: find.byType(NavigationDestination)).at(
        tab.index,
      ));
  await settleMocks(tester);
}

/// Profile → Log out → تأكيد → Welcome
Future<void> _logOut(WidgetTester tester) async {
  await _openTab(tester, ShellTab.profile);
  await scrollTo(tester, find.text('Log out'));
  await tester.tap(find.text('Log out'));
  await tester.pumpAndSettle();
  await tester.tap(find.widgetWithText(TextButton, 'Log out'));
  await tester.pump(const Duration(seconds: 2));
  await settleMocks(tester);
  expect(find.byType(WelcomeScreen), findsOneWidget);
}

void main() {
  driftRuntimeOptions.dontWarnAboutMultipleDatabases = true;

  testWidgets('a@x.com → log out → b@x.com through the real screens: nothing of a@x.com is left', (tester) async {
    final db = AppDatabaseHolder.memory();
    addTearDown(() => unawaited(db.close()));
    usePhoneSize(tester, height: 1400);
    await tester.pumpWidget(await testScope(
      const TradingApp(),
      signedIn: null,
      sessionRestored: false,
      overrides: [
        // القاعدة بالذاكرة (الملف الحقيقي بيعلق بالاختبار)، والباقي = providers التطبيق نفسها
        appDatabaseProvider.overrideWithValue(db),
        // السوق المحاكى بالاختبار على kTestNow: ساعة الكاش نفسها (متل التطبيق: الاتنين DateTime.now)
        marketCacheClockProvider.overrideWithValue(() => kTestNow),
        marketDataRepositoryProvider.overrideWith(createMarketDataRepository),
        signalsRepositoryProvider.overrideWith(createSignalsRepository),
        newsRepositoryProvider.overrideWith(createNewsRepository),
        notificationsRepositoryProvider.overrideWith(createNotificationsRepository),
        notificationsSourceRepositoryProvider.overrideWith((ref) {
          ref.watch(cacheOwnerProvider);
          return SimulatedNotificationsRepository(clock: () => kTestNow, prefs: ref.watch(sharedPreferencesProvider));
        }),
      ],
    ));
    // splash → Welcome (ما في جلسة محفوظة)
    for (var i = 0; i < 20; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }
    await settleMocks(tester);

    // ── a@x.com ──
    await _logIn(tester, 'a@x.com');
    final c = _container(tester);
    final idA = c.read(authControllerProvider).currentUser!.id;
    expect(idA, 'uid_a@x.com');

    // Home: العدّاد، Signals: القائمة، Community: الأخبار، الجرس: الصندوق
    final seededUnread = c.read(unreadNotificationsProvider);
    expect(seededUnread, greaterThan(0));
    await _openTab(tester, ShellTab.signals);
    final feedA = await _wait(tester, c.read(signalsFeedViewModelProvider.future));
    expect(feedA, isNotEmpty);
    await _openTab(tester, ShellTab.community);
    expect((await _wait(tester, c.read(newsViewModelProvider.future))).articles, isNotEmpty);

    // أشياء خاصة بـ a: طلب تحليل، حذف إشعار + الكل مقروء، استراتيجية، تنبيه
    final requested = await _wait(
      tester,
      c
          .read(signalsRepositoryProvider)
          .requestAnalysis(const AnalysisRequest(symbol: 'EUR/USD', timeframe: Timeframe.h1)),
    );
    await _wait(tester, c.read(signalsFeedViewModelProvider.notifier).refresh());
    final deleted = c.read(notificationsViewModelProvider).value!.first;
    await _wait(tester, c.read(notificationsViewModelProvider.notifier).remove(deleted.id));
    await _wait(tester, c.read(notificationsViewModelProvider.notifier).markAllRead());
    expect(c.read(unreadNotificationsProvider), 0);
    await _wait(tester,
        c.read(signalProfileProvider.notifier).save(SignalProfile.defaults.copyWith(symbols: const {'XAU/USD'})));
    await _wait(
      tester,
      c.read(alertsViewModelProvider.notifier).create(const AlertDraft(
            symbol: 'EUR/USD',
            condition: AlertCondition.above,
            value: 9,
          )),
    );
    await _wait(
        tester, c.read(workspacesViewModelProvider.notifier).create(name: 'Gold desk', symbols: const ['XAU/USD']));
    expect(c.read(workspacesViewModelProvider).value!.custom, hasLength(1));
    c.read(assistantViewModelProvider.notifier).send('What is the trend on gold?').ignore();
    await tester.pump(const Duration(seconds: 3));
    expect(c.read(assistantViewModelProvider).messages, isNotEmpty);
    expect(c.read(alertsViewModelProvider).value, hasLength(1));
    await _wait(tester, (c.read(signalsRepositoryProvider) as CachingSignalsRepository).flushWrites());
    await _wait(tester, (c.read(notificationsRepositoryProvider) as CachingNotificationsRepository).flushWrites());
    await _wait(tester, (c.read(marketDataRepositoryProvider) as CachingMarketDataRepository).flushWrites());
    expect(requested.isDetected, isTrue);
    expect(await _wait(tester, SignalsCache(db).count(owner: idA)), greaterThan(0),
        reason: 'feed + requested saved for a');
    expect(await _wait(tester, NotificationsCache(db).count(owner: idA)), greaterThan(0));

    // ── Log out ──
    await _logOut(tester);
    await tester.pump(const Duration(milliseconds: 200));
    expect(await _wait(tester, SignalsCache(db).count(owner: idA)), 0, reason: 'Drift rows of a deleted');
    expect(await _wait(tester, NotificationsCache(db).count()), 0);
    expect((await _wait(tester, MarketCache(db).readQuotes())), isNotNull, reason: 'market data stays');

    // ── b@x.com ──
    await _logIn(tester, 'b@x.com');
    final idB = c.read(authControllerProvider).currentUser!.id;
    expect(idB, 'uid_b@x.com');

    // العدّاد = صندوق b (من الأول)، مش 0 تبع a
    await _wait(tester, c.read(notificationsViewModelProvider.future));
    expect(c.read(unreadNotificationsProvider), seededUnread);
    expect([for (final n in c.read(notificationsViewModelProvider).value!) n.id], contains(deleted.id));
    // القائمة: ما في طلب a، والاستراتيجية مش تبعه
    await _openTab(tester, ShellTab.signals);
    final feedB = await _wait(tester, c.read(signalsFeedViewModelProvider.future));
    expect(feedB.where((o) => o.requestedByYou), isEmpty, reason: 'no requested signal of a@x.com');
    expect(c.read(signalProfileProvider).symbols, SignalProfile.defaults.symbols, reason: 'strategy is per account');
    // التنبيهات والحدّ اليومي للمساعد إلو هو
    expect(await _wait(tester, c.read(alertsViewModelProvider.future)), isEmpty, reason: 'alerts are per account');
    expect(c.read(workspacesViewModelProvider).value!.custom, isEmpty, reason: 'workspaces are per account');
    expect(c.read(assistantViewModelProvider).messages, isEmpty, reason: 'the assistant chat is per account');
    expect(c.read(chartAnalysisRepositoryProvider), isA<SimulatedChartAnalysisRepository>());
    expect((c.read(chartAnalysisRepositoryProvider) as SimulatedChartAnalysisRepository).userId, idB,
        reason: 'the daily limit counter is per account');
    expect(await _wait(tester, SignalsCache(db).count(owner: idA)), 0);
    expect((await _wait(tester, MarketCache(db).readQuotes())), isNotNull, reason: 'market data still there');
  });

  test('per-account data on this device: claimed by the first account, cleared on switch / sign-out, settings stay',
      () async {
    SharedPreferences.setMockInitialValues({
      LocalSignalProfileRepository.storageKey: '{"symbols":["XAU/USD"]}',
      LocalAlertsRepository.storageKey: '[]',
      LocalWorkspacesRepository.storageKey: '[]',
      'risk_limits': '{"capital":1000}',
    });
    final prefs = await SharedPreferences.getInstance();
    final auth = StateProvider<AuthState>((ref) => const SignedOut());
    final c = ProviderContainer(overrides: [
      sharedPreferencesProvider.overrideWithValue(prefs),
      authStateProvider.overrideWith((ref) => ref.watch(auth)),
      appDatabaseProvider.overrideWith((ref) => AppDatabaseHolder.memory()),
    ]);
    addTearDown(c.dispose);
    c.listen(userCacheGuardProvider, (_, __) {});

    // قبل H5d ما في صاحب: أول حساب بيدخل بياخدها
    c.read(auth.notifier).state = const SignedIn(UserModel(id: 'uid_a', email: 'a@x.com'));
    await pumpEventQueue();
    expect(prefs.getString(LocalSignalProfileRepository.storageKey), isNotNull);
    expect(prefs.getString(kAccountPrefsOwnerKey), 'uid_a');

    // حساب تاني بدون خروج: بتنمسح
    c.read(auth.notifier).state = const SignedIn(UserModel(id: 'uid_b', email: 'b@x.com'));
    await pumpEventQueue();
    for (final key in kAccountPrefsKeys) {
      expect(prefs.containsKey(key), isFalse, reason: key);
    }
    expect(prefs.getString(kAccountPrefsOwnerKey), 'uid_b');

    // خروج: بتنمسح كمان؛ إعدادات الجهاز بتضل
    await prefs.setString(LocalAlertsRepository.storageKey, '[]');
    c.read(auth.notifier).state = const SignedOut();
    await pumpEventQueue();
    expect(prefs.containsKey(LocalAlertsRepository.storageKey), isFalse);
    expect(prefs.containsKey(kAccountPrefsOwnerKey), isFalse);
    expect(prefs.getString('risk_limits'), isNotNull);
  });
}
