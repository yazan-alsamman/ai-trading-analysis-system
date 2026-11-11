// اختبارات الـ Home: قائمة المتابعة (8 أدوات بسعرها ورأي النموذج)، الثيمين
// والعربي والخط الكبير، فتح شاشة الأداة، حالات الخطأ/الفاضي، وسباق التحديث.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/core/widgets/feedback_states.dart';
import 'package:trading_app/core/widgets/source_tag.dart';
import 'package:trading_app/features/home/view_models/watchlist_view_model.dart';
import 'package:trading_app/features/home/views/home_screen.dart';
import 'package:trading_app/features/home/widgets/watchlist_row.dart';
import 'package:trading_app/features/markets/data/market_data_repository.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/markets/data/simulated_market_source.dart';
import 'package:trading_app/features/markets/models/market_models.dart';
import 'package:trading_app/features/markets/views/market_screen.dart';

import '../../helpers/test_app.dart';

Future<void> pumpHome(
  WidgetTester tester, {
  String locale = 'en',
  String theme = 'light',
  double height = 900,
  List<Override> overrides = const [],
}) async {
  usePhoneSize(tester, height: height);
  await tester.pumpWidget(await testScope(
    const TestApp(home: HomeScreen()),
    locale: locale,
    prefs: {themeModeStorageKey: theme},
    overrides: overrides,
  ));
  await tester.pumpAndSettle();
}

/// repository بأدوات بنتحكّم فيها (فاضي / خطأ / طلبات معلّقة)
final class FakeInstrumentsRepo extends SimulatedMarketDataRepository {
  FakeInstrumentsRepo() : super(source: SimulatedMarketSource(clock: () => kTestNow));

  Object? error;
  List<Instrument>? instrumentsOverride;
  final List<Completer<List<Instrument>>> pending = [];
  bool hold = false;

  @override
  Future<List<Instrument>> instruments() async {
    if (error != null) throw error!;
    if (hold) {
      final c = Completer<List<Instrument>>();
      pending.add(c);
      return c.future;
    }
    return instrumentsOverride ?? await super.instruments();
  }
}

void main() {
  for (final theme in ['light', 'dark']) {
    testWidgets('watchlist: 8 instruments with price, change and model read ($theme)', (tester) async {
      // أطول: سطر رأي النموذج بيلتف بخط الاختبار المربّع بدل ما ينقص
      await pumpHome(tester, theme: theme, height: 1100);
      expect(find.text('Home'), findsOneWidget);
      expect(find.text('Watchlist'), findsOneWidget);
      expect(find.byType(WatchlistRow), findsNWidgets(8));
      expect(find.byType(SourceTag), findsOneWidget); // "Simulated" مرّة وحدة للقائمة
      // السطر: التاريخ + حالة الجلسات (أربعاء 14:05 UTC)
      expect(find.textContaining('London · New York overlap'), findsOneWidget);
      expect(find.text('Signals are for educational purposes and are not investment advice.'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('every row reads its price, change and model read aloud', (tester) async {
    final semantics = tester.ensureSemantics();
    await pumpHome(tester);
    final eur = find.bySemanticsLabel(RegExp(r'^EUR/USD, Euro / US Dollar, \d\.\d{5}, (Up|Down|Unchanged) '));
    expect(eur, findsOneWidget);
    expect(find.bySemanticsLabel(RegExp(r'^XAU/USD, .*, \d{4}\.\d{2}, ')), findsOneWidget);
    expect(find.bySemanticsLabel(RegExp(r'Model read: ')), findsWidgets);
    semantics.dispose();
  });

  testWidgets('Arabic: RTL, Arabic copy, no layout errors', (tester) async {
    await pumpHome(tester, locale: 'ar', theme: 'dark');
    expect(Directionality.of(tester.element(find.byType(HomeScreen))), TextDirection.rtl);
    expect(find.text('الرئيسية'), findsOneWidget);
    expect(find.text('قائمة المتابعة'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  for (final locale in ['en', 'ar']) {
    testWidgets('largest font ($locale): no overflow, sparklines give way to numbers', (tester) async {
      useLargeText(tester);
      await pumpHome(tester, locale: locale, height: 2400);
      expect(tester.takeException(), isNull);
      expect(find.byType(WatchlistRow), findsNWidgets(8));
    });
  }

  testWidgets('tapping a row opens its Market screen (once, even on a double tap)', (tester) async {
    usePhoneSize(tester, height: 900);
    await tester.pumpWidget(await testScope(const TestApp()));
    await tester.pumpAndSettle();
    final row = find.widgetWithText(WatchlistRow, 'GBP/USD');
    await tester.tap(row);
    await tester.tap(row, warnIfMissed: false);
    await tester.pumpAndSettle();
    expect(find.byType(MarketScreen), findsOneWidget);
    expect(find.text('British Pound / US Dollar'), findsOneWidget);

    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(find.byType(MarketScreen), findsNothing);
  });

  testWidgets('error state with retry', (tester) async {
    final repo = FakeInstrumentsRepo()..error = StateError('down');
    await pumpHome(tester, overrides: [marketDataRepositoryProvider.overrideWithValue(repo)]);
    expect(find.byType(ErrorState), findsOneWidget);
    expect(find.text('Prices could not be loaded.'), findsOneWidget);

    repo.error = null;
    await tester.tap(find.text('Try again'));
    await tester.pumpAndSettle();
    expect(find.byType(WatchlistRow), findsNWidgets(8));
  });

  testWidgets('empty state', (tester) async {
    final repo = FakeInstrumentsRepo()..instrumentsOverride = const [];
    await pumpHome(tester, overrides: [marketDataRepositoryProvider.overrideWithValue(repo)]);
    expect(find.text('No instruments yet'), findsOneWidget);
  });

  testWidgets('pull to refresh: a failure keeps the list and shows a snackbar', (tester) async {
    final repo = FakeInstrumentsRepo();
    await pumpHome(tester, overrides: [marketDataRepositoryProvider.overrideWithValue(repo)]);
    repo.error = StateError('timeout');
    await tester.fling(find.byType(CustomScrollView), const Offset(0, 500), 1200);
    await tester.pumpAndSettle();
    expect(find.byType(WatchlistRow), findsNWidgets(8));
    expect(find.text('Prices could not be loaded.'), findsOneWidget);
  });

  test('watchlist refresh race: an older refresh never overwrites a newer one', () async {
    final repo = FakeInstrumentsRepo();
    final container = ProviderContainer(overrides: [
      connectivityOverride(),
      ...simulatedMarketOverrides(),
      marketDataRepositoryProvider.overrideWithValue(repo),
    ]);
    addTearDown(container.dispose);
    container.listen(watchlistViewModelProvider, (_, __) {});
    final all = await container.read(watchlistViewModelProvider.future);

    repo.hold = true;
    final vm = container.read(watchlistViewModelProvider.notifier);
    final older = vm.refresh();
    final newer = vm.refresh();
    repo.pending[1].complete(all.take(2).toList()); // الأحدث بيخلص أول
    await newer;
    repo.pending[0].complete(all); // الأقدم بيخلص بعدين: لازم ينرمى
    await older;
    expect(container.read(watchlistViewModelProvider).value, hasLength(2));
  });

  testWidgets('a hidden Home (tab not shown) skips tick rebuilds and catches up when shown', (tester) async {
    final repo = _TickingRepo();
    final visible = ValueNotifier(false);
    addTearDown(visible.dispose);
    usePhoneSize(tester, height: 1100);
    await tester.pumpWidget(await testScope(
      TestApp(
        home: ValueListenableBuilder<bool>(
          valueListenable: visible,
          builder: (_, on, child) => TickerMode(enabled: on, child: child!),
          child: const HomeScreen(),
        ),
      ),
      overrides: [marketDataRepositoryProvider.overrideWithValue(repo)],
    ));
    await tester.pumpAndSettle();
    final before = tester.widget<WatchlistRow>(find.byType(WatchlistRow).first).instrument;
    final ticked = Quote(symbol: before.symbol, price: 1.23456, reference: 1.2, time: kTestNow.add(const Duration(seconds: 3)));

    repo.tickController.add([ticked]);
    await tester.pump();
    expect(find.text(before.format(1.23456)), findsNothing, reason: 'hidden row did not rebuild');

    visible.value = true;
    await tester.pump();
    expect(find.text(before.format(1.23456)), findsOneWidget, reason: 'shown again: latest price');
    await tester.pump(const Duration(seconds: 1));
  });
}

/// السوق المحاكى بس النبضات يدوية
final class _TickingRepo extends SimulatedMarketDataRepository {
  _TickingRepo() : super(source: SimulatedMarketSource(clock: () => kTestNow));

  final tickController = StreamController<List<Quote>>.broadcast();

  @override
  Stream<List<Quote>> ticks() => tickController.stream;
}
