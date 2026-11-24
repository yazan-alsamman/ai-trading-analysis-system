// اختبارات الـ shell: التبويبات، سهم/زر الرجوع لـ Home، وشريط "غير متصل".

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/app/shell/app_shell.dart';
import 'package:trading_app/app/shell/widgets/back_to_home_button.dart';
import 'package:trading_app/features/membership/views/plans_screen.dart';
import 'package:trading_app/features/home/views/home_screen.dart';
import 'package:trading_app/features/profile/views/profile_screen.dart';
import 'package:trading_app/features/signals/views/signals_screen.dart';

import '../helpers/test_app.dart';

Future<void> pumpShell(WidgetTester tester, {String locale = 'en'}) async {
  usePhoneSize(tester);
  await tester.pumpWidget(await testScope(const TestApp(), locale: locale));
  await settleMocks(tester);
}

int selectedTab(WidgetTester tester) =>
    tester.widget<NavigationBar>(find.byType(NavigationBar)).selectedIndex;

Future<void> openTab(WidgetTester tester, int index) async {
  final destinations = find.descendant(
    of: find.byType(NavigationBar),
    matching: find.byType(NavigationDestination),
  );
  await tester.tap(destinations.at(index));
  await tester.pumpAndSettle();
}

/// السهم الظاهر بالتبويب الحالي (IndexedStack بيبني التبويبات المزارة بس
/// بيرسم الحالي - فمنفلتر على الظاهر)
Finder visibleBackArrow() => find.byType(BackToHomeButton).hitTestable();

void main() {
  for (final (locale, labels) in [
    ('en', ['Home', 'Signals', 'Assistant', 'Community', 'Profile']),
    ('ar', ['الرئيسية', 'الإشارات', 'المساعد', 'المجتمع', 'حسابي']),
  ]) {
    testWidgets('shows the five renamed tabs and starts on Home ($locale)',
        (tester) async {
      await pumpShell(tester, locale: locale);

      expect(find.byType(AppShell), findsOneWidget);
      for (final label in labels) {
        expect(
          find.descendant(of: find.byType(NavigationBar), matching: find.text(label)),
          findsOneWidget,
        );
      }
      expect(selectedTab(tester), 0);
      expect(find.byType(HomeScreen), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  group('A1: no demo strip', () {
    testWidgets('the shell shows no "Simulated data" strip', (tester) async {
      await pumpShell(tester);
      expect(find.textContaining('Simulated data', findRichText: true), findsNothing);
      expect(find.textContaining('demo data', findRichText: true), findsNothing);
      expect(find.byTooltip('Dismiss'), findsNothing);
    });

    testWidgets('offline strip appears when simulating offline and stays', (tester) async {
      await pumpShell(tester);
      expect(find.textContaining('You’re offline', findRichText: true), findsNothing);

      // Profile → Settings → Developer → Simulate offline، وبعدين رجوع للـ shell
      await openTab(tester, 4);
      await tester.tap(find.text('Settings'));
      await tester.pumpAndSettle();
      await scrollTo(tester, find.text('Simulate offline'));
      await tester.tap(find.text('Simulate offline'));
      await tester.pumpAndSettle();
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      expect(find.textContaining('You’re offline', findRichText: true), findsOneWidget);
      expect(
        find.textContaining('Showing the last received data.', findRichText: true),
        findsOneWidget,
      );

      // بيضل ظاهر بكل التبويبات لحد ما يرجع الاتصال
      await openTab(tester, 0);
      expect(find.textContaining('You’re offline', findRichText: true), findsOneWidget);
    });
  });

  group('A2: back to Home', () {
    testWidgets('Home has no back arrow', (tester) async {
      await pumpShell(tester);
      expect(visibleBackArrow(), findsNothing);
    });

    for (final (index, name) in [
      (1, 'Signals'),
      (2, 'Assistant'),
      (3, 'Community'),
      (4, 'Profile'),
    ]) {
      testWidgets('$name shows the arrow and tapping it selects Home', (tester) async {
        await pumpShell(tester);
        await openTab(tester, index);
        expect(selectedTab(tester), index);

        expect(visibleBackArrow(), findsOneWidget);
        expect(find.byTooltip('Back to Home'), findsWidgets);
        final size = tester.getSize(visibleBackArrow());
        expect(size.width, greaterThanOrEqualTo(48));
        expect(size.height, greaterThanOrEqualTo(48));

        await tester.tap(visibleBackArrow());
        await tester.pumpAndSettle();
        expect(selectedTab(tester), 0);
      });

      testWidgets('system Back from $name selects Home, not exit', (tester) async {
        await pumpShell(tester);
        await openTab(tester, index);

        final handled = await tester.binding.handlePopRoute();
        await tester.pumpAndSettle();
        expect(handled, isTrue, reason: 'the shell must consume Back');
        expect(selectedTab(tester), 0);
        expect(find.byType(AppShell), findsOneWidget);
      });
    }

    testWidgets('arrow points the other way in Arabic (RTL)', (tester) async {
      await pumpShell(tester, locale: 'ar');
      await openTab(tester, 1);
      expect(find.byType(SignalsScreen), findsOneWidget);
      final arrow = visibleBackArrow();
      expect(Directionality.of(tester.element(arrow)), TextDirection.rtl);
      // matchTextDirection: الأيقونة بتنقلب تلقائيًا بالـ RTL
      final icon = tester.widget<Icon>(find.descendant(of: arrow, matching: find.byType(Icon)));
      expect(icon.icon!.matchTextDirection, isTrue);
      expect(find.byTooltip('رجوع إلى الرئيسية'), findsWidgets);
      // وبيضل بيوصّل لـ Home
      await tester.tap(arrow);
      await tester.pumpAndSettle();
      expect(selectedTab(tester), 0);
    });

    testWidgets('a detail screen keeps its own arrow back to its tab', (tester) async {
      await pumpShell(tester);
      await openTab(tester, 4);
      await scrollTo(tester, find.text('Plan'));
      await tester.tap(find.text('Plan'));
      await tester.pumpAndSettle();
      expect(find.byType(PlansScreen), findsOneWidget);
      expect(find.byType(BackButton), findsOneWidget); // سهم شاشة التفاصيل نفسها
      expect(find.byType(ProfileScreen).hitTestable(), findsNothing);

      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      expect(selectedTab(tester), 4);
      expect(find.byType(ProfileScreen).hitTestable(), findsOneWidget);
    });
  });

  group('Header: arrow and title on one row', () {
    for (final locale in ['en', 'ar']) {
      for (final (index, title) in locale == 'en'
          ? [(1, 'Signals'), (2, 'Assistant'), (3, 'Community'), (4, 'Profile')]
          : [(1, 'الإشارات'), (2, 'المساعد'), (3, 'المجتمع'), (4, 'حسابي')]) {
        testWidgets('tab $index ($locale)', (tester) async {
          await pumpShell(tester, locale: locale);
          await openTab(tester, index);
          final header = find.byType(TabHeader).hitTestable();
          expectArrowBesideTitle(
            tester,
            arrow: find.descendant(of: header, matching: find.byType(IconButton)),
            title: find.descendant(of: header, matching: find.text(title)),
            rtl: locale == 'ar',
          );
        });
      }
    }

    // التبويبات الجديدة بس - Assistant/Community القديمة بتنعاد تصميمها بخطوتها
    for (final (name, screen) in [
      ('Signals', const SignalsScreen()),
      ('Profile', const ProfileScreen()),
    ]) {
      for (final locale in ['en', 'ar']) {
        testWidgets('largest font: $name header still fits ($locale)', (tester) async {
          useLargeText(tester);
          usePhoneSize(tester);
          await tester.pumpWidget(await testScope(TestApp(home: screen), locale: locale));
          await tester.pumpAndSettle();
          expect(find.byType(TabHeader), findsOneWidget);
          expect(tester.takeException(), isNull);
        });
      }
    }
  });

  testWidgets('the Assistant tab is a robot head: outlined, filled when selected, labelled "Assistant"', (tester) async {
    await pumpShell(tester);
    final bar = find.byType(NavigationBar);
    expect(find.descendant(of: bar, matching: find.byIcon(Icons.smart_toy_outlined)), findsOneWidget);
    expect(find.descendant(of: bar, matching: find.byIcon(Icons.auto_awesome_outlined)), findsNothing);
    await openTab(tester, 2);
    expect(find.descendant(of: bar, matching: find.byIcon(Icons.smart_toy)), findsOneWidget);
    expect(find.descendant(of: bar, matching: find.text('Assistant')), findsOneWidget);
    final size = tester.getSize(find.descendant(of: bar, matching: find.byType(NavigationDestination)).at(2));
    expect(size.height, greaterThanOrEqualTo(48));
  });
}
