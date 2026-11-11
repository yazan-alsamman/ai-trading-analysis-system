// E1: الإعدادات (API_BASE_URL / USE_REAL_API) ونقطة التبديل لكل ميزة.

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:trading_app/core/network/api_config.dart';
import 'package:trading_app/core/network/api_providers.dart';
import 'package:trading_app/core/network/auth_interceptor.dart';
import 'package:trading_app/core/storage/preferences_provider.dart';
import 'package:trading_app/features/alerts/data/alerts_repository.dart';
import 'package:trading_app/features/markets/data/market_data_repository.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';

final _probe = Provider.family<String, bool>(
  (ref, withReal) => apiSource(
    ref,
    ApiFeature.news,
    simulated: () => 'simulated',
    real: withReal ? () => 'real' : null,
  ),
);

ProviderContainer _container(Set<ApiFeature> real, [List<Override> extra = const []]) {
  final c = ProviderContainer(overrides: [
    apiConfigProvider.overrideWithValue(ApiConfig(baseUrl: 'https://api.test.invalid/api/v1', realApi: real)),
    ...extra,
  ]);
  addTearDown(c.dispose);
  return c;
}

void main() {
  test('default config: clearly fake dev URL, every feature simulated', () {
    final config = ApiConfig.fromEnvironment();
    expect(config.baseUrl, ApiConfig.fakeDevBaseUrl);
    expect(Uri.parse(config.baseUrl).host, endsWith('.invalid'));
    expect(config.realApi, isEmpty);
    expect(config.connectTimeout, const Duration(seconds: 10));
  });

  test('USE_REAL_API parsing: names, spaces, unknown names ignored', () {
    expect(ApiConfig.parseRealApi(''), isEmpty);
    expect(ApiConfig.parseRealApi('auth, markets ,nope,'), {ApiFeature.auth, ApiFeature.markets});
  });

  test('apiSource: simulated by default; real only when the flag is on and a real repository exists', () {
    expect(_container({}).read(_probe(true)), 'simulated');
    expect(_container({ApiFeature.news}).read(_probe(true)), 'real');
    expect(_container({ApiFeature.news}).read(_probe(false)), 'simulated', reason: 'not built yet → stays simulated');
    expect(_container({ApiFeature.auth}).read(_probe(true)), 'simulated', reason: 'another feature’s flag');
  });

  test('feature providers go through the switch and stay simulated (no repository connected in E1)', () async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    final c = _container(ApiFeature.values.toSet(), [sharedPreferencesProvider.overrideWithValue(prefs)]);
    // H4a: simulated alerts are stored locally (LocalAlertsRepository extends the in-memory one)
    expect(c.read(alertsRepositoryProvider), isA<LocalAlertsRepository>());
    expect(c.read(marketDataRepositoryProvider), isA<SimulatedMarketDataRepository>());
  });

  test('apiClientProvider: base URL and timeouts from the config, auth interceptor installed', () {
    final client = _container({}).read(apiClientProvider);
    expect(client.dio.options.baseUrl, 'https://api.test.invalid/api/v1');
    expect(client.dio.options.receiveTimeout, const Duration(seconds: 20));
    expect(client.dio.interceptors.whereType<AuthInterceptor>(), hasLength(1));
  });
}
