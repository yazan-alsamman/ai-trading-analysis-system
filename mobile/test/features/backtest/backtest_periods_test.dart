// T3: فترات Backtest بالسنين (2 / 3 / 5 سنين): المحرّك حتمي ومتّسق مع خلايا
// Insights، الدفعات صغيرة (ما في تعليق)، تقليل نقاط المنحنى بيحفظ الأول والآخر
// والأدنى والأعلى، الإلغاء والسباق بفترة طويلة، وشرائح الفترات (EN/AR، خط 2.0).

import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:syncfusion_flutter_charts/charts.dart';

import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/core/widgets/direction_badge.dart';
import 'package:trading_app/features/backtest/data/backtest_repository.dart';
import 'package:trading_app/features/backtest/models/backtest.dart';
import 'package:trading_app/features/backtest/view_models/backtest_view_model.dart';
import 'package:trading_app/features/backtest/views/backtest_screen.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/markets/data/simulated_market_source.dart';
import 'package:trading_app/features/markets/models/market_models.dart';
import 'package:trading_app/features/signals/data/signal_profile_repository.dart';
import 'package:trading_app/features/signals/data/simulated_outcomes.dart';
import 'package:trading_app/features/signals/models/signal_profile.dart';

import '../../helpers/test_app.dart';

const longPeriods = [BacktestPeriod.y2, BacktestPeriod.y3, BacktestPeriod.y5];

/// كل الأدوات والأطر والاتجاهات وبدون حدود = نفس خلايا Insights
BacktestRequest wide(BacktestPeriod period) => BacktestRequest(
      symbols: kProductSymbols.toSet(),
      timeframes: Timeframe.modelTimeframes.toSet(),
      directions: const {SignalDirection.long, SignalDirection.short},
      minProbability: 0,
      minRiskReward: 0,
      period: period,
    );

BacktestRequest saved(BacktestPeriod period) =>
    BacktestRequest.from(SignalProfile.defaults, symbols: SignalProfile.defaults.symbols, period: period);

List<(DateTime, double, int)> curve(BacktestResult r) => [for (final p in r.equity) (p.time, p.r, p.signals)];

/// مصدر نتحكّم فيه: كل تشغيل بيستنى لحد ما نكمّله نحن
final class _Backtests implements BacktestRepository {
  final calls = <({BacktestRequest request, BacktestCancelToken? cancel, Completer<BacktestResult> completer})>[];

  @override
  bool get isSimulated => true;

  @override
  Future<BacktestResult> run(
    BacktestRequest request, {
    BacktestCancelToken? cancel,
    void Function(double progress)? onProgress,
  }) {
    final completer = Completer<BacktestResult>();
    calls.add((request: request, cancel: cancel, completer: completer));
    return completer.future;
  }
}

final class _Profile implements SignalProfileRepository {
  @override
  SignalProfile read() => SignalProfile.defaults;

  @override
  Future<void> save(SignalProfile profile) async {}

  @override
  Future<void> clear() async {}
}

ProviderContainer container(BacktestRepository Function(Ref ref) repo) {
  final c = ProviderContainer(overrides: [
    connectivityOverride(),
    ...simulatedMarketOverrides(),
    signalProfileRepositoryProvider.overrideWithValue(_Profile()),
    backtestRepositoryProvider.overrideWith(repo),
  ]);
  addTearDown(c.dispose);
  c.listen(backtestViewModelProvider, (_, __) {});
  return c;
}

BacktestResult fakeResult(BacktestPeriod period, {int signals = 30}) => BacktestResult(
      period: period,
      signals: signals,
      hits: signals ~/ 2,
      avgRiskReward: 2,
      maxDrawdown: 3,
      equity: [
        EquityPoint(time: DateTime.utc(2024), r: 0, signals: 0),
        EquityPoint(time: DateTime.utc(2025), r: 4, signals: signals),
      ],
    );

/// [n] نقطة بمنحنى متعرّج حتمي، القاع والقمة بالنص
List<EquityPoint> zigzag(int n) => [
      for (var i = 0; i < n; i++)
        EquityPoint(
          time: DateTime.utc(2020).add(Duration(days: i)),
          r: i == 0
              ? 0
              : i == n ~/ 3
                  ? -40
                  : i == 2 * n ~/ 3
                      ? 55
                      : 10 * math.sin(i / 17) + (i % 7) - 3,
          signals: i,
        ),
    ];

void main() {
  group('Simulated engine: periods in years', () {
    final source = SimulatedMarketSource(clock: () => kTestNow);
    final repo = SimulatedBacktestRepository(source: source, step: Duration.zero);

    for (final period in longPeriods) {
      test('${period.days} days: the same request gives the same result, all day long', () async {
        final a = await repo.run(saved(period));
        final b = await repo.run(saved(period));
        final later = await SimulatedBacktestRepository(
          source: SimulatedMarketSource(clock: () => kTestNow.add(const Duration(hours: 9))),
          step: Duration.zero,
        ).run(saved(period));
        for (final other in [b, later]) {
          expect(other.period, period);
          expect(other.signals, a.signals);
          expect(other.hits, a.hits);
          expect(other.avgRiskReward, a.avgRiskReward);
          expect(other.maxDrawdown, a.maxDrawdown);
          expect(curve(other), curve(a));
        }
        final last = SimulatedOutcomes(source).lastFullDay;
        expect(a.equity.first.time,
            DateTime.fromMillisecondsSinceEpoch((last - period.days + 1) * Duration.millisecondsPerDay, isUtc: true));
        expect(a.equity.last.signals, a.signals);
      });
    }

    // A3c: الخلايا = خلايا طريقة الاستراتيجية (مش سجل النموذج يلي بتجمعه Insights)
    test('no filters: every window equals the method outcome cells; longer windows contain shorter', () async {
      final outcomes = SimulatedOutcomes(source);
      final last = outcomes.lastFullDay;
      var previous = 0;
      for (final period in BacktestPeriod.values) {
        final request = wide(period);
        final r = await repo.run(request);
        final cells = outcomes.total(last - period.days + 1, last, methodId: request.methodId);
        expect(r.signals, cells.resolved, reason: '${period.days} days');
        expect(r.hits, cells.hits, reason: '${period.days} days');
        expect(r.signals, greaterThan(previous));
        previous = r.signals;
      }
    });

    test('the last year of a 5-year run is the 1-year run (same signals, same results)', () async {
      final year = await repo.run(saved(BacktestPeriod.y1));
      final five = await repo.run(saved(BacktestPeriod.y5));
      final start = year.equity.first.time;
      final before = five.equity.lastWhere((p) => p.time.isBefore(start));
      expect(five.signals - before.signals, year.signals);
      expect(five.equity.last.r - before.r, closeTo(year.equity.last.r, 0.02));
    });

    test('long periods run in small chunks: progress climbs to 1, no chunk over ${SimulatedBacktestRepository.maxChunkDays} days',
        () async {
      for (final period in BacktestPeriod.values) {
        final progress = <double>[];
        await repo.run(saved(period), onProgress: progress.add);
        expect(progress, hasLength(SimulatedBacktestRepository.chunkCount(period.days)));
        expect(progress.length, greaterThanOrEqualTo(SimulatedBacktestRepository.chunks));
        expect(SimulatedBacktestRepository.chunkDays(period.days),
            lessThanOrEqualTo(SimulatedBacktestRepository.maxChunkDays));
        expect(progress, orderedEquals([...progress]..sort()));
        expect(progress.last, 1);
      }
      // الفترات القديمة ما تغيّرت: 8 دفعات
      expect(SimulatedBacktestRepository.chunkCount(365), 8);
      expect(SimulatedBacktestRepository.chunkCount(1825), 40);
    });

    test('a 5-year run stops half way when cancelled', () async {
      final token = BacktestCancelToken();
      final progress = <double>[];
      final run = repo.run(wide(BacktestPeriod.y5), cancel: token, onProgress: (p) {
        progress.add(p);
        if (p >= 0.5) token.cancel();
      });
      await expectLater(run, throwsA(isA<BacktestCancelledException>()));
      expect(progress.last, lessThan(0.6));
    });

    test('a 5-year run with no filters finishes quickly', () async {
      final watch = Stopwatch()..start();
      await repo.run(wide(BacktestPeriod.y5));
      expect(watch.elapsed, lessThan(const Duration(seconds: 3)));
    });

    test('the API window accepts 730, 1095 and 1825 days', () {
      expect([for (final p in longPeriods) p.days], [730, 1095, 1825]);
      for (final p in longPeriods) {
        expect(BacktestPeriod.fromDays(p.days), p);
        expect(saved(p).toJson()['window_days'], p.days);
        expect(p.isMultiYear, isTrue);
      }
      expect(BacktestPeriod.y1.isMultiYear, isFalse);
    });
  });

  group('downsampleEquity', () {
    test('short curves are kept as they are', () {
      final points = zigzag(kMaxChartPoints);
      expect(identical(downsampleEquity(points), points), isTrue);
    });

    for (final n in [kMaxChartPoints + 1, 731, 1826, 5000]) {
      test('$n points: at most $kMaxChartPoints, first, last, min and max kept, in time order', () {
        final points = zigzag(n);
        final kept = downsampleEquity(points);
        expect(kept.length, lessThanOrEqualTo(kMaxChartPoints));
        expect(kept.first, same(points.first));
        expect(kept.last, same(points.last));
        final low = points.reduce((a, b) => b.r < a.r ? b : a);
        final high = points.reduce((a, b) => b.r > a.r ? b : a);
        expect(kept, contains(same(low)));
        expect(kept, contains(same(high)));
        for (var i = 1; i < kept.length; i++) {
          expect(kept[i].time.isAfter(kept[i - 1].time), isTrue);
        }
        for (final p in kept) {
          expect(points, contains(same(p)));
        }
      });
    }

    test('a real 5-year curve: drawn points keep its low, high and end; figures use every point', () async {
      final r = await SimulatedBacktestRepository(source: SimulatedMarketSource(clock: () => kTestNow), step: Duration.zero)
          .run(wide(BacktestPeriod.y5));
      expect(r.equity.length, greaterThan(kMaxChartPoints));
      final kept = downsampleEquity(r.equity);
      expect(kept.length, lessThanOrEqualTo(kMaxChartPoints));
      final values = [for (final p in r.equity) p.r];
      expect(kept.map((p) => p.r).reduce(math.min), values.reduce(math.min));
      expect(kept.map((p) => p.r).reduce(math.max), values.reduce(math.max));
      expect(kept.last.signals, r.signals);
    });
  });

  group('BacktestViewModel with long periods', () {
    test('a 5-year run is cancelled by a period change; only the latest run lands', () async {
      final backtests = _Backtests();
      final c = container((_) => backtests);
      final vm = c.read(backtestViewModelProvider.notifier);
      vm.selectPeriod(BacktestPeriod.y5);
      unawaited(vm.run());
      final first = backtests.calls.single;
      expect(first.request.period, BacktestPeriod.y5);
      expect(first.request.toJson()['window_days'], 1825);

      vm.selectPeriod(BacktestPeriod.y3);
      expect(first.cancel!.isCancelled, isTrue);
      expect(c.read(backtestViewModelProvider).status, isA<BacktestIdle>());

      unawaited(vm.run());
      final second = backtests.calls.last;
      second.completer.complete(fakeResult(BacktestPeriod.y3, signals: 12));
      await pumpEventQueue();
      first.completer.complete(fakeResult(BacktestPeriod.y5, signals: 99));
      await pumpEventQueue();
      final status = c.read(backtestViewModelProvider).status as BacktestDone;
      expect(status.result.period, BacktestPeriod.y3);
      expect(status.result.signals, 12);
    });

    test('a real 5-year run: Run twice runs once; an instrument change mid-run cancels it and stays idle', () async {
      final c = container(
        (ref) => SimulatedBacktestRepository(source: ref.watch(simulatedMarketSourceProvider), step: Duration.zero),
      );
      final vm = c.read(backtestViewModelProvider.notifier);
      vm.selectPeriod(BacktestPeriod.y5);
      final run = vm.run();
      unawaited(vm.run()); // مشغول: بتنتجاهل
      expect(c.read(backtestViewModelProvider).status, isA<BacktestRunning>());
      vm.toggleSymbol('EUR/USD', false);
      await run;
      await pumpEventQueue();
      expect(c.read(backtestViewModelProvider).status, isA<BacktestIdle>());

      await vm.run();
      final done = c.read(backtestViewModelProvider).status as BacktestDone;
      expect(done.result.period, BacktestPeriod.y5);
      expect(done.result.signals, greaterThan(0));
    });
  });

  group('Period chips', () {
    for (final locale in ['en', 'ar']) {
      for (final theme in ['light', 'dark']) {
        testWidgets('six periods, one line each at text scale 2.0; 5 years runs ($locale, $theme)', (tester) async {
          useLargeText(tester);
          usePhoneSize(tester, height: 812);
          await tester.pumpWidget(await testScope(
            const TestApp(home: BacktestScreen()),
            locale: locale,
            prefs: {themeModeStorageKey: theme},
            overrides: [
              backtestRepositoryProvider.overrideWith(
                (ref) => SimulatedBacktestRepository(source: ref.watch(simulatedMarketSourceProvider), step: Duration.zero),
              ),
            ],
          ));
          await tester.pumpAndSettle();
          final en = locale == 'en';
          final labels = en
              ? ['30 days', '90 days', '1 year', '2 years', '3 years', '5 years']
              : ['30 يومًا', '90 يومًا', 'سنة واحدة', 'سنتين', '3 سنوات', '5 سنوات'];
          expect(find.byType(ChoiceChip), findsNWidgets(labels.length));
          for (final label in labels) {
            final text = find.descendant(of: find.byType(ChoiceChip), matching: find.text(label));
            await tester.ensureVisible(text);
            await tester.pumpAndSettle();
            final paragraph = tester.renderObject<RenderParagraph>(text);
            expect(paragraph.didExceedMaxLines, isFalse);
            final boxes = paragraph.getBoxesForSelection(TextSelection(baseOffset: 0, extentOffset: label.length));
            expect({for (final b in boxes) b.top.round()}, hasLength(1), reason: '$label wraps');
            final chip = tester.getRect(find.ancestor(of: text, matching: find.byType(ChoiceChip)));
            expect(chip.height, greaterThanOrEqualTo(48));
            expect(chip.width, lessThanOrEqualTo(375));
          }
          expect(tester.takeException(), isNull);

          final five = find.text(labels.last);
          await tester.tap(five);
          await tester.pumpAndSettle();
          expect(tester.widget<ChoiceChip>(find.ancestor(of: five, matching: find.byType(ChoiceChip))).selected, isTrue);
          final handle = tester.ensureSemantics();
          expect(tester.getSemantics(find.ancestor(of: five, matching: find.byType(ChoiceChip))),
              isSemantics(label: labels.last, isSelected: true, hasTapAction: true));
          handle.dispose();

          final run = find.text(en ? 'Run test' : 'شغّل الاختبار');
          await scrollTo(tester, run);
          await tester.tap(run);
          await tester.pumpAndSettle();
          expect(find.text(en ? 'Results · last 5 years' : 'النتائج · آخر 5 سنوات'), findsOneWidget);
          final done = find.text(en ? 'Simulated · past results are not a promise of future results'
              : 'محاكاة · النتائج السابقة ليست وعدًا بنتائج مستقبلية');
          expect(done, findsOneWidget);
          // المنحنى مقروء: نقاط قليلة بالرسم، والعيّنة الكاملة تحتو
          final chart = tester.widget<SfCartesianChart>(find.byType(SfCartesianChart));
          final series = chart.series.single as LineSeries<EquityPoint, DateTime>;
          expect(series.dataSource!.length, lessThanOrEqualTo(kMaxChartPoints));
          expect(tester.takeException(), isNull);
        });
      }
    }

    testWidgets('long periods: every figure shows its full sample, no profit wording', (tester) async {
      usePhoneSize(tester, height: 2400);
      await tester.pumpWidget(await testScope(
        const TestApp(home: BacktestScreen()),
        overrides: [
          backtestRepositoryProvider.overrideWith(
            (ref) => SimulatedBacktestRepository(source: ref.watch(simulatedMarketSourceProvider), step: Duration.zero),
          ),
        ],
      ));
      await tester.pumpAndSettle();
      await tester.tap(find.text('5 years'));
      await tester.pumpAndSettle();
      await scrollTo(tester, find.text('Run test'));
      await tester.tap(find.text('Run test'));
      await tester.pumpAndSettle();
      final status = ProviderScope.containerOf(tester.element(find.byType(BacktestScreen)))
          .read(backtestViewModelProvider)
          .status as BacktestDone;
      final n = '${status.result.signals}';
      expect(find.textContaining('of $n signals reached the target first'), findsOneWidget);
      expect(find.text('planned, across $n signals'), findsOneWidget);
      expect(find.text('largest drop from a high, across $n signals'), findsOneWidget);
      expect(find.textContaining('from $n signals'), findsOneWidget);
      expect(find.textContaining(RegExp('profit|guarantee(d)? (return|gain)', caseSensitive: false)), findsNothing);
    });
  });
}
