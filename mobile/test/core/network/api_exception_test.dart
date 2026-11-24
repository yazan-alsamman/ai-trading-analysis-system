import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:trading_app/core/network/api_exception.dart';
import 'package:trading_app/features/signals/view_models/signals_feed_view_model.dart';

import '../../helpers/fake_api.dart';

final _now = DateTime.utc(2026, 10, 21, 14, 5);

Headers _headers(Map<String, String> values) => Headers.fromMap({for (final e in values.entries) e.key: [e.value]});

void main() {
  group('status codes → kinds', () {
    const cases = {
      401: ApiErrorKind.unauthorized,
      403: ApiErrorKind.forbidden,
      404: ApiErrorKind.notFound,
      409: ApiErrorKind.conflict,
      400: ApiErrorKind.validation,
      422: ApiErrorKind.validation,
      429: ApiErrorKind.rateLimited,
      500: ApiErrorKind.server,
      503: ApiErrorKind.server,
      418: ApiErrorKind.unknown,
    };
    for (final entry in cases.entries) {
      test('${entry.key} → ${entry.value.name}', () {
        final error = ApiException.fromResponse(entry.key, body: const {'detail': 'nope'});
        expect(error.kind, entry.value);
        expect(error.statusCode, entry.key);
        expect(error.message, 'nope');
      });
    }

    test('422: FastAPI field errors by field name', () {
      final error = ApiException.fromResponse(422, body: const {
        'detail': [
          {'loc': ['body', 'email'], 'msg': 'value is not a valid email address', 'type': 'value_error'},
          {'loc': ['body', 'password'], 'msg': 'String should have at least 8 characters', 'type': 'string_too_short'},
        ],
      });
      expect(error.kind, ApiErrorKind.validation);
      expect(error.fieldErrors, {
        'email': 'value is not a valid email address',
        'password': 'String should have at least 8 characters',
      });
      expect(error.message, 'value is not a valid email address');
    });

    test('a body that is not the backend shape still maps by status; X-Request-ID kept', () {
      final error = ApiException.fromResponse(500, body: 'Internal Server Error', headers: _headers(const {'X-Request-ID': 'req-1'}));
      expect(error.kind, ApiErrorKind.server);
      expect(error.message, isNull);
      expect(error.requestId, 'req-1');
    });
  });

  group('429 reset time', () {
    test('Retry-After seconds → retryAfter and resetAt', () {
      final error = ApiException.fromResponse(
        429,
        body: const {'detail': 'Rate limit exceeded', 'retry_after': 30},
        headers: _headers(const {'Retry-After': '30', 'RateLimit-Reset': '30'}),
        now: () => _now,
      );
      expect(error.kind, ApiErrorKind.rateLimited);
      expect(error.retryAfter, const Duration(seconds: 30));
      expect(error.resetAt, _now.add(const Duration(seconds: 30)));
    });

    test('Retry-After as an HTTP date', () {
      final error = ApiException.fromResponse(
        429,
        headers: _headers(const {'Retry-After': 'Wed, 21 Oct 2026 14:07:00 GMT'}),
        now: () => _now,
      );
      expect(error.retryAfter, const Duration(minutes: 2));
      expect(error.resetAt, DateTime.utc(2026, 10, 21, 14, 7));
    });

    test('only the body retry_after', () {
      final error = ApiException.fromResponse(429, body: const {'detail': 'Rate limit exceeded', 'retry_after': 12}, now: () => _now);
      expect(error.resetAt, _now.add(const Duration(seconds: 12)));
    });

    test('only RateLimit-Reset', () {
      final error = ApiException.fromResponse(429, headers: _headers(const {'RateLimit-Reset': '45'}), now: () => _now);
      expect(error.resetAt, _now.add(const Duration(seconds: 45)));
    });

    test('no reset information → resetAt null (still rateLimited)', () {
      final error = ApiException.fromResponse(429, body: const {'detail': 'Rate limit exceeded'});
      expect(error.kind, ApiErrorKind.rateLimited);
      expect(error.retryAfter, isNull);
      expect(error.resetAt, isNull);
    });

    test('503 keeps retryAfter but has no resetAt', () {
      final error = ApiException.fromResponse(503, body: const {'detail': 'Server busy', 'retry_after': 2}, now: () => _now);
      expect(error.kind, ApiErrorKind.server);
      expect(error.retryAfter, const Duration(seconds: 2));
      expect(error.resetAt, isNull);
    });

    test('HTTP date parser rejects junk', () {
      expect(parseHttpDate('Wed, 21 Oct 2026 14:07:00 GMT'), DateTime.utc(2026, 10, 21, 14, 7));
      expect(() => parseHttpDate('tomorrow'), throwsFormatException);
    });
  });

  group('through ApiClient (fake adapter)', () {
    Future<ApiException> failureOf(FakeReply reply) async {
      final adapter = FakeApiAdapter((_) => reply);
      final client = fakeApiClient(adapter, now: () => _now);
      try {
        await client.get('/anything', decode: passJson);
      } on ApiException catch (e) {
        return e;
      }
      fail('expected an ApiException');
    }

    test('connection error → network (offline)', () async {
      final error = await failureOf(FakeReply.fail((o) => DioException.connectionError(requestOptions: o, reason: 'no route')));
      expect(error.kind, ApiErrorKind.network);
      expect(error.isOffline, isTrue);
    });

    test('connect / receive timeouts → timeout (offline)', () async {
      final connect = await failureOf(FakeReply.fail(
        (o) => DioException.connectionTimeout(requestOptions: o, timeout: const Duration(seconds: 10)),
      ));
      final receive = await failureOf(FakeReply.fail(
        (o) => DioException.receiveTimeout(requestOptions: o, timeout: const Duration(seconds: 20)),
      ));
      expect(connect.kind, ApiErrorKind.timeout);
      expect(receive.kind, ApiErrorKind.timeout);
      expect(connect.isOffline && receive.isOffline, isTrue);
    });

    test('404 with the backend body', () async {
      final error = await failureOf(const FakeReply(404, {'detail': 'Workspace not found'}));
      expect(error.kind, ApiErrorKind.notFound);
      expect(error.message, 'Workspace not found');
      expect(error.isOffline, isFalse);
    });

    test('429 through the client carries the reset time', () async {
      final error = await failureOf(const FakeReply(429, {'detail': 'Rate limit exceeded', 'retry_after': 60}, {'Retry-After': '60'}));
      expect(error.kind, ApiErrorKind.rateLimited);
      expect(error.resetAt, _now.add(const Duration(minutes: 1)));
    });

    test('JSON in and out; a body the decoder rejects → server', () async {
      final adapter = FakeApiAdapter((o) => FakeReply(200, {'echo': o.data, 'accept': o.headers['Accept']}));
      final client = fakeApiClient(adapter);
      final echo = await client.post('/echo', body: const {'a': 1}, decode: (json) => json! as Map);
      expect(echo['echo'], {'a': 1});
      expect(echo['accept'], 'application/json');
      expect(adapter.requests.single.uri.toString(), '$kTestApiBaseUrl/echo');

      await expectLater(
        client.get('/echo', decode: (json) => (json! as Map)['missing'] as String),
        throwsA(isA<ApiException>().having((e) => e.kind, 'kind', ApiErrorKind.server)),
      );
    });
  });

  group('offline mapping', () {
    test('network / timeout become the feature offline exception', () async {
      await expectLater(
        Future<int>.error(const ApiException(ApiErrorKind.network)).offlineAs(() => const SignalsOfflineException()),
        throwsA(isA<SignalsOfflineException>()),
      );
      await expectLater(
        Future<int>.error(const ApiException(ApiErrorKind.timeout)).offlineAs(() => const SignalsOfflineException()),
        throwsA(isA<SignalsOfflineException>()),
      );
    });

    test('other errors pass through unchanged; values too', () async {
      await expectLater(
        Future<int>.error(const ApiException(ApiErrorKind.server)).offlineAs(() => const SignalsOfflineException()),
        throwsA(isA<ApiException>().having((e) => e.kind, 'kind', ApiErrorKind.server)),
      );
      expect(await Future.value(7).offlineAs(() => const SignalsOfflineException()), 7);
    });
  });
}
