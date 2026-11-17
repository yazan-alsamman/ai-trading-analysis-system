// اختبارات Edit profile و Password & security (Stage B).

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/features/profile/views/edit_profile_screen.dart';
import 'package:trading_app/features/profile/views/security_screen.dart';
import 'package:trading_app/providers/app_providers.dart';

import '../../helpers/test_app.dart';

/// شاشة فوق شاشة بسيطة، حتى الرجوع يكون ممكن
Future<void> pushOver(WidgetTester tester, Widget screen, {String locale = 'en', String theme = 'light'}) async {
  usePhoneSize(tester);
  await tester.pumpWidget(await testScope(
    TestApp(
      home: Builder(
        builder: (context) => Scaffold(
          body: Center(
            child: TextButton(
              onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => screen)),
              child: const Text('open'),
            ),
          ),
        ),
      ),
    ),
    locale: locale,
    prefs: {themeModeStorageKey: theme},
  ));
  await tester.tap(find.text('open'));
  await tester.pumpAndSettle();
}

/// مستخدم داخل بالـ AuthController (الـ login التجريبي فيه تأخير 2 ثانية)
Future<void> signIn(WidgetTester tester) async {
  final container = ProviderScope.containerOf(tester.element(find.byType(Navigator).first));
  final login = container.read(authControllerProvider).login(email: 'trader@example.com', password: 'research42');
  await tester.pump(const Duration(seconds: 3));
  await login;
  await tester.pumpAndSettle();
}

void main() {
  group('Edit profile', () {
    for (final (locale, theme) in [('en', 'light'), ('ar', 'dark')]) {
      testWidgets('renders ($locale, $theme), Save is off until something changes', (tester) async {
        await pushOver(tester, const EditProfileScreen(), locale: locale, theme: theme);
        expect(find.byType(EditProfileScreen), findsOneWidget);
        final save = tester.widget<FilledButton>(find.byType(FilledButton));
        expect(save.onPressed, isNull);
        expect(tester.takeException(), isNull);
      });
    }

    testWidgets('leaving with unsaved edits asks first', (tester) async {
      await pushOver(tester, const EditProfileScreen());
      await tester.enterText(find.byType(TextFormField).first, 'Sara');
      await tester.pumpAndSettle();

      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      expect(find.text('Discard changes?'), findsOneWidget);
      await tester.tap(find.text('Keep editing'));
      await tester.pumpAndSettle();
      expect(find.byType(EditProfileScreen), findsOneWidget);

      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      await tester.tap(find.text('Discard'));
      await tester.pumpAndSettle();
      expect(find.byType(EditProfileScreen), findsNothing);
    });

    testWidgets('saving updates the account and closes the screen', (tester) async {
      await pushOver(tester, const EditProfileScreen());
      await signIn(tester);
      // الشاشة انفتحت قبل الدخول، فمنفتحها من جديد لتقرأ المستخدم
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextFormField).first, 'Sara Nassar');
      await tester.pumpAndSettle();
      await tester.tap(find.text('Save Changes'));
      await tester.pump(const Duration(seconds: 1));
      await tester.pumpAndSettle();

      expect(find.byType(EditProfileScreen), findsNothing);
      expect(find.text('Profile updated successfully'), findsOneWidget);
      final container = ProviderScope.containerOf(tester.element(find.text('open')));
      expect(container.read(authControllerProvider).currentUser?.displayName, 'Sara Nassar');
    });

    testWidgets('largest font: no overflow', (tester) async {
      useLargeText(tester);
      await pushOver(tester, const EditProfileScreen(), locale: 'ar');
      await tester.drag(find.byType(ListView), const Offset(0, -3000));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });
  });

  group('Password & security', () {
    testWidgets('only the working password form is shown (no fake toggles)', (tester) async {
      await pushOver(tester, const SecurityScreen());
      expect(find.byType(TextFormField), findsNWidgets(3));
      expect(find.byType(Switch), findsNothing);
      expect(find.textContaining('Biometric'), findsNothing);
      expect(find.textContaining('Two-factor'), findsNothing);
    });

    testWidgets('validates the new password and the confirmation', (tester) async {
      await pushOver(tester, const SecurityScreen());
      final fields = find.byType(TextFormField);
      await tester.enterText(fields.at(0), 'old');
      await tester.enterText(fields.at(1), 'short');
      await tester.enterText(fields.at(2), 'other');
      await tester.tap(find.text('Update Password'));
      await tester.pumpAndSettle();
      expect(find.text('Minimum 8 characters'), findsOneWidget);
      expect(find.text('Passwords do not match'), findsOneWidget);
    });

    testWidgets('a valid change clears the form and confirms', (tester) async {
      await pushOver(tester, const SecurityScreen());
      final fields = find.byType(TextFormField);
      await tester.enterText(fields.at(0), 'OldPass1!');
      await tester.enterText(fields.at(1), 'NewPass1!');
      await tester.enterText(fields.at(2), 'NewPass1!');
      await tester.tap(find.text('Update Password'));
      await tester.pump(const Duration(seconds: 1));
      await tester.pumpAndSettle();
      expect(find.text('Password updated successfully'), findsOneWidget);
      expect(tester.widget<TextFormField>(fields.at(1)).controller!.text, isEmpty);
    });

    testWidgets('largest font in Arabic: no overflow', (tester) async {
      useLargeText(tester);
      await pushOver(tester, const SecurityScreen(), locale: 'ar', theme: 'dark');
      await tester.drag(find.byType(ListView), const Offset(0, -3000));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });
  });
}
