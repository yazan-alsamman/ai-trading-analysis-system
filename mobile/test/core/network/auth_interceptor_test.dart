import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:trading_app/core/network/api_client.dart';
import 'package:trading_app/core/network/api_exception.dart';
import 'package:trading_app/core/network/auth_interceptor.dart';
import 'package:trading_app/core/network/token_store.dart';
import 'package:trading_app/services/secure_storage_service.dart';

import '../../helpers/fake_api.dart';

/// سيرفر وهمي: `/auth/refresh` بيرجّع `new` / `r2`، وأي طلب تاني مقبول بس
/// بالـ token المقبول [valid]
final class _Server {
  String valid = 'new';
  Completer<void>? refreshGate;
  FakeReply refreshReply = FakeReply(200, tokenPairJson('new', 'r2'));

  late final adapter = FakeApiAdapter(_handle);

  Future<FakeReply> _handle(RequestOptions o) async {
    if (o.uri.path.endsWith('/auth/refresh')) {
      if (refreshGate case final gate?) await gate.future;
      return refreshReply;
    }
    return o.headers['Authorization'] == 'Bearer $valid'
        ? FakeReply(200, {'path': o.uri.path})
        : const FakeReply(401, {'detail': 'Could not validate credentials'});
  }

  int get refreshes => adapter.to('/auth/refresh').length;
}

void main() {
  late TokenStore tokens;
  late _Server server;
  late ApiClient client;
  late int expired;

  Future<void> setUpWith({Map<String, String> stored = const {'auth_token': 'old', 'auth_refresh_token': 'r1'}}) async {
    FlutterSecureStorage.setMockInitialValues({...stored});
    tokens = TokenStore(SecureStorageService());
    server = _Server();
    expired = 0;
    client = fakeApiClient(server.adapter, tokens: tokens, onSessionExpired: () async => expired++);
  }

  Future<Object?> get(String path) => client.get(path, decode: passJson);

  test('attaches the saved access token', () async {
    await setUpWith(stored: {'auth_token': 'new', 'auth_refresh_token': 'r1'});
    await get('/users/me');
    expect(server.adapter.requests.single.headers['Authorization'], 'Bearer new');
    expect(server.refreshes, 0);
  });

  test('no saved token → no Authorization header; skipAuth requests never get one', () async {
    await setUpWith(stored: const {});
    server.valid = 'none';
    server.adapter.handler = (o) => const FakeReply(200, {'ok': true});
    await get('/news');
    await client.post('/auth/login', body: {}, decode: passJson, options: Options(extra: {AuthInterceptor.skipAuth: true}));
    expect(server.adapter.requests.map((r) => r.headers.containsKey('Authorization')), [false, false]);
  });

  test('401 → one refresh with the refresh token, new pair saved, request retried once', () async {
    await setUpWith();
    final result = await get('/users/me');
    expect(result, {'path': '/api/v1/users/me'});
    expect(server.refreshes, 1);
    final refresh = server.adapter.to('/auth/refresh').single;
    expect(refresh.data, {'refresh_token': 'r1'});
    expect(refresh.headers.containsKey('Authorization'), isFalse);
    final calls = server.adapter.to('/users/me');
    expect(calls.map((r) => r.headers['Authorization']), ['Bearer old', 'Bearer new']);
    expect(await tokens.accessToken(), 'new');
    expect(await tokens.refreshToken(), 'r2');
    expect(expired, 0);
  });

  test('concurrent 401s share one refresh; a request sent during it waits and goes out with the new token', () async {
    await setUpWith();
    server.refreshGate = Completer<void>();
    final first = [get('/a'), get('/b'), get('/c')];
    await pumpEventQueue();
    expect(server.refreshes, 1);
    final queued = get('/d'); // بيبلّش أثناء الـ refresh
    await pumpEventQueue();
    expect(server.adapter.to('/d'), isEmpty, reason: 'queued until the refresh is done');
    server.refreshGate!.complete();
    final results = await Future.wait([...first, queued]);
    expect(results, hasLength(4));
    expect(server.refreshes, 1);
    expect(server.adapter.to('/d').map((r) => r.headers['Authorization']), ['Bearer new']);
    for (final path in ['/a', '/b', '/c']) {
      expect(server.adapter.to(path).map((r) => r.headers['Authorization']), ['Bearer old', 'Bearer new']);
    }
  });

  test('a 401 that arrives after another request already refreshed only retries', () async {
    await setUpWith(stored: {'auth_token': 'new', 'auth_refresh_token': 'r1'});
    // طلب انبعت بالـ token القديم، وطلب تاني عمل refresh قبل ما يرجع الـ 401
    server.adapter.handler = (o) async {
      if (o.headers['Authorization'] == 'Bearer new') {
        await tokens.save(const TokenPair(accessToken: 'newer', refreshToken: 'r3'));
        return const FakeReply(401, {'detail': 'expired'});
      }
      return FakeReply(200, {'ok': o.headers['Authorization']});
    };
    expect(await get('/late'), {'ok': 'Bearer newer'});
    expect(server.refreshes, 0, reason: 'the token already changed: retry only');
    expect(server.adapter.to('/late'), hasLength(2));
  });

  test('refresh rejected → session ends once, tokens cleared, every caller gets unauthorized', () async {
    await setUpWith();
    server.refreshReply = const FakeReply(401, {'detail': 'Token has expired'});
    final results = await Future.wait([
      for (final p in ['/a', '/b', '/c']) get(p).then<Object?>((v) => v, onError: (Object e) => e),
    ]);
    for (final r in results) {
      expect(r, isA<ApiException>().having((e) => e.kind, 'kind', ApiErrorKind.unauthorized));
    }
    expect(server.refreshes, 1);
    expect(expired, 1);
    expect(await tokens.accessToken(), isNull);
    expect(await tokens.refreshToken(), isNull);
  });

  test('no refresh loop: the retried request 401s again → no second refresh, session ends', () async {
    await setUpWith();
    server.valid = 'never';
    await expectLater(get('/users/me'), throwsA(isA<ApiException>().having((e) => e.kind, 'kind', ApiErrorKind.unauthorized)));
    expect(server.refreshes, 1);
    expect(server.adapter.to('/users/me'), hasLength(2)); // الأصلي + إعادة وحدة
    expect(expired, 1);
  });

  test('no refresh token saved → no refresh call, session ends', () async {
    await setUpWith(stored: {'auth_token': 'old'});
    await expectLater(get('/users/me'), throwsA(isA<ApiException>()));
    expect(server.refreshes, 0);
    expect(expired, 1);
  });

  test('refresh cannot reach the server → session kept, the caller gets the network error (offline state)', () async {
    await setUpWith();
    server.refreshReply = FakeReply.fail((o) => DioException.connectionError(requestOptions: o, reason: 'offline'));
    await expectLater(
      get('/users/me'),
      throwsA(isA<ApiException>().having((e) => e.isOffline, 'isOffline', isTrue)),
    );
    expect(expired, 0);
    expect(await tokens.refreshToken(), 'r1');
  });

  test('refresh 5xx or 429 keeps the session too', () async {
    for (final reply in [const FakeReply(503, {'detail': 'Server busy'}), const FakeReply(429, {'detail': 'Rate limit exceeded'}, {'Retry-After': '5'})]) {
      await setUpWith();
      server.refreshReply = reply;
      await expectLater(get('/users/me'), throwsA(isA<ApiException>()));
      expect(expired, 0);
      expect(await tokens.refreshToken(), 'r1');
    }
  });

  test('a 401 on a skipAuth request (login) never refreshes', () async {
    await setUpWith();
    server.adapter.handler = (o) => const FakeReply(401, {'detail': 'Incorrect email or password'});
    await expectLater(
      client.post('/auth/login', body: {}, decode: passJson, options: Options(extra: {AuthInterceptor.skipAuth: true})),
      throwsA(isA<ApiException>().having((e) => e.kind, 'kind', ApiErrorKind.unauthorized)),
    );
    expect(server.refreshes, 0);
    expect(expired, 0);
  });

  test('JWT exp: valid session only while the refresh token has not expired', () async {
    final now = DateTime.utc(2026, 11, 8, 12);
    FlutterSecureStorage.setMockInitialValues({'auth_refresh_token': fakeJwt(expires: now.add(const Duration(days: 1)))});
    expect(await TokenStore(SecureStorageService()).hasValidSession(now: now), isTrue);
    FlutterSecureStorage.setMockInitialValues({'auth_refresh_token': fakeJwt(expires: now.subtract(const Duration(minutes: 1)))});
    expect(await TokenStore(SecureStorageService()).hasValidSession(now: now), isFalse);
    FlutterSecureStorage.setMockInitialValues({'auth_refresh_token': 'opaque-token'});
    expect(await TokenStore(SecureStorageService()).hasValidSession(now: now), isTrue);
    FlutterSecureStorage.setMockInitialValues({});
    expect(await TokenStore(SecureStorageService()).hasValidSession(now: now), isFalse);
  });
}
