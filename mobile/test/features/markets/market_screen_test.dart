// اختبارات شاشة الأداة: الرسم (Syncfusion) بالأنواع والأطر، المؤشرات، رأي
// النموذج والمناطق، "Set alert" (تحقق + إنشاء)، وسحب التنبيه للحذف مع Undo.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:syncfusion_flutter_charts/charts.dart';

import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/features/alerts/view_models/alerts_view_model.dart';
import 'package:trading_app/features/alerts/widgets/set_alert_sheet.dart';
import 'package:trading_app/features/markets/views/market_screen.dart';
import 'package:trading_app/features/markets/widgets/feed_status_pill.dart';
import 'package:trading_app/features/markets/widgets/price_chart.dart';
import 'package:trading_app/features/markets/widgets/signal_summary.dart';
import 'package:trading_app/features/markets/view_models/market_view_model.dart';

import '../../helpers/test_app.dart';

Future<void> pumpMarket(
  WidgetTester tester, {
  String symbol = 'EUR/USD',
  String locale = 'en',
  String theme = 'light',
  double height = 1800,
}) async {
  usePhoneSize(tester, height: height);
  await tester.pumpWidget(await testScope(
    TestApp(home: MarketScreen(symbol: symbol)),
    locale: locale,
    prefs: {themeModeStorageKey: theme},
  ));
  await tester.pumpAndSettle();
}

ProviderContainer containerOf(WidgetTester tester) =>
    ProviderScope.containerOf(tester.element(find.byType(MarketScreen)));

void main() {
  for (final theme in ['light', 'dark']) {
    testWidgets('price, feed pill, chart and model read ($theme)', (tester) async {
      await pumpMarket(tester, theme: theme);
      expect(find.text('EUR/USD'), findsOneWidget);
      expect(find.text('Euro / US Dollar'), findsOneWidget);
      expect(find.byType(FeedStatusPill), findsOneWidget);
      expect(find.text('Live'), findsOneWidget);
      expect(find.text('Simulated'), findsWidgets);
      expect(find.byType(PriceChart), findsOneWidget);
      expect(find.byType(SfCartesianChart), findsOneWidget);
      expect(find.byType(SignalSummary), findsOneWidget);
      expect(find.text('Set alert'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('timeframe and chart type switch the chart', (tester) async {
    await pumpMarket(tester);
    final container = containerOf(tester);
    await tester.tap(find.widgetWithText(ChoiceChip, '4h').first);
    await tester.pumpAndSettle();
    expect(container.read(marketViewModelProvider('EUR/USD')).timeframe.label, '4h');
    expect(tester.widget<PriceChart>(find.byType(PriceChart)).timeframe.label, '4h');

    await tester.tap(find.byTooltip('Line'));
    await tester.pumpAndSettle();
    expect(tester.widget<PriceChart>(find.byType(PriceChart)).chartType, ChartType.line);
    await tester.tap(find.byTooltip('Area'));
    await tester.pumpAndSettle();
    expect(tester.widget<PriceChart>(find.byType(PriceChart)).chartType, ChartType.area);
    expect(tester.takeException(), isNull);
  });

  testWidgets('indicators sheet: RSI and MACD add panels under the chart', (tester) async {
    final semantics = tester.ensureSemantics();
    await pumpMarket(tester);
    await tester.tap(find.text('Indicators'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('RSI 14'));
    await tester.tap(find.text('MACD (12, 26, 9)'));
    await tester.tap(find.text('SMA 20'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Done'));
    await tester.pumpAndSettle();
    expect(find.byType(SfCartesianChart), findsNWidgets(3)); // الرئيسي + لوحتين
    final on = containerOf(tester).read(marketViewModelProvider('EUR/USD')).indicators;
    expect(on, {ChartIndicator.rsi, ChartIndicator.macd, ChartIndicator.sma});
    expect(find.bySemanticsLabel('Indicators, 3 on'), findsOneWidget);
    expect(tester.takeException(), isNull);
    semantics.dispose();
  });

  testWidgets('model read chips choose which zones are drawn', (tester) async {
    await pumpMarket(tester);
    final chart = tester.widget<PriceChart>(find.byType(PriceChart));
    final summary = tester.widget<SignalSummary>(find.byType(SignalSummary));
    // الرسم بيبيّن نفس الرأي المعروض بالخلاصة
    expect(chart.read?.id, summary.shown?.id);
    final detected = summary.opportunities.where((o) => o.isDetected).toList();
    if (detected.length > 1) {
      final other = detected.firstWhere((o) => o.id != summary.shown!.id);
      await tester.tap(find.widgetWithText(ChoiceChip, other.timeframe.label).last);
      await tester.pumpAndSettle();
      expect(tester.widget<PriceChart>(find.byType(PriceChart)).read?.id, other.id);
    }
  });

  testWidgets('Set alert: validation, then create → listed under Your alerts', (tester) async {
    await pumpMarket(tester);
    await tester.tap(find.text('Set alert'));
    await tester.pumpAndSettle();
    expect(find.byType(SetAlertSheet), findsOneWidget);
    expect(find.textContaining('Alert me when it rises to'), findsOneWidget);

    await tester.enterText(find.byType(TextField).first, '');
    await tester.tap(find.text('Create alert'));
    await tester.pumpAndSettle();
    expect(find.text('Enter a price'), findsOneWidget);

    await tester.tap(find.text('−1%'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Alert me when it falls to'), findsOneWidget);
    await tester.tap(find.text('Create alert'));
    await tester.pumpAndSettle();

    expect(find.byType(SetAlertSheet), findsNothing);
    expect(find.textContaining('Alert set: EUR/USD'), findsOneWidget);
    expect(find.text('YOUR ALERTS'), findsOneWidget);
    expect(find.textContaining('Falls to'), findsOneWidget);
    expect(containerOf(tester).read(alertsViewModelProvider).value, hasLength(1));
  });

  testWidgets('swipe an alert to delete, then Undo brings it back', (tester) async {
    await pumpMarket(tester);
    await tester.tap(find.text('Set alert'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Create alert'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Rises to'), findsOneWidget);
    ScaffoldMessenger.of(tester.element(find.byType(MarketScreen))).removeCurrentSnackBar();
    await tester.pumpAndSettle();

    await tester.drag(find.textContaining('Rises to'), const Offset(-600, 0));
    await tester.pumpAndSettle();
    expect(find.textContaining('Rises to'), findsNothing);
    expect(find.text('Alert deleted'), findsOneWidget);

    await tester.tap(find.text('Undo'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Rises to'), findsOneWidget);
  });

  testWidgets('pause and resume an alert', (tester) async {
    await pumpMarket(tester);
    await tester.tap(find.text('Set alert'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Create alert'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Pause'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Paused'), findsOneWidget);
    await tester.tap(find.byTooltip('Resume'));
    await tester.pumpAndSettle();
    // the state line (the section heading is "Active alerts")
    expect(find.text('Active'), findsOneWidget);
  });

  for (final locale in ['en', 'ar']) {
    testWidgets('largest font ($locale): scrolls without overflow, sheet too', (tester) async {
      useLargeText(tester);
      await pumpMarket(tester, locale: locale, height: 3200);
      expect(tester.takeException(), isNull);
      await tester.tap(find.byType(FloatingActionButton));
      await tester.pumpAndSettle();
      expect(find.byType(SetAlertSheet), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('unknown symbol shows an empty state, not a crash', (tester) async {
    await pumpMarket(tester, symbol: 'BTC/USD');
    expect(find.byType(PriceChart), findsNothing);
    expect(find.byType(FloatingActionButton), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
