// E1: الجلسة لما الـ API الحقيقي مفعّل للـ auth: "داخل" = tokens صالحة بالتخزين
// الآمن (+ نسخة المستخدم للواجهة)، الـ splash بيقرأها، والـ refresh المرفوض
// بيطلّع المستخدم ويمسح الجلسة المحفوظة (→ Welcome). المحاكاة بتضل متل G3.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:trading_app/app/app.dart';
import 'package:trading_app/app/router/app_routes.dart';
import 'package:trading_app/app/shell/app_shell.dart';
import 'package:trading_app/core/network/api_config.dart';
import 'package:trading_app/core/network/api_exception.dart';
import 'package:trading_app/core/network/api_providers.dart';
import 'package:trading_app/core/network/token_store.dart';
import 'package:trading_app/features/auth/auth_state.dart';
import 'package:trading_app/features/auth/data/session_store.dart';
import 'package:trading_app/features/auth/views/splash_screen.dart';
import 'package:trading_app/features/auth/views/welcome_screen.dart';
import 'package:trading_app/features/home/views/home_screen.dart';
import 'package:trading_app/features/insights/views/insights_screen.dart';
import 'package:trading_app/models/user_model.dart';
import 'package:trading_app/services/secure_storage_service.dart';

import '../../helpers/fake_api.dart';
import '../../helpers/test_app.dart';

const _user = UserModel(id: 'u1', email: 'real@example.com', displayName: 'Rana Real');

/// جلسة الـ API الحقيقي المحفوظة (refresh صالح ليوم إذا ما انقال غير هيك)
({Map<String, Object> prefs, Map<String, String> secure}) _realSession({DateTime? refreshExpires}) {
  final saved = SavedSession(user: _user);
  return (
    prefs: saved.prefs,
    secure: {
      'auth_token': 'access-1',
      'auth_refresh_token': fakeJwt(expires: refreshExpires ?? DateTime.now().add(const Duration(days: 1))),
    },
  );
}

const _realAuth = ApiConfig(baseUrl: kTestApiBaseUrl, realApi: {ApiFeature.auth});

ProviderContainer _container(WidgetTester tester) =>
    ProviderScope.containerOf(tester.element(find.byType(Navigator).first));

/// إقلاع بارد على TradingApp الحقيقي (splash ← الجلسة المحفوظة)
Future<void> _coldStart(
  WidgetTester tester, {
  required ApiConfig config,
  Map<String, Object> prefs = const {},
  Map<String, String> secure = const {},
  FakeApiAdapter? adapter,
}) async {
  usePhoneSize(tester);
  await tester.pumpWidget(await testScope(
    const TradingApp(),
    signedIn: null,
    sessionRestored: false,
    prefs: prefs,
    secure: secure,
    overrides: [
      apiConfigProvider.overrideWithValue(config),
      if (adapter != null) apiHttpAdapterProvider.overrideWithValue(adapter),
    ],
  ));
  await tester.pump();
  expect(find.byType(SplashScreen), findsOneWidget);
  await tester.pump(SplashScreen.displayDuration + const Duration(milliseconds: 100));
  await settleMocks(tester);
}

Future<({String? user, String? access, String? refresh})> _stored() async => (
      user: (await SharedPreferences.getInstance()).getString(SessionStore.userKey),
      access: await const FlutterSecureStorage().read(key: 'auth_token'),
      refresh: await const FlutterSecureStorage().read(key: 'auth_refresh_token'),
    );

void main() {
  group('SessionStore (real API mode)', () {
    Future<SessionStore> store({Map<String, Object> prefs = const {}, Map<String, String> secure = const {}}) async {
      SharedPreferences.setMockInitialValues(prefs);
      FlutterSecureStorage.setMockInitialValues({...secure});
      return SessionStore(
        secureStorage: SecureStorageService(),
        preferences: await SharedPreferences.getInstance(),
        realApi: true,
      );
    }

    test('save with the login tokens → read gives the user back; tokens in secure storage', () async {
      final s = await store();
      final refresh = fakeJwt(expires: DateTime.now().add(const Duration(days: 7)));
      await s.save(_user, tokens: TokenPair(accessToken: 'access-1', refreshToken: refresh));
      expect((await s.read())?.email, 'real@example.com');
      final saved = await _stored();
      expect(saved.access, 'access-1');
      expect(saved.refresh, refresh);
    });

    test('no tokens (e.g. the mock login) → nothing is saved', () async {
      final s = await store();
      await expectLater(s.save(_user), throwsStateError);
      expect((await _stored()).user, isNull);
      expect(await s.read(), isNull);
    });

    test('a profile re-save keeps the existing tokens', () async {
      final session = _realSession();
      final s = await store(prefs: session.prefs, secure: session.secure);
      await s.save(_user.copyWith(displayName: 'Rana R.'));
      expect((await s.read())?.displayName, 'Rana R.');
      expect((await _stored()).access, 'access-1');
    });

    test('expired refresh token → no session, everything cleared', () async {
      final session = _realSession(refreshExpires: DateTime.now().subtract(const Duration(minutes: 1)));
      final s = await store(prefs: session.prefs, secure: session.secure);
      expect(await s.read(), isNull);
      final saved = await _stored();
      expect([saved.user, saved.access, saved.refresh], [null, null, null]);
    });

    test('only the G3 mock token (no refresh token) is not a real session', () async {
      final saved = SavedSession(user: _user);
      final s = await store(prefs: saved.prefs, secure: saved.secure);
      expect(await s.read(), isNull);
      expect((await _stored()).user, isNull);
    });
  });

  group('cold start', () {
    testWidgets('real API: valid tokens → splash → /home, the saved user is back', (tester) async {
      final session = _realSession();
      await _coldStart(tester, config: _realAuth, prefs: session.prefs, secure: session.secure);
      expect(find.byType(HomeScreen), findsOneWidget);
      expect(find.byType(WelcomeScreen, skipOffstage: false), findsNothing);
      expect(_container(tester).read(authStateProvider), isA<SignedIn>());
    });

    testWidgets('real API: expired refresh token → /welcome, storage cleaned', (tester) async {
      final session = _realSession(refreshExpires: DateTime.now().subtract(const Duration(hours: 1)));
      await _coldStart(tester, config: _realAuth, prefs: session.prefs, secure: session.secure);
      expect(find.byType(WelcomeScreen), findsOneWidget);
      expect((await _stored()).refresh, isNull);
    });

    testWidgets('simulated (default): the G3 mock session still opens Home', (tester) async {
      final saved = SavedSession(user: _user);
      await _coldStart(
        tester,
        config: const ApiConfig(baseUrl: kTestApiBaseUrl),
        prefs: saved.prefs,
        secure: saved.secure,
      );
      expect(find.byType(HomeScreen), findsOneWidget);
    });
  });

  testWidgets('refresh rejected deep inside a tab → signed out, saved session cleared, /welcome with nothing to pop',
      (tester) async {
    final session = _realSession();
    final adapter = FakeApiAdapter((o) => o.uri.path.endsWith('/auth/refresh')
        ? const FakeReply(401, {'detail': 'Token has expired'})
        : const FakeReply(401, {'detail': 'Could not validate credentials'}));
    await _coldStart(tester, config: _realAuth, prefs: session.prefs, secure: session.secure, adapter: adapter);
    expect(find.byType(HomeScreen), findsOneWidget);
    testRouter(tester).push<void>(AppRoutes.insights);
    await settleMocks(tester);
    expect(find.byType(InsightsScreen), findsOneWidget);

    final container = _container(tester);
    // dio بيستعمل مؤقتات حقيقية (المهل): الطلب بيمشي برّا الوقت الوهمي
    final error = await tester.runAsync(() async {
      try {
        await container.read(apiClientProvider).get('/users/me', decode: passJson);
        return null;
      } on ApiException catch (e) {
        return e;
      }
    });
    expect(error?.kind, ApiErrorKind.unauthorized);
    await tester.pumpAndSettle();

    expect(adapter.to('/auth/refresh'), hasLength(1));
    expect(container.read(authStateProvider), isA<SignedOut>());
    expect(find.byType(WelcomeScreen), findsOneWidget);
    expect(find.byType(AppShell, skipOffstage: false), findsNothing);
    expect(Navigator.of(tester.element(find.byType(WelcomeScreen))).canPop(), isFalse);
    final saved = await _stored();
    expect([saved.user, saved.access, saved.refresh], [null, null, null]);
  });
}
