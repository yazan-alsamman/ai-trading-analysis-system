// اختبارات ViewModels تبع Signals (بدون واجهة): القائمة (تحميل، خطأ، بدون
// اتصال، تغيير الاستراتيجية أثناء التحميل، تحديثات ورا بعض) والتفاصيل
// (مش موجودة، خطأ، بدون اتصال، من القائمة، إشارة بتخلص والشاشة مفتوحة).

import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/core/data/clock.dart';
import 'package:trading_app/core/data/json.dart';
import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/signals/data/opportunity_dto.dart';
import 'package:trading_app/features/signals/data/signal_profile_repository.dart';
import 'package:trading_app/features/signals/data/signals_repository.dart';
import 'package:trading_app/features/signals/models/analysis_method.dart';
import 'package:trading_app/features/signals/models/analysis_request.dart';
import 'package:trading_app/features/signals/models/model_accuracy.dart';
import 'package:trading_app/features/signals/models/opportunity.dart';
import 'package:trading_app/features/signals/models/signal_profile.dart';
import 'package:trading_app/features/signals/models/signal_rationale.dart';
import 'package:trading_app/features/signals/view_models/signal_detail_view_model.dart';
import 'package:trading_app/features/signals/view_models/signals_feed_view_model.dart';

import '../../helpers/test_app.dart';

Opportunity signal(
  String id, {
  String tf = '1h',
  String direction = 'long',
  Duration validFor = const Duration(hours: 1),
}) =>
    OpportunityDto.fromJson(Json({
      'id': id,
      'symbol': 'EUR/USD',
      'timeframe': tf,
      'status': direction == 'neutral' ? 'not_detected' : 'detected',
      'direction': direction,
      'probability': 0.7,
      'entryZone': {'low': 1.0800, 'high': 1.0810},
      'stopLossZone': {'low': 1.0750, 'high': 1.0760},
      'takeProfitZone': {'low': 1.0900, 'high': 1.0910},
      'riskReward': 2,
      'generatedAt': kTestNow.millisecondsSinceEpoch,
      'validUntil': kTestNow.add(validFor).millisecondsSinceEpoch,
    })).toDomain()!;

/// مصدر إشارات بنتحكّم فيه: كل طلب قائمة بيستنى لحد ما نكمّله نحن
final class _Signals implements SignalsRepository {
  final feedCalls = <(SignalProfile, Completer<List<Opportunity>>)>[];
  final byId = <String, Opportunity>{};
  var detailCalls = 0;
  Object? detailError;
  Completer<Opportunity?>? detailGate;
  var siblingsFail = false;

  @override
  bool get isSimulated => true;

  @override
  Future<List<Opportunity>> feed(SignalProfile profile) {
    final completer = Completer<List<Opportunity>>();
    feedCalls.add((profile, completer));
    return completer.future;
  }

  @override
  Future<Opportunity?> opportunity(String id) async {
    detailCalls++;
    if (detailGate case final gate?) return gate.future;
    if (detailError case final error?) throw error;
    return byId[id];
  }

  @override
  Future<Opportunity> requestAnalysis(
    AnalysisRequest request, {
    AnalysisCancelToken? cancel,
    void Function(AnalysisStage stage)? onStage,
  }) =>
      throw UnimplementedError();

  @override
  Future<List<Opportunity>> opportunities(String symbol, {String methodId = AnalysisMethod.defaultId}) async {
    if (siblingsFail) throw StateError('siblings failed');
    return [for (final o in byId.values) if (o.symbol == symbol) o];
  }

  @override
  Future<ModelAccuracy> accuracy() => throw UnimplementedError();
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

(ProviderContainer, _Signals) setUpContainer({List<Override> overrides = const []}) {
  final signals = _Signals();
  final container = ProviderContainer(overrides: [
    connectivityOverride(),
    ...simulatedMarketOverrides(),
    signalsRepositoryProvider.overrideWithValue(signals),
    signalProfileRepositoryProvider.overrideWithValue(_MemoryProfiles()),
    ...overrides,
  ]);
  addTearDown(container.dispose);
  return (container, signals);
}

void goOffline(ProviderContainer c) => c.read(networkStatusProvider.notifier).set(NetworkStatus.offline);

void goOnline(ProviderContainer c) => c.read(networkStatusProvider.notifier).set(NetworkStatus.online);

List<String>? ids(AsyncValue<List<Opportunity>> value) => value.valueOrNull?.map((o) => o.id).toList();

void main() {
  group('SignalsFeedViewModel', () {
    test('loading, then the ranked list for the saved strategy', () async {
      final (c, signals) = setUpContainer();
      c.listen(signalsFeedViewModelProvider, (_, __) {});
      expect(c.read(signalsFeedViewModelProvider).isLoading, isTrue);
      expect(signals.feedCalls.single.$1, SignalProfile.defaults);

      signals.feedCalls.single.$2.complete([signal('a')]);
      await pumpEventQueue();
      expect(ids(c.read(signalsFeedViewModelProvider)), ['a']);
    });

    test('strategy changed while loading: the old answer is dropped', () async {
      final (c, signals) = setUpContainer();
      c.listen(signalsFeedViewModelProvider, (_, __) {});
      final narrower = SignalProfile.defaults.copyWith(symbols: {'EUR/USD'});
      await c.read(signalProfileProvider.notifier).save(narrower);
      c.read(signalsFeedViewModelProvider);
      expect(signals.feedCalls.map((call) => call.$1), [SignalProfile.defaults, narrower]);

      signals.feedCalls[1].$2.complete([signal('new')]);
      signals.feedCalls[0].$2.complete([signal('old')]);
      await pumpEventQueue();
      expect(ids(c.read(signalsFeedViewModelProvider)), ['new']);
    });

    test('rapid refreshes: only the newest answer lands', () async {
      final (c, signals) = setUpContainer();
      c.listen(signalsFeedViewModelProvider, (_, __) {});
      signals.feedCalls.single.$2.complete([signal('first')]);
      await pumpEventQueue();

      final vm = c.read(signalsFeedViewModelProvider.notifier);
      final older = vm.refresh();
      final newer = vm.refresh();
      signals.feedCalls[2].$2.complete([signal('newer')]);
      signals.feedCalls[1].$2.complete([signal('older')]);
      await (older, newer).wait;
      expect(ids(c.read(signalsFeedViewModelProvider)), ['newer']);
    });

    test('a refresh overtaken by a strategy change does not overwrite it', () async {
      final (c, signals) = setUpContainer();
      c.listen(signalsFeedViewModelProvider, (_, __) {});
      signals.feedCalls.single.$2.complete([signal('first')]);
      await pumpEventQueue();

      final refresh = c.read(signalsFeedViewModelProvider.notifier).refresh();
      await c.read(signalProfileProvider.notifier).save(SignalProfile.defaults.copyWith(symbols: {'XAU/USD'}));
      c.read(signalsFeedViewModelProvider);
      signals.feedCalls[2].$2.complete([signal('rebuilt')]);
      signals.feedCalls[1].$2.complete([signal('stale-refresh')]);
      await refresh;
      await pumpEventQueue();
      expect(ids(c.read(signalsFeedViewModelProvider)), ['rebuilt']);
    });

    test('a failed refresh keeps the list and reports the error; an overtaken failure is silent', () async {
      final (c, signals) = setUpContainer();
      c.listen(signalsFeedViewModelProvider, (_, __) {});
      signals.feedCalls.single.$2.complete([signal('kept')]);
      await pumpEventQueue();
      final vm = c.read(signalsFeedViewModelProvider.notifier);

      final failing = vm.refresh();
      signals.feedCalls[1].$2.completeError(StateError('server'));
      await expectLater(failing, throwsStateError);
      expect(ids(c.read(signalsFeedViewModelProvider)), ['kept']);

      final overtaken = vm.refresh();
      final latest = vm.refresh();
      signals.feedCalls[2].$2.completeError(StateError('server'));
      signals.feedCalls[3].$2.complete([signal('latest')]);
      await expectLater(overtaken, completes);
      await latest;
      expect(ids(c.read(signalsFeedViewModelProvider)), ['latest']);
    });

    test('first load error, then Try again', () async {
      final (c, signals) = setUpContainer();
      c.listen(signalsFeedViewModelProvider, (_, __) {});
      signals.feedCalls.single.$2.completeError(StateError('server'));
      await pumpEventQueue();
      expect(c.read(signalsFeedViewModelProvider).error, isStateError);

      final retry = c.read(signalsFeedViewModelProvider.notifier).retry();
      await pumpEventQueue();
      signals.feedCalls[1].$2.complete([signal('a')]);
      await retry;
      expect(ids(c.read(signalsFeedViewModelProvider)), ['a']);
    });

    test('offline: nothing is sent, and it loads by itself when back online', () async {
      final (c, signals) = setUpContainer();
      goOffline(c);
      c.listen(signalsFeedViewModelProvider, (_, __) {});
      await pumpEventQueue();
      expect(c.read(signalsFeedViewModelProvider).error, isA<SignalsOfflineException>());
      expect(signals.feedCalls, isEmpty);
      await expectLater(
        c.read(signalsFeedViewModelProvider.notifier).refresh(),
        throwsA(isA<SignalsOfflineException>()),
      );

      goOnline(c);
      c.read(signalsFeedViewModelProvider);
      signals.feedCalls.single.$2.complete([signal('a')]);
      await pumpEventQueue();
      expect(ids(c.read(signalsFeedViewModelProvider)), ['a']);
    });

    test('a signal that expires while the list is open disappears on the next clock tick', () async {
      final clock = StreamController<DateTime>();
      addTearDown(clock.close);
      final (c, signals) = setUpContainer(overrides: [clockProvider.overrideWith((ref) => clock.stream)]);
      c.listen(visibleSignalsProvider, (_, __) {});
      clock.add(kTestNow);
      signals.feedCalls.single.$2.complete([signal('short', validFor: const Duration(minutes: 1)), signal('long')]);
      await pumpEventQueue();
      expect(ids(c.read(visibleSignalsProvider)), ['short', 'long']);

      clock.add(kTestNow.add(const Duration(minutes: 2)));
      await pumpEventQueue();
      expect(ids(c.read(visibleSignalsProvider)), ['long']);
    });
  });

  group('SignalDetailViewModel', () {
    Future<void> settle(ProviderContainer c, String id) async {
      c.listen(signalDetailViewModelProvider(id), (_, __) {});
      await pumpEventQueue();
    }

    test('loading, then instrument, plan, reasons and validity', () async {
      final (c, signals) = setUpContainer();
      signals.byId
        ..['s'] = signal('s')
        ..['s-4h'] = signal('s-4h', tf: '4h');
      c.listen(signalDetailViewModelProvider('s'), (_, __) {});
      expect(c.read(signalDetailViewModelProvider('s')).isLoading, isTrue);
      await pumpEventQueue();

      final detail = c.read(signalDetailViewModelProvider('s')).value!;
      expect(detail.instrument.symbol, 'EUR/USD');
      expect(detail.plan.targetPips, closeTo(100, 1e-6));
      expect(detail.plan.stopPips, closeTo(50, 1e-6));
      expect(detail.plan.riskReward, 2);
      expect(detail.validUntil, kTestNow.add(const Duration(hours: 1)));
      expect(detail.expired, isFalse);
      final agreement = detail.rationale.whereType<AgreementReason>().single;
      expect((agreement.agreeing, agreement.analysed), (2, 2));
    });

    test('unknown or neutral signal: not found (null)', () async {
      final (c, signals) = setUpContainer();
      signals.byId['flat'] = signal('flat', direction: 'neutral');
      await settle(c, 'missing');
      await settle(c, 'flat');
      final missing = c.read(signalDetailViewModelProvider('missing'));
      expect((missing.hasValue, missing.value, missing.hasError), (true, null, false));
      expect(c.read(signalDetailViewModelProvider('flat')).valueOrNull, isNull);
      expect(c.read(signalDetailViewModelProvider('flat')).hasError, isFalse);
    });

    test('error, then Try again', () async {
      final (c, signals) = setUpContainer();
      signals
        ..byId['s'] = signal('s')
        ..detailError = StateError('server');
      await settle(c, 's');
      expect(c.read(signalDetailViewModelProvider('s')).error, isStateError);

      signals.detailError = null;
      await c.read(signalDetailViewModelProvider('s').notifier).retry();
      expect(c.read(signalDetailViewModelProvider('s')).value?.signal.id, 's');
    });

    test('offline: nothing is sent, and it loads when back online', () async {
      final (c, signals) = setUpContainer();
      signals.byId['s'] = signal('s');
      goOffline(c);
      await settle(c, 's');
      expect(c.read(signalDetailViewModelProvider('s')).error, isA<SignalsOfflineException>());
      expect(signals.detailCalls, 0);

      goOnline(c);
      await pumpEventQueue();
      c.read(signalDetailViewModelProvider('s'));
      await pumpEventQueue();
      expect(c.read(signalDetailViewModelProvider('s')).value?.signal.id, 's');
      expect(signals.detailCalls, 1);
    });

    test('opened from the list: no request, works offline', () async {
      final (c, signals) = setUpContainer();
      c.listen(signalsFeedViewModelProvider, (_, __) {});
      signals.feedCalls.single.$2.complete([signal('listed')]);
      await pumpEventQueue();
      goOffline(c);

      await settle(c, 'listed');
      expect(c.read(signalDetailViewModelProvider('listed')).value?.signal.id, 'listed');
      expect(signals.detailCalls, 0);
    });

    test('other timeframes failing only hides the agreement reason', () async {
      final (c, signals) = setUpContainer();
      signals
        ..byId['s'] = signal('s')
        ..siblingsFail = true;
      await settle(c, 's');
      final detail = c.read(signalDetailViewModelProvider('s')).value!;
      expect(detail.rationale.whereType<AgreementReason>(), isEmpty);
      expect(detail.rationale.whereType<ChanceReason>(), hasLength(1));
    });

    test('already expired when opened: shown as expired', () async {
      final (c, signals) = setUpContainer();
      signals.byId['old'] = signal('old', validFor: const Duration(minutes: -5));
      await settle(c, 'old');
      expect(c.read(signalDetailViewModelProvider('old')).value?.expired, isTrue);
    });

    test('expires while open: marked expired without reloading', () async {
      final (c, signals) = setUpContainer();
      signals.byId['soon'] = signal('soon', validFor: const Duration(milliseconds: 40));
      await settle(c, 'soon');
      expect(c.read(signalDetailViewModelProvider('soon')).value?.expired, isFalse);

      await Future<void>.delayed(const Duration(milliseconds: 120));
      final after = c.read(signalDetailViewModelProvider('soon'));
      expect(after.value?.expired, isTrue);
      expect(after.value?.signal.id, 'soon');
      expect(signals.detailCalls, 1);
    });

    test('closed while loading: the late answer is ignored', () async {
      final (c, signals) = setUpContainer();
      final gate = signals.detailGate = Completer<Opportunity?>();
      final sub = c.listen(signalDetailViewModelProvider('s'), (_, __) {});
      await pumpEventQueue();
      sub.close();
      await pumpEventQueue();

      gate.complete(signal('s', validFor: const Duration(milliseconds: 10)));
      await Future<void>.delayed(const Duration(milliseconds: 50));
      expect(c.exists(signalDetailViewModelProvider('s')), isFalse);
    });
  });
}
