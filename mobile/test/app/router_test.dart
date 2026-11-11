// اختبارات الـ router (go_router، G2): الـ auth guard، الإقلاع (splash)، نهاية
// الجلسة، الـ shell (حالة كل تبويب)، حماية الضغطة المزدوجة، المسار المش معروف،
// تفاصيل إشارة من مسار، الـ Hero والشريط السفلي، وsheet الـ Strategy →
// Backtest → رجوع. كلها على جدول المسارات الحقيقي (appRouterProvider).

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/app/app.dart';
import 'package:trading_app/app/router/app_router.dart';
import 'package:trading_app/app/router/app_routes.dart';
import 'package:trading_app/app/shell/app_shell.dart';
import 'package:trading_app/app/shell/shell_tab.dart';
import 'package:trading_app/features/auth/auth_state.dart';
import 'package:trading_app/features/auth/views/login_screen.dart';
import 'package:trading_app/features/auth/views/register_screen.dart';
import 'package:trading_app/features/auth/views/splash_screen.dart';
import 'package:trading_app/features/auth/views/welcome_screen.dart';
import 'package:trading_app/features/backtest/views/backtest_screen.dart';
import 'package:trading_app/features/community/views/expert_chat_screen.dart';
import 'package:trading_app/features/help/views/legal_screen.dart';
import 'package:trading_app/features/home/views/home_screen.dart';
import 'package:trading_app/features/home/widgets/watchlist_row.dart';
import 'package:trading_app/features/insights/views/insights_screen.dart';
import 'package:trading_app/features/markets/views/market_screen.dart';
import 'package:trading_app/features/markets/widgets/market_hero.dart';
import 'package:trading_app/features/profile/views/profile_screen.dart';
import 'package:trading_app/features/signals/views/signal_detail_screen.dart';
import 'package:trading_app/features/signals/widgets/accuracy_line.dart';
import 'package:trading_app/features/signals/widgets/signal_row.dart';
import 'package:trading_app/models/user_model.dart';

import '../helpers/test_app.dart';

const _user = SignedIn(UserModel(id: 'u', email: 'trader@example.com'));

/// التطبيق على الـ router الحقيقي، على [route]
Future<void> _pump(
  WidgetTester tester, {
  String route = AppRoutes.home,
  bool? signedIn = true,
  List<Override> overrides = const [],
  double height = 812,
}) async {
  usePhoneSize(tester, height: height);
  await tester.pumpWidget(await testScope(TestApp(initialRoute: route), signedIn: signedIn, overrides: overrides));
  await settleMocks(tester);
}

/// مسار الشاشة يلي فوق (مع يلي انفتح بـ push)
String _location(WidgetTester tester) => testRouter(tester).state.uri.toString();

/// قائمة الـ Home العمودية
Finder _homeList() => find
    .descendant(
      of: find.byType(HomeScreen),
      matching: find.byWidgetPredicate((w) => w is Scrollable && w.axisDirection == AxisDirection.down),
    )
    .first;

/// الشريط السفلي ظاهر (مش مخفي تحت شاشة كاملة)
Finder _visibleBar() => find.byType(NavigationBar).hitTestable();

Future<void> _openTab(WidgetTester tester, ShellTab tab) async {
  await tester.tap(
    find.descendant(of: find.byType(NavigationBar), matching: find.byType(NavigationDestination)).at(tab.index),
  );
  await tester.pumpAndSettle();
}

/// الـ tag تبع أول Hero جوّا [of]
Object _heroTag(WidgetTester tester, Finder of) =>
    tester.widget<Hero>(find.descendant(of: of, matching: find.byType(Hero)).first).tag;

void main() {
  group('guard (authRedirect)', () {
    test('signed out: every protected path → /welcome; public paths stay', () {
      for (final path in [
        AppRoutes.home,
        AppRoutes.signals,
        AppRoutes.market('EUR/USD', tab: ShellTab.assistant),
        AppRoutes.signalDetail('s1', symbol: 'XAU/USD'),
        AppRoutes.backtest,
        AppRoutes.expertChat('expert-1'),
        AppRoutes.legal(LegalDocument.riskDisclosure),
      ]) {
        expect(authRedirect(path: Uri.parse(path).path, signedIn: false, sessionRestored: true), AppRoutes.welcome,
            reason: path);
      }
      for (final path in [AppRoutes.welcome, AppRoutes.login, AppRoutes.registration, AppRoutes.otpVerification]) {
        expect(authRedirect(path: path, signedIn: false, sessionRestored: true), isNull, reason: path);
      }
    });

    test('signed in: Welcome / Log in / Create account → /home; Verify email and the app stay', () {
      for (final path in AppRoutes.signedOutOnly) {
        expect(authRedirect(path: path, signedIn: true, sessionRestored: true), AppRoutes.home, reason: path);
      }
      for (final path in [AppRoutes.otpVerification, AppRoutes.home, AppRoutes.insights, AppRoutes.plans]) {
        expect(authRedirect(path: path, signedIn: true, sessionRestored: true), isNull, reason: path);
      }
    });

    test('before the session is read: the splash stays, any other path goes back to it', () {
      expect(authRedirect(path: AppRoutes.splash, signedIn: true, sessionRestored: false), isNull);
      expect(authRedirect(path: AppRoutes.splash, signedIn: false, sessionRestored: false), isNull);
      expect(authRedirect(path: AppRoutes.home, signedIn: true, sessionRestored: false), AppRoutes.splash);
      expect(authRedirect(path: AppRoutes.welcome, signedIn: false, sessionRestored: false), AppRoutes.splash);
      // بعدها: جلسة → الرئيسية، بدونها → Welcome
      expect(authRedirect(path: AppRoutes.splash, signedIn: true, sessionRestored: true), AppRoutes.home);
      expect(authRedirect(path: AppRoutes.splash, signedIn: false, sessionRestored: true), AppRoutes.welcome);
      // معرض الـ design system بيفتح دايمًا
      expect(authRedirect(path: AppRoutes.designSystem, signedIn: false, sessionRestored: false), isNull);
    });

    testWidgets('signed out: a protected path opens Welcome, with no bar', (tester) async {
      await _pump(tester, route: AppRoutes.market('EUR/USD'), signedIn: false);
      expect(find.byType(WelcomeScreen), findsOneWidget);
      expect(find.byType(MarketScreen), findsNothing);
      expect(find.byType(NavigationBar), findsNothing);
      expect(_location(tester), AppRoutes.welcome);
    });

    for (final (route, screen) in [(AppRoutes.login, LoginScreen), (AppRoutes.registration, RegistrationScreen)]) {
      testWidgets('signed in: opening $route lands on Home', (tester) async {
        await _pump(tester, route: route);
        expect(find.byType(screen), findsNothing);
        expect(find.byType(HomeScreen), findsOneWidget);
        expect(_location(tester), AppRoutes.home);

        // ونفس الشي لو انفتح بـ push من جوّا التطبيق
        testRouter(tester).push<void>(route);
        await tester.pumpAndSettle();
        expect(find.byType(screen), findsNothing);
        expect(find.byType(HomeScreen), findsOneWidget);
      });
    }
  });

  group('cold start (real TradingApp)', () {
    // الجلسة الحقيقية: "داخل" = جلسة محفوظة على الجهاز (G3)
    Future<void> coldStart(WidgetTester tester, {required bool signedIn}) async {
      usePhoneSize(tester);
      final saved = SavedSession();
      await tester.pumpWidget(await testScope(
        const TradingApp(),
        signedIn: null,
        sessionRestored: false,
        prefs: signedIn ? saved.prefs : const {},
        secure: signedIn ? saved.secure : const {},
      ));
      await tester.pump();
      expect(find.byType(SplashScreen), findsOneWidget);
      // كل الـ splash: ولا إطار فيه Welcome (للمسجّل) ولا الـ shell (لغير المسجّل)
      for (var elapsed = 0; elapsed < SplashScreen.displayDuration.inMilliseconds; elapsed += 100) {
        await tester.pump(const Duration(milliseconds: 100));
        if (signedIn) {
          expect(find.byType(WelcomeScreen, skipOffstage: false), findsNothing, reason: '$elapsed ms');
        } else {
          expect(find.byType(AppShell, skipOffstage: false), findsNothing, reason: '$elapsed ms');
        }
      }
      await tester.pump(const Duration(milliseconds: 200));
      await tester.pumpAndSettle();
    }

    testWidgets('saved session: splash → /home, Welcome never shown', (tester) async {
      await coldStart(tester, signedIn: true);
      expect(find.byType(SplashScreen), findsNothing);
      expect(find.byType(WelcomeScreen, skipOffstage: false), findsNothing);
      expect(find.byType(HomeScreen), findsOneWidget);
      expect(_visibleBar(), findsOneWidget);
      expect(_location(tester), AppRoutes.home);
      // الرجوع ما بيرجّع للـ splash
      expect(Navigator.of(tester.element(find.byType(AppShell))).canPop(), isFalse);
    });

    testWidgets('no saved session: splash → /welcome', (tester) async {
      await coldStart(tester, signedIn: false);
      expect(find.byType(SplashScreen), findsNothing);
      expect(find.byType(WelcomeScreen), findsOneWidget);
      expect(_location(tester), AppRoutes.welcome);
      expect(Navigator.of(tester.element(find.byType(WelcomeScreen))).canPop(), isFalse);
    });
  });

  testWidgets('session end deep inside a tab (sub-screen + full-screen route) clears to /welcome', (tester) async {
    final session = StateProvider<AuthState>((ref) => _user);
    await _pump(
      tester,
      signedIn: null,
      overrides: [authStateProvider.overrideWith((ref) => ref.watch(session))],
      height: 1200,
    );
    await _openTab(tester, ShellTab.signals);
    await tester.tap(find.byType(AccuracyLine));
    await tester.pumpAndSettle();
    testRouter(tester).push<void>(AppRoutes.backtest);
    await tester.pumpAndSettle();
    expect(find.byType(BacktestScreen), findsOneWidget);

    ProviderScope.containerOf(tester.element(find.byType(BacktestScreen))).read(session.notifier).state =
        const SignedOut();
    await tester.pumpAndSettle();
    expect(find.byType(WelcomeScreen), findsOneWidget);
    expect(find.byType(AppShell, skipOffstage: false), findsNothing);
    expect(find.byType(BacktestScreen, skipOffstage: false), findsNothing);
    expect(Navigator.of(tester.element(find.byType(WelcomeScreen))).canPop(), isFalse);
    expect(_location(tester), AppRoutes.welcome);
  });

  group('shell', () {
    testWidgets('each tab keeps its screens and scroll when switching tabs', (tester) async {
      await _pump(tester);
      // Home: سكرول لتحت
      await tester.drag(_homeList(), const Offset(0, -300));
      await tester.pumpAndSettle();
      final homeOffset = tester.state<ScrollableState>(_homeList()).position.pixels;
      expect(homeOffset, greaterThan(0));

      // Signals: Insights مفتوحة
      await _openTab(tester, ShellTab.signals);
      await tester.tap(find.byType(AccuracyLine));
      await tester.pumpAndSettle();
      expect(find.byType(InsightsScreen), findsOneWidget);
      expect(_location(tester), AppRoutes.insights);

      await _openTab(tester, ShellTab.profile);
      expect(find.byType(ProfileScreen), findsOneWidget);
      expect(find.byType(InsightsScreen), findsNothing);

      // رجوع لـ Signals: Insights لسّا فوق القائمة
      await _openTab(tester, ShellTab.signals);
      expect(find.byType(InsightsScreen), findsOneWidget);
      expect(_location(tester), AppRoutes.insights);

      // رجوع لـ Home: نفس السكرول
      await _openTab(tester, ShellTab.home);
      expect(find.byType(HomeScreen), findsOneWidget);
      expect(tester.state<ScrollableState>(_homeList()).position.pixels, homeOffset);

      // Back من Insights بيرجّع لقائمة Signals، مش لتبويب تاني
      await _openTab(tester, ShellTab.signals);
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      expect(find.byType(InsightsScreen), findsNothing);
      expect(find.byType(AccuracyLine), findsOneWidget);
      expect(_location(tester), AppRoutes.signals);
    });

    testWidgets('a double tap on a Home row opens one Market screen', (tester) async {
      await _pump(tester);
      final row = find.byType(WatchlistRow).first;
      await tester.tap(row);
      await tester.tap(row, warnIfMissed: false);
      await tester.pumpAndSettle();
      expect(find.byType(MarketScreen, skipOffstage: false), findsOneWidget);

      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      expect(find.byType(MarketScreen, skipOffstage: false), findsNothing);
      expect(find.byType(HomeScreen), findsOneWidget);
      expect(_location(tester), AppRoutes.home);
    });
  });

  group('unknown route', () {
    for (final path in ['/does-not-exist', '/profile/help/legal/nope', '/otp', '/signals/s1']) {
      testWidgets('$path shows the unknown-route screen', (tester) async {
        await _pump(tester, route: path);
        expect(find.byType(UnknownRouteScreen), findsOneWidget);
        expect(find.textContaining('Route not found'), findsOneWidget);
      });
    }
  });

  group('signal detail from a path', () {
    testWidgets('opens with its id and symbol inside the Signals tab', (tester) async {
      await _pump(tester, route: AppRoutes.signals);
      final signal = tester.widget<SignalRow>(find.byType(SignalRow).first).signal;
      testRouter(tester).go(AppRoutes.signalDetail(signal.id, symbol: signal.symbol));
      await settleMocks(tester);
      final screen = tester.widget<SignalDetailScreen>(find.byType(SignalDetailScreen));
      expect(screen.signalId, signal.id);
      expect(screen.symbol, signal.symbol);
      expect(find.text('Signal not available'), findsNothing);
      expect(_visibleBar(), findsOneWidget);
      expect(tester.widget<NavigationBar>(find.byType(NavigationBar)).selectedIndex, ShellTab.signals.index);
    });

    testWidgets('an unknown id shows "not found"', (tester) async {
      await _pump(tester, route: AppRoutes.signalDetail('missing', symbol: 'EUR/USD'));
      expect(find.byType(SignalDetailScreen), findsOneWidget);
      expect(find.text('Signal not available'), findsOneWidget);
      expect(find.text('EUR/USD'), findsOneWidget); // العنوان من المسار
    });
  });

  group('Hero tags and the bottom bar', () {
    testWidgets('Home row → Market: same Hero tag, bar stays visible', (tester) async {
      await _pump(tester);
      final row = find.byType(WatchlistRow).first;
      final symbol = tester.widget<WatchlistRow>(row).instrument.symbol;
      expect(_heroTag(tester, row), MarketSymbolHero.tag(symbol));

      await tester.tap(row);
      await tester.pumpAndSettle();
      expect(_heroTag(tester, find.byType(MarketScreen)), MarketSymbolHero.tag(symbol));
      expect(_visibleBar(), findsOneWidget);
      expect(_location(tester), AppRoutes.market(symbol));
    });

    testWidgets('Signals row → detail: same Hero tag, bar stays visible', (tester) async {
      await _pump(tester, route: AppRoutes.signals);
      final row = find.byType(SignalRow).first;
      final id = tester.widget<SignalRow>(row).signal.id;
      expect(_heroTag(tester, row), SignalRow.heroTag(id));

      await tester.tap(row);
      await tester.pumpAndSettle();
      expect(_heroTag(tester, find.byType(SignalDetailScreen)), SignalRow.heroTag(id));
      expect(_visibleBar(), findsOneWidget);
    });

    for (final (route, screen) in [
      (AppRoutes.welcome, WelcomeScreen),
      (AppRoutes.login, LoginScreen),
      (AppRoutes.registration, RegistrationScreen),
    ]) {
      testWidgets('full screen, no bar: $route', (tester) async {
        await _pump(tester, route: route, signedIn: false);
        expect(find.byType(screen), findsOneWidget);
        expect(find.byType(NavigationBar), findsNothing);
      });
    }

    testWidgets('full screen, no bar: expert chat (back returns to Community with the bar)', (tester) async {
      await _pump(tester, route: AppRoutes.community);
      testRouter(tester).push<void>(AppRoutes.expertChat('expert-1'));
      await settleMocks(tester);
      expect(find.byType(ExpertChatScreen), findsOneWidget);
      expect(find.byType(NavigationBar), findsNothing);

      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      expect(find.byType(ExpertChatScreen), findsNothing);
      expect(_visibleBar(), findsOneWidget);
      expect(_location(tester), AppRoutes.community);
    });
  });

  group('Strategy sheet → Backtest → back', () {
    for (final (name, back) in [
      ('system Back', (WidgetTester tester) => tester.binding.handlePopRoute()),
      ('header arrow', (WidgetTester tester) => tester.pageBack()),
    ]) {
      testWidgets('$name returns to the open sheet, then the sheet closes to Signals', (tester) async {
        await _pump(tester, route: AppRoutes.signals, height: 1600);
        await tester.tap(find.text('Strategy'));
        await tester.pumpAndSettle();
        final open = find.text('Test on past data');
        await tester.ensureVisible(open);
        await tester.pumpAndSettle();
        await tester.tap(open);
        await tester.pumpAndSettle();
        expect(find.byType(BacktestScreen), findsOneWidget);
        expect(find.byType(NavigationBar), findsNothing);

        await back(tester);
        await tester.pumpAndSettle();
        expect(find.byType(BacktestScreen), findsNothing);
        expect(find.text('Test on past data'), findsOneWidget, reason: 'the sheet is still open');
        expect(find.byType(WelcomeScreen, skipOffstage: false), findsNothing);
        expect(_location(tester), AppRoutes.signals);

        // Back مرة تانية بيسكّر الـ sheet بس
        await tester.binding.handlePopRoute();
        await tester.pumpAndSettle();
        expect(find.text('Test on past data'), findsNothing);
        expect(find.byType(AccuracyLine), findsOneWidget);
        expect(_visibleBar(), findsOneWidget);
        expect(tester.widget<NavigationBar>(find.byType(NavigationBar)).selectedIndex, ShellTab.signals.index);
      });
    }
  });
}
