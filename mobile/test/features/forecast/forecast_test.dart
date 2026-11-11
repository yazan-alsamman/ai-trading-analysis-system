// H1 + H1b: توقّع النموذج على رسم الأداة، على كل الأطر (1m · 15m · 1h · 4h · 1D).
// ForecastPath حتمي ومتّسق مع خطة الإشارة وطريقة الاستراتيجية (أو بيلحق أقوى
// إشارة باحتمال أقل)، الأفق والنطاق حسب الإطار، تحويل الـ DTO، الـ ViewModel
// (سباق تبديل الإطار، قديم، تحديث عند سكرة الشمعة، الأطر المدعومة من الإعداد،
// تغيير الاستراتيجية، بدون اتصال)، وحالات المفتاح والشرح على شاشة السوق.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:syncfusion_flutter_charts/charts.dart';

import 'package:trading_app/core/data/json.dart';
import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/core/widgets/direction_badge.dart';
import 'package:trading_app/core/widgets/not_advice_notice.dart';
import 'package:trading_app/features/forecast/data/forecast_dto.dart';
import 'package:trading_app/features/forecast/data/forecast_repository.dart';
import 'package:trading_app/features/forecast/models/forecast_config.dart';
import 'package:trading_app/features/forecast/models/forecast_path.dart';
import 'package:trading_app/features/forecast/view_models/forecast_view_model.dart';
import 'package:trading_app/features/markets/data/simulated_market_source.dart';
import 'package:trading_app/features/markets/models/market_models.dart';
import 'package:trading_app/features/markets/view_models/market_view_model.dart';
import 'package:trading_app/features/markets/views/market_screen.dart';
import 'package:trading_app/features/markets/widgets/price_chart.dart';
import 'package:trading_app/features/markets/widgets/signal_summary.dart';
import 'package:trading_app/features/signals/data/signal_profile_repository.dart';
import 'package:trading_app/features/signals/data/signals_repository.dart';
import 'package:trading_app/features/signals/models/analysis_method.dart';
import 'package:trading_app/features/signals/models/opportunity.dart';
import 'package:trading_app/features/signals/models/signal_profile.dart';

import '../../helpers/test_app.dart';

const _ma = AnalysisMethod.maCrossoverId;
const _rsi = AnalysisMethod.rsiReversalId;

final _source = SimulatedMarketSource(clock: () => kTestNow);
final _real = SimulatedForecastRepository(source: _source);

/// التوقّع المحاكى على [kTestNow] (محسوب مرة وحدة، ما بيتغيّر مع الساعة)
Future<ForecastPath> _path(String symbol, Timeframe tf, [String method = _ma]) async =>
    (await _real.forecast(symbol, tf, methodId: method))!;

ForecastPath _copy(ForecastPath p, {DateTime? validUntil, Timeframe? timeframe}) => ForecastPath(
      symbol: p.symbol,
      timeframe: timeframe ?? p.timeframe,
      methodId: p.methodId,
      signalId: p.signalId,
      basisTimeframe: p.basisTimeframe,
      direction: p.direction,
      probability: p.probability,
      anchorTime: p.anchorTime,
      anchorPrice: p.anchorPrice,
      target: p.target,
      generatedAt: p.generatedAt,
      validUntil: validUntil ?? p.validUntil,
      points: p.points,
    );

/// مصدر توقّع وهمي: بيعدّ الطلبات، وبيوقّف كل طلب لحد [release] لما [gated]
final class _FakeForecasts implements ForecastRepository {
  _FakeForecasts({this.gated = false, this.answer});

  bool gated;

  /// الجواب لكل طلب (null = المحاكى على [kTestNow])
  Future<ForecastPath?> Function(String symbol, Timeframe tf, String method)? answer;
  Object? error;
  final calls = <({String symbol, Timeframe tf, String method, ForecastCancelToken? cancel})>[];
  final _gates = <Completer<void>>[];

  @override
  bool get isSimulated => true;

  @override
  Future<ForecastPath?> forecast(String symbol, Timeframe tf, {required String methodId, ForecastCancelToken? cancel}) async {
    calls.add((symbol: symbol, tf: tf, method: methodId, cancel: cancel));
    if (gated) {
      final gate = Completer<void>();
      _gates.add(gate);
      await gate.future;
    }
    if (error != null) throw error!;
    return answer != null ? answer!(symbol, tf, methodId) : _real.forecast(symbol, tf, methodId: methodId);
  }

  /// يخلّي الطلب رقم [index] يرجع
  void release(int index) => _gates[index].complete();
}

final class _MemoryProfiles implements SignalProfileRepository {
  SignalProfile saved = SignalProfile.defaults;

  @override
  SignalProfile read() => saved;

  @override
  Future<void> save(SignalProfile profile) async => saved = profile;

  @override
  Future<void> clear() async => saved = SignalProfile.defaults;
}

ProviderContainer _container(ForecastRepository repo, {DateTime Function()? clock, Set<Timeframe>? supported}) {
  final c = ProviderContainer(overrides: [
    connectivityOverride(),
    ...simulatedMarketOverrides(clock: clock),
    signalProfileRepositoryProvider.overrideWithValue(_MemoryProfiles()),
    forecastRepositoryProvider.overrideWithValue(repo),
    if (supported != null) forecastSupportedTimeframesProvider.overrideWithValue(supported),
  ]);
  addTearDown(c.dispose);
  return c;
}

/// بيفتح الـ ViewModel لأداة (متل الشاشة) وبيشغّل المفتاح على [tf]
ForecastState _open(ProviderContainer c, {String symbol = 'EUR/USD', Timeframe tf = Timeframe.h1}) {
  c.listen(forecastViewModelProvider(symbol), (_, __) {}, fireImmediately: true);
  final vm = c.read(marketViewModelProvider(symbol).notifier);
  vm.setTimeframe(tf);
  vm.toggleForecast();
  return c.read(forecastViewModelProvider(symbol));
}

void main() {
  group('ForecastPath (simulated)', () {
    test('deterministic: same instrument, timeframe, method and time = the same forecast', () async {
      final other = SimulatedForecastRepository(source: SimulatedMarketSource(clock: () => kTestNow));
      var compared = 0;
      for (final method in AnalysisMethod.knownIds) {
        for (final symbol in kProductSymbols) {
          for (final tf in Timeframe.values) {
            final a = _real.forecastJson(symbol, tf, methodId: method);
            final b = other.forecastJson(symbol, tf, methodId: method);
            expect(a, b, reason: '$method $symbol ${tf.label}');
            final p = await _real.forecast(symbol, tf, methodId: method);
            final q = await other.forecast(symbol, tf, methodId: method);
            expect(p?.points, q?.points);
            if (p != null) compared++;
          }
        }
      }
      expect(compared, greaterThan(20));
    });

    test('a path on every timeframe (1m · 15m · 1h · 4h · 1D) for a strategy with a signal', () async {
      for (final tf in Timeframe.values) {
        final f = await _real.forecast('EUR/USD', tf, methodId: _ma);
        expect(f, isNotNull, reason: tf.label);
        expect(f!.timeframe, tf);
        expect(f.points, hasLength(forecastHorizon(tf).candles));
        expect(f.points.first.time, f.anchorTime.add(tf.duration), reason: 'one candle step on the chart timeframe');
        expect(f.anchorTime, tf.bucketStart(kTestNow));
        expect(f.validUntil, f.anchorTime.add(tf.duration * forecastHorizon(tf).validCandles));
      }
      // 1h إلو خطة؛ 1m و 15m (محايد) و 1D بيلحقوا إشارة 1h
      expect((await _path('EUR/USD', Timeframe.h1)).follows, isFalse);
      for (final tf in [Timeframe.m1, Timeframe.m15, Timeframe.d1]) {
        expect((await _path('EUR/USD', tf)).basisTimeframe, Timeframe.h1, reason: tf.label);
      }
    });

    test('horizon and band scale with the timeframe; few candles keep the chart readable', () async {
      for (final symbol in ['EUR/USD', 'XAU/USD', 'USD/JPY']) {
        Duration? lastHorizon;
        double? lastBand;
        for (final tf in Timeframe.values) {
          final f = await _path(symbol, tf);
          final horizon = f.endTime.difference(f.anchorTime);
          final band = (f.points.last.high - f.points.last.low) / f.anchorPrice;
          final why = '$symbol ${tf.label}';
          expect(horizon, tf.duration * forecastHorizon(tf).candles, reason: why);
          if (lastHorizon != null) expect(horizon, greaterThan(lastHorizon), reason: '$why: farther ahead');
          if (lastBand != null) expect(band, greaterThan(lastBand), reason: '$why: wider band');
          lastHorizon = horizon;
          lastBand = band;
          expect(f.points.length, lessThanOrEqualTo(PriceChart.visibleCandles ~/ 5), reason: why);
          // صالح لسكرة شمعة على الأقل؛ ما بيطوّل أكتر من 3 شموع (1D: يوم)
          final valid = f.validUntil.difference(f.anchorTime);
          expect(valid, greaterThanOrEqualTo(tf.duration), reason: why);
          expect(valid, lessThanOrEqualTo(tf == Timeframe.d1 ? const Duration(days: 1) : tf.duration * 3), reason: why);
        }
      }
      expect(Timeframe.m1.duration * forecastHorizon(Timeframe.m1).validCandles, lessThanOrEqualTo(const Duration(minutes: 5)),
          reason: '1m: a few minutes');
      expect(Timeframe.d1.duration * forecastHorizon(Timeframe.d1).validCandles, const Duration(days: 1),
          reason: '1D: a day');
    });

    test('consistent with the signal plan of the saved method on every timeframe', () async {
      final signals = SimulatedSignalsRepository(source: _source);
      var own = 0, follows = 0, neutral = 0;
      for (final method in AnalysisMethod.knownIds) {
        for (final symbol in kProductSymbols) {
          final reads = await signals.opportunities(symbol, methodId: method);
          final best = ModelRead.from(reads, kTestNow).best;
          for (final tf in Timeframe.values) {
            final f = await _real.forecast(symbol, tf, methodId: method);
            final why = '$method $symbol ${tf.label}';
            final o = reads.where((o) => o.timeframe == tf && o.isDetected).firstOrNull;
            if (best == null) {
              expect(f, isNull, reason: '$why: a neutral strategy = no forecast');
              neutral++;
              continue;
            }
            expect(f, isNotNull, reason: why);
            expect(f!.methodId, method);
            expect(f.points, hasLength(forecastHorizon(tf).candles), reason: why);
            for (final (i, p) in f.points.indexed) {
              expect(p.time, f.anchorTime.add(tf.duration * (i + 1)));
              expect(p.low, lessThanOrEqualTo(p.expected));
              expect(p.expected, lessThanOrEqualTo(p.high));
            }
            // النطاق بيتوسّع مع الوقت
            expect(f.points.last.high - f.points.last.low, greaterThan(f.points.first.high - f.points.first.low));
            expect(f.target, f.expectedLevel);
            if (f.direction == SignalDirection.long) {
              expect(f.expectedLevel, greaterThan(f.anchorPrice), reason: why);
            } else {
              expect(f.expectedLevel, lessThan(f.anchorPrice), reason: why);
            }

            if (o != null) {
              // خطة على هالإطار: نفس الإشارة، والمسار بيخلص عند هدفها
              own++;
              expect(f.follows, isFalse, reason: why);
              expect(f.signalId, o.id, reason: why);
              expect(f.direction, o.direction, reason: why);
              expect(f.probability, o.probability, reason: why);
              expect(f.validUntil, o.validUntil);
              expect(f.anchorTime, o.generatedAt);
              expect(f.anchorPrice, closeTo(o.entryZone.mid, 1e-9 + o.entryZone.high - o.entryZone.low));
              expect(f.expectedLevel, greaterThanOrEqualTo(o.takeProfitZone.low), reason: why);
              expect(f.expectedLevel, lessThanOrEqualTo(o.takeProfitZone.high), reason: why);
            } else {
              // ما في خطة: بيلحق أقوى إشارة (نفس خلاصة الرأي) باحتمال أقل
              follows++;
              expect(f.follows, isTrue, reason: why);
              expect(f.signalId, best.id, reason: why);
              expect(f.basisTimeframe, best.timeframe, reason: why);
              expect(f.direction, best.direction, reason: why);
              expect(f.probability, lessThan(best.probability), reason: why);
              expect(f.probability, greaterThanOrEqualTo(forecastMinProbability), reason: why);
            }
          }
        }
      }
      expect(own, greaterThan(5));
      expect(follows, greaterThan(20));
      expect(neutral, greaterThan(5));
    });

    test('depends on the strategy method the same way the signal does', () async {
      // USD/CAD 1h: MA Crossover = Short، RSI Reversal = Long (على kTestNow)
      final signals = SimulatedSignalsRepository(source: _source);
      final ma = await _path('USD/CAD', Timeframe.h1, _ma);
      final rsi = await _path('USD/CAD', Timeframe.h1, _rsi);
      expect(ma.direction, SignalDirection.short);
      expect(rsi.direction, SignalDirection.long);
      expect(ma.signalId, endsWith('@$_ma'));
      expect(rsi.signalId, endsWith('@$_rsi'));
      for (final f in [ma, rsi]) {
        final o = (await signals.opportunities('USD/CAD', methodId: f.methodId)).firstWhere((o) => o.timeframe == Timeframe.h1);
        expect((f.direction, f.probability, f.signalId), (o.direction, o.probability, o.id));
      }
    });

    test('a neutral strategy, an unknown instrument or method = no forecast', () async {
      // EUR/USD بـ RSI Reversal محايد على كل الأطر (على kTestNow)
      for (final tf in Timeframe.values) {
        expect(await _real.forecast('EUR/USD', tf, methodId: _rsi), isNull, reason: tf.label);
      }
      expect(await _real.forecast('BTC/USD', Timeframe.h1, methodId: _ma), isNull);
      expect(await _real.forecast('EUR/USD', Timeframe.h1, methodId: 'ai_model'), isNull);
    });

    test('likelihood words: high ≥ 70%, moderate ≥ 60%, else low', () {
      expect(ForecastLikelihood.of(0.72), ForecastLikelihood.high);
      expect(ForecastLikelihood.of(0.7), ForecastLikelihood.high);
      expect(ForecastLikelihood.of(0.64), ForecastLikelihood.moderate);
      expect(ForecastLikelihood.of(0.58), ForecastLikelihood.low);
    });
  });

  group('followFrom (live last candle)', () {
    test('starts at the last candle, the gap fades, the path still ends at the target', () async {
      final f = await _path('EUR/USD', Timeframe.h1);
      final live = f.anchorPrice + 0.0012;
      final pts = f.followFrom(f.anchorTime, live);
      expect(pts, hasLength(f.points.length + 1));
      expect((pts.first.time, pts.first.expected, pts.first.low, pts.first.high), (f.anchorTime, live, live, live));
      expect(pts.last, f.points.last);
      // الفرق بيتلاشى بالتدريج
      final gaps = [for (var i = 1; i < pts.length; i++) pts[i].expected - f.points[i - 1].expected];
      for (var i = 1; i < gaps.length; i++) {
        expect(gaps[i], lessThan(gaps[i - 1]));
      }
      expect(f.followFrom(f.anchorTime, live), pts, reason: 'deterministic');
      expect(f.followFrom(f.anchorTime, f.anchorPrice).skip(1), f.points, reason: 'no gap = the path as is');
    });

    test('a new candle drops the passed point; after the path ends nothing is drawn', () async {
      final f = await _path('EUR/USD', Timeframe.h1);
      final next = f.anchorTime.add(Timeframe.h1.duration);
      final pts = f.followFrom(next, f.points.first.expected);
      expect(pts.first.time, next);
      expect(pts, hasLength(f.points.length));
      expect(pts.skip(1), f.points.skip(1), reason: 'live price = the expected one → no shift');
      expect(f.followFrom(f.points.last.time, 1.1), isEmpty);
    });
  });

  group('ForecastDto', () {
    Map<String, Object?> valid() => _real.forecastJson('EUR/USD', Timeframe.h1, methodId: _ma)!;

    test('valid → domain; the mapping is the only place that knows the shape', () {
      final p = ForecastDto.fromJson(Json(valid())).toDomain()!;
      expect(p.symbol, 'EUR/USD');
      expect(p.timeframe, Timeframe.h1);
      expect(p.direction, SignalDirection.short);
      expect(p.points, hasLength(forecastHorizon(Timeframe.h1).candles));
      expect(p.basisTimeframe, Timeframe.h1);
      expect(p.follows, isFalse);
    });

    test('basis_timeframe: another timeframe = follows; missing or unknown = the chart timeframe', () {
      final m1 = _real.forecastJson('EUR/USD', Timeframe.m1, methodId: _ma)!;
      expect(m1['basis_timeframe'], '1h');
      final p = ForecastDto.fromJson(Json(m1)).toDomain()!;
      expect((p.timeframe, p.basisTimeframe, p.follows), (Timeframe.m1, Timeframe.h1, true));
      for (final basis in [null, '7m']) {
        final q = ForecastDto.fromJson(Json({...m1, 'basis_timeframe': basis})).toDomain()!;
        expect((q.basisTimeframe, q.follows), (Timeframe.m1, false));
      }
    });

    test('invalid → null, bad points are dropped, nothing throws', () {
      Map<String, Object?> w(Map<String, Object?> patch) => {...valid(), ...patch};
      ForecastPath? parse(Map<String, Object?> j) => ForecastDto.fromJson(Json(j)).toDomain();
      expect(parse(w({'direction': 'neutral'})), isNull);
      expect(parse(w({'probability': 1.2})), isNull);
      expect(parse(w({'probability': 'x'})), isNull);
      expect(parse(w({'anchor': null})), isNull);
      expect(parse(w({'timeframe': '3m'})), isNull);
      expect(parse(w({'method_id': 'ai_model'})), isNull);
      expect(parse(w({'valid_until': valid()['generated_at']})), isNull);
      expect(parse(w({'points': []})), isNull);
      expect(parse(w({'points': 'nope'})), isNull);
      final points = [...(valid()['points']! as List).cast<Map<String, Object?>>()];
      final mixed = [
        points[0],
        {'time': points[0]['time'], 'expected': 1, 'low': 1, 'high': 1}, // نفس الوقت
        {'time': points[1]['time'], 'expected': 2, 'low': 3, 'high': 4}, // expected برّا النطاق
        'not a map',
        points[1],
      ];
      expect(parse(w({'points': mixed}))!.points, hasLength(2));
    });
  });

  group('ForecastViewModel', () {
    test('off by default: no request; on → loading → the repository forecast', () async {
      final fake = _FakeForecasts();
      final c = _container(fake);
      c.listen(forecastViewModelProvider('EUR/USD'), (_, __) {}, fireImmediately: true);
      expect(c.read(forecastViewModelProvider('EUR/USD')), isA<ForecastOff>());
      expect(fake.calls, isEmpty);

      c.read(marketViewModelProvider('EUR/USD').notifier).toggleForecast();
      expect(c.read(forecastViewModelProvider('EUR/USD')), isA<ForecastLoading>());
      await pumpEventQueue();
      final state = c.read(forecastViewModelProvider('EUR/USD'));
      expect(state, isA<ForecastReady>());
      expect((state as ForecastReady).path.signalId, (await _path('EUR/USD', Timeframe.h1)).signalId);
      expect(fake.calls.single.method, _ma, reason: 'the saved strategy method');

      c.read(marketViewModelProvider('EUR/USD').notifier).toggleForecast();
      expect(c.read(forecastViewModelProvider('EUR/USD')), isA<ForecastOff>());
    });

    for (final order in ['new first', 'old first']) {
      test('timeframe switch mid-request: old one cancelled, only the latest is drawn ($order)', () async {
        final fake = _FakeForecasts(gated: true);
        final c = _container(fake);
        expect(_open(c), isA<ForecastLoading>());
        final vm = c.read(forecastViewModelProvider('EUR/USD').notifier);
        final firstGeneration = vm.generation;

        c.read(marketViewModelProvider('EUR/USD').notifier).setTimeframe(Timeframe.h4);
        expect(c.read(forecastViewModelProvider('EUR/USD')), isA<ForecastLoading>());
        expect(vm.generation, firstGeneration + 1);
        expect(fake.calls.map((r) => r.tf), [Timeframe.h1, Timeframe.h4]);
        expect(fake.calls.first.cancel!.isCancelled, isTrue);
        expect(fake.calls.last.cancel!.isCancelled, isFalse);

        if (order == 'new first') {
          fake.release(1);
          await pumpEventQueue();
          fake.release(0);
        } else {
          fake.release(0);
          await pumpEventQueue();
          expect(c.read(forecastViewModelProvider('EUR/USD')), isA<ForecastLoading>(), reason: 'old 1h answer dropped');
          fake.release(1);
        }
        await pumpEventQueue();
        final state = c.read(forecastViewModelProvider('EUR/USD')) as ForecastReady;
        expect(state.path.timeframe, Timeframe.h4);
        expect(state.path.direction, SignalDirection.long, reason: 'EUR/USD 4h = Long, 1h = Short');
      });
    }

    test('closing the instrument (dispose) cancels its request; the late answer is dropped', () async {
      final fake = _FakeForecasts(gated: true);
      final c = _container(fake);
      final sub = c.listen(forecastViewModelProvider('EUR/USD'), (_, __) {});
      c.read(marketViewModelProvider('EUR/USD').notifier).toggleForecast();
      c.read(forecastViewModelProvider('EUR/USD'));
      sub.close();
      await pumpEventQueue();
      expect(fake.calls.single.cancel!.isCancelled, isTrue);
      fake.release(0);
      await pumpEventQueue();
    });

    test('an answer for another timeframe is an error, not drawn', () async {
      final h4 = await _path('EUR/USD', Timeframe.h4);
      final c = _container(_FakeForecasts(answer: (_, __, ___) async => h4));
      _open(c);
      await pumpEventQueue();
      expect(c.read(forecastViewModelProvider('EUR/USD')), isA<ForecastFailed>());
    });

    test('past its validity on arrival → Outdated', () async {
      var now = kTestNow;
      final path = await _path('EUR/USD', Timeframe.h1);
      final fake = _FakeForecasts(gated: true, answer: (_, __, ___) async => path);
      final c = _container(fake, clock: () => now);
      _open(c);
      now = path.validUntil.add(const Duration(minutes: 1));
      fake.release(0);
      await pumpEventQueue();
      final state = c.read(forecastViewModelProvider('EUR/USD'));
      expect(state, isA<ForecastOutdated>());
      expect((state as ForecastOutdated).path, same(path));
    });

    test('a timer marks a shown forecast Outdated at its validity; Refresh asks again', () async {
      final path = _copy(await _path('EUR/USD', Timeframe.h1), validUntil: kTestNow.add(const Duration(milliseconds: 80)));
      final fake = _FakeForecasts(answer: (_, __, ___) async => path);
      final c = _container(fake);
      _open(c);
      await pumpEventQueue();
      expect(c.read(forecastViewModelProvider('EUR/USD')), isA<ForecastReady>());
      await Future<void>.delayed(const Duration(milliseconds: 20));
      expect(c.read(forecastViewModelProvider('EUR/USD')), isA<ForecastReady>());
      await Future<void>.delayed(const Duration(milliseconds: 100));
      expect(c.read(forecastViewModelProvider('EUR/USD')), isA<ForecastOutdated>());

      c.read(forecastViewModelProvider('EUR/USD').notifier).retry();
      c.read(forecastViewModelProvider('EUR/USD'));
      expect(fake.calls, hasLength(2));
    });

    test('changing the saved strategy asks again with the new method (direction follows the signal)', () async {
      final fake = _FakeForecasts();
      final c = _container(fake);
      _open(c, symbol: 'USD/CAD');
      await pumpEventQueue();
      expect((c.read(forecastViewModelProvider('USD/CAD')) as ForecastReady).path.direction, SignalDirection.short);

      await c.read(signalProfileProvider.notifier).save(SignalProfile.defaults.copyWith(methodId: _rsi));
      expect(c.read(forecastViewModelProvider('USD/CAD')), isA<ForecastLoading>());
      await pumpEventQueue();
      final path = (c.read(forecastViewModelProvider('USD/CAD')) as ForecastReady).path;
      expect(path.methodId, _rsi);
      expect(path.direction, SignalDirection.long);
      expect(fake.calls.map((r) => r.method), [_ma, _rsi]);
    });

    test('offline: hidden, nothing sent; back online → asks again', () async {
      final fake = _FakeForecasts();
      final c = _container(fake);
      c.listen(forecastViewModelProvider('EUR/USD'), (_, __) {});
      c.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      c.read(marketViewModelProvider('EUR/USD').notifier).toggleForecast();
      expect(c.read(forecastViewModelProvider('EUR/USD')), isA<ForecastOffline>());
      expect(fake.calls, isEmpty);

      c.read(networkStatusProvider.notifier).set(NetworkStatus.online);
      expect(c.read(forecastViewModelProvider('EUR/USD')), isA<ForecastLoading>());
      await pumpEventQueue();
      expect(c.read(forecastViewModelProvider('EUR/USD')), isA<ForecastReady>());
      expect(fake.calls, hasLength(1));
    });

    test('1m and 15m (no plan there): drawn, following the 1h signal with a lower probability', () async {
      final fake = _FakeForecasts();
      final c = _container(fake);
      _open(c, tf: Timeframe.m1);
      await pumpEventQueue();
      final h1 = await _path('EUR/USD', Timeframe.h1);
      final m1 = (c.read(forecastViewModelProvider('EUR/USD')) as ForecastReady).path;
      expect(
        (m1.timeframe, m1.basisTimeframe, m1.signalId, m1.direction),
        (Timeframe.m1, Timeframe.h1, h1.signalId, h1.direction),
      );
      expect(m1.probability, lessThan(h1.probability));

      c.read(marketViewModelProvider('EUR/USD').notifier).setTimeframe(Timeframe.m15);
      c.read(forecastViewModelProvider('EUR/USD'));
      await pumpEventQueue();
      final m15 = (c.read(forecastViewModelProvider('EUR/USD')) as ForecastReady).path;
      expect((m15.timeframe, m15.direction, m15.follows), (Timeframe.m15, h1.direction, true));
      expect(fake.calls.map((r) => r.tf), [Timeframe.m1, Timeframe.m15]);
    });

    test('a neutral strategy: "No forecast right now" (no setup) on every timeframe, not an error', () async {
      final c = _container(_FakeForecasts());
      await c.read(signalProfileProvider.notifier).save(SignalProfile.defaults.copyWith(methodId: _rsi));
      for (final tf in Timeframe.values) {
        _open(c, tf: tf);
        await pumpEventQueue();
        expect(
          (c.read(forecastViewModelProvider('EUR/USD')) as ForecastUnavailable).reason,
          ForecastUnavailableReason.noSetup,
          reason: tf.label,
        );
        c.read(marketViewModelProvider('EUR/USD').notifier).toggleForecast();
      }
    });

    test('supported timeframes come from one config: an unsupported one = unavailable, no request', () async {
      expect(forecastSupportedTimeframes, Timeframe.values.toSet(), reason: 'every timeframe today');
      final fake = _FakeForecasts();
      final c = _container(fake, supported: {Timeframe.h1});
      expect((_open(c, tf: Timeframe.m15) as ForecastUnavailable).reason, ForecastUnavailableReason.timeframe);
      expect(fake.calls, isEmpty);
      c.read(marketViewModelProvider('EUR/USD').notifier).setTimeframe(Timeframe.h1);
      c.read(forecastViewModelProvider('EUR/USD'));
      await pumpEventQueue();
      expect(c.read(forecastViewModelProvider('EUR/USD')), isA<ForecastReady>());
      expect(fake.calls.map((r) => r.tf), [Timeframe.h1]);
    });

    test('refresh time = the next candle close (a followed forecast also at the next 15m close)', () {
      final now = DateTime.utc(2026, 10, 21, 14, 5, 20);
      expect(forecastRefreshAt(Timeframe.m1, now, follows: true), DateTime.utc(2026, 10, 21, 14, 6));
      expect(forecastRefreshAt(Timeframe.h1, now, follows: false), DateTime.utc(2026, 10, 21, 15));
      expect(forecastRefreshAt(Timeframe.h1, now, follows: true), DateTime.utc(2026, 10, 21, 14, 15));
      expect(forecastRefreshAt(Timeframe.d1, now, follows: false), DateTime.utc(2026, 10, 22));
      expect(forecastRefreshAt(Timeframe.d1, now, follows: true), DateTime.utc(2026, 10, 21, 14, 15));
    });

    test('error → Failed; Try again → Ready', () async {
      final fake = _FakeForecasts()..error = StateError('boom');
      final c = _container(fake);
      _open(c);
      await pumpEventQueue();
      expect(c.read(forecastViewModelProvider('EUR/USD')), isA<ForecastFailed>());
      fake.error = null;
      c.read(forecastViewModelProvider('EUR/USD').notifier).retry();
      expect(c.read(forecastViewModelProvider('EUR/USD')), isA<ForecastLoading>());
      await pumpEventQueue();
      expect(c.read(forecastViewModelProvider('EUR/USD')), isA<ForecastReady>());
    });
  });

  group('Market screen', () {
    Future<_FakeForecasts> pump(
      WidgetTester tester, {
      _FakeForecasts? fake,
      String locale = 'en',
      String theme = 'light',
      List<Override> overrides = const [],
    }) async {
      final repo = fake ?? _FakeForecasts();
      usePhoneSize(tester, height: 2400);
      await tester.pumpWidget(await testScope(
        const TestApp(home: MarketScreen(symbol: 'EUR/USD')),
        locale: locale,
        prefs: {themeModeStorageKey: theme},
        overrides: [forecastRepositoryProvider.overrideWithValue(repo), ...overrides],
      ));
      await tester.pumpAndSettle();
      return repo;
    }

    final toggle = find.byKey(const ValueKey('forecast-toggle'));
    final legend = find.byKey(const ValueKey('forecast-legend'));
    SfCartesianChart mainChart(WidgetTester tester) => tester.widget<SfCartesianChart>(find.byType(SfCartesianChart).first);
    LineSeries<ForecastPoint, DateTime>? line(WidgetTester tester) =>
        mainChart(tester).series.whereType<LineSeries<ForecastPoint, DateTime>>().firstOrNull;

    testWidgets('toggle lives in the chart toolbar only (not in the Indicators sheet); off by default', (tester) async {
      final fake = await pump(tester);
      expect(toggle, findsOneWidget);
      expect(find.text('Forecast'), findsOneWidget);
      expect(tester.getSize(toggle).height, greaterThanOrEqualTo(48));
      expect(legend, findsNothing);
      expect(line(tester), isNull);
      expect(fake.calls, isEmpty);

      await tester.tap(find.text('Indicators'));
      await tester.pumpAndSettle();
      expect(find.text('Forecast'), findsOneWidget, reason: 'no duplicate in the sheet');
    });

    testWidgets('loading (toggle disabled + indicator) → drawn: dashed line, band, label, notice, summary', (tester) async {
      final semantics = tester.ensureSemantics();
      final fake = await pump(tester, fake: _FakeForecasts(gated: true));
      await tester.tap(toggle);
      await tester.pump();
      expect(tester.widget<FilterChip>(toggle).onSelected, isNull, reason: 'disabled while loading');
      expect(find.descendant(of: toggle, matching: find.byType(CircularProgressIndicator)), findsOneWidget);
      expect(find.bySemanticsLabel(RegExp('Forecast, loading')), findsOneWidget);

      fake.release(0);
      await tester.pumpAndSettle();
      final path = await _path('EUR/USD', Timeframe.h1);
      expect(tester.widget<FilterChip>(toggle).onSelected, isNotNull);
      expect(tester.widget<FilterChip>(toggle).selected, isTrue);
      expect(find.text('Model forecast · 58% · Short'), findsOneWidget);
      expect(find.textContaining('Expected level ${path.expectedLevel.toStringAsFixed(5)}'), findsOneWidget);
      expect(find.textContaining('low probability (58%)'), findsOneWidget);
      expect(find.descendant(of: legend, matching: find.text('Simulated')), findsOneWidget);
      expect(find.descendant(of: legend, matching: find.byType(NotAdviceNotice)), findsOneWidget);
      expect(find.textContaining('guarantee'), findsNothing);

      final dashed = line(tester)!;
      expect(dashed.dashArray, [6, 4]);
      expect(dashed.animationDuration, 0);
      expect(mainChart(tester).series.whereType<RangeAreaSeries<ForecastPoint, DateTime>>(), hasLength(1));
      expect(
        find.bySemanticsLabel(RegExp(
            'Model forecast: Short, low probability \\(58%\\)\\. Expected level ${RegExp.escape(path.expectedLevel.toStringAsFixed(5))}')),
        findsOneWidget,
      );
      // خلاصة الرأي والمناطق = نفس إشارة إطار الرسم (ما في تناقض)
      final summary = tester.widget<SignalSummary>(find.byType(SignalSummary));
      expect(summary.shown!.id, path.signalId);
      expect(tester.widget<PriceChart>(find.byType(PriceChart)).read!.id, path.signalId);
      semantics.dispose();
    });

    testWidgets('follows the last candle as ticks arrive, with no new request', (tester) async {
      var now = kTestNow;
      final fake = await pump(tester, overrides: simulatedMarketOverrides(clock: () => now));
      await tester.tap(toggle);
      await tester.pumpAndSettle();
      final path = await _path('EUR/USD', Timeframe.h1);
      final before = line(tester)!.dataSource!.toList();
      expect(before.last, path.points.last);

      now = kTestNow.add(const Duration(minutes: 20));
      await tester.pump(const Duration(seconds: 2));
      await tester.pump(const Duration(seconds: 2));
      final candles = tester.widget<PriceChart>(find.byType(PriceChart)).candles;
      final after = line(tester)!.dataSource!.toList();
      expect(after.first.expected, candles.last.close);
      expect(after.first.expected, isNot(before.first.expected));
      expect(after.last, path.points.last, reason: 'still ends at the target');
      expect(fake.calls, hasLength(1));
    });

    Future<void> pickTimeframe(WidgetTester tester, String label) async {
      final chip = find.widgetWithText(ChoiceChip, label).first;
      await tester.ensureVisible(chip);
      await tester.tap(chip);
      await tester.pumpAndSettle();
    }

    testWidgets('1m and 15m: drawn (dashed path + band), follows the 1h signal, in the chart summary', (tester) async {
      final semantics = tester.ensureSemantics();
      final fake = await pump(tester);
      final h1 = await _path('EUR/USD', Timeframe.h1);
      for (final (label, tf) in [('1m', Timeframe.m1), ('15m', Timeframe.m15)]) {
        await pickTimeframe(tester, label);
        if (!tester.widget<FilterChip>(toggle).selected) {
          await tester.tap(toggle);
          await tester.pumpAndSettle();
        }
        final path = await _path('EUR/USD', tf);
        expect(path.follows, isTrue);
        final dashed = line(tester)!;
        expect(dashed.dashArray, [6, 4]);
        expect(dashed.dataSource!.last, path.points.last);
        expect(dashed.dataSource!.length, path.points.length + 1, reason: '$label: from the last candle');
        expect(mainChart(tester).series.whereType<RangeAreaSeries<ForecastPoint, DateTime>>(), hasLength(1));
        expect(find.text('Model forecast · 50% · Short'), findsOneWidget, reason: label);
        expect(find.text('Follows your strategy’s 1h signal, with a lower probability on $label.'), findsOneWidget);
        expect(find.textContaining('over the next ${forecastHorizon(tf).candles} candles'), findsOneWidget);
        expect(find.descendant(of: legend, matching: find.byType(NotAdviceNotice)), findsOneWidget);
        expect(find.text('No forecast right now'), findsNothing);
        expect(
          find.bySemanticsLabel(RegExp('Model forecast: Short, low probability \\(50%\\)\\. Expected level '
              '${RegExp.escape(path.expectedLevel.toStringAsFixed(5))}.*Follows your strategy’s 1h signal')),
          findsOneWidget,
          reason: label,
        );
        // خلاصة الرأي والمناطق = نفس الإشارة يلي التوقّع بيلحقها (نفس الاتجاه)
        final summary = tester.widget<SignalSummary>(find.byType(SignalSummary));
        expect(summary.shown!.id, h1.signalId);
        expect(summary.shown!.direction, path.direction);
        expect(summary.shown!.probability, greaterThan(path.probability));
      }
      expect(fake.calls.map((r) => r.tf), [Timeframe.m1, Timeframe.m15]);
      semantics.dispose();
    });

    testWidgets('4h and 1D drawn too; 1D keeps its label and dates the far end', (tester) async {
      await pump(tester);
      await tester.tap(toggle);
      await tester.pumpAndSettle();
      await pickTimeframe(tester, '4h');
      expect(line(tester), isNotNull);
      expect(find.text('Model forecast · 58% · Long'), findsOneWidget, reason: '4h has its own plan');
      await pickTimeframe(tester, '1D');
      final path = await _path('EUR/USD', Timeframe.d1);
      expect(line(tester)!.dataSource!.last, path.points.last);
      expect(find.text('Follows your strategy’s 1h signal, with a lower probability on 1D.'), findsOneWidget);
      // المسار بيقطع أيام: التاريخ مع الساعة
      final context = tester.element(legend);
      final end = path.endTime.toLocal();
      expect(
        find.textContaining('by ${MaterialLocalizations.of(context).formatShortMonthDay(end)} '),
        findsOneWidget,
      );
    });

    testWidgets('a neutral strategy: "No forecast right now" with the reason, nothing drawn', (tester) async {
      await pump(tester);
      final container = ProviderScope.containerOf(tester.element(find.byType(MarketScreen)));
      await container.read(signalProfileProvider.notifier).save(SignalProfile.defaults.copyWith(methodId: _rsi));
      await tester.pumpAndSettle();
      await pickTimeframe(tester, '1m');
      await tester.tap(toggle);
      await tester.pumpAndSettle();
      expect(find.text('No forecast right now'), findsOneWidget);
      expect(find.text('Your strategy sees no clear setup right now. That is a valid answer.'), findsOneWidget);
      expect(find.descendant(of: legend, matching: find.byType(NotAdviceNotice)), findsOneWidget);
      expect(line(tester), isNull);
    });

    testWidgets('a timeframe left out of the config: "Not available for this timeframe", no request', (tester) async {
      final fake = await pump(
        tester,
        overrides: [forecastSupportedTimeframesProvider.overrideWithValue({Timeframe.h1, Timeframe.h4})],
      );
      await pickTimeframe(tester, '1m');
      await tester.tap(toggle);
      await tester.pumpAndSettle();
      expect(find.text('No forecast right now'), findsOneWidget);
      expect(find.text('Not available for this timeframe. Forecasts cover 1h, 4h.'), findsOneWidget);
      expect(line(tester), isNull);
      expect(fake.calls, isEmpty);
      await pickTimeframe(tester, '1h');
      expect(line(tester), isNotNull);
      expect(fake.calls.map((r) => r.tf), [Timeframe.h1]);
    });

    testWidgets('1m: ticks never ask again; the next candle close refreshes once, the path stays drawn meanwhile',
        (tester) async {
      var now = kTestNow;
      final fake = await pump(
        tester,
        fake: _FakeForecasts(gated: true, answer: (symbol, tf, method) async {
          final repo = SimulatedForecastRepository(source: SimulatedMarketSource(clock: () => now));
          return repo.forecast(symbol, tf, methodId: method);
        }),
        overrides: simulatedMarketOverrides(clock: () => now),
      );
      await pickTimeframe(tester, '1m');
      await tester.tap(toggle);
      await tester.pump();
      fake.release(0);
      await tester.pumpAndSettle();
      final first = line(tester)!.dataSource!.last;

      // 50 ثانية من النبضات (كل 1.5 ثانية): ولا طلب جديد
      for (var i = 0; i < 25; i++) {
        now = now.add(const Duration(seconds: 2));
        await tester.pump(const Duration(seconds: 2));
      }
      expect(fake.calls, hasLength(1));
      expect(line(tester)!.dataSource!.last, first);

      // سكرة الشمعة (14:06): طلب واحد، والمسار القديم بيضل مرسوم لحد الجواب
      now = kTestNow.add(const Duration(seconds: 61));
      await tester.pump(const Duration(seconds: 11));
      expect(fake.calls, hasLength(2));
      expect(line(tester), isNotNull, reason: 'no flicker while refreshing');
      expect(find.descendant(of: toggle, matching: find.byType(CircularProgressIndicator)), findsNothing);
      fake.release(1);
      await tester.pumpAndSettle();
      final next = await SimulatedForecastRepository(source: SimulatedMarketSource(clock: () => now))
          .forecast('EUR/USD', Timeframe.m1, methodId: _ma);
      expect(next!.anchorTime, kTestNow.add(const Duration(minutes: 1)));
      expect(line(tester)!.dataSource!.last, next.points.last);
      expect(fake.calls, hasLength(2));
      final summary = tester.widget<SignalSummary>(find.byType(SignalSummary));
      expect(summary.shown!.id, next.signalId, reason: 'read card and forecast stay on the same signal');
    });

    testWidgets('error + Try again; offline hides it and says why', (tester) async {
      final fake = await pump(tester, fake: _FakeForecasts()..error = StateError('boom'));
      await tester.tap(toggle);
      await tester.pumpAndSettle();
      expect(find.text('The forecast could not be loaded.'), findsOneWidget);
      fake.error = null;
      await tester.tap(find.descendant(of: legend, matching: find.text('Try again')));
      await tester.pumpAndSettle();
      expect(line(tester), isNotNull);

      final container = ProviderScope.containerOf(tester.element(find.byType(MarketScreen)));
      container.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      await tester.pumpAndSettle();
      expect(find.text('You’re offline, so the forecast is hidden. It comes back when you’re online.'), findsOneWidget);
      expect(line(tester), isNull);
      container.read(networkStatusProvider.notifier).set(NetworkStatus.online);
      await tester.pumpAndSettle();
      expect(line(tester), isNotNull);
    });

    testWidgets('outdated: not drawn, marked "Outdated" with Refresh', (tester) async {
      final path = _copy(await _path('EUR/USD', Timeframe.h1), validUntil: kTestNow.add(const Duration(seconds: 30)));
      final fake = await pump(tester, fake: _FakeForecasts(answer: (_, __, ___) async => path));
      await tester.tap(toggle);
      await tester.pumpAndSettle();
      expect(line(tester), isNotNull);
      await tester.pump(const Duration(seconds: 31));
      await tester.pumpAndSettle();
      expect(find.text('Outdated'), findsOneWidget);
      expect(find.text('This forecast has passed its validity, so it is no longer drawn.'), findsOneWidget);
      expect(line(tester), isNull);
      await tester.tap(find.text('Refresh forecast'));
      await tester.pump();
      expect(fake.calls, hasLength(2));
      await tester.pumpAndSettle();
    });

    testWidgets('reduced motion: static loading mark, no animated drawing', (tester) async {
      tester.platformDispatcher.accessibilityFeaturesTestValue = const FakeAccessibilityFeatures(disableAnimations: true);
      addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
      final fake = await pump(tester, fake: _FakeForecasts(gated: true));
      await tester.tap(toggle);
      await tester.pump();
      expect(find.descendant(of: toggle, matching: find.byIcon(Icons.hourglass_top_rounded)), findsOneWidget);
      expect(find.descendant(of: toggle, matching: find.byType(CircularProgressIndicator)), findsNothing);
      fake.release(0);
      await tester.pumpAndSettle();
      expect(line(tester)!.animationDuration, 0);
    });

    for (final locale in ['en', 'ar']) {
      for (final theme in ['light', 'dark']) {
        testWidgets('$locale · $theme · text scale 2.0: no overflow, 48 dp, labels not cut', (tester) async {
          useLargeText(tester);
          await pump(tester, locale: locale, theme: theme);
          await tester.tap(toggle);
          await tester.pumpAndSettle();
          expect(tester.takeException(), isNull);
          expect(tester.getSize(toggle).height, greaterThanOrEqualTo(48));
          final title = locale == 'en' ? 'Model forecast · 58% · Short' : 'توقّع النموذج · 58% · هبوط';
          expect(find.text(title), findsOneWidget);
          expect(find.text(locale == 'en' ? 'Forecast' : 'التوقّع'), findsOneWidget);
          for (final t in tester.widgetList<Text>(find.descendant(of: legend, matching: find.byType(Text)))) {
            expect(t.overflow, isNot(TextOverflow.ellipsis));
            expect(t.maxLines, isNull);
          }
          expect(
            Directionality.of(tester.element(legend)),
            locale == 'ar' ? TextDirection.rtl : TextDirection.ltr,
          );

          // 1m: بيلحق إشارة 1h، والسطر الإضافي ما بيفيض
          await pickTimeframe(tester, '1m');
          expect(tester.takeException(), isNull);
          expect(
            find.text(locale == 'en'
                ? 'Follows your strategy’s 1h signal, with a lower probability on 1m.'
                : 'يتبع إشارة استراتيجيتك على 1h، باحتمال أقل على 1m.'),
            findsOneWidget,
          );
          for (final t in tester.widgetList<Text>(find.descendant(of: legend, matching: find.byType(Text)))) {
            expect(t.overflow, isNot(TextOverflow.ellipsis));
            expect(t.maxLines, isNull);
          }

          await tester.dragUntilVisible(toggle, find.byType(Scrollable).first, const Offset(0, 300));
          await tester.pumpAndSettle();
          await tester.tap(find.text(locale == 'en' ? 'Forecast' : 'التوقّع'));
          await tester.pumpAndSettle();
          expect(legend, findsNothing);
        });
      }
    }
  });
}
