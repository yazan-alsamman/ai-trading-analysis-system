// اختبارات Community → Experts (Stage B + T2): شريط News / Experts، بطاقات الخبراء،
// زر Subscribe المفعّل (T2)، والعربي.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/core/data/json.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/features/community/data/experts_repository.dart';
import 'package:trading_app/features/community/views/community_screen.dart';
import 'package:trading_app/features/community/widgets/expert_card.dart';

import '../../helpers/test_app.dart';

Future<void> openExperts(WidgetTester tester, {String locale = 'en', String theme = 'light', double height = 812}) async {
  usePhoneSize(tester, height: height);
  await tester.pumpWidget(await testScope(
    const TestApp(home: CommunityScreen()),
    locale: locale,
    prefs: {themeModeStorageKey: theme},
  ));
  await settleMocks(tester);
  await tester.tap(find.text(locale == 'en' ? 'Experts' : 'الخبراء'));
  await tester.pumpAndSettle();
}

void main() {
  for (final theme in ['light', 'dark']) {
    testWidgets('Experts lists the simulated profiles ($theme)', (tester) async {
      await openExperts(tester, theme: theme, height: 3000);
      expect(find.byType(ExpertCard), findsNWidgets(3));
      expect(find.text('Lina Haddad'), findsOneWidget);
      expect(find.text('Simulated'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('Subscribe is enabled on every card and says it is simulated (T2)', (tester) async {
    await openExperts(tester, height: 3000);
    final buttons = tester.widgetList<OutlinedButton>(find.widgetWithText(OutlinedButton, 'Subscribe'));
    expect(buttons, hasLength(3));
    expect(buttons.every((b) => b.onPressed != null), isTrue);
    expect(find.textContaining('Subscriptions are not open yet'), findsNothing);
    expect(find.textContaining('Subscriptions and replies are simulated'), findsOneWidget);
  });

  testWidgets('News stays the first section', (tester) async {
    usePhoneSize(tester);
    await tester.pumpWidget(await testScope(const TestApp(home: CommunityScreen())));
    await settleMocks(tester);
    final segmented = tester.widget<SegmentedButton<CommunitySection>>(find.byType(SegmentedButton<CommunitySection>));
    expect(segmented.selected, {CommunitySection.news});
  });

  testWidgets('Arabic: translated profiles, RTL, largest font fits', (tester) async {
    useLargeText(tester);
    await openExperts(tester, locale: 'ar', theme: 'dark');
    expect(find.text('لينا حداد'), findsOneWidget);
    expect(Directionality.of(tester.element(find.byType(CommunityScreen))), TextDirection.rtl);
    await tester.drag(find.byType(ExpertCard).first, const Offset(0, -4000));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });

  test('expert payload: other asset classes are dropped, incomplete rows rejected', () {
    final expert = expertFromJson(const Json({
      'id': 'x',
      'name': 'A',
      'headline': 'B',
      'availability': 'C',
      'markets': ['XAU/USD', 'BTC/USD', 'AAPL'],
    }));
    expect(expert?.markets, ['XAU/USD']);
    expect(expertFromJson(const Json({'id': 'x', 'name': ' '})), isNull);
  });
}
