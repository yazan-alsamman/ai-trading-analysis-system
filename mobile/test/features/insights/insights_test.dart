// اختبارات Insights: قراءة شكل الـ API، المصدر المحاكى (متّسق مع سطر الدقة)،
// الـ ViewModel (تحميل، خطأ، بدون اتصال، تبديل الفترة بسرعة) والشاشة
// (EN/AR، فاتح/غامق، خط كبير، الحالات، فتحها من سطر الدقة).

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:syncfusion_flutter_charts/charts.dart';

import 'package:trading_app/core/data/json.dart';
import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/features/insights/data/insights_repository.dart';
import 'package:trading_app/features/insights/data/track_record_dto.dart';
import 'package:trading_app/features/insights/models/track_record.dart';
import 'package:trading_app/features/insights/view_models/insights_view_model.dart';
import 'package:trading_app/features/insights/views/insights_screen.dart';
import 'package:trading_app/features/insights/widgets/accuracy_breakdown.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/markets/data/simulated_market_source.dart';
import 'package:trading_app/features/markets/models/market_models.dart';
import 'package:trading_app/features/signals/data/signals_repository.dart';
import 'package:trading_app/features/signals/models/model_accuracy.dart';
import 'package:trading_app/features/signals/views/signals_screen.dart';
import 'package:trading_app/features/signals/widgets/accuracy_line.dart';

import '../../helpers/test_app.dart';

Map<String, Object?> payload({int days = 30, int resolved = 40, int hits = 22}) => {
      'window_days': days,
      'resolved': resolved,
      'hits': hits,
      'by_symbol': [
        {'symbol': 'XAU/USD', 'resolved': 12, 'hits': 7},
        {'symbol': 'eur/usd', 'resolved': 28, 'hits': 15},
      ],
      'by_timeframe': [
        {'timeframe': '4h', 'resolved': 10, 'hits': 6},
        {'timeframe': '15m', 'resolved': 30, 'hits': 16},
      ],
      'series': [
        {'start': 2 * Duration.millisecondsPerDay, 'days': 3, 'resolved': 4, 'hits': 2},
        {'start': 0, 'days': 3, 'resolved': 0, 'hits': 0},
      ],
    };

TrackRecord record(InsightsPeriod period, {int resolved = 40, int hits = 22}) =>
    trackRecordFromJson(Json(payload(days: period.days, resolved: resolved, hits: hits)))!;

/// مصدر نتحكّم فيه: كل طلب بيستنى لحد ما نكمّله نحن
final class _Insights implements InsightsRepository {
  final calls = <(InsightsPeriod, Completer<TrackRecord>)>[];

  @override
  bool get isSimulated => true;

  @override
  Future<TrackRecord> trackRecord(InsightsPeriod period) {
    final completer = Completer<TrackRecord>();
    calls.add((period, completer));
    return completer.future;
  }
}

/// مصدر بيرجّع فورًا: [result] أو خطأ
final class _Fixed implements InsightsRepository {
  _Fixed(this.result);

  TrackRecord? Function(InsightsPeriod) result;

  @override
  bool get isSimulated => true;

  @override
  Future<TrackRecord> trackRecord(InsightsPeriod period) async => result(period) ?? (throw StateError('down'));
}

/// سطر الدقة (للفترة الأولى): [windowDays]
final class _Accuracy implements SignalsRepository {
  _Accuracy(this.windowDays);

  final int windowDays;

  @override
  bool get isSimulated => true;

  @override
  Future<ModelAccuracy> accuracy() async => ModelAccuracy(resolved: 50, hits: 30, windowDays: windowDays);

  @override
  noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

(ProviderContainer, _Insights) setUpContainer({List<Override> overrides = const []}) {
  final insights = _Insights();
  final container = ProviderContainer(overrides: [
    connectivityOverride(),
    ...simulatedMarketOverrides(),
    insightsRepositoryProvider.overrideWithValue(insights),
    ...overrides,
  ]);
  addTearDown(container.dispose);
  return (container, insights);
}

Future<void> pumpInsights(
  WidgetTester tester, {
  String locale = 'en',
  Map<String, Object> prefs = const {},
  List<Override> overrides = const [],
  double height = 2400,
}) async {
  usePhoneSize(tester, height: height);
  await tester.pumpWidget(await testScope(
    const TestApp(home: InsightsScreen()),
    locale: locale,
    prefs: prefs,
    overrides: overrides,
  ));
  await tester.pumpAndSettle();
}

void main() {
  group('trackRecordFromJson', () {
    test('parses totals, rows in product / timeframe order and the series oldest first', () {
      final r = trackRecordFromJson(Json(payload()))!;
      expect(r.period, InsightsPeriod.d30);
      expect(r.overall.resolved, 40);
      expect(r.overall.hits, 22);
      expect(r.byInstrument.map((e) => e.symbol), ['EUR/USD', 'XAU/USD']);
      expect(r.byInstrument.first.accuracy.hitRate, 15 / 28);
      expect(r.byTimeframe.map((e) => e.timeframe), [Timeframe.m15, Timeframe.h4]);
      expect(r.series.map((p) => p.start.millisecondsSinceEpoch), [0, 2 * Duration.millisecondsPerDay]);
      expect(r.series.first.accuracy.hitRate, isNull); // ما في نتائج → ما في 0%
      expect(r.series.last.end, DateTime.utc(1970, 1, 5));
      expect(r.isEmpty, isFalse);
    });

    test('invalid totals or an unknown window → null', () {
      expect(trackRecordFromJson(Json(payload(resolved: 10, hits: 11))), isNull);
      expect(trackRecordFromJson(Json(payload(days: 14))), isNull);
      expect(trackRecordFromJson(const Json({'resolved': 1, 'hits': 1})), isNull);
      expect(trackRecordFromJson(Json(payload(resolved: -1, hits: 0))), isNull);
    });

    test('bad rows are dropped, duplicates count once', () {
      final r = trackRecordFromJson(Json({
        ...payload(),
        'by_symbol': [
          {'symbol': 'BTC/USD', 'resolved': 5, 'hits': 2}, // مش من المنتج
          {'symbol': 'GBP/USD', 'resolved': 3, 'hits': 4}, // hits > resolved
          {'symbol': 'USD/JPY', 'resolved': 6, 'hits': 3},
          {'symbol': 'USD/JPY', 'resolved': 9, 'hits': 9},
          'oops',
        ],
        'by_timeframe': [
          {'timeframe': '1d', 'resolved': 5, 'hits': 2}, // مش إطار للنموذج
          {'timeframe': 'x', 'resolved': 5, 'hits': 2},
          {'timeframe': '1h', 'resolved': 5, 'hits': 2},
        ],
        'series': [
          {'start': 0, 'days': 0, 'resolved': 1, 'hits': 1},
          {'days': 1, 'resolved': 1, 'hits': 1},
        ],
      }))!;
      expect(r.byInstrument.single.symbol, 'USD/JPY');
      expect(r.byInstrument.single.accuracy.resolved, 6);
      expect(r.byTimeframe.single.timeframe, Timeframe.h1);
      expect(r.series, isEmpty);
    });

    test('small sample: fewer than $kMinTrackSample signals', () {
      expect(const ModelAccuracy(resolved: 9, hits: 5, windowDays: 7).isSmallSample, isTrue);
      expect(const ModelAccuracy(resolved: 10, hits: 5, windowDays: 7).isSmallSample, isFalse);
    });
  });

  group('SimulatedInsightsRepository', () {
    final source = SimulatedMarketSource(clock: () => kTestNow);
    final repo = SimulatedInsightsRepository(source: source);

    for (final period in InsightsPeriod.values) {
      test('${period.days} days: every breakdown adds up to the total', () async {
        final r = await repo.trackRecord(period);
        expect(r.period, period);
        expect(r.byInstrument.map((e) => e.symbol), kProductSymbols);
        expect(r.byTimeframe.map((e) => e.timeframe), Timeframe.modelTimeframes);
        expect(r.series, hasLength(period.days ~/ SimulatedInsightsRepository.bucketDays(period)));
        int sum(Iterable<ModelAccuracy> xs, int Function(ModelAccuracy) f) => xs.fold(0, (a, x) => a + f(x));
        for (final parts in [
          r.byInstrument.map((e) => e.accuracy),
          r.byTimeframe.map((e) => e.accuracy),
          r.series.map((p) => p.accuracy),
        ]) {
          expect(sum(parts, (a) => a.resolved), r.overall.resolved);
          expect(sum(parts, (a) => a.hits), r.overall.hits);
        }
        // آخر نقطة بتخلص مبارح (أيام مكتملة بس)
        expect(r.series.last.end, DateTime.utc(2026, 10, 20));
      });
    }

    test('longer windows hold more signals; same day = same numbers', () async {
      final week = await repo.trackRecord(InsightsPeriod.d7);
      final month = await repo.trackRecord(InsightsPeriod.d30);
      final quarter = await repo.trackRecord(InsightsPeriod.d90);
      expect(week.overall.resolved, lessThanOrEqualTo(month.overall.resolved));
      expect(month.overall.resolved, lessThanOrEqualTo(quarter.overall.resolved));
      expect(quarter.overall.resolved, greaterThan(0));
      final again = await SimulatedInsightsRepository(
        source: SimulatedMarketSource(clock: () => kTestNow.add(const Duration(hours: 9))),
      ).trackRecord(InsightsPeriod.d90);
      expect(again.overall.hits, quarter.overall.hits);
    });

    test('90 days matches the Signals accuracy line exactly', () async {
      final quarter = await repo.trackRecord(InsightsPeriod.d90);
      final line = await SimulatedSignalsRepository(source: source).accuracy();
      expect(line.windowDays, 90);
      expect(line.resolved, quarter.overall.resolved);
      expect(line.hits, quarter.overall.hits);
    });
  });

  group('InsightsViewModel', () {
    test('opens on the accuracy line window, 90 days when it has not loaded', () async {
      final (c, _) = setUpContainer();
      expect(c.read(insightsPeriodProvider), InsightsPeriod.d90);

      final (c2, _) = setUpContainer(overrides: [
        signalsRepositoryProvider.overrideWithValue(_Accuracy(30)),
      ]);
      c2.listen(modelAccuracyProvider, (_, __) {});
      await c2.read(modelAccuracyProvider.future);
      expect(c2.read(insightsPeriodProvider), InsightsPeriod.d30);
    });

    test('loading, then the record for the period', () async {
      final (c, insights) = setUpContainer();
      c.listen(insightsViewModelProvider, (_, __) {});
      expect(c.read(insightsViewModelProvider).isLoading, isTrue);
      expect(insights.calls.single.$1, InsightsPeriod.d90);
      insights.calls.single.$2.complete(record(InsightsPeriod.d90));
      await pumpEventQueue();
      expect(c.read(insightsViewModelProvider).valueOrNull?.period, InsightsPeriod.d90);
    });

    test('rapid period switches: only the latest period lands, whatever order answers come in', () async {
      final (c, insights) = setUpContainer();
      c.listen(insightsViewModelProvider, (_, __) {});
      final period = c.read(insightsPeriodProvider.notifier);
      period.select(InsightsPeriod.d7);
      c.read(insightsViewModelProvider);
      period.select(InsightsPeriod.d30);
      c.read(insightsViewModelProvider);
      expect(insights.calls.map((call) => call.$1), [InsightsPeriod.d90, InsightsPeriod.d7, InsightsPeriod.d30]);
      expect(c.read(insightsViewModelProvider).isLoading, isTrue);

      // الأحدث أول، بعدين القدام (واحد منهم بيفشل) - ولا واحد منهم بيكتب فوقه
      insights.calls[2].$2.complete(record(InsightsPeriod.d30, resolved: 30, hits: 21));
      await pumpEventQueue();
      insights.calls[0].$2.complete(record(InsightsPeriod.d90, resolved: 90, hits: 45));
      insights.calls[1].$2.completeError(StateError('late failure'));
      await pumpEventQueue();
      final state = c.read(insightsViewModelProvider);
      expect(state.hasError, isFalse);
      expect(state.valueOrNull?.period, InsightsPeriod.d30);
      expect(state.valueOrNull?.overall.resolved, 30);
    });

    test('switching while the old answer is still pending shows loading, not the old period', () async {
      final (c, insights) = setUpContainer();
      c.listen(insightsViewModelProvider, (_, __) {});
      insights.calls.single.$2.complete(record(InsightsPeriod.d90));
      await pumpEventQueue();
      c.read(insightsPeriodProvider.notifier).select(InsightsPeriod.d7);
      final state = c.read(insightsViewModelProvider);
      expect(state.isLoading, isTrue);
      insights.calls.last.$2.complete(record(InsightsPeriod.d7));
      await pumpEventQueue();
      expect(c.read(insightsViewModelProvider).valueOrNull?.period, InsightsPeriod.d7);
    });

    test('an answer for another period is an error, not shown under the chip', () async {
      final (c, insights) = setUpContainer();
      c.listen(insightsViewModelProvider, (_, __) {});
      insights.calls.single.$2.complete(record(InsightsPeriod.d7));
      await pumpEventQueue();
      expect(c.read(insightsViewModelProvider).hasError, isTrue);
    });

    test('error, then Try again loads', () async {
      final (c, insights) = setUpContainer();
      c.listen(insightsViewModelProvider, (_, __) {});
      insights.calls.single.$2.completeError(StateError('down'));
      await pumpEventQueue();
      expect(c.read(insightsViewModelProvider).error, isA<StateError>());

      final retry = c.read(insightsViewModelProvider.notifier).retry();
      await pumpEventQueue();
      insights.calls.last.$2.complete(record(InsightsPeriod.d90));
      await retry;
      expect(c.read(insightsViewModelProvider).valueOrNull?.period, InsightsPeriod.d90);
    });

    test('offline: nothing sent, loads by itself when back online', () async {
      final (c, insights) = setUpContainer();
      c.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      c.listen(insightsViewModelProvider, (_, __) {});
      await pumpEventQueue();
      expect(c.read(insightsViewModelProvider).error, isA<InsightsOfflineException>());
      expect(insights.calls, isEmpty);

      c.read(networkStatusProvider.notifier).set(NetworkStatus.online);
      c.read(insightsViewModelProvider);
      await pumpEventQueue();
      expect(insights.calls, hasLength(1));
      insights.calls.single.$2.complete(record(InsightsPeriod.d90));
      await pumpEventQueue();
      expect(c.read(insightsViewModelProvider).hasValue, isTrue);
    });

    test('screen closed while loading: the late answer is dropped quietly', () async {
      final (c, insights) = setUpContainer();
      final sub = c.listen(insightsViewModelProvider, (_, __) {});
      sub.close();
      await pumpEventQueue();
      insights.calls.single.$2.complete(record(InsightsPeriod.d90));
      await pumpEventQueue();
      // instance جديد بيبلّش من الأول (ما في نتيجة قديمة محفوظة)
      c.listen(insightsViewModelProvider, (_, __) {});
      expect(c.read(insightsViewModelProvider).isLoading, isTrue);
      expect(insights.calls, hasLength(2));
    });
  });

  group('InsightsScreen', () {
    for (final mode in ['light', 'dark']) {
      for (final locale in ['en', 'ar']) {
        testWidgets('headline, chart, breakdowns, note ($mode, $locale)', (tester) async {
          await pumpInsights(tester, locale: locale, prefs: {themeModeStorageKey: mode});
          final en = locale == 'en';
          expect(find.text(en ? 'Insights' : 'أداء النموذج'), findsOneWidget);
          expect(find.text(en ? 'Hit rate · last 90 days' : 'نسبة الإصابة · آخر 90 يومًا'), findsOneWidget);
          expect(find.byType(SfCartesianChart), findsOneWidget);
          expect(find.text(en ? 'By instrument' : 'حسب الأداة'), findsOneWidget);
          expect(find.text(en ? 'By timeframe' : 'حسب الإطار الزمني'), findsOneWidget);
          expect(find.byType(AccuracyRow), findsNWidgets(kProductSymbols.length + Timeframe.modelTimeframes.length));
          expect(find.text(en ? 'Simulated' : 'محاكاة'), findsOneWidget);
          expect(
            find.textContaining(en ? 'Past results are not a promise of future results.' : 'النتائج السابقة ليست وعدًا بنتائج مستقبلية.'),
            findsOneWidget,
          );
          expect(tester.takeException(), isNull);
        });
      }
    }

    testWidgets('every figure carries its sample size', (tester) async {
      await pumpInsights(tester, overrides: [
        insightsRepositoryProvider.overrideWithValue(_Fixed((p) => record(p))),
      ]);
      expect(find.text('22 of 40 finished signals reached the target before the stop'), findsOneWidget);
      expect(find.text('18 hit the stop first'), findsOneWidget);
      expect(find.text('28 signals'), findsOneWidget); // EUR/USD
      expect(find.text('12 signals'), findsOneWidget); // XAU/USD
      expect(find.text('30 signals'), findsOneWidget); // 15m
      expect(find.text('10 signals'), findsOneWidget); // 4h
      expect(find.bySemanticsLabel('EUR/USD, Euro / US Dollar: 54%, 15 of 28 signals reached the target.'), findsOneWidget);
    });

    testWidgets('small samples are marked, rows without results show no percentage', (tester) async {
      await pumpInsights(tester, overrides: [
        insightsRepositoryProvider.overrideWithValue(_Fixed((p) => trackRecordFromJson(Json({
              'window_days': p.days,
              'resolved': 4,
              'hits': 3,
              'by_symbol': [
                {'symbol': 'EUR/USD', 'resolved': 4, 'hits': 3},
                {'symbol': 'GBP/USD', 'resolved': 0, 'hits': 0},
              ],
            })))),
      ]);
      expect(find.text('4 signals · Small sample'), findsOneWidget);
      expect(find.text('0 signals'), findsOneWidget);
      expect(find.text('—'), findsOneWidget);
      expect(find.text('Not enough finished signals to draw a trend.'), findsOneWidget);
    });

    testWidgets('period chips: tap 7 days shows the 7-day record, selected for screen readers', (tester) async {
      await pumpInsights(tester);
      await tester.tap(find.widgetWithText(ChoiceChip, '7 days'));
      await tester.pumpAndSettle();
      expect(find.text('Hit rate · last 7 days'), findsOneWidget);
      final chip = tester.widget<ChoiceChip>(find.widgetWithText(ChoiceChip, '7 days'));
      expect(chip.selected, isTrue);
      expect(tester.getSize(find.widgetWithText(ChoiceChip, '7 days')).height, greaterThanOrEqualTo(48));
    });

    testWidgets('loading skeleton while the record loads; chips stay usable', (tester) async {
      final insights = _Insights();
      await pumpInsights(tester, overrides: [insightsRepositoryProvider.overrideWithValue(insights)]);
      expect(find.bySemanticsLabel('Loading'), findsOneWidget);
      await tester.tap(find.widgetWithText(ChoiceChip, '30 days'));
      await tester.pump();
      expect(insights.calls.map((c) => c.$1), [InsightsPeriod.d90, InsightsPeriod.d30]);
      insights.calls[1].$2.complete(record(InsightsPeriod.d30));
      insights.calls[0].$2.complete(record(InsightsPeriod.d90, resolved: 90, hits: 10));
      await tester.pumpAndSettle();
      expect(find.text('Hit rate · last 30 days'), findsOneWidget);
      expect(find.text('22 of 40 finished signals reached the target before the stop'), findsOneWidget);
    });

    testWidgets('empty period: explains, offers 90 days', (tester) async {
      await pumpInsights(tester, overrides: [
        insightsRepositoryProvider.overrideWithValue(
          _Fixed((p) => p == InsightsPeriod.d90 ? record(p) : record(p, resolved: 0, hits: 0)),
        ),
      ]);
      await tester.tap(find.widgetWithText(ChoiceChip, '7 days'));
      await tester.pumpAndSettle();
      expect(find.text('No finished signals in this period'), findsOneWidget);
      expect(find.textContaining('%'), findsNothing); // ما في نسبة مخترعة
      await tester.tap(find.text('Show 90 days'));
      await tester.pumpAndSettle();
      expect(find.text('Hit rate · last 90 days'), findsOneWidget);
    });

    testWidgets('error with Try again', (tester) async {
      final repo = _Fixed((_) => null);
      await pumpInsights(tester, overrides: [insightsRepositoryProvider.overrideWithValue(repo)]);
      expect(find.text('The track record could not be loaded.'), findsOneWidget);
      repo.result = (p) => record(p);
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Hit rate · last 90 days'), findsOneWidget);
    });

    testWidgets('offline: offline state, loads when back online', (tester) async {
      usePhoneSize(tester, height: 2400);
      final scope = await testScope(const TestApp(home: InsightsScreen()));
      await tester.pumpWidget(scope);
      final container = ProviderScope.containerOf(tester.element(find.byType(InsightsScreen)));
      container.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      container.invalidate(insightsViewModelProvider);
      await tester.pumpAndSettle();
      expect(find.text('You’re offline'), findsOneWidget);
      expect(find.text('The track record will load when you’re back online.'), findsOneWidget);
      container.read(networkStatusProvider.notifier).set(NetworkStatus.online);
      await tester.pumpAndSettle();
      expect(find.text('Hit rate · last 90 days'), findsOneWidget);
    });

    for (final locale in ['en', 'ar']) {
      testWidgets('largest font, phone height ($locale): no overflow', (tester) async {
        useLargeText(tester);
        await pumpInsights(tester, locale: locale, height: 812);
        expect(tester.takeException(), isNull);
        await scrollTo(tester, find.text(locale == 'en' ? 'How to read this' : 'كيف تقرأ هذه الأرقام'));
        expect(tester.takeException(), isNull);
      });
    }

    // A3c: Insights = دقة النموذج نفسه، مستقلة عن طريقة الاستراتيجية
    for (final (locale, intro, note) in [
      (
        'en',
        'The accuracy of the AI model’s signals. It is the same whichever analysis method you choose.',
        'This is the AI model’s own record, independent of the analysis method in your strategy.',
      ),
      (
        'ar',
        'دقة إشارات نموذج الذكاء الاصطناعي. لا تتغير مهما كانت طريقة التحليل التي تختارها.',
        'هذا سجل نموذج الذكاء الاصطناعي نفسه، ولا يتأثر بطريقة التحليل في استراتيجيتك.',
      ),
    ]) {
      testWidgets('intro and note say it is the AI model accuracy, independent of the method ($locale)',
          (tester) async {
        await pumpInsights(tester, locale: locale);
        expect(find.text(intro), findsOneWidget);
        await scrollTo(tester, find.textContaining(note));
        expect(find.textContaining(note), findsOneWidget);
        expect(tester.takeException(), isNull);
      });
    }

    testWidgets('reduced motion: the chart draws without animation', (tester) async {
      tester.platformDispatcher.accessibilityFeaturesTestValue = const FakeAccessibilityFeatures(disableAnimations: true);
      addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
      await pumpInsights(tester);
      final chart = tester.widget<SfCartesianChart>(find.byType(SfCartesianChart));
      expect(chart.series.single.animationDuration, 0);
    });

    testWidgets('meets the tap target guideline', (tester) async {
      final handle = tester.ensureSemantics();
      await pumpInsights(tester);
      await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
      handle.dispose();
    });
  });

  group('accuracy line → Insights', () {
    testWidgets('opens once on a double tap, back returns to Signals', (tester) async {
      usePhoneSize(tester, height: 1200);
      await tester.pumpWidget(await testScope(const TestApp(home: SignalsScreen())));
      await tester.pumpAndSettle();
      final line = find.byType(AccuracyLine);
      expect(tester.getSize(line).height, greaterThanOrEqualTo(48));
      expect(find.bySemanticsLabel(RegExp('Model accuracy')), findsOneWidget);
      await tester.tap(line);
      await tester.tap(line, warnIfMissed: false);
      await tester.pumpAndSettle();
      expect(find.byType(InsightsScreen), findsOneWidget);
      // نفس رقم السطر (90 يوم)
      expect(find.text('Hit rate · last 90 days'), findsOneWidget);

      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.byType(InsightsScreen), findsNothing);
      expect(find.byType(AccuracyLine), findsOneWidget);
    });

    testWidgets('the Insights headline equals the accuracy line', (tester) async {
      usePhoneSize(tester, height: 1200);
      await tester.pumpWidget(await testScope(const TestApp(home: SignalsScreen())));
      await tester.pumpAndSettle();
      final container = ProviderScope.containerOf(tester.element(find.byType(SignalsScreen)));
      final line = container.read(modelAccuracyProvider).requireValue;
      await tester.tap(find.byType(AccuracyLine));
      await tester.pumpAndSettle();
      expect(
        find.text('${line.hits} of ${line.resolved} finished signals reached the target before the stop'),
        findsOneWidget,
      );
    });
  });
}
