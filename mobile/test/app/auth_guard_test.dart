// اختبارات الـ auth guard: بدون جلسة أي شاشة محمية بتتحوّل لـ Welcome، ولما
// الجلسة تنتهي وأنت جوّا التطبيق بترجع لـ Welcome والشجرة بتنمسح.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:trading_app/app/app.dart';
import 'package:trading_app/app/router/app_router.dart';
import 'package:trading_app/app/router/app_routes.dart';
import 'package:trading_app/app/shell/app_shell.dart';
import 'package:trading_app/core/storage/preferences_provider.dart';
import 'package:trading_app/features/auth/auth_state.dart';
import 'package:trading_app/models/user_model.dart';
import 'package:trading_app/features/auth/views/welcome_screen.dart';

import '../helpers/test_app.dart';

const _user = SignedIn(UserModel(id: 'u', email: 'trader@example.com'));


void main() {
  test('guard: public routes stay public, protected routes need a session', () {
    // الـ splash عنده قاعدته الخاصة (بيستنى قراءة الجلسة) - مختبرة بـ router_test
    for (final path in AppRoutes.publicRoutes.difference({AppRoutes.splash})) {
      expect(authRedirect(path: path, signedIn: false, sessionRestored: true), isNull, reason: path);
    }
    expect(
      authRedirect(path: AppRoutes.market('EUR/USD'), signedIn: false, sessionRestored: true),
      AppRoutes.welcome,
    );
    expect(authRedirect(path: AppRoutes.home, signedIn: true, sessionRestored: true), isNull);
  });

  test('authState follows the session', () {
    expect(const SignedOut().isSignedIn, isFalse);
    expect(_user.isSignedIn, isTrue);
  });

  testWidgets('signed out: opening Home lands on Welcome', (tester) async {
    usePhoneSize(tester);
    await tester.pumpWidget(await testScope(const TestApp(), signedIn: false));
    await tester.pumpAndSettle();
    expect(find.byType(AppShell), findsNothing);
    expect(find.byType(WelcomeScreen), findsOneWidget);
  });

  testWidgets('session ends inside the app → Welcome, stack cleared', (tester) async {
    usePhoneSize(tester);
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    final session = StateProvider<AuthState>((ref) => _user);
    await tester.pumpWidget(ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        authStateProvider.overrideWith((ref) => ref.watch(session)),
        ...simulatedMarketOverrides(),
      ],
      child: const TradingApp(),
    ));
    // splash → (جلسة موجودة) → الرئيسية
    await tester.pump(const Duration(milliseconds: 1400));
    await tester.pumpAndSettle();
    expect(find.byType(AppShell), findsOneWidget);

    final container = ProviderScope.containerOf(tester.element(find.byType(AppShell)));
    container.read(session.notifier).state = const SignedOut();
    await tester.pumpAndSettle();
    expect(find.byType(AppShell), findsNothing);
    expect(find.byType(WelcomeScreen), findsOneWidget);
    expect(Navigator.of(tester.element(find.byType(WelcomeScreen))).canPop(), isFalse);
  });
}
