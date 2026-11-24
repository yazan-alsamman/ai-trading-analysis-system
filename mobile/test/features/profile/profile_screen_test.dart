// اختبارات تبويب Profile (Stage B): بطاقة الهوية + أربع وجهات + تسجيل الخروج،
// بالثيمين وبالعربي وبالخط الكبير، وكل وجهة بتفتح شاشتها.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/features/help/views/help_about_screen.dart';
import 'package:trading_app/features/membership/models/membership_models.dart';
import 'package:trading_app/features/membership/views/plans_screen.dart';
import 'package:trading_app/features/profile/views/edit_profile_screen.dart';
import 'package:trading_app/features/profile/views/profile_screen.dart';
import 'package:trading_app/features/profile/views/security_screen.dart';
import 'package:trading_app/features/settings/views/settings_screen.dart';

import '../../helpers/test_app.dart';

Future<void> pumpProfile(
  WidgetTester tester, {
  Map<String, Object> prefs = const {},
  double height = 812,
  String locale = 'en',
}) async {
  usePhoneSize(tester, height: height);
  await tester.pumpWidget(
    await testScope(const TestApp(home: ProfileScreen()), prefs: prefs, locale: locale),
  );
  await tester.pumpAndSettle();
}

void main() {
  for (final mode in ['light', 'dark']) {
    testWidgets('shows identity, four rows and Log out without scrolling ($mode)', (tester) async {
      await pumpProfile(tester, prefs: {themeModeStorageKey: mode});
      for (final row in ['Plan', 'Password & security', 'Settings', 'Help & about', 'Log out']) {
        expect(find.text(row).hitTestable(), findsOneWidget, reason: row);
      }
      expect(find.text('trader@example.com'), findsNothing); // ما في مستخدم بالـ AuthController
      expect(tester.takeException(), isNull);
    });
  }

  // القرارات: ما في Tools ولا "Soon" ولا صف حساب مكرر، وصف Current plan ممنوع
  testWidgets('no Tools heading, Soon labels, Account settings or Current plan row', (tester) async {
    usePhoneSize(tester, height: 2000);
    await tester.pumpWidget(await testScope(
      const TestApp(home: ProfileScreen()),
      overrides: [currentPlanIs(PlanId.professional)],
    ));
    await tester.pumpAndSettle();
    for (final gone in [
      'TOOLS',
      'Soon',
      'Account Settings',
      'Current plan',
      'Professional',
      'Experts',
      'Signal accuracy',
      'Strategy',
      'Design gallery',
      'Simulate offline', // صار تحت Settings → Developer
      'Appearance', // صار تحت Settings
    ]) {
      expect(find.text(gone), findsNothing, reason: gone);
    }
  });

  for (final (row, screen) in [
    ('Plan', PlansScreen),
    ('Password & security', SecurityScreen),
    ('Settings', SettingsScreen),
    ('Help & about', HelpAboutScreen),
  ]) {
    testWidgets('$row opens its screen', (tester) async {
      await pumpProfile(tester);
      await tester.tap(find.text(row));
      await tester.pumpAndSettle();
      expect(find.byType(screen), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('the identity card opens Edit profile', (tester) async {
    await pumpProfile(tester);
    await tester.tap(find.bySemanticsLabel(RegExp('Edit profile')));
    await tester.pumpAndSettle();
    expect(find.byType(EditProfileScreen), findsOneWidget);
  });

  testWidgets('Log out asks first and Cancel keeps the user in', (tester) async {
    await pumpProfile(tester);
    await tester.tap(find.text('Log out'));
    await tester.pumpAndSettle();

    expect(find.byType(AlertDialog), findsOneWidget);
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(find.byType(AlertDialog), findsNothing);
    expect(find.byType(ProfileScreen), findsOneWidget);
  });

  for (final locale in ['en', 'ar']) {
    testWidgets('largest font: every row fits ($locale)', (tester) async {
      useLargeText(tester);
      await pumpProfile(tester, locale: locale);
      await tester.drag(find.byType(CustomScrollView), const Offset(0, -2000));
      await tester.pumpAndSettle();
      expect(find.text(locale == 'en' ? 'Log out' : 'تسجيل الخروج'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('Arabic: RTL with translated rows', (tester) async {
    await pumpProfile(tester, locale: 'ar');
    expect(Directionality.of(tester.element(find.byType(ProfileScreen))), TextDirection.rtl);
    for (final row in ['الخطة', 'كلمة المرور والأمان', 'الإعدادات', 'المساعدة وحول التطبيق']) {
      expect(find.text(row), findsOneWidget, reason: row);
    }
  });
}
