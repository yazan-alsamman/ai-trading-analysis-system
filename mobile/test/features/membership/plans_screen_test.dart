// اختبارات شاشة Plans (Stage C - المبسّطة): سطر السعر مرة وحدة، 3 بطاقات،
// "Compare plans" بـ bottom sheet، الأسئلة مطويّة - بالثيمين وبالعربي وبخط كبير.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/core/widgets/page_header.dart';
import 'package:trading_app/features/membership/models/membership_models.dart';
import 'package:trading_app/features/membership/views/plans_screen.dart';
import 'package:trading_app/features/membership/widgets/plan_card.dart';

import '../../helpers/test_app.dart';

Future<void> pumpPlans(
  WidgetTester tester, {
  String locale = 'en',
  String theme = 'light',
  double height = 812,
  PlanId? currentPlan,
}) async {
  usePhoneSize(tester, height: height);
  await tester.pumpWidget(await testScope(
    const TestApp(home: PlansScreen()),
    locale: locale,
    prefs: {themeModeStorageKey: theme},
    overrides: [currentPlanIs(currentPlan)],
  ));
  await tester.pumpAndSettle();
}

Future<void> openCompare(WidgetTester tester, {String label = 'Compare plans'}) async {
  await scrollTo(tester, find.text(label));
  await tester.tap(find.text(label));
  await tester.pumpAndSettle();
}

void main() {
  for (final theme in ['light', 'dark']) {
    testWidgets('three plans, the price line once, compare and FAQ ($theme)', (tester) async {
      await pumpPlans(tester, theme: theme, height: 4000);
      expect(find.byType(PlanCard), findsNWidgets(3));
      for (final name in ['Essential', 'Professional', 'Elite']) {
        expect(find.text(name), findsOneWidget);
      }
      // السعر مكتوب مرة وحدة فوق، مش بكل بطاقة
      expect(find.textContaining('Pricing to be announced', findRichText: true), findsOneWidget);
      expect(find.text('Compare plans'), findsOneWidget);
      expect(find.text('What does each plan cost?'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('the web-only sections are gone (why-cards, plan finder)', (tester) async {
    await pumpPlans(tester, height: 4000);
    expect(find.textContaining('One research desk.', findRichText: true), findsNothing);
    expect(find.text('One honest workflow'), findsNothing);
    expect(find.textContaining('Answer three questions'), findsNothing);
    expect(find.byType(ChoiceChip), findsNothing);
  });

  testWidgets('no price numbers or currency anywhere', (tester) async {
    await pumpPlans(tester, height: 4000);
    final texts = tester
        .widgetList<Text>(find.byType(Text))
        .map((t) => t.data ?? t.textSpan?.toPlainText() ?? '')
        .join(' ');
    expect(texts, isNot(contains(r'$')));
    expect(texts, isNot(contains('€')));
    expect(texts, isNot(contains('/ month')));
  });

  testWidgets('"Choose …" looks disabled but explains in a sheet', (tester) async {
    final semantics = tester.ensureSemantics();
    await pumpPlans(tester, height: 4000);
    expect(find.bySemanticsLabel('Choose Essential'), findsOneWidget);
    await tester.tap(find.text('Choose Essential'));
    await tester.pumpAndSettle();
    expect(find.text('Your selection'), findsOneWidget);
    expect(find.textContaining('Paid activation is not available yet.', findRichText: true), findsOneWidget);
    await tester.tap(find.text('Close'));
    await tester.pumpAndSettle();
    expect(find.text('Your selection'), findsNothing);
    semantics.dispose();
  });

  testWidgets('Compare opens a sheet that starts on Professional and switches plans', (tester) async {
    await pumpPlans(tester, height: 1600);
    await openCompare(tester);
    final segmented = find.byType(SegmentedButton<PlanId>);
    expect(tester.widget<SegmentedButton<PlanId>>(segmented).selected, {PlanId.professional});
    expect(find.text('Gold + 7 FX majors'), findsWidgets);
    expect(find.text('Not included'), findsNWidgets(2)); // assistant + research history

    await tester.tap(find.descendant(of: segmented, matching: find.text('Elite')));
    await tester.pumpAndSettle();
    expect(find.text('Not included'), findsNothing);

    await tester.tap(find.descendant(of: segmented, matching: find.text('Essential')));
    await tester.pumpAndSettle();
    expect(find.text('Gold (XAU/USD)'), findsWidgets);
    expect(find.text('One workspace'), findsOneWidget);
  });

  testWidgets('Compare starts on the current plan when there is one', (tester) async {
    await pumpPlans(tester, currentPlan: PlanId.elite, height: 1600);
    await openCompare(tester);
    expect(tester.widget<SegmentedButton<PlanId>>(find.byType(SegmentedButton<PlanId>)).selected, {PlanId.elite});
  });

  testWidgets('FAQ is collapsed and opens like an accordion', (tester) async {
    await pumpPlans(tester, height: 4000);
    const answer = 'Because sizing risk correctly and seeing how the model has '
        'performed should never be a premium feature.';
    expect(find.text(answer), findsNothing);
    await tester.tap(find.text('Why are risk tools and analytics in every plan?'));
    await tester.pumpAndSettle();
    expect(find.text(answer), findsOneWidget);
  });

  testWidgets('loading shows skeletons, not a spinner', (tester) async {
    usePhoneSize(tester);
    await tester.pumpWidget(await testScope(const TestApp(home: PlansScreen())));
    expect(find.byType(CircularProgressIndicator), findsNothing);
    await tester.pumpAndSettle();
    expect(find.byType(PlanCard), findsWidgets);
  });

  testWidgets('Arabic: RTL and translated copy, no overflow', (tester) async {
    await pumpPlans(tester, locale: 'ar', theme: 'dark', height: 4000);
    expect(find.textContaining('سيُعلَن عن الأسعار لاحقًا', findRichText: true), findsOneWidget);
    // أسماء الخطط أسماء منتج: بتضل إنجليزي بالعربي
    expect(find.text('Elite'), findsOneWidget);
    expect(find.text('اختر Elite'), findsOneWidget);
    expect(find.text('قارن الخطط'), findsOneWidget);
    expect(Directionality.of(tester.element(find.byType(PlansScreen))), TextDirection.rtl);
    expect(tester.takeException(), isNull);
  });

  for (final locale in ['en', 'ar']) {
    testWidgets('largest font ($locale): page and compare sheet scroll without overflow', (tester) async {
      useLargeText(tester);
      await pumpPlans(tester, locale: locale);
      await openCompare(tester, label: locale == 'en' ? 'Compare plans' : 'قارن الخطط');
      await tester.drag(find.byType(SegmentedButton<PlanId>), const Offset(0, -3000));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      Navigator.of(tester.element(find.byType(SegmentedButton<PlanId>))).pop();
      await tester.pumpAndSettle();
      for (var i = 0; i < 8; i++) {
        await tester.drag(find.byType(ListView).first, const Offset(0, -900));
        await tester.pumpAndSettle();
      }
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('the current plan (from the repository) is marked', (tester) async {
    await pumpPlans(tester, currentPlan: PlanId.elite, height: 4000);
    final elite = tester.widget<PlanCard>(
      find.byWidgetPredicate((w) => w is PlanCard && w.plan == PlanId.elite),
    );
    expect(elite.isCurrent, isTrue);
    expect(find.text('Current plan'), findsOneWidget);
  });

  for (final locale in ['en', 'ar']) {
    testWidgets('header: back arrow and title on one row ($locale)', (tester) async {
      usePhoneSize(tester);
      await tester.pumpWidget(await testScope(const TestApp(), locale: locale));
      await settleMocks(tester);
      // تبويب Profile من الشريط السفلي
      await tester.tap(find.descendant(of: find.byType(NavigationBar), matching: find.byType(NavigationDestination)).at(4));
      await tester.pumpAndSettle();
      final plansRow = find.text(locale == 'en' ? 'Plan' : 'الخطة');
      await scrollTo(tester, plansRow);
      await tester.tap(plansRow);
      await tester.pumpAndSettle();
      expectArrowBesideTitle(
        tester,
        arrow: find.byType(BackButton),
        title: find.descendant(
          of: find.byType(PageHeader),
          matching: find.text(locale == 'en' ? 'Plans' : 'الخطط'),
        ),
        rtl: locale == 'ar',
      );
    });
  }
}
