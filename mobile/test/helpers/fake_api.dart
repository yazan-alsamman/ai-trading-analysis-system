import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:trading_app/core/network/api_client.dart';
import 'package:trading_app/core/network/api_config.dart';
import 'package:trading_app/core/network/auth_interceptor.dart';
import 'package:trading_app/core/network/token_store.dart';

/// عنوان الاختبارات (ما في شبكة حقيقية: كل الطلبات بتوقف عند [FakeApiAdapter])
const kTestApiBaseUrl = 'https://api.test.invalid/api/v1';

/// رد وهمي: جسم JSON + رمز حالة + headers، أو [error] (فشل اتصال / مهلة)
final class FakeReply {
  const FakeReply(this.status, [this.body, this.headers = const {}]) : error = null;

  const FakeReply.fail(DioException Function(RequestOptions options) this.error)
      : status = 0,
        body = null,
        headers = const {};

  final int status;
  final Object? body;
  final Map<String, String> headers;
  final DioException Function(RequestOptions options)? error;
}

/// adapter بدل الشبكة: [handler] بيقرّر الرد لكل طلب، و[requests] بيسجّلهم
final class FakeApiAdapter implements HttpClientAdapter {
  FakeApiAdapter(this.handler);

  FutureOr<FakeReply> Function(RequestOptions options) handler;
  final List<RequestOptions> requests = [];

  /// الطلبات على [path] (آخر جزء من المسار)
  List<RequestOptions> to(String path) => [for (final r in requests) if (r.uri.path.endsWith(path)) r];

  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<Uint8List>? requestStream, Future<void>? cancelFuture) async {
    requests.add(options);
    final reply = await handler(options);
    if (reply.error case final error?) throw error(options);
    return ResponseBody.fromString(
      reply.body == null ? '' : jsonEncode(reply.body),
      reply.status,
      headers: {
        if (reply.body != null) Headers.contentTypeHeader: [Headers.jsonContentType],
        for (final h in reply.headers.entries) h.key.toLowerCase(): [h.value],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

/// ApiClient على [adapter] (+ AuthInterceptor إذا في [tokens])
ApiClient fakeApiClient(
  FakeApiAdapter adapter, {
  TokenStore? tokens,
  Future<void> Function()? onSessionExpired,
  DateTime Function()? now,
}) {
  final client = ApiClient(config: const ApiConfig(baseUrl: kTestApiBaseUrl), adapter: adapter, now: now);
  if (tokens != null) {
    client.dio.interceptors.add(AuthInterceptor(
      dio: client.dio,
      tokens: tokens,
      onSessionExpired: onSessionExpired ?? () async {},
    ));
  }
  return client;
}

/// JWT وهمي (توقيع مش مهم - التطبيق بيقرأ `exp` بس)
String fakeJwt({required DateTime expires, String sub = 'u1', String type = 'refresh'}) {
  String part(Map<String, Object> json) => base64Url.encode(utf8.encode(jsonEncode(json))).replaceAll('=', '');
  return '${part({'alg': 'HS256', 'typ': 'JWT'})}.${part({'sub': sub, 'type': type, 'exp': expires.millisecondsSinceEpoch ~/ 1000})}.sig';
}

/// جسم `TokenPair` تبع الـ backend
Map<String, Object> tokenPairJson(String access, String refresh) =>
    {'access_token': access, 'refresh_token': refresh, 'token_type': 'bearer', 'expires_in': 900};

Object? passJson(Object? json) => json;
