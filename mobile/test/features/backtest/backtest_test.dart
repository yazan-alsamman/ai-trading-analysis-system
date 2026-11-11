// اختبارات Backtest: قراءة شكل الـ API، المحرّك المحاكى (حتمي ومتّسق مع
// Insights)، الـ ViewModel (تشغيل، Run مرتين، إلغاء وسباق، خطأ، بدون اتصال)
// والشاشة (EN/AR، فاتح/غامق، خط كبير، الحالات، فتحها من Strategy).

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:syncfusion_flutter_charts/charts.dart';

import 'package:trading_app/core/data/json.dart';
import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/core/widgets/direction_badge.dart';
import 'package:trading_app/features/backtest/data/backtest_dto.dart';
import 'package:trading_app/features/backtest/data/backtest_engine.dart';
import 'package:trading_app/features/backtest/data/backtest_repository.dart';
import 'package:trading_app/features/backtest/models/backtest.dart';
import 'package:trading_app/features/backtest/view_models/backtest_view_model.dart';
import 'package:trading_app/features/backtest/views/backtest_screen.dart';
import 'package:trading_app/features/insights/data/insights_repository.dart';
import 'package:trading_app/features/insights/models/track_record.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/markets/data/simulated_market_source.dart';
import 'package:trading_app/features/markets/models/market_models.dart';
import 'package:trading_app/features/signals/data/signal_profile_repository.dart';
import 'package:trading_app/features/signals/data/simulated_outcomes.dart';
import 'package:trading_app/features/signals/models/analysis_method.dart';
import 'package:trading_app/features/signals/models/signal_profile.dart';
import 'package:trading_app/features/signals/views/signals_screen.dart';

import '../../helpers/test_app.dart';

Map<String, Object?> payload({int days = 90, int signals = 40, int hits = 22}) => {
      'window_days': days,
      'signals': signals,
      'hits': hits,
      'avg_risk_reward': signals == 0 ? null : 1.94,
      'max_drawdown_r': signals == 0 ? 0 : 3.5,
      'equity': [
        if (signals > 0) ...[
          {'time': 2 * Duration.millisecondsPerDay, 'r': 4.5, 'signals': signals},
          {'time': 0, 'r': 0, 'signals': 0},
          {'time': Duration.millisecondsPerDay, 'r': -1, 'signals': 1},
        ],
      ],
    };

BacktestResult result(BacktestPeriod period, {int signals = 40, int hits = 22}) =>
    backtestResultFromJson(Json(payload(days: period.days, signals: signals, hits: hits)))!;

/// كل الأدوات والأطر والاتجاهات وبدون حدود = نفس خلايا Insights
BacktestRequest wide(BacktestPeriod period) => BacktestRequest(
      symbols: kProductSymbols.toSet(),
      timeframes: Timeframe.modelTimeframes.toSet(),
      directions: const {SignalDirection.long, SignalDirection.short},
      minProbability: 0,
      minRiskReward: 0,
      period: period,
    );

typedef _Call = ({
  BacktestRequest request,
  BacktestCancelToken? cancel,
  void Function(double)? onProgress,
  Completer<BacktestResult> completer,
});

/// مصدر نتحكّم فيه: كل تشغيل بيستنى لحد ما نكمّله نحن
final class _Backtests implements BacktestRepository {
  final calls = <_Call>[];

  @override
  bool get isSimulated => true;

  @override
  Future<BacktestResult> run(
    BacktestRequest request, {
    BacktestCancelToken? cancel,
    void Function(double progress)? onProgress,
  }) {
    final completer = Completer<BacktestResult>();
    calls.add((request: request, cancel: cancel, onProgress: onProgress, completer: completer));
    return completer.future;
  }
}

/// مصدر بيرجّع فورًا: [answer] أو خطأ
final class _Fixed implements BacktestRepository {
  _Fixed(this.answer);

  BacktestResult? Function(BacktestRequest) answer;

  @override
  bool get isSimulated => true;

  @override
  Future<BacktestResult> run(
    BacktestRequest request, {
    BacktestCancelToken? cancel,
    void Function(double progress)? onProgress,
  }) async =>
      answer(request) ?? (throw StateError('down'));
}

(ProviderContainer, _Backtests) setUpContainer() {
  final backtests = _Backtests();
  final container = ProviderContainer(overrides: [
    connectivityOverride(),
    ...simulatedMarketOverrides(),
    signalProfileRepositoryProvider.overrideWithValue(_Profile()),
    backtestRepositoryProvider.overrideWithValue(backtests),
  ]);
  addTearDown(container.dispose);
  return (container, backtests);
}

/// الاستراتيجية المحفوظة = الافتراضية (بدون تخزين)
final class _Profile implements SignalProfileRepository {
  @override
  SignalProfile read() => SignalProfile.defaults;

  @override
  Future<void> save(SignalProfile profile) async {}

  @override
  Future<void> clear() async {}
}

/// المحاكى بدون استراحة بين الدفعات
Override instantBacktests() => backtestRepositoryProvider.overrideWith(
      (ref) => SimulatedBacktestRepository(source: ref.watch(simulatedMarketSourceProvider), step: Duration.zero),
    );

Future<void> pumpBacktest(
  WidgetTester tester, {
  String locale = 'en',
  Map<String, Object> prefs = const {},
  List<Override>? overrides,
  double height = 2400,
}) async {
  usePhoneSize(tester, height: height);
  await tester.pumpWidget(await testScope(
    const TestApp(home: BacktestScreen()),
    locale: locale,
    prefs: prefs,
    overrides: overrides ?? [instantBacktests()],
  ));
  await tester.pumpAndSettle();
}

Future<void> tapRun(WidgetTester tester, {String label = 'Run test'}) async {
  await scrollTo(tester, find.text(label));
  await tester.tap(find.text(label));
  await tester.pumpAndSettle();
}

void main() {
  group('backtestResultFromJson', () {
    test('parses the figures and the curve oldest first', () {
      final r = backtestResultFromJson(Json(payload()))!;
      expect(r.period, BacktestPeriod.d90);
      expect(r.signals, 40);
      expect(r.hits, 22);
      expect(r.accuracy.hitRate, 22 / 40);
      expect(r.avgRiskReward, 1.94);
      expect(r.maxDrawdown, 3.5);
      expect(r.equity.map((p) => p.r), [0, -1, 4.5]);
      expect(r.equity.last.signals, 40);
      expect(r.isEmpty, isFalse);
    });

    test('no matching signals: empty result, no average', () {
      final r = backtestResultFromJson(Json(payload(signals: 0, hits: 0)))!;
      expect(r.isEmpty, isTrue);
      expect(r.avgRiskReward, isNull);
      expect(r.maxDrawdown, 0);
      expect(r.equity, isEmpty);
    });

    test('invalid totals or an unknown window → null', () {
      expect(backtestResultFromJson(Json(payload(signals: 10, hits: 11))), isNull);
      expect(backtestResultFromJson(Json(payload(days: 7))), isNull);
      expect(backtestResultFromJson(Json({...payload(), 'max_drawdown_r': -1})), isNull);
      expect(backtestResultFromJson(Json({...payload(), 'avg_risk_reward': null})), isNull);
      expect(backtestResultFromJson(Json({...payload(), 'max_drawdown_r': null})), isNull);
      expect(backtestResultFromJson(const Json({'signals': 1, 'hits': 1})), isNull);
    });

    test('bad curve points are dropped, duplicate times count once', () {
      final r = backtestResultFromJson(Json({
        ...payload(),
        'equity': [
          {'time': 0, 'r': 0, 'signals': 0},
          {'time': 0, 'r': 9, 'signals': 3},
          {'r': 1, 'signals': 1},
          {'time': 5, 'signals': 1},
          {'time': 6, 'r': 1, 'signals': 99}, // أكتر من مجموع الإشارات
          'oops',
        ],
      }))!;
      expect(r.equity.single.r, 0);
    });

    test('the request body lists symbols and timeframes in product order', () {
      final body = BacktestRequest.from(
        SignalProfile.defaults,
        symbols: const {'USD/JPY', 'EUR/USD'},
        period: BacktestPeriod.y1,
      ).toJson();
      expect(body['symbols'], ['EUR/USD', 'USD/JPY']);
      expect(body['timeframes'], ['15m', '1h', '4h']);
      expect(body['directions'], ['long', 'short']);
      expect(body['min_probability'], 0.6);
      expect(body['min_risk_reward'], 1.5);
      expect(body['window_days'], 365);
    });
  });

  group('SimulatedBacktestRepository', () {
    final source = SimulatedMarketSource(clock: () => kTestNow);
    final repo = SimulatedBacktestRepository(source: source, step: Duration.zero);
    final saved = BacktestRequest.from(
      SignalProfile.defaults,
      symbols: SignalProfile.defaults.symbols,
      period: BacktestPeriod.d90,
    );

    test('deterministic: the same request gives the same result, all day long', () async {
      final a = await repo.run(saved);
      final b = await repo.run(saved);
      final later = await SimulatedBacktestRepository(
        source: SimulatedMarketSource(clock: () => kTestNow.add(const Duration(hours: 9))),
        step: Duration.zero,
      ).run(saved);
      for (final other in [b, later]) {
        expect(other.signals, a.signals);
        expect(other.hits, a.hits);
        expect(other.avgRiskReward, a.avgRiskReward);
        expect(other.maxDrawdown, a.maxDrawdown);
        expect(other.equity.map((p) => (p.time, p.r, p.signals)), a.equity.map((p) => (p.time, p.r, p.signals)));
      }
      expect(a.signals, greaterThan(kMinTrackSample));
    });

    for (final (period, insights) in [(BacktestPeriod.d30, InsightsPeriod.d30), (BacktestPeriod.d90, InsightsPeriod.d90)]) {
      // A3c: الـ Backtest دايمًا بطريقة فنية، فما عاد "= Insights" (سجل النموذج).
      // القاعدة الجديدة: حتمي ونفس النتيجة بكل مكان لنفس الاستراتيجية والفترة.
      test('no filters, ${period.days} days = the method own cells; deterministic across runs and repositories',
          () async {
        final request = wide(period);
        expect(request.methodId, AnalysisMethod.defaultId);
        final backtest = await repo.run(request);
        final outcomes = SimulatedOutcomes(source);
        final last = outcomes.lastFullDay;
        final cells = outcomes.total(last - period.days + 1, last, methodId: request.methodId);
        expect(backtest.signals, cells.resolved);
        expect(backtest.hits, cells.hits);
        // تاني مرة، ومصدر جديد = نفس الأرقام والمنحنى
        final again = await repo.run(request);
        final fresh = await SimulatedBacktestRepository(source: source, step: Duration.zero).run(request);
        for (final other in [again, fresh]) {
          expect(other.signals, backtest.signals);
          expect(other.hits, backtest.hits);
          expect(other.maxDrawdown, backtest.maxDrawdown);
          expect(other.equity.map((p) => p.r), backtest.equity.map((p) => p.r));
        }
        // Insights (سجل النموذج) لهالفترة موجود ومستقل عن الطريقة
        final record = await SimulatedInsightsRepository(source: source).trackRecord(insights);
        expect(record.overall.resolved, outcomes.total(last - period.days + 1, last).resolved);
      });
    }

    test('every counted signal matches the strategy; filters only narrow', () async {
      final outcomes = SimulatedOutcomes(source);
      final engine = SimulatedBacktestEngine(outcomes);
      final last = outcomes.lastFullDay;
      final found = engine.signals(saved, last - 89, last);
      expect(found, isNotEmpty);
      for (final s in found) {
        expect(saved.symbols, contains(s.symbol));
        expect(s.probability, greaterThanOrEqualTo(0.6));
        expect(s.riskReward, greaterThanOrEqualTo(1.5));
        expect(s.direction, isNot(SignalDirection.neutral));
      }
      final all = await repo.run(wide(BacktestPeriod.d90));
      final mine = await repo.run(saved);
      expect(mine.signals, found.length);
      expect(mine.signals, lessThan(all.signals));
      final year = await repo.run(wide(BacktestPeriod.y1));
      expect(year.signals, greaterThan(all.signals));
    });

    test('the curve starts at 0 on the first day and ends at the sum of results', () async {
      final r = await repo.run(saved);
      final last = SimulatedOutcomes(source).lastFullDay;
      expect(r.equity.first.r, 0);
      expect(r.equity.first.time, DateTime.fromMillisecondsSinceEpoch((last - 89) * Duration.millisecondsPerDay, isUtc: true));
      expect(r.equity.last.signals, r.signals);
      final misses = r.signals - r.hits;
      // مجموع R = مجموع عوائد الإصابات − عدد الوقفات
      expect(r.equity.last.r, greaterThan(r.hits * 1.5 - misses - 0.01));
      expect(r.equity.last.r, lessThan(r.hits * 2.5 - misses + 0.01));
      var peak = 0.0;
      for (final p in r.equity) {
        if (p.r > peak) peak = p.r;
        expect(peak - p.r, lessThanOrEqualTo(r.maxDrawdown + 0.01));
      }
      expect(r.avgRiskReward, inInclusiveRange(1.5, 2.5));
    });

    test('progress climbs to 1; a cancelled run gives no result', () async {
      final progress = <double>[];
      await repo.run(saved, onProgress: progress.add);
      expect(progress, hasLength(SimulatedBacktestRepository.chunks));
      expect(progress, orderedEquals([...progress]..sort()));
      expect(progress.last, 1);

      final token = BacktestCancelToken();
      final run = repo.run(saved, cancel: token, onProgress: (_) => token.cancel());
      await expectLater(run, throwsA(isA<BacktestCancelledException>()));
    });

    test('an invalid request is refused', () {
      expect(
        repo.run(BacktestRequest.from(SignalProfile.defaults, symbols: const {}, period: BacktestPeriod.d30)),
        throwsArgumentError,
      );
    });
  });

  group('BacktestViewModel', () {
    test('starts idle on the saved strategy (its instruments, 90 days)', () {
      final (c, backtests) = setUpContainer();
      final state = c.read(backtestViewModelProvider);
      expect(state.symbols, SignalProfile.defaults.symbols);
      expect(state.period, BacktestPeriod.d90);
      expect(state.status, isA<BacktestIdle>());
      expect(backtests.calls, isEmpty);
    });

    test('Run: running with progress, then the result', () async {
      final (c, backtests) = setUpContainer();
      c.listen(backtestViewModelProvider, (_, __) {});
      final vm = c.read(backtestViewModelProvider.notifier);
      unawaited(vm.run());
      expect(c.read(backtestViewModelProvider).status, isA<BacktestRunning>());
      final call = backtests.calls.single;
      expect(call.request.symbols, SignalProfile.defaults.symbols);
      expect(call.request.minProbability, 0.6);
      call.onProgress!(0.5);
      expect((c.read(backtestViewModelProvider).status as BacktestRunning).progress, 0.5);
      call.completer.complete(result(BacktestPeriod.d90));
      await pumpEventQueue();
      final status = c.read(backtestViewModelProvider).status;
      expect(status, isA<BacktestDone>());
      expect((status as BacktestDone).result.signals, 40);
    });

    test('Run twice starts one run', () async {
      final (c, backtests) = setUpContainer();
      c.listen(backtestViewModelProvider, (_, __) {});
      final vm = c.read(backtestViewModelProvider.notifier);
      unawaited(vm.run());
      unawaited(vm.run());
      await pumpEventQueue();
      expect(backtests.calls, hasLength(1));
      expect(c.read(backtestViewModelProvider).canRun, isFalse);
    });

    test('changing the period while running cancels it; only the latest run lands', () async {
      final (c, backtests) = setUpContainer();
      c.listen(backtestViewModelProvider, (_, __) {});
      final vm = c.read(backtestViewModelProvider.notifier);
      unawaited(vm.run());
      final first = backtests.calls.single;

      vm.selectPeriod(BacktestPeriod.d30);
      expect(first.cancel!.isCancelled, isTrue);
      expect(c.read(backtestViewModelProvider).status, isA<BacktestIdle>());

      unawaited(vm.run());
      final second = backtests.calls.last;
      expect(second.request.period, BacktestPeriod.d30);

      // القديم بيتأخر: تقدّمه ونتيجته (أو فشله) ما بيوصلوا للشاشة
      first.onProgress!(0.9);
      expect((c.read(backtestViewModelProvider).status as BacktestRunning).progress, 0);
      second.completer.complete(result(BacktestPeriod.d30, signals: 12, hits: 7));
      await pumpEventQueue();
      first.completer.complete(result(BacktestPeriod.d90, signals: 99, hits: 50));
      await pumpEventQueue();
      final status = c.read(backtestViewModelProvider).status as BacktestDone;
      expect(status.result.period, BacktestPeriod.d30);
      expect(status.result.signals, 12);
    });

    test('a late failure of a cancelled run is ignored', () async {
      final (c, backtests) = setUpContainer();
      c.listen(backtestViewModelProvider, (_, __) {});
      final vm = c.read(backtestViewModelProvider.notifier);
      unawaited(vm.run());
      vm.toggleSymbol('EUR/USD', false);
      expect(backtests.calls.single.cancel!.isCancelled, isTrue);
      expect(c.read(backtestViewModelProvider).symbols, isNot(contains('EUR/USD')));
      backtests.calls.single.completer.completeError(StateError('late'));
      await pumpEventQueue();
      expect(c.read(backtestViewModelProvider).status, isA<BacktestIdle>());
    });

    test('a new setting after a result goes back to idle (no stale figures)', () async {
      final (c, backtests) = setUpContainer();
      c.listen(backtestViewModelProvider, (_, __) {});
      final vm = c.read(backtestViewModelProvider.notifier);
      unawaited(vm.run());
      backtests.calls.single.completer.complete(result(BacktestPeriod.d90));
      await pumpEventQueue();
      vm.toggleSymbol('NZD/USD', true);
      expect(c.read(backtestViewModelProvider).status, isA<BacktestIdle>());
      vm.selectPeriod(BacktestPeriod.d90); // نفس الفترة: ولا شي
      expect(backtests.calls, hasLength(1));
    });

    test('no instrument: Run does nothing', () async {
      final (c, backtests) = setUpContainer();
      c.listen(backtestViewModelProvider, (_, __) {});
      final vm = c.read(backtestViewModelProvider.notifier);
      for (final s in SignalProfile.defaults.symbols) {
        vm.toggleSymbol(s, false);
      }
      expect(c.read(backtestViewModelProvider).canRun, isFalse);
      await vm.run();
      expect(backtests.calls, isEmpty);
    });

    test('an answer for another period is an error', () async {
      final (c, backtests) = setUpContainer();
      c.listen(backtestViewModelProvider, (_, __) {});
      unawaited(c.read(backtestViewModelProvider.notifier).run());
      backtests.calls.single.completer.complete(result(BacktestPeriod.y1));
      await pumpEventQueue();
      expect(c.read(backtestViewModelProvider).status, isA<BacktestFailed>());
    });

    test('error, then Try again runs again', () async {
      final (c, backtests) = setUpContainer();
      c.listen(backtestViewModelProvider, (_, __) {});
      final vm = c.read(backtestViewModelProvider.notifier);
      unawaited(vm.run());
      backtests.calls.single.completer.completeError(StateError('down'));
      await pumpEventQueue();
      final failed = c.read(backtestViewModelProvider).status as BacktestFailed;
      expect(failed.offline, isFalse);

      unawaited(vm.run());
      backtests.calls.last.completer.complete(result(BacktestPeriod.d90));
      await pumpEventQueue();
      expect(c.read(backtestViewModelProvider).status, isA<BacktestDone>());
    });

    test('offline: nothing sent, runs by itself when back online', () async {
      final (c, backtests) = setUpContainer();
      c.listen(backtestViewModelProvider, (_, __) {});
      c.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      await c.read(backtestViewModelProvider.notifier).run();
      expect((c.read(backtestViewModelProvider).status as BacktestFailed).offline, isTrue);
      expect(backtests.calls, isEmpty);

      c.read(networkStatusProvider.notifier).set(NetworkStatus.online);
      await pumpEventQueue();
      expect(backtests.calls, hasLength(1));
      backtests.calls.single.completer.complete(result(BacktestPeriod.d90));
      await pumpEventQueue();
      expect(c.read(backtestViewModelProvider).status, isA<BacktestDone>());
    });

    test('screen closed while running: the run is cancelled, the late answer dropped', () async {
      final (c, backtests) = setUpContainer();
      final sub = c.listen(backtestViewModelProvider, (_, __) {});
      unawaited(c.read(backtestViewModelProvider.notifier).run());
      sub.close();
      await pumpEventQueue();
      expect(backtests.calls.single.cancel!.isCancelled, isTrue);
      backtests.calls.single.completer.complete(result(BacktestPeriod.d90));
      await pumpEventQueue();
      // instance جديد بيبلّش من الأول
      c.listen(backtestViewModelProvider, (_, __) {});
      expect(c.read(backtestViewModelProvider).status, isA<BacktestIdle>());
    });
  });

  group('BacktestScreen', () {
    for (final mode in ['light', 'dark']) {
      for (final locale in ['en', 'ar']) {
        testWidgets('settings, Run, figures and curve ($mode, $locale)', (tester) async {
          await pumpBacktest(tester, locale: locale, prefs: {themeModeStorageKey: mode});
          final en = locale == 'en';
          expect(find.text(en ? 'Backtest' : 'اختبار تاريخي'), findsOneWidget);
          final disclaimer = en
              ? 'Simulated · past results are not a promise of future results'
              : 'محاكاة · النتائج السابقة ليست وعدًا بنتائج مستقبلية';
          expect(find.text(disclaimer), findsOneWidget);
          expect(find.byType(FilterChip), findsNWidgets(kProductSymbols.length));
          expect(find.byType(SfCartesianChart), findsNothing);

          await tapRun(tester, label: en ? 'Run test' : 'شغّل الاختبار');
          expect(find.byType(SfCartesianChart), findsOneWidget);
          expect(find.text(en ? 'Results · last 90 days' : 'النتائج · آخر 90 يومًا'), findsOneWidget);
          expect(find.text(en ? 'Max drawdown' : 'أقصى تراجع'), findsOneWidget);
          expect(find.text(disclaimer), findsOneWidget); // بكل الحالات
          expect(tester.takeException(), isNull);
        });
      }
    }

    testWidgets('every figure carries its sample size; no profit wording', (tester) async {
      await pumpBacktest(tester, overrides: [backtestRepositoryProvider.overrideWithValue(_Fixed((r) => result(r.period)))]);
      await tapRun(tester);
      expect(find.text('40'), findsOneWidget);
      expect(find.text('55%'), findsOneWidget);
      expect(find.text('22 of 40 signals reached the target first'), findsOneWidget);
      expect(find.text('1 : 1.9'), findsOneWidget);
      expect(find.text('planned, across 40 signals'), findsOneWidget);
      expect(find.text('−3.5 R'), findsOneWidget);
      expect(find.text('largest drop from a high, across 40 signals'), findsOneWidget);
      expect(find.textContaining('from 40 signals'), findsOneWidget); // تحت المنحنى
      expect(find.bySemanticsLabel('Hit rate: 55%, 22 of 40 signals reached the target first.'), findsOneWidget);
      expect(find.textContaining(RegExp('profit|guarantee(d)? (return|gain)', caseSensitive: false)), findsNothing);
    });

    testWidgets('small samples are marked', (tester) async {
      await pumpBacktest(tester, overrides: [
        backtestRepositoryProvider.overrideWithValue(_Fixed((r) => result(r.period, signals: 4, hits: 3))),
      ]);
      await tapRun(tester);
      expect(find.textContaining('· Small sample'), findsNWidgets(4));
    });

    testWidgets('running: progress, Run is busy; a period change cancels and goes idle', (tester) async {
      final backtests = _Backtests();
      await pumpBacktest(tester, overrides: [backtestRepositoryProvider.overrideWithValue(backtests)]);
      await tester.tap(find.text('Run test'));
      await tester.pump();
      expect(find.text('Testing on past data…'), findsOneWidget);
      expect(find.byType(LinearProgressIndicator), findsOneWidget);
      backtests.calls.single.onProgress!(0.5);
      await tester.pump();
      expect(find.text('50%'), findsOneWidget);
      // الزر مشغول: ضغطة تانية ما بتشغّل تاني
      await tester.tap(find.byType(FilledButton), warnIfMissed: false);
      await tester.pump();
      expect(backtests.calls, hasLength(1));

      await tester.tap(find.widgetWithText(ChoiceChip, '1 year'));
      await tester.pump();
      expect(backtests.calls.single.cancel!.isCancelled, isTrue);
      expect(find.text('Choose instruments and a period, then run the test.'), findsOneWidget);
      backtests.calls.single.completer.complete(result(BacktestPeriod.d90));
      await tester.pumpAndSettle();
      expect(find.byType(SfCartesianChart), findsNothing);
    });

    testWidgets('no instrument: message, Run is off', (tester) async {
      await pumpBacktest(tester);
      for (final s in SignalProfile.defaults.symbols) {
        await tester.tap(find.widgetWithText(FilterChip, s));
      }
      await tester.pumpAndSettle();
      expect(find.text('Pick at least one instrument.'), findsOneWidget);
      expect(tester.widget<FilledButton>(find.byType(FilledButton)).onPressed, isNull);
    });

    testWidgets('empty: explains, Try 1 year runs the year', (tester) async {
      await pumpBacktest(tester, overrides: [
        backtestRepositoryProvider.overrideWithValue(
          _Fixed((r) => r.period == BacktestPeriod.y1 ? result(r.period) : result(r.period, signals: 0, hits: 0)),
        ),
      ]);
      await tapRun(tester);
      expect(find.text('No past signals matched your strategy'), findsOneWidget);
      expect(find.text('Hit rate'), findsNothing); // ما في نسبة مخترعة
      await tester.tap(find.text('Try 1 year'));
      await tester.pumpAndSettle();
      expect(find.text('Results · last 1 year'), findsOneWidget);
    });

    testWidgets('error with Try again', (tester) async {
      final repo = _Fixed((_) => null);
      await pumpBacktest(tester, overrides: [backtestRepositoryProvider.overrideWithValue(repo)]);
      await tapRun(tester);
      expect(find.text('The test could not be run.'), findsOneWidget);
      repo.answer = (r) => result(r.period);
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Results · last 90 days'), findsOneWidget);
    });

    testWidgets('offline: offline state, runs when back online', (tester) async {
      await pumpBacktest(tester);
      final container = ProviderScope.containerOf(tester.element(find.byType(BacktestScreen)));
      container.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      await tapRun(tester);
      expect(find.text('You’re offline'), findsOneWidget);
      expect(find.text('The test will run when you’re back online.'), findsOneWidget);
      container.read(networkStatusProvider.notifier).set(NetworkStatus.online);
      await tester.pumpAndSettle();
      await tester.pump(const Duration(seconds: 1));
      expect(find.text('Results · last 90 days'), findsOneWidget);
    });

    for (final locale in ['en', 'ar']) {
      testWidgets('largest font, phone height ($locale): no overflow, labels whole', (tester) async {
        useLargeText(tester);
        await pumpBacktest(tester, locale: locale, height: 812);
        expect(tester.takeException(), isNull);
        // ولا تسمية زر أو شريحة بتنقص بـ "…"
        final labels = find.descendant(
          of: find.byWidgetPredicate((w) => w is ButtonStyleButton || w is FilterChip || w is ChoiceChip),
          matching: find.byType(Text),
        );
        expect(labels, findsWidgets);
        for (final text in tester.widgetList<Text>(labels)) {
          expect(text.overflow, isNot(TextOverflow.ellipsis));
        }
        await tapRun(tester, label: locale == 'en' ? 'Run test' : 'شغّل الاختبار');
        expect(tester.takeException(), isNull);
        await scrollTo(tester, find.text(locale == 'en' ? 'How to read this' : 'كيف تقرأ هذه الأرقام'));
        expect(tester.takeException(), isNull);
      });
    }

    testWidgets('reduced motion: the curve draws without animation', (tester) async {
      tester.platformDispatcher.accessibilityFeaturesTestValue = const FakeAccessibilityFeatures(disableAnimations: true);
      addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
      await pumpBacktest(tester);
      await tapRun(tester);
      final chart = tester.widget<SfCartesianChart>(find.byType(SfCartesianChart));
      expect(chart.series.single.animationDuration, 0);
    });

    testWidgets('meets the tap target guideline', (tester) async {
      final handle = tester.ensureSemantics();
      await pumpBacktest(tester);
      await tapRun(tester);
      await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
      handle.dispose();
    });
  });

  group('Strategy → Backtest', () {
    testWidgets('opens once on a double tap, pre-filled with the saved strategy; back returns to the sheet',
        (tester) async {
      usePhoneSize(tester, height: 1600);
      await tester.pumpWidget(await testScope(const TestApp(home: SignalsScreen()), overrides: [instantBacktests()]));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Strategy'));
      await tester.pumpAndSettle();
      final open = find.text('Test on past data');
      await tester.ensureVisible(open);
      await tester.pumpAndSettle();
      expect(tester.getSize(find.ancestor(of: open, matching: find.byType(OutlinedButton))).height,
          greaterThanOrEqualTo(48));
      await tester.tap(open);
      await tester.tap(open, warnIfMissed: false);
      await tester.pumpAndSettle();
      expect(find.byType(BacktestScreen), findsOneWidget);
      final selected = [
        for (final chip in tester.widgetList<FilterChip>(find.byType(FilterChip)))
          if (chip.selected) ((chip.label as Text).data),
      ];
      expect(selected.toSet(), SignalProfile.defaults.symbols);
      expect(find.text('Filters: 15m, 1h, 4h · Long, Short · probability ≥ 60% · reward : risk ≥ 1 : 1.5'),
          findsOneWidget);

      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.byType(BacktestScreen), findsNothing);
      expect(find.text('Test on past data'), findsOneWidget);
    });
  });
}
