// G3: الجلسة المحفوظة. Log in / التحقق من البريد بيحفظوا الجلسة، الـ splash
// بيقرأها (جلسة → الرئيسية بدون ولا إطار Welcome، بدونها → Welcome)، تسجيل
// الخروج ونهاية الجلسة بيمسحوها، وسكّر التطبيق بنص التسجيل (قبل التحقق) =
// Welcome بالإقلاع الجاي. "سكّر وافتح" = شجرة جديدة على TradingApp بنفس التخزين.

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:trading_app/app/app.dart';
import 'package:trading_app/app/router/app_routes.dart';
import 'package:trading_app/app/shell/app_shell.dart';
import 'package:trading_app/app/shell/shell_tab.dart';
import 'package:trading_app/features/auth/data/session_store.dart';
import 'package:trading_app/features/auth/view_models/auth_view_models.dart';
import 'package:trading_app/features/auth/views/otp_screen.dart';
import 'package:trading_app/features/auth/views/splash_screen.dart';
import 'package:trading_app/features/auth/views/welcome_screen.dart';
import 'package:trading_app/features/home/views/home_screen.dart';
import 'package:trading_app/models/user_model.dart';
import 'package:trading_app/providers/app_providers.dart';
import 'package:trading_app/services/secure_storage_service.dart';

import '../../helpers/test_app.dart';

ProviderContainer _container(WidgetTester tester) =>
    ProviderScope.containerOf(tester.element(find.byType(Navigator).first));

/// "يسكّر" التطبيق ويفتحه من جديد بنفس التخزين، ويرجع إذا Welcome بيّنت
/// بأي إطار من الـ splash لحد الشاشة الأولى
Future<bool> _restart(WidgetTester tester) async {
  final saved = await SavedSession.current();
  await tester.pumpWidget(const SizedBox());
  usePhoneSize(tester);
  await tester.pumpWidget(await testScope(
    const TradingApp(),
    signedIn: null,
    sessionRestored: false,
    prefs: {if (saved.user != null) SessionStore.userKey: saved.user!},
    secure: {if (saved.token != null) 'auth_token': saved.token!},
  ));
  await tester.pump();
  expect(find.byType(SplashScreen), findsOneWidget);
  var sawWelcome = false;
  for (var elapsed = 0; elapsed <= SplashScreen.displayDuration.inMilliseconds + 200; elapsed += 100) {
    await tester.pump(const Duration(milliseconds: 100));
    if (find.byType(SplashScreen).evaluate().isEmpty) break;
    sawWelcome |= find.byType(WelcomeScreen, skipOffstage: false).evaluate().isNotEmpty;
  }
  await settleMocks(tester);
  return sawWelcome || find.byType(WelcomeScreen, skipOffstage: false).evaluate().isNotEmpty;
}

Future<void> _expectNoSavedSession() async {
  final saved = await SavedSession.current();
  expect(saved.user, isNull, reason: 'no saved user');
  expect(saved.token, isNull, reason: 'no saved token');
}

Finder _field(String label) => find.ancestor(of: find.text(label), matching: find.byType(Column)).first;

Future<void> _type(WidgetTester tester, String label, String value) async {
  await tester.enterText(find.descendant(of: _field(label), matching: find.byType(TextField)), value);
  await tester.pump();
}

Future<void> _logInThroughUi(WidgetTester tester) async {
  usePhoneSize(tester);
  await tester.pumpWidget(await testScope(const TestApp(initialRoute: AppRoutes.login), signedIn: null));
  await tester.pumpAndSettle();
  await _type(tester, 'Email', 'lina@example.com');
  await _type(tester, 'Password', 'research42');
  await tester.tap(find.widgetWithText(FilledButton, 'Log in'));
  await tester.pump(const Duration(seconds: 3));
  await settleMocks(tester);
  expect(find.byType(AppShell), findsOneWidget);
}

/// Create account عبر الواجهة لحد شاشة Verify email
Future<void> _signUpUntilVerify(WidgetTester tester) async {
  usePhoneSize(tester);
  await tester.pumpWidget(await testScope(const TestApp(initialRoute: AppRoutes.registration), signedIn: null));
  await tester.pumpAndSettle();
  await _type(tester, 'Full name', 'Sara Haddad');
  await _type(tester, 'Email', 'sara@example.com');
  await _type(tester, 'Password', 'research42');
  await _type(tester, 'Confirm password', 'research42');
  await scrollTo(tester, find.text('I understand this is not financial advice.'));
  await tester.tap(find.text('I understand this is not financial advice.'));
  await tester.pump();
  await scrollTo(tester, find.widgetWithText(FilledButton, 'Create account'));
  await tester.tap(find.widgetWithText(FilledButton, 'Create account'));
  await tester.pump(const Duration(seconds: 3));
  await tester.pumpAndSettle();
  expect(find.byType(OtpVerificationScreen), findsOneWidget);
}

void main() {
  group('SessionStore', () {
    late SessionStore store;
    const user = UserModel(
      id: 'u1',
      email: 'lina@example.com',
      displayName: 'Lina',
      avatarUrl: '/tmp/picked.jpg',
      role: UserRole.expert,
    );

    Future<void> setUpStore({Map<String, Object> prefs = const {}, Map<String, String> secure = const {}}) async {
      SharedPreferences.setMockInitialValues(prefs);
      FlutterSecureStorage.setMockInitialValues({...secure}); // نسخة قابلة للتعديل
      store = SessionStore(secureStorage: SecureStorageService(), preferences: await SharedPreferences.getInstance());
    }

    test('save → read gives the user back; clear removes both parts', () async {
      await setUpStore();
      expect(await store.read(), isNull);
      await store.save(user);
      final read = (await store.read())!;
      expect(read.id, 'u1');
      expect(read.email, 'lina@example.com');
      expect(read.displayName, 'Lina');
      expect(read.role, UserRole.expert);
      await store.clear();
      expect(await store.read(), isNull);
      await _expectNoSavedSession();
    });

    test('stores only the minimum: no password, no avatar path, the token in secure storage', () async {
      await setUpStore();
      await store.save(user);
      final saved = await SavedSession.current();
      final json = jsonDecode(saved.user!) as Map<String, dynamic>;
      expect(json.keys.toSet(), {'id', 'email', 'displayName', 'role'});
      expect(saved.user, isNot(contains('research42')));
      expect(saved.token, 'mock_token_u1');
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getKeys(), {SessionStore.userKey}, reason: 'the token is not in SharedPreferences');
    });

    for (final (name, prefs, secure) in [
      ('a token without a user (old install)', <String, Object>{}, {'auth_token': 'mock_token_u1'}),
      ('a user without a token', {SessionStore.userKey: '{"id":"u1","email":"a@b.c"}'}, <String, String>{}),
      ('a corrupted user', {SessionStore.userKey: '{not json'}, {'auth_token': 'mock_token_u1'}),
      ('a user with an empty id', {SessionStore.userKey: '{"id":"","email":"a@b.c"}'}, {'auth_token': 't'}),
    ]) {
      test('$name = no session, and it is cleared', () async {
        await setUpStore(prefs: prefs, secure: secure);
        expect(await store.read(), isNull);
        await _expectNoSavedSession();
      });
    }
  });

  group('cold start', () {
    testWidgets('saved session: splash → /home, no Welcome frame, the saved user is back', (tester) async {
      final saved = SavedSession();
      usePhoneSize(tester);
      // التخزين وحده (ما في تطبيق شغّال)، بعدين إقلاع
      await tester.pumpWidget(await testScope(const SizedBox(), prefs: saved.prefs, secure: saved.secure));
      expect(await _restart(tester), isFalse, reason: 'Welcome must not appear');
      expect(find.byType(HomeScreen), findsOneWidget);
      final user = _container(tester).read(authControllerProvider).currentUser!;
      expect(user.email, 'saved@example.com');
      expect(user.displayName, 'Sara Saved');
    });

    testWidgets('no saved session (fresh install): splash → /welcome', (tester) async {
      usePhoneSize(tester);
      await tester.pumpWidget(await testScope(const SizedBox()));
      expect(await _restart(tester), isTrue);
      expect(find.byType(WelcomeScreen), findsOneWidget);
      expect(find.byType(AppShell, skipOffstage: false), findsNothing);
    });

    testWidgets('a corrupted saved session: splash → /welcome, and it is cleaned up', (tester) async {
      usePhoneSize(tester);
      await tester.pumpWidget(await testScope(
        const SizedBox(),
        prefs: {SessionStore.userKey: '{broken'},
        secure: {'auth_token': 'mock_token_x'},
      ));
      expect(await _restart(tester), isTrue);
      expect(find.byType(WelcomeScreen), findsOneWidget);
      await _expectNoSavedSession();
    });
  });

  group('log in', () {
    testWidgets('log in saves the session; the next cold start opens Home', (tester) async {
      await _logInThroughUi(tester);
      final saved = await SavedSession.current();
      expect(saved.token, isNotNull);
      expect(jsonDecode(saved.user!)['email'], 'lina@example.com');

      expect(await _restart(tester), isFalse);
      expect(find.byType(HomeScreen), findsOneWidget);
      expect(_container(tester).read(authControllerProvider).currentUser!.email, 'lina@example.com');
    });

    testWidgets('a profile edit is kept in the saved session', (tester) async {
      await _logInThroughUi(tester);
      final update = _container(tester).read(authControllerProvider).updateProfile(displayName: 'Lina Haddad');
      await tester.pump(const Duration(seconds: 1));
      expect(await update, isTrue);
      await _restart(tester);
      expect(_container(tester).read(authControllerProvider).currentUser!.displayName, 'Lina Haddad');
    });
  });

  group('log out and session end', () {
    testWidgets('log out (Profile) clears the saved session; the next cold start opens Welcome', (tester) async {
      await _logInThroughUi(tester);
      await tester.tap(find.descendant(of: find.byType(NavigationBar), matching: find.byType(NavigationDestination)).at(
            ShellTab.profile.index,
          ));
      await tester.pumpAndSettle();
      await scrollTo(tester, find.text('Log out'));
      await tester.tap(find.text('Log out'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(TextButton, 'Log out'));
      await tester.pump(const Duration(seconds: 2));
      await tester.pumpAndSettle();
      expect(find.byType(WelcomeScreen), findsOneWidget);
      await _expectNoSavedSession();

      expect(await _restart(tester), isTrue);
      expect(find.byType(WelcomeScreen), findsOneWidget);
      expect(find.byType(AppShell, skipOffstage: false), findsNothing);
    });

    testWidgets('session end deep inside a tab clears the saved session and goes to /welcome', (tester) async {
      await _logInThroughUi(tester);
      await tester.tap(find.descendant(of: find.byType(NavigationBar), matching: find.byType(NavigationDestination)).at(
            ShellTab.signals.index,
          ));
      await tester.pumpAndSettle();
      testRouter(tester).push<void>(AppRoutes.insights);
      await settleMocks(tester);

      await _container(tester).read(authControllerProvider).endSession();
      await tester.pumpAndSettle();
      expect(find.byType(WelcomeScreen), findsOneWidget);
      expect(find.byType(AppShell, skipOffstage: false), findsNothing);
      expect(Navigator.of(tester.element(find.byType(WelcomeScreen))).canPop(), isFalse);
      await _expectNoSavedSession();

      expect(await _restart(tester), isTrue);
      expect(find.byType(WelcomeScreen), findsOneWidget);
    });
  });

  group('sign up', () {
    testWidgets('Create account does not save a session; closing before verification → Welcome', (tester) async {
      await _signUpUntilVerify(tester);
      // داخل بالذاكرة (لازم يوصل لـ /otp)، بس ولا شي محفوظ
      expect(_container(tester).read(authControllerProvider).currentUser!.email, 'sara@example.com');
      await _expectNoSavedSession();

      expect(await _restart(tester), isTrue);
      expect(find.byType(WelcomeScreen), findsOneWidget);
      expect(find.byType(OtpVerificationScreen, skipOffstage: false), findsNothing);
      expect(_container(tester).read(authControllerProvider).currentUser, isNull);
    });

    testWidgets('the session is saved when the email is verified; the next cold start opens Home', (tester) async {
      await _signUpUntilVerify(tester);
      await tester.enterText(find.byType(TextField), '24680');
      await tester.pump(OtpViewModel.latency);
      await tester.pumpAndSettle();
      expect(find.text('Email verified'), findsOneWidget);
      final saved = await SavedSession.current();
      expect(saved.token, isNotNull);
      expect(jsonDecode(saved.user!)['displayName'], 'Sara Haddad');

      await tester.tap(find.text('Continue'));
      await settleMocks(tester);
      expect(find.byType(AppShell), findsOneWidget);

      expect(await _restart(tester), isFalse);
      expect(find.byType(HomeScreen), findsOneWidget);
      expect(_container(tester).read(authControllerProvider).currentUser!.displayName, 'Sara Haddad');
    });
  });
}
