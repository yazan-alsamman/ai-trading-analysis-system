import 'package:dio/dio.dart';

import 'api_config.dart';
import 'api_exception.dart';

// ═══════════════════════════════════════════════════════════
// ApiClient - كل طلبات الـ backend بتمرّ من هون (dio)
// ═══════════════════════════════════════════════════════════
//
// - العنوان والمهل من [ApiConfig] (--dart-define، ما في أسرار بالكود).
// - JSON بالاتجاهين (`Accept` + `Content-Type: application/json`).
// - أي فشل بيطلع [ApiException] بس (ولا مرة DioException).
// - الـ token والـ refresh: [AuthInterceptor] (بيضيفه apiClientProvider).
// - الـ repositories بتاخد [ApiClient] وبتحوّل الـ JSON لـ models (متل الـ DTOs
//   الموجودة). [decode] بيرمي → ApiException(server): استجابة ما بتنفهم.

typedef JsonDecoder<T> = T Function(Object? json);

final class ApiClient {
  ApiClient({required ApiConfig config, HttpClientAdapter? adapter, DateTime Function()? now})
      : _now = now ?? DateTime.now,
        dio = Dio(
          BaseOptions(
            baseUrl: config.baseUrl,
            connectTimeout: config.connectTimeout,
            sendTimeout: config.sendTimeout,
            receiveTimeout: config.receiveTimeout,
            contentType: Headers.jsonContentType,
            responseType: ResponseType.json,
            headers: const {Headers.acceptHeader: Headers.jsonContentType},
          ),
        ) {
    if (adapter != null) dio.httpClientAdapter = adapter;
  }

  /// الـ Dio نفسه (للـ interceptors والاختبارات - الـ repositories بتستخدم الدوال تحت)
  final Dio dio;
  final DateTime Function() _now;

  Future<T> get<T>(String path, {Map<String, Object?>? query, required JsonDecoder<T> decode, Options? options}) =>
      _send(() => dio.get<Object?>(path, queryParameters: query, options: options), decode);

  Future<T> post<T>(String path, {Object? body, Map<String, Object?>? query, required JsonDecoder<T> decode, Options? options}) =>
      _send(() => dio.post<Object?>(path, data: body, queryParameters: query, options: options), decode);

  Future<T> put<T>(String path, {Object? body, required JsonDecoder<T> decode, Options? options}) =>
      _send(() => dio.put<Object?>(path, data: body, options: options), decode);

  Future<T> patch<T>(String path, {Object? body, required JsonDecoder<T> decode, Options? options}) =>
      _send(() => dio.patch<Object?>(path, data: body, options: options), decode);

  /// 204 بدون جسم → [decode] بياخد null
  Future<T> delete<T>(String path, {Object? body, required JsonDecoder<T> decode, Options? options}) =>
      _send(() => dio.delete<Object?>(path, data: body, options: options), decode);

  Future<T> _send<T>(Future<Response<Object?>> Function() request, JsonDecoder<T> decode) async {
    final Response<Object?> response;
    try {
      response = await request();
    } on DioException catch (e) {
      throw ApiException.fromDio(e, now: _now);
    }
    try {
      return decode(response.data);
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException(
        ApiErrorKind.server,
        statusCode: response.statusCode,
        message: 'Unexpected response: $e',
        requestId: response.headers.value('x-request-id'),
      );
    }
  }

  void close() => dio.close(force: true);
}
