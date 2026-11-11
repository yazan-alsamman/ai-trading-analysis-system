// A3a: "Request analysis" - المحرّك المحاكى، الـ ViewModel (الحالات، الإلغاء،
// الطلب المزدوج، الـ override ما بينحفظ، السباق، بدون اتصال) والإشارة المطلوبة
// بتنفتح بمعرّفها من مسار التفاصيل.

import 'dart:async';

import 'package:flutter/widgets.dart';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/app/router/app_routes.dart';
import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/widgets/direction_badge.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/markets/data/simulated_market_source.dart';
import 'package:trading_app/features/markets/models/market_models.dart';
import 'package:trading_app/features/signals/data/analysis_engine.dart';
import 'package:trading_app/features/signals/data/signal_profile_repository.dart';
import 'package:trading_app/features/signals/data/signals_repository.dart';
import 'package:trading_app/features/signals/models/analysis_method.dart';
import 'package:trading_app/features/signals/models/analysis_request.dart';
import 'package:trading_app/features/signals/models/model_accuracy.dart';
import 'package:trading_app/features/signals/models/opportunity.dart';
import 'package:trading_app/features/signals/models/signal_profile.dart';
import 'package:trading_app/features/signals/models/signal_rationale.dart';
import 'package:trading_app/features/signals/view_models/request_analysis_view_model.dart';
import 'package:trading_app/features/signals/view_models/signal_detail_view_model.dart';
import 'package:trading_app/features/signals/view_models/signals_feed_view_model.dart';
import 'package:trading_app/features/signals/views/signal_detail_screen.dart';

import '../../helpers/test_app.dart';

final _source = SimulatedMarketSource(clock: () => kTestNow);

/// أول (أداة، إطار، طريقة) قراءتها مكتشفة / محايدة على [kTestNow]
AnalysisRequest _find({required bool detected, String? method}) {
  final repo = SimulatedSignalsRepository(source: _source);
  for (final m in method == null ? AnalysisMethod.knownIds : [method]) {
    for (final symbol in kProductSymbols) {
      for (final (i, json) in repo.opportunitiesJson(symbol, methodId: m).indexed) {
        if ((json['status'] == 'detected') == detected) {
          return AnalysisRequest(symbol: symbol, timeframe: Timeframe.modelTimeframes[i], methodId: m);
        }
      }
    }
  }
  throw StateError('no ${detected ? 'detected' : 'neutral'} read at kTestNow');
}

/// مصدر بنتحكّم فيه: كل طلب تحليل بيستنى لحد ما نكمّله نحن، بعدين بيرجّع
/// نتيجة المحاكى (بدون انتظار)
final class _Gated implements SignalsRepository {
  _Gated() : sim = SimulatedSignalsRepository(source: _source, requestLatencyScale: 0);

  final SimulatedSignalsRepository sim;
  final calls = <({AnalysisRequest request, Completer<void> gate, AnalysisCancelToken? cancel})>[];
  Object? fail;

  @override
  bool get isSimulated => true;

  @override
  Future<Opportunity> requestAnalysis(
    AnalysisRequest request, {
    AnalysisCancelToken? cancel,
    void Function(AnalysisStage stage)? onStage,
  }) async {
    final gate = Completer<void>();
    calls.add((request: request, gate: gate, cancel: cancel));
    onStage?.call(AnalysisStage.pending);
    await gate.future;
    if (cancel?.isCancelled ?? false) throw const AnalysisCancelledException();
    onStage?.call(AnalysisStage.analyzing);
    if (fail case final error?) throw error;
    return sim.requestAnalysis(request, cancel: cancel);
  }

  @override
  Future<List<Opportunity>> opportunities(String symbol, {String methodId = AnalysisMethod.defaultId}) =>
      sim.opportunities(symbol, methodId: methodId);

  @override
  Future<List<Opportunity>> feed(SignalProfile profile) => sim.feed(profile);

  @override
  Future<Opportunity?> opportunity(String id) => sim.opportunity(id);

  @override
  Future<ModelAccuracy> accuracy() => sim.accuracy();
}

final class _MemoryProfiles implements SignalProfileRepository {
  _MemoryProfiles([SignalProfile? saved]) : saved = saved ?? SignalProfile.defaults;

  SignalProfile saved;
  var writes = 0;

  @override
  SignalProfile read() => saved;

  @override
  Future<void> save(SignalProfile profile) async {
    writes++;
    saved = profile;
  }

  @override
  Future<void> clear() async => writes++;
}

typedef _Setup = ({
  ProviderContainer container,
  List<RequestAnalysisState> states,
  ProviderSubscription<RequestAnalysisState> sub,
});

_Setup _setUp({SignalsRepository? signals, _MemoryProfiles? profiles}) {
  final container = ProviderContainer(overrides: [
    connectivityOverride(),
    ...simulatedMarketOverrides(),
    signalProfileRepositoryProvider.overrideWithValue(profiles ?? _MemoryProfiles()),
    signalsRepositoryProvider.overrideWithValue(
      signals ?? SimulatedSignalsRepository(source: _source, requestLatencyScale: 0.01),
    ),
  ]);
  addTearDown(container.dispose);
  final states = <RequestAnalysisState>[];
  final sub = container.listen(requestAnalysisViewModelProvider, (_, next) => states.add(next), fireImmediately: true);
  return (container: container, states: states, sub: sub);
}

RequestAnalysisViewModel _vm(ProviderContainer c) => c.read(requestAnalysisViewModelProvider.notifier);

Future<void> _flush() => Future<void>.delayed(Duration.zero);

void main() {
  group('simulated engine', () {
    test('latency is 1.5 to 3 s and deterministic per (instrument, timeframe, method, bucket)', () {
      final seen = <Duration>{};
      for (final spec in SimulatedMarketSource.specs) {
        for (final tf in Timeframe.modelTimeframes) {
          for (final m in AnalysisMethod.knownIds) {
            final d = SimulatedAnalysisEngine.requestLatency(spec, tf, m, 12345);
            expect(d, SimulatedAnalysisEngine.requestLatency(spec, tf, m, 12345));
            expect(d.inMilliseconds, inInclusiveRange(1500, 3000));
            seen.add(d);
          }
        }
      }
      expect(seen.length, greaterThan(10), reason: 'not one fixed wait');
    });

    test('stages pending → analyzing, then the same numbers as the feed for that bucket', () async {
      final repo = SimulatedSignalsRepository(source: _source, requestLatencyScale: 0);
      for (final method in AnalysisMethod.knownIds) {
        final request = _find(detected: true, method: method);
        final stages = <AnalysisStage>[];
        final result = await repo.requestAnalysis(request, onStage: stages.add);
        expect(stages, [AnalysisStage.pending, AnalysisStage.analyzing]);
        final listed = (await repo.opportunities(request.symbol, methodId: method))
            .firstWhere((o) => o.timeframe == request.timeframe);
        expect(result.id, '${SimulatedSignalsRepository.requestedPrefix}${listed.id}');
        expect((result.direction, result.probability, result.riskReward),
            (listed.direction, listed.probability, listed.riskReward));
        expect(result.methodId, method);
        expect(result.requestedByYou, isTrue);
        expect(listed.requestedByYou, isFalse);
      }
    });

    test('a real run takes 1.5 to 3 s', () async {
      final repo = SimulatedSignalsRepository(source: _source);
      final watch = Stopwatch()..start();
      await repo.requestAnalysis(_find(detected: true));
      expect(watch.elapsedMilliseconds, inInclusiveRange(1450, 3300));
    });

    test('detected results are kept for their validity and resolve by id; neutral ones are not kept', () async {
      final repo = SimulatedSignalsRepository(source: _source, requestLatencyScale: 0);
      final signal = await repo.requestAnalysis(_find(detected: true));
      expect(await repo.opportunity(signal.id), same(signal));
      expect((await repo.feed(SignalProfile.defaults)).first.id, signal.id);

      final neutral = await repo.requestAnalysis(_find(detected: false));
      expect(neutral.isDetected, isFalse);
      expect(await repo.opportunity(neutral.id), isNull);

      // "إعادة تشغيل": repository جديد ما بيعرف المعرّف
      expect(await SimulatedSignalsRepository(source: _source).opportunity(signal.id), isNull);
      // بعد ما تخلص صلاحيتها بتنشال
      final later = SimulatedSignalsRepository(
        source: SimulatedMarketSource(clock: () => signal.validUntil.add(const Duration(minutes: 1))),
      );
      expect(later.requestedSignals(signal.validUntil.add(const Duration(minutes: 1))), isEmpty);
      final expiring = SimulatedSignalsRepository(
        source: SimulatedMarketSource(clock: () => kTestNow),
        requestLatencyScale: 0,
      );
      final kept = await expiring.requestAnalysis(_find(detected: true));
      expect(expiring.requestedSignals(kept.validUntil.add(const Duration(seconds: 1))), isEmpty);
      expect(await expiring.opportunity(kept.id), isNull);
    });

    test('requesting the same bucket twice keeps one copy (no duplicates in the feed)', () async {
      final repo = SimulatedSignalsRepository(source: _source, requestLatencyScale: 0);
      final request = _find(detected: true, method: AnalysisMethod.maCrossoverId);
      await repo.requestAnalysis(request);
      await repo.requestAnalysis(request);
      final feed = await repo.feed(SignalProfile.defaults.copyWith(minProbability: 0, minRiskReward: 0));
      final base = feed.first.id.substring(SimulatedSignalsRepository.requestedPrefix.length);
      expect(feed.where((o) => o.requestedByYou).length, 1);
      expect(feed.where((o) => o.id == base), isEmpty, reason: 'the requested copy replaces the listed one');
    });

    test('a cancelled request throws, stores nothing; an invalid request is rejected', () async {
      final repo = SimulatedSignalsRepository(source: _source, requestLatencyScale: 0.01);
      final token = AnalysisCancelToken();
      final run = repo.requestAnalysis(_find(detected: true), cancel: token);
      token.cancel();
      await expectLater(run, throwsA(isA<AnalysisCancelledException>()));
      expect(repo.requestedSignals(kTestNow), isEmpty);
      expect(
        () => repo.requestAnalysis(const AnalysisRequest(symbol: 'BTC/USD', timeframe: Timeframe.h1)),
        throwsArgumentError,
      );
      expect(const AnalysisRequest(symbol: 'EUR/USD', timeframe: Timeframe.d1).isValid, isFalse);
      expect(const AnalysisRequest(symbol: 'EUR/USD', timeframe: Timeframe.h1, methodId: 'x').isValid, isFalse);
    });
  });

  group('RequestAnalysisViewModel', () {
    test('idle → pending → analyzing → done with the saved method', () async {
      final setup = _setUp(profiles: _MemoryProfiles(SignalProfile.defaults.copyWith(methodId: 'ma_crossover')));
      final request = _find(detected: true, method: AnalysisMethod.maCrossoverId);
      await _vm(setup.container).request(symbol: request.symbol, timeframe: request.timeframe);
      expect(setup.states.map((s) => s.runtimeType), [RequestIdle, RequestPending, RequestAnalyzing, RequestDone]);
      final done = setup.states.last as RequestDone;
      expect(done.request.methodId, AnalysisMethod.maCrossoverId);
      expect(done.detail.methodId, AnalysisMethod.maCrossoverId);
      expect(done.detail.signal.requestedByYou, isTrue);
      expect(done.isNoClearSetup, isFalse);
    });

    test('exactly 3 top reasons first, each with an influence label, then the rest', () async {
      final setup = _setUp();
      final request = _find(detected: true, method: AnalysisMethod.maCrossoverId);
      await _vm(setup.container).request(symbol: request.symbol, timeframe: request.timeframe);
      final detail = (setup.container.read(requestAnalysisViewModelProvider) as RequestDone).detail;
      expect(detail.topReasons.length, kTopReasons);
      expect(detail.topReasons.every((r) => ReasonInfluence.values.contains(r.influence)), isTrue);
      expect([...detail.topReasons, ...detail.otherReasons], detail.rationale);
      final strengths = detail.rationale.map((r) => r.strength).toList();
      for (var i = 1; i < strengths.length; i++) {
        expect(strengths[i], lessThanOrEqualTo(strengths[i - 1]));
      }
      // الاتفاق بين الأطر من نفس الطريقة
      expect(detail.rationale.whereType<AgreementReason>(), isNotEmpty);
    });

    test('influence labels: High ≥ 0.65, Medium ≥ 0.45, else Low', () {
      expect(const ChanceReason(0.7).influence, ReasonInfluence.high);
      expect(const MaCrossReason(direction: SignalDirection.long, timeframe: Timeframe.h1, gap: 0).influence,
          ReasonInfluence.medium);
      expect(const VolatilityReason(RiskLevel.high).influence, ReasonInfluence.low);
      expect(const RsiReason(direction: SignalDirection.long, timeframe: Timeframe.h1, value: 20).influence,
          ReasonInfluence.medium);
      expect(const RsiReason(direction: SignalDirection.long, timeframe: Timeframe.h1, value: 8).influence,
          ReasonInfluence.high);
      expect(const MaCrossReason(direction: SignalDirection.long, timeframe: Timeframe.h1, gap: 2).influence,
          ReasonInfluence.high);
    });

    test('a neutral outcome is a valid done result with its reason ("No clear setup right now")', () async {
      final setup = _setUp();
      final request = _find(detected: false);
      await _vm(setup.container)
          .request(symbol: request.symbol, timeframe: request.timeframe, methodOverride: request.methodId);
      final state = setup.container.read(requestAnalysisViewModelProvider);
      expect(state, isA<RequestDone>());
      final done = state as RequestDone;
      expect(done.isNoClearSetup, isTrue);
      expect(done.detail.rationale.first, isA<NoSetupReason>());
      expect((done.detail.rationale.first as NoSetupReason).methodId, request.methodId);
      expect(setup.states.whereType<RequestFailed>(), isEmpty);
    });

    test('a double request acts once', () async {
      final gated = _Gated();
      final setup = _setUp(signals: gated);
      final request = _find(detected: true, method: AnalysisMethod.maCrossoverId);
      final vm = _vm(setup.container);
      final first = vm.request(symbol: request.symbol, timeframe: request.timeframe);
      final second = vm.request(symbol: request.symbol, timeframe: request.timeframe);
      await _flush();
      expect(gated.calls.length, 1);
      gated.calls.single.gate.complete();
      await Future.wait([first, second]);
      expect(setup.states.whereType<RequestDone>().length, 1);
    });

    test('cancel stops the request: idle, token cancelled, nothing stored', () async {
      final gated = _Gated();
      final setup = _setUp(signals: gated);
      final request = _find(detected: true, method: AnalysisMethod.maCrossoverId);
      final vm = _vm(setup.container);
      final run = vm.request(symbol: request.symbol, timeframe: request.timeframe);
      await _flush();
      expect(setup.container.read(requestAnalysisViewModelProvider).isBusy, isTrue);
      vm.cancel();
      expect(setup.container.read(requestAnalysisViewModelProvider), isA<RequestIdle>());
      expect(gated.calls.single.cancel!.isCancelled, isTrue);
      gated.calls.single.gate.complete();
      await run;
      expect(setup.container.read(requestAnalysisViewModelProvider), isA<RequestIdle>());
      expect(gated.sim.requestedSignals(kTestNow), isEmpty);
      vm.cancel(); // مش شغّال: ولا شي
      expect(setup.container.read(requestAnalysisViewModelProvider), isA<RequestIdle>());
    });

    test('only the latest request updates the state (race after cancel)', () async {
      final gated = _Gated();
      final setup = _setUp(signals: gated);
      final a = _find(detected: true, method: AnalysisMethod.maCrossoverId);
      final b = _find(detected: true, method: AnalysisMethod.rsiReversalId);
      final vm = _vm(setup.container);
      final runA = vm.request(symbol: a.symbol, timeframe: a.timeframe, methodOverride: a.methodId);
      await _flush();
      vm.cancel();
      final runB = vm.request(symbol: b.symbol, timeframe: b.timeframe, methodOverride: b.methodId);
      await _flush();
      expect(gated.calls.length, 2);
      // B بيخلص أول، بعدين A القديم
      gated.calls[1].gate.complete();
      await runB;
      gated.calls[0].gate.complete();
      await runA;
      final done = setup.container.read(requestAnalysisViewModelProvider) as RequestDone;
      expect(done.request, b);
      expect(setup.states.whereType<RequestDone>().length, 1);
    });

    // A3c: الطرق = الفنية بس (النموذج مش خيار)؛ كل طريقة: مكتشفة + محايدة
    for (final method in AnalysisMethod.knownIds) {
      test('request flow with $method: detected and neutral results carry the method (never ai)', () async {
        final setup = _setUp(
          profiles: _MemoryProfiles(SignalProfile.defaults.copyWith(methodId: method)),
          signals: SimulatedSignalsRepository(source: _source, requestLatencyScale: 0),
        );
        for (final detected in [true, false]) {
          final request = _find(detected: detected, method: method);
          await _vm(setup.container).request(symbol: request.symbol, timeframe: request.timeframe);
          final done = setup.container.read(requestAnalysisViewModelProvider) as RequestDone;
          expect(done.request.methodId, method);
          expect(done.detail.methodId, method);
          expect(done.isNoClearSetup, !detected);
          expect(done.detail.signal.probability, inExclusiveRange(0, 1));
          if (detected) {
            expect(done.detail.rationale.whereType<ChanceReason>(), isNotEmpty, reason: 'model probability reason');
          } else {
            expect(done.detail.rationale.whereType<NoSetupReason>().single.methodId, method);
          }
        }
      });
    }

    test('the saved method is the default request method (MA Crossover when nothing is saved)', () {
      final setup = _setUp();
      expect(_vm(setup.container).savedMethodId, AnalysisMethod.maCrossoverId);
      expect(const AnalysisRequest(symbol: 'EUR/USD', timeframe: Timeframe.h1).methodId, AnalysisMethod.maCrossoverId);
      expect(
        const AnalysisRequest(symbol: 'EUR/USD', timeframe: Timeframe.h1, methodId: AnalysisMethod.legacyAiModelId)
            .isValid,
        isFalse,
      );
    });

    test('the per-request override never changes the saved strategy', () async {
      final profiles = _MemoryProfiles();
      final setup = _setUp(profiles: profiles);
      final request = _find(detected: true, method: AnalysisMethod.rsiReversalId);
      await _vm(setup.container).request(
        symbol: request.symbol,
        timeframe: request.timeframe,
        methodOverride: AnalysisMethod.rsiReversalId,
      );
      final done = setup.container.read(requestAnalysisViewModelProvider) as RequestDone;
      expect(done.detail.methodId, AnalysisMethod.rsiReversalId);
      expect(profiles.writes, 0);
      expect(setup.container.read(signalProfileProvider), SignalProfile.defaults);
      expect(_vm(setup.container).savedMethodId, AnalysisMethod.maCrossoverId);
    });

    test('offline sends nothing and says why; back online a new request works', () async {
      final gated = _Gated();
      final setup = _setUp(signals: gated);
      setup.container.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      expect(setup.container.read(networkStatusProvider), NetworkStatus.offline);
      final request = _find(detected: true, method: AnalysisMethod.maCrossoverId);
      await _vm(setup.container).request(symbol: request.symbol, timeframe: request.timeframe);
      final state = setup.container.read(requestAnalysisViewModelProvider);
      expect(state, isA<RequestFailed>());
      expect((state as RequestFailed).reason, RequestAnalysisFailure.offline);
      expect(gated.calls, isEmpty);

      setup.container.read(networkStatusProvider.notifier).set(NetworkStatus.online);
      final run = _vm(setup.container).request(symbol: request.symbol, timeframe: request.timeframe);
      await _flush();
      gated.calls.single.gate.complete();
      await run;
      expect(setup.container.read(requestAnalysisViewModelProvider), isA<RequestDone>());
    });

    test('a source failure → failed(error); reset → idle; an invalid request → failed(invalid)', () async {
      final gated = _Gated()..fail = StateError('down');
      final setup = _setUp(signals: gated);
      final request = _find(detected: true, method: AnalysisMethod.maCrossoverId);
      final vm = _vm(setup.container);
      final run = vm.request(symbol: request.symbol, timeframe: request.timeframe);
      await _flush();
      gated.calls.single.gate.complete();
      await run;
      expect((setup.container.read(requestAnalysisViewModelProvider) as RequestFailed).reason,
          RequestAnalysisFailure.error);
      vm.reset();
      expect(setup.container.read(requestAnalysisViewModelProvider), isA<RequestIdle>());
      await vm.request(symbol: 'BTC/USD', timeframe: Timeframe.h1);
      expect((setup.container.read(requestAnalysisViewModelProvider) as RequestFailed).reason,
          RequestAnalysisFailure.invalid);
      expect(gated.calls.length, 1);
    });

    test('disposed mid-request: the token is cancelled and nothing is written after', () async {
      final gated = _Gated();
      final setup = _setUp(signals: gated);
      final request = _find(detected: true, method: AnalysisMethod.maCrossoverId);
      final run = _vm(setup.container).request(symbol: request.symbol, timeframe: request.timeframe);
      await _flush();
      setup.sub.close();
      await _flush();
      expect(gated.calls.single.cancel!.isCancelled, isTrue);
      gated.calls.single.gate.complete();
      await run; // ما في استثناء من كتابة بعد الـ dispose
      expect(gated.sim.requestedSignals(kTestNow), isEmpty);
    });

    test('state transitions are guarded (State pattern)', () {
      const r = AnalysisRequest(symbol: 'EUR/USD', timeframe: Timeframe.h1);
      expect(const RequestIdle().canMoveTo(const RequestPending(r)), isTrue);
      expect(const RequestIdle().canMoveTo(const RequestAnalyzing(r)), isFalse);
      expect(const RequestAnalyzing(r).canMoveTo(const RequestPending(r)), isFalse);
      expect(const RequestPending(r).isBusy, isTrue);
      expect(const RequestFailed(RequestAnalysisFailure.offline).isBusy, isFalse);
    });

    test('a requested signal shows at the top of a loaded Signals list, flagged "requested by you"', () async {
      final setup = _setUp();
      setup.container.listen(signalsFeedViewModelProvider, (_, __) {});
      await setup.container.read(signalsFeedViewModelProvider.future);
      final request = _find(detected: true, method: AnalysisMethod.rsiReversalId);
      await _vm(setup.container).request(
        symbol: request.symbol,
        timeframe: request.timeframe,
        methodOverride: request.methodId,
      );
      final done = setup.container.read(requestAnalysisViewModelProvider) as RequestDone;
      final list = setup.container.read(signalsFeedViewModelProvider).value!;
      expect(list.first.id, done.detail.signal.id);
      expect(list.first.requestedByYou, isTrue);
      // التفاصيل بنفس المعرّف (من القائمة)
      final sub = setup.container.listen(signalDetailViewModelProvider(list.first.id), (_, __) {});
      final detail = await setup.container.read(signalDetailViewModelProvider(list.first.id).future);
      expect(detail!.probability, done.detail.probability);
      sub.close();
    });
  });

  group('requested signal on the detail route', () {
    Override instant() => signalsRepositoryProvider.overrideWith(
          (ref) => SimulatedSignalsRepository(source: ref.watch(simulatedMarketSourceProvider), requestLatencyScale: 0),
        );

    testWidgets('/signals/:id?symbol= opens it; after a restart the same id is "not found"', (tester) async {
      usePhoneSize(tester, height: 2400);
      await tester.pumpWidget(await testScope(const TestApp(initialRoute: AppRoutes.signals), overrides: [instant()]));
      await settleMocks(tester);
      final container = ProviderScope.containerOf(tester.element(find.byType(TestApp)));
      container.listen(requestAnalysisViewModelProvider, (_, __) {});
      final request = _find(detected: true, method: AnalysisMethod.maCrossoverId);
      unawaited(container
          .read(requestAnalysisViewModelProvider.notifier)
          .request(symbol: request.symbol, timeframe: request.timeframe, methodOverride: request.methodId));
      await settleMocks(tester);
      final done = container.read(requestAnalysisViewModelProvider) as RequestDone;
      final id = done.detail.signal.id;
      expect(id, startsWith(SimulatedSignalsRepository.requestedPrefix));

      testRouter(tester).go(AppRoutes.signalDetail(id, symbol: request.symbol));
      await settleMocks(tester);
      expect(find.byType(SignalDetailScreen), findsOneWidget);
      expect(find.text('Signal not available'), findsNothing);
      expect(find.textContaining('10-period average'), findsWidgets);

      // إعادة تشغيل: ProviderScope جديد (الذاكرة فاضية)
      await tester.pumpWidget(const SizedBox());
      await tester.pumpWidget(await testScope(
        TestApp(initialRoute: AppRoutes.signalDetail(id, symbol: request.symbol)),
        overrides: [instant()],
      ));
      await settleMocks(tester);
      expect(find.text('Signal not available'), findsOneWidget);
    });
  });
}
