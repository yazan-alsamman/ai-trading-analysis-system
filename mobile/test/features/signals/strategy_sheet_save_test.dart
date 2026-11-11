// اختبارات Save بـ "Strategy": بيحفظ وبيضل بالـ sheet ("Saved" + إعلان)،
// القائمة وراها بتتحدّث، ضغطة مزدوجة = حفظة وحدة، الإغلاق بيرمي التعديلات،
// والرجوع من Backtest بيرجّع لنفس الـ sheet المفتوحة.

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:trading_app/core/storage/preferences_provider.dart';
import 'package:trading_app/core/widgets/app_button.dart';
import 'package:trading_app/core/widgets/direction_badge.dart';
import 'package:trading_app/features/backtest/data/backtest_repository.dart';
import 'package:trading_app/features/backtest/views/backtest_screen.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/markets/models/market_models.dart';
import 'package:trading_app/features/signals/data/signal_profile_repository.dart';
import 'package:trading_app/features/signals/models/signal_profile.dart';
import 'package:trading_app/features/signals/view_models/signals_feed_view_model.dart';
import 'package:trading_app/features/signals/views/signals_screen.dart';
import 'package:trading_app/features/signals/widgets/strategy_bar.dart';
import 'package:trading_app/features/signals/widgets/strategy_sheet.dart';

import '../../helpers/test_app.dart';

/// استراتيجية خاصة (أداتين، 1h + 4h، صعود بس)
final custom = SignalProfile.defaults.copyWith(
  symbols: {'XAU/USD', 'EUR/USD'},
  timeframes: {Timeframe.h1, Timeframe.h4},
  directions: {SignalDirection.long},
);

Map<String, Object> stored(SignalProfile profile) =>
    {LocalSignalProfileRepository.storageKey: jsonEncode(profile.toJson())};

/// بيعدّ الحفظات (فوق التخزين الحقيقي)
final class _CountingProfiles implements SignalProfileRepository {
  _CountingProfiles(this.inner, this.saves);

  final SignalProfileRepository inner;
  final List<SignalProfile> saves;

  @override
  SignalProfile read() => inner.read();

  @override
  Future<void> save(SignalProfile profile) {
    saves.add(profile);
    return inner.save(profile);
  }

  @override
  Future<void> clear() => inner.clear();
}

final saves = <SignalProfile>[];

Future<void> pumpSignals(WidgetTester tester, {Map<String, Object> prefs = const {}}) async {
  saves.clear();
  usePhoneSize(tester, height: 1800);
  await tester.pumpWidget(await testScope(
    const TestApp(home: SignalsScreen()),
    prefs: prefs,
    overrides: [
      backtestRepositoryProvider.overrideWith(
        (ref) => SimulatedBacktestRepository(source: ref.watch(simulatedMarketSourceProvider), step: Duration.zero),
      ),
      signalProfileRepositoryProvider.overrideWith(
        (ref) => _CountingProfiles(LocalSignalProfileRepository(ref.watch(sharedPreferencesProvider)), saves),
      ),
    ],
  ));
  await tester.pumpAndSettle();
}

ProviderContainer containerOf(WidgetTester tester) =>
    ProviderScope.containerOf(tester.element(find.byType(SignalsScreen, skipOffstage: false)));

Future<void> openSheet(WidgetTester tester) async {
  await tester.tap(find.byType(StrategyBar));
  await tester.pumpAndSettle();
}

Future<void> tapInSheet(WidgetTester tester, String label) async {
  final target = find.text(label);
  await tester.ensureVisible(target);
  await tester.pumpAndSettle();
  await tester.tap(target);
  await tester.pumpAndSettle();
}

Future<void> toggle(WidgetTester tester, String chip) async {
  await tester.tap(find.widgetWithText(FilterChip, chip));
  await tester.pumpAndSettle();
}

/// أول AppButton بالـ sheet = Save
AppButton saveButton(WidgetTester tester) => tester.widget<AppButton>(
      find.descendant(of: find.byType(StrategySheet), matching: find.byType(AppButton)).first,
    );

void main() {
  testWidgets('Save: stays open, shows "Saved" (icon + label, announced), persists, the list behind updates',
      (tester) async {
    await pumpSignals(tester);
    final c = containerOf(tester);
    await openSheet(tester);
    expect(saveButton(tester).onPressed, isNull); // ما في تعديل
    await toggle(tester, 'NZD/USD');
    expect(saveButton(tester).label, 'Save');
    expect(saveButton(tester).onPressed, isNotNull);

    await tapInSheet(tester, 'Save');
    expect(find.byType(StrategySheet), findsOneWidget);
    expect(saveButton(tester).label, 'Saved');
    expect(saveButton(tester).icon, Icons.check_rounded);
    expect(saveButton(tester).onPressed, isNull);
    expect(tester.takeAnnouncements().map((a) => a.message), contains('Strategy saved'));

    final saved = c.read(signalProfileProvider);
    expect(saved.symbols, isNot(contains('NZD/USD')));
    expect(saves, [saved]);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString(LocalSignalProfileRepository.storageKey), jsonEncode(saved.toJson()));
    // البطاقة والقائمة وراها على المحفوظة (والـ sheet لسّا مفتوحة)
    expect(find.text('MA Crossover · 7 instruments · above 60%'), findsOneWidget);
    final feed = await c.read(signalsFeedViewModelProvider.future);
    final expected = await c.read(signalsRepositoryProvider).feed(saved);
    expect(feed.map((o) => o.id), expected.map((o) => o.id));
  });

  testWidgets('editing again re-enables Save; a double tap saves once', (tester) async {
    await pumpSignals(tester);
    await openSheet(tester);
    await toggle(tester, 'NZD/USD');
    await tapInSheet(tester, 'Save');
    expect(saves, hasLength(1));

    await toggle(tester, 'USD/CAD');
    expect(saveButton(tester).label, 'Save');
    expect(saveButton(tester).onPressed, isNotNull);
    final save = find.text('Save');
    await tester.ensureVisible(save);
    await tester.pumpAndSettle();
    await tester.tap(save);
    await tester.tap(save, warnIfMissed: false);
    await tester.pumpAndSettle();
    expect(saves, hasLength(2));
    expect(saves.last.symbols, isNot(contains('USD/CAD')));
    expect(find.text('Saved'), findsOneWidget);
  });

  testWidgets('closing with unsaved edits discards them; the saved strategy stays', (tester) async {
    await pumpSignals(tester, prefs: stored(custom));
    await openSheet(tester);
    await toggle(tester, 'GBP/USD');
    final close = find.byTooltip('Close');
    expect(tester.getSize(close).height, greaterThanOrEqualTo(48));
    await tester.tap(close);
    await tester.pumpAndSettle();
    expect(find.byType(StrategySheet), findsNothing);
    expect(saves, isEmpty);
    expect(containerOf(tester).read(signalProfileProvider), custom);

    await openSheet(tester);
    expect(tester.widget<FilterChip>(find.widgetWithText(FilterChip, 'GBP/USD')).selected, isFalse);
    expect(saveButton(tester).onPressed, isNull);
  });

  testWidgets('Back from Backtest returns to the same open sheet', (tester) async {
    await pumpSignals(tester);
    await openSheet(tester);
    await toggle(tester, 'NZD/USD');
    await tapInSheet(tester, 'Save');
    await tapInSheet(tester, 'Test on past data');
    expect(find.byType(BacktestScreen), findsOneWidget);
    expect(
      {
        for (final chip in tester.widgetList<FilterChip>(find.byType(FilterChip)))
          if (chip.selected) (chip.label as Text).data!,
      },
      {...kProductSymbols}..remove('NZD/USD'),
    );

    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(find.byType(BacktestScreen), findsNothing);
    expect(find.byType(StrategySheet), findsOneWidget);
    expect(tester.widget<FilterChip>(find.widgetWithText(FilterChip, 'NZD/USD')).selected, isFalse);
    expect(saveButton(tester).label, 'Saved');
  });

  testWidgets('the empty-state button opens the same sheet; Save keeps it open there too', (tester) async {
    // احتمال أدنى 90% → ما في إشارات (المحاكى ≤ 78%)
    await pumpSignals(tester, prefs: stored(custom.copyWith(minProbability: 0.9)));
    expect(find.text('No signals match your strategy'), findsOneWidget);
    final open = find.widgetWithText(OutlinedButton, 'Strategy');
    await tester.ensureVisible(open);
    await tester.pumpAndSettle();
    await tester.tap(open);
    await tester.pumpAndSettle();
    expect(find.byType(StrategySheet), findsOneWidget);
    await toggle(tester, 'GBP/USD');
    await tapInSheet(tester, 'Save');
    expect(find.byType(StrategySheet), findsOneWidget);
    expect(saves.single.symbols, contains('GBP/USD'));
  });

  testWidgets('largest font (ar): "Saved" and the close button fit, nothing cut off', (tester) async {
    useLargeText(tester);
    usePhoneSize(tester, height: 1800);
    await tester.pumpWidget(await testScope(const TestApp(home: SignalsScreen()), locale: 'ar'));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(StrategyBar));
    await tester.pumpAndSettle();
    // قسم الطريقة فوق (A3b): بالخط الكبير الشرائح تحت الشاشة
    await tester.ensureVisible(find.widgetWithText(FilterChip, 'NZD/USD'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilterChip, 'NZD/USD'));
    await tester.pumpAndSettle();
    await tapInSheet(tester, 'حفظ');
    final saved = find.text('تم الحفظ');
    expect(saved, findsOneWidget);
    expect(tester.widget<Text>(saved).overflow, isNot(TextOverflow.ellipsis));
    expect(find.byTooltip('إغلاق'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
