// اختبارات Help & about (Stage B): "ما بيتداول أبدًا"، الأسئلة، الوثائق
// القانونية، تراخيص الطرف الثالث، والنسخة.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/core/app_info.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/features/help/views/help_about_screen.dart';
import 'package:trading_app/features/help/views/legal_screen.dart';

import '../../helpers/test_app.dart';

Future<void> pumpHelp(WidgetTester tester, {String locale = 'en', String theme = 'light', double height = 2400}) async {
  usePhoneSize(tester, height: height);
  await tester.pumpWidget(await testScope(
    const TestApp(home: HelpAboutScreen()),
    locale: locale,
    prefs: {themeModeStorageKey: theme},
  ));
  await tester.pumpAndSettle();
}

void main() {
  for (final (locale, theme) in [('en', 'light'), ('en', 'dark'), ('ar', 'light'), ('ar', 'dark')]) {
    testWidgets('about, never trades, FAQ, legal and version ($locale, $theme)', (tester) async {
      await pumpHelp(tester, locale: locale, theme: theme);
      expect(find.text(locale == 'en' ? 'It never trades.' : 'لا ينفّذ أي صفقة.'), findsOneWidget);
      expect(find.byType(ExpansionTile), findsNWidgets(4));
      expect(find.textContaining(AppInfo.version), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('no made-up contact details or unwritten legal pages', (tester) async {
    await pumpHelp(tester);
    expect(find.textContaining('@'), findsNothing);
    expect(find.textContaining('+1'), findsNothing);
    expect(find.text('Terms of Service'), findsNothing);
    expect(find.text('Privacy Policy'), findsNothing);
  });

  testWidgets('a question opens in place', (tester) async {
    await pumpHelp(tester);
    expect(find.textContaining('It is a probability, not a promise'), findsNothing);
    await tester.tap(find.text('What is a model read?'));
    await tester.pumpAndSettle();
    expect(find.textContaining('It is a probability, not a promise'), findsOneWidget);
  });

  for (final (row, heading) in [
    ('Risk disclosure', '1. What the app is'),
    ('Data on this phone', 'No analytics or trackers'),
  ]) {
    testWidgets('$row opens its document', (tester) async {
      await pumpHelp(tester);
      await tester.tap(find.text(row));
      await tester.pumpAndSettle();
      expect(find.byType(LegalScreen), findsOneWidget);
      expect(find.text(heading), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('Third-party notices opens the licence page', (tester) async {
    await pumpHelp(tester);
    await tester.tap(find.text('Third-party notices'));
    await tester.pumpAndSettle();
    expect(find.byType(LicensePage), findsOneWidget);
  });

  for (final locale in ['en', 'ar']) {
    testWidgets('largest font: help and the risk disclosure fit ($locale)', (tester) async {
      useLargeText(tester);
      await pumpHelp(tester, locale: locale, height: 812);
      await tester.drag(find.byType(ListView), const Offset(0, -6000));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);

      await tester.pumpWidget(await testScope(
        const TestApp(home: LegalScreen(document: LegalDocument.riskDisclosure)),
        locale: locale,
      ));
      await tester.pumpAndSettle();
      await tester.drag(find.byType(ListView), const Offset(0, -6000));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });
  }
}
