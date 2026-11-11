// E1: networkStatusProvider من مصدر الاتصال الحقيقي (connectivity_plus، هون
// وهمي)، "Simulate offline" (debug) بيفرض offline فوقه، وخطأ network / timeout
// من الـ API بيطلع حالة الـ offline الموجودة بالشاشة.

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/app/router/app_routes.dart';
import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/network/api_exception.dart';
import 'package:trading_app/core/network/connectivity_source.dart';
import 'package:trading_app/core/widgets/offline_banner.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/markets/data/simulated_market_source.dart';
import 'package:trading_app/features/signals/data/signals_repository.dart';
import 'package:trading_app/features/signals/models/analysis_method.dart';
import 'package:trading_app/features/signals/models/analysis_request.dart';
import 'package:trading_app/features/signals/models/model_accuracy.dart';
import 'package:trading_app/features/signals/models/opportunity.dart';
import 'package:trading_app/features/signals/models/signal_profile.dart';
import 'package:trading_app/features/signals/view_models/signals_feed_view_model.dart';

import '../../helpers/test_app.dart';

final class _FailingSource implements ConnectivitySource {
  @override
  Future<NetworkStatus> current() => Future.error(StateError('no plugin'));

  @override
  Stream<NetworkStatus> changes() => Stream.error(StateError('no plugin'));
}

/// Signals عـ "API" ما بيوصل: القائمة بتفشل network → SignalsOfflineException
final class _UnreachableSignals implements SignalsRepository {
  _UnreachableSignals() : _sim = SimulatedSignalsRepository(source: SimulatedMarketSource(clock: () => kTestNow));

  final SignalsRepository _sim;
  int feedCalls = 0;

  @override
  bool get isSimulated => false;

  @override
  Future<List<Opportunity>> feed(SignalProfile profile) {
    feedCalls++;
    return Future<List<Opportunity>>.error(const ApiException(ApiErrorKind.network))
        .offlineAs(() => const SignalsOfflineException());
  }

  @override
  Future<Opportunity?> opportunity(String id) => _sim.opportunity(id);

  @override
  Future<Opportunity> requestAnalysis(
    AnalysisRequest request, {
    AnalysisCancelToken? cancel,
    void Function(AnalysisStage stage)? onStage,
  }) =>
      throw UnimplementedError();

  @override
  Future<List<Opportunity>> opportunities(String symbol, {String methodId = AnalysisMethod.defaultId}) => _sim.opportunities(symbol, methodId: methodId);

  @override
  Future<ModelAccuracy> accuracy() => _sim.accuracy();
}

void main() {
  test('connectivity results → status: any network = online, none / nothing = offline', () {
    expect(networkStatusFrom([ConnectivityResult.wifi]), NetworkStatus.online);
    expect(networkStatusFrom([ConnectivityResult.mobile, ConnectivityResult.vpn]), NetworkStatus.online);
    expect(networkStatusFrom([ConnectivityResult.none, ConnectivityResult.ethernet]), NetworkStatus.online);
    expect(networkStatusFrom([ConnectivityResult.none]), NetworkStatus.offline);
    expect(networkStatusFrom(const []), NetworkStatus.offline);
  });

  group('networkStatusProvider', () {
    (ProviderContainer, FakeConnectivitySource) setUpWith(NetworkStatus initial) {
      final device = FakeConnectivitySource(initial);
      final container = ProviderContainer(overrides: [connectivityOverride(device)]);
      addTearDown(container.dispose);
      container.listen(networkStatusProvider, (_, __) {});
      return (container, device);
    }

    test('reads the device state at start (online until the first read)', () async {
      final (c, _) = setUpWith(NetworkStatus.offline);
      expect(c.read(networkStatusProvider), NetworkStatus.online);
      await pumpEventQueue();
      expect(c.read(networkStatusProvider), NetworkStatus.offline);
    });

    test('follows device changes', () async {
      final (c, device) = setUpWith(NetworkStatus.online);
      await pumpEventQueue();
      device.emit(NetworkStatus.offline);
      await pumpEventQueue();
      expect(c.read(networkStatusProvider), NetworkStatus.offline);
      device.emit(NetworkStatus.online);
      await pumpEventQueue();
      expect(c.read(networkStatusProvider), NetworkStatus.online);
    });

    test('debug "Simulate offline" forces offline over the device; off returns to the device state', () async {
      final (c, device) = setUpWith(NetworkStatus.online);
      await pumpEventQueue();
      c.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      expect(c.read(networkStatusProvider), NetworkStatus.offline);
      expect(c.read(simulatedOfflineProvider), isTrue);
      device.emit(NetworkStatus.online);
      await pumpEventQueue();
      expect(c.read(networkStatusProvider), NetworkStatus.offline, reason: 'still forced');

      device.emit(NetworkStatus.offline);
      await pumpEventQueue();
      c.read(networkStatusProvider.notifier).set(NetworkStatus.online);
      expect(c.read(networkStatusProvider), NetworkStatus.offline, reason: 'the device itself is offline');
      device.emit(NetworkStatus.online);
      await pumpEventQueue();
      expect(c.read(networkStatusProvider), NetworkStatus.online);
    });

    test('a source that fails (no plugin) leaves the app online, no crash', () async {
      final c = ProviderContainer(overrides: [connectivitySourceProvider.overrideWithValue(_FailingSource())]);
      addTearDown(c.dispose);
      c.listen(networkStatusProvider, (_, __) {});
      await pumpEventQueue();
      expect(c.read(networkStatusProvider), NetworkStatus.online);
    });
  });

  group('on screen', () {
    testWidgets('the offline banner follows the device connection', (tester) async {
      final device = FakeConnectivitySource();
      usePhoneSize(tester);
      await tester.pumpWidget(await testScope(const TestApp(), overrides: [connectivityOverride(device)]));
      await settleMocks(tester);
      final banner = find.descendant(
        of: find.byType(OfflineBanner),
        matching: find.textContaining('Showing the last received data.', findRichText: true),
      );
      expect(banner, findsNothing);

      device.emit(NetworkStatus.offline);
      await tester.pumpAndSettle();
      expect(banner, findsOneWidget);

      device.emit(NetworkStatus.online);
      await tester.pumpAndSettle();
      expect(banner, findsNothing);
    });

    testWidgets('an API network error shows the screen’s existing offline state', (tester) async {
      final repo = _UnreachableSignals();
      usePhoneSize(tester);
      await tester.pumpWidget(await testScope(
        const TestApp(initialRoute: AppRoutes.signals),
        overrides: [signalsRepositoryProvider.overrideWithValue(repo)],
      ));
      await settleMocks(tester);
      expect(repo.feedCalls, greaterThan(0));
      expect(find.text('Signals will load when you’re back online.'), findsOneWidget);
      expect(find.text('Signals could not be loaded.'), findsNothing);
    });
  });
}
