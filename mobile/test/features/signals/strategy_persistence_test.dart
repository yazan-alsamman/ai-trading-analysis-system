// اختبارات بقاء "Strategy": المحفوظة بتضل فعّالة لحد ما المستخدم يشيلها
// (إعادة فتح الـ sheet و Backtest، إعادة تشغيل، اتصال)، تعديلات Backtest للجلسة
// بس، و"Remove strategy" مع Undo بيحدّث كل يلي بيقرأها.

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/storage/preferences_provider.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/core/widgets/direction_badge.dart';
import 'package:trading_app/features/backtest/data/backtest_repository.dart';
import 'package:trading_app/features/backtest/view_models/backtest_view_model.dart';
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

/// التخزين متل ما بيكون بعد حفظ [custom]
Map<String, Object> storedCustom() => {LocalSignalProfileRepository.storageKey: jsonEncode(custom.toJson())};

Override instantBacktests() => backtestRepositoryProvider.overrideWith(
      (ref) => SimulatedBacktestRepository(source: ref.watch(simulatedMarketSourceProvider), step: Duration.zero),
    );

Future<void> pumpSignals(
  WidgetTester tester, {
  Map<String, Object> prefs = const {},
  String locale = 'en',
}) async {
  usePhoneSize(tester, height: 1800);
  await tester.pumpWidget(await testScope(
    const TestApp(home: SignalsScreen()),
    prefs: prefs,
    locale: locale,
    overrides: [instantBacktests()],
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

/// الأدوات المختارة بشاشة Backtest
Set<String> backtestSymbols(WidgetTester tester) => {
      for (final chip in tester.widgetList<FilterChip>(find.byType(FilterChip)))
        if (chip.selected) (chip.label as Text).data!,
    };

Future<void> closeSheet(WidgetTester tester) async {
  Navigator.of(tester.element(find.byType(StrategySheet))).pop();
  await tester.pumpAndSettle();
}

void main() {
  group('SignalProfileNotifier', () {
    Future<ProviderContainer> containerWith(Map<String, Object> prefs) async {
      SharedPreferences.setMockInitialValues(prefs);
      final shared = await SharedPreferences.getInstance();
      final c = ProviderContainer(overrides: [connectivityOverride(), sharedPreferencesProvider.overrideWithValue(shared)]);
      addTearDown(c.dispose);
      return c;
    }

    test('a saved strategy survives a restart (new provider scope, same storage)', () async {
      final first = await containerWith(const {});
      expect(first.read(hasCustomStrategyProvider), isFalse);
      await first.read(signalProfileProvider.notifier).save(custom);
      final stored = Map<String, Object>.from({
        LocalSignalProfileRepository.storageKey:
            first.read(sharedPreferencesProvider).getString(LocalSignalProfileRepository.storageKey)!,
      });

      final restarted = await containerWith(stored);
      expect(restarted.read(signalProfileProvider), custom);
      expect(restarted.read(hasCustomStrategyProvider), isTrue);
    });

    test('nothing resets it by itself: offline / online, feed refresh, listeners coming and going', () async {
      final c = await containerWith(storedCustom());
      final sub = c.listen(signalProfileProvider, (_, __) {});
      c.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      c.read(networkStatusProvider.notifier).set(NetworkStatus.online);
      c.invalidate(signalsFeedViewModelProvider);
      sub.close();
      await pumpEventQueue();
      expect(c.read(signalProfileProvider), custom);
    });

    test('remove: defaults everywhere, storage cleared; Undo (save previous) restores it', () async {
      final c = await containerWith(storedCustom());
      final previous = await c.read(signalProfileProvider.notifier).remove();
      expect(previous, custom);
      expect(c.read(signalProfileProvider), SignalProfile.defaults);
      expect(c.read(signalProfileProvider).symbols, kProductSymbols.toSet());
      expect(c.read(hasCustomStrategyProvider), isFalse);
      final prefs = c.read(sharedPreferencesProvider);
      expect(prefs.getString(LocalSignalProfileRepository.storageKey), isNull);

      await c.read(signalProfileProvider.notifier).save(previous);
      expect(c.read(signalProfileProvider), custom);
      expect(prefs.getString(LocalSignalProfileRepository.storageKey), isNotNull);
    });

    test('saving the defaults is the same as no saved strategy', () async {
      final c = await containerWith(storedCustom());
      await c.read(signalProfileProvider.notifier).save(SignalProfile.defaults);
      expect(c.read(hasCustomStrategyProvider), isFalse);
      expect(c.read(sharedPreferencesProvider).getString(LocalSignalProfileRepository.storageKey), isNull);
    });

    test('Backtest pre-fills from the current strategy and follows save / remove', () async {
      final c = await containerWith(storedCustom());
      c.listen(backtestViewModelProvider, (_, __) {});
      expect(c.read(backtestViewModelProvider).symbols, custom.symbols);
      c.read(backtestViewModelProvider.notifier).toggleSymbol('NZD/USD', true);
      expect(c.read(signalProfileProvider), custom); // للجلسة بس

      await c.read(signalProfileProvider.notifier).remove();
      expect(c.read(backtestViewModelProvider).symbols, kProductSymbols.toSet());
    });
  });

  group('Strategy on screen', () {
    testWidgets('saved: stays on after closing and reopening the sheet and Backtest', (tester) async {
      await pumpSignals(tester);
      expect(find.text('Default: MA Crossover · all instruments'), findsOneWidget);
      await openSheet(tester);
      expect(find.text('Remove strategy'), findsNothing); // ما في شي محفوظ
      for (final s in kProductSymbols.where((s) => !custom.symbols.contains(s))) {
        await tester.tap(find.widgetWithText(FilterChip, s));
      }
      await tester.pumpAndSettle();
      await tapInSheet(tester, 'Save');
      await closeSheet(tester);
      expect(find.text('MA Crossover · 2 instruments · above 60%'), findsOneWidget);

      for (var round = 0; round < 2; round++) {
        await openSheet(tester);
        expect(find.text('Remove strategy'), findsOneWidget);
        final selected = {
          for (final chip in tester.widgetList<FilterChip>(find.byType(FilterChip)))
            if (chip.selected && kProductSymbols.contains((chip.label as Text).data)) (chip.label as Text).data!,
        };
        expect(selected, custom.symbols);
        await tapInSheet(tester, 'Test on past data');
        expect(find.byType(BacktestScreen), findsOneWidget);
        expect(find.text('Using your saved strategy · MA Crossover'), findsOneWidget);
        expect(backtestSymbols(tester), custom.symbols);
        await tester.pageBack();
        await tester.pumpAndSettle();
        await closeSheet(tester);
        expect(find.text('MA Crossover · 2 instruments · above 60%'), findsOneWidget);
      }
    });

    testWidgets('restart with stored data: the card and Backtest still use it', (tester) async {
      await pumpSignals(tester, prefs: storedCustom());
      expect(find.text('MA Crossover · 2 instruments · above 60%'), findsOneWidget);
      await openSheet(tester);
      await tapInSheet(tester, 'Test on past data');
      expect(backtestSymbols(tester), custom.symbols);
    });

    testWidgets('Backtest edits are session-only; reopening starts fresh (no old result)', (tester) async {
      await pumpSignals(tester, prefs: storedCustom());
      await openSheet(tester);
      await tapInSheet(tester, 'Test on past data');

      await tester.tap(find.widgetWithText(FilterChip, 'NZD/USD'));
      await tester.tap(find.widgetWithText(ChoiceChip, '1 year'));
      await tester.pumpAndSettle();
      await tapInSheet(tester, 'Run test');
      expect(find.text('Results · last 1 year'), findsOneWidget);

      final c = containerOf(tester);
      expect(c.read(signalProfileProvider), custom);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString(LocalSignalProfileRepository.storageKey), jsonEncode(custom.toJson()));

      await tester.pageBack();
      await tester.pumpAndSettle();
      await tapInSheet(tester, 'Test on past data');
      expect(backtestSymbols(tester), custom.symbols);
      expect(tester.widget<ChoiceChip>(find.widgetWithText(ChoiceChip, '90 days')).selected, isTrue);
      expect(find.text('Choose instruments and a period, then run the test.'), findsOneWidget);
      expect(find.textContaining('Results ·'), findsNothing);
    });

    testWidgets('a newly saved strategy is what the next Backtest uses', (tester) async {
      await pumpSignals(tester, prefs: storedCustom());
      await openSheet(tester);
      await tester.tap(find.widgetWithText(FilterChip, 'GBP/USD'));
      await tester.pumpAndSettle();
      await tapInSheet(tester, 'Save');
      // الـ sheet لسّا مفتوحة: Backtest منها مباشرة بياخد الجديدة
      await tapInSheet(tester, 'Test on past data');
      expect(backtestSymbols(tester), {...custom.symbols, 'GBP/USD'});
    });

    testWidgets('Remove: defaults everywhere at once; Undo restores it', (tester) async {
      await pumpSignals(tester, prefs: storedCustom());
      final c = containerOf(tester);
      await c.read(signalsFeedViewModelProvider.future);
      await openSheet(tester);
      final remove = find.text('Remove strategy');
      await tester.ensureVisible(remove);
      await tester.pumpAndSettle();
      expect(
        tester.getSize(find.ancestor(of: remove, matching: find.byType(TextButton))).height,
        greaterThanOrEqualTo(48),
      );
      await tester.tap(remove);
      await tester.pumpAndSettle();

      expect(find.byType(StrategySheet), findsNothing); // ولا dialog
      expect(find.text('Strategy removed. Showing every instrument.'), findsOneWidget);
      expect(find.text('Default: MA Crossover · all instruments'), findsOneWidget);
      expect(c.read(signalProfileProvider), SignalProfile.defaults);
      // القائمة بتعيد التحميل على الافتراضي
      final feed = await c.read(signalsFeedViewModelProvider.future);
      final expected = await c.read(signalsRepositoryProvider).feed(SignalProfile.defaults);
      expect(feed.map((o) => o.id), expected.map((o) => o.id));

      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();
      expect(find.text('MA Crossover · 2 instruments · above 60%'), findsOneWidget);
      expect(c.read(signalProfileProvider), custom);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString(LocalSignalProfileRepository.storageKey), isNotNull);
    });

    testWidgets('after Remove, Backtest pre-fills with the defaults', (tester) async {
      await pumpSignals(tester, prefs: storedCustom());
      await openSheet(tester);
      await tapInSheet(tester, 'Remove strategy');
      await openSheet(tester);
      expect(find.text('Remove strategy'), findsNothing);
      await tapInSheet(tester, 'Test on past data');
      expect(find.text('Using the default strategy · MA Crossover'), findsOneWidget);
      expect(backtestSymbols(tester), kProductSymbols.toSet());
    });

    for (final (locale, mode) in [('ar', 'dark'), ('en', 'light')]) {
      testWidgets('largest font ($locale, $mode): card and Remove fit, nothing cut off', (tester) async {
        useLargeText(tester);
        usePhoneSize(tester, height: 1800);
        await tester.pumpWidget(await testScope(
          const TestApp(home: SignalsScreen()),
          prefs: {...storedCustom(), themeModeStorageKey: mode},
          locale: locale,
        ));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        await tester.tap(find.byType(StrategyBar));
        await tester.pumpAndSettle();
        final remove = find.text(locale == 'en' ? 'Remove strategy' : 'إزالة الاستراتيجية');
        await tester.ensureVisible(remove);
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        expect(tester.widget<Text>(remove).overflow, isNot(TextOverflow.ellipsis));
        expect(tester.widget<Text>(remove).maxLines, isNull);
      });
    }
  });
}
