// اختبارات "Size this trade": من رأي النموذج على شاشة الأداة، وحساب الحجم
// بالـ sheet (مع رأس المال من Settings أو بدونه).

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/core/widgets/direction_badge.dart';
import 'package:trading_app/features/markets/models/market_models.dart';
import 'package:trading_app/features/markets/views/market_screen.dart';
import 'package:trading_app/features/risk/data/risk_limits_repository.dart';
import 'package:trading_app/features/risk/models/risk_limits.dart';
import 'package:trading_app/features/risk/widgets/size_trade_sheet.dart';
import 'package:trading_app/features/signals/models/opportunity.dart';

import '../../helpers/test_app.dart';

const eurUsd = Instrument(symbol: 'EUR/USD', kind: MarketKind.forex, precision: 5);

final longRead = Opportunity(
  id: 'test',
  symbol: 'EUR/USD',
  timeframe: Timeframe.h1,
  status: OpportunityStatus.detected,
  direction: SignalDirection.long,
  setupType: SetupType.trendFollowing,
  riskLevel: RiskLevel.medium,
  probability: 0.64,
  entryZone: const PriceZone(1.08740, 1.08760),
  stopLossZone: const PriceZone(1.08490, 1.08510),
  takeProfitZone: const PriceZone(1.09240, 1.09260),
  riskReward: 2,
  generatedAt: kTestNow,
  validUntil: kTestNow.add(const Duration(hours: 3)),
);

Map<String, Object> capital(double amount) => {
      LocalRiskLimitsRepository.storageKey: jsonEncode(RiskLimits(capital: amount).toJson()),
    };

Future<void> pumpSheet(
  WidgetTester tester, {
  Map<String, Object> prefs = const {},
  String locale = 'en',
  String theme = 'light',
}) async {
  usePhoneSize(tester, height: 1600);
  await tester.pumpWidget(await testScope(
    TestApp(home: Scaffold(body: SizeTradeSheet(instrument: eurUsd, read: longRead))),
    prefs: {themeModeStorageKey: theme, ...prefs},
    locale: locale,
  ));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('prefilled from the model plan and the saved capital', (tester) async {
    await pumpSheet(tester, prefs: capital(10000));
    expect(find.text('Size this trade · EUR/USD'), findsOneWidget);
    expect(find.text('From the 1h model plan'), findsOneWidget);
    // 1% من 10,000 على وقف 25 نقطة = 40,000 EUR
    expect(find.text('40,000 EUR'), findsOneWidget);
    expect(find.text('USD 100.00 · 1%'), findsOneWidget);
    expect(find.text('0.00250 · 25 pips'), findsOneWidget);
    expect(find.text('USD 200.00 · 1 : 2.0'), findsOneWidget);
    expect(find.textContaining('Close to your limit'), findsOneWidget);
    expect(find.textContaining('never places trades'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('without a saved capital it asks for one, then sizes', (tester) async {
    await pumpSheet(tester);
    expect(find.text('Enter capital, risk, entry and stop to see the size.'), findsOneWidget);
    expect(find.textContaining('Settings → Capital & risk'), findsOneWidget);

    await tester.enterText(find.byType(TextField).first, '20000');
    await tester.pumpAndSettle();
    expect(find.text('80,000 EUR'), findsOneWidget);
  });

  testWidgets('risk chips change the size and the limit status', (tester) async {
    await pumpSheet(tester, prefs: capital(10000));
    await tester.tap(find.widgetWithText(ChoiceChip, '0.5%'));
    await tester.pumpAndSettle();
    expect(find.text('20,000 EUR'), findsOneWidget);
    expect(find.textContaining('Within your limit'), findsOneWidget);

    await tester.tap(find.widgetWithText(ChoiceChip, '2%'));
    await tester.pumpAndSettle();
    expect(find.text('80,000 EUR'), findsOneWidget);
    expect(find.textContaining('Above your limit'), findsOneWidget);
  });

  testWidgets('a stop equal to the entry is explained, not sized', (tester) async {
    await pumpSheet(tester, prefs: capital(10000));
    final fields = find.byType(TextField);
    await tester.enterText(fields.at(3), '1.08750');
    await tester.pumpAndSettle();
    expect(find.text('The stop must differ from the entry.'), findsOneWidget);
  });

  for (final (locale, theme) in [('ar', 'dark'), ('en', 'dark')]) {
    testWidgets('largest font: no overflow ($locale, $theme)', (tester) async {
      useLargeText(tester);
      await pumpSheet(tester, prefs: capital(10000), locale: locale, theme: theme);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('"Size this trade" on the Market screen opens the sheet', (tester) async {
    usePhoneSize(tester, height: 2400);
    // أول أداة إلها رأي حالي بالوقت الثابت (المصدر المحاكى حتمي)
    for (final symbol in kProductSymbols) {
      await tester.pumpWidget(await testScope(TestApp(key: ValueKey(symbol), home: MarketScreen(symbol: symbol))));
      await tester.pumpAndSettle();
      if (find.text('Size this trade').evaluate().isEmpty) continue;

      await tester.ensureVisible(find.text('Size this trade'));
      await tester.tap(find.text('Size this trade'));
      await tester.pumpAndSettle();
      expect(find.byType(SizeTradeSheet), findsOneWidget);
      expect(find.text('Size this trade · $symbol'), findsOneWidget);
      return;
    }
    fail('no instrument had a model read at kTestNow');
  });
}
