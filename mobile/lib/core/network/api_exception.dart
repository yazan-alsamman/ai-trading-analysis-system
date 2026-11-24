import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

// ═══════════════════════════════════════════════════════════
// ApiException - خطأ واحد مفهوم لكل طلب فشل
// ═══════════════════════════════════════════════════════════
//
// الـ repositories ما بتشوف DioException أبدًا: ApiClient بيحوّلها لهون حسب
// نوع الفشل ورمز الحالة وجسم الخطأ تبع الـ backend (FastAPI):
//   {"detail": "نص"}                                 ← أغلب الأخطاء
//   {"detail": [{"loc": [...], "msg": "..."}]}       ← 422 (حقول)
//   {"detail": "Rate limit exceeded", "retry_after": N} + Retry-After / RateLimit-Reset ← 429

enum ApiErrorKind {
  /// ما في وصول للسيرفر (ما في نت، DNS، الاتصال انقطع)
  network,

  /// الطلب طوّل أكتر من المهلة
  timeout,

  /// 401 - الجلسة مش صالحة (الـ interceptor بيجرّب refresh مرة قبلها)
  unauthorized,

  /// 403
  forbidden,

  /// 404
  notFound,

  /// 409 (اسم مكرّر، نسخة أقدم من يلي عالسيرفر...)
  conflict,

  /// 400 / 422 - البيانات المرسلة مرفوضة
  validation,

  /// 429 - [ApiException.resetAt] إذا الاستجابة فيها وقت
  rateLimited,

  /// 5xx، أو استجابة ما بتنفهم
  server,

  /// أي شي تاني (طلب انلغى، شهادة مرفوضة، رمز غير متوقّع)
  unknown,
}

@immutable
final class ApiException implements Exception {
  const ApiException(
    this.kind, {
    this.statusCode,
    this.message,
    this.fieldErrors = const {},
    this.retryAfter,
    this.resetAt,
    this.requestId,
  });

  final ApiErrorKind kind;
  final int? statusCode;

  /// `detail` من الـ backend (للسجلات - الواجهة بتعرض نصها المترجم حسب [kind])
  final String? message;

  /// 422: اسم الحقل (آخر جزء من `loc`) → الرسالة
  final Map<String, String> fieldErrors;

  /// 429 / 503: بعد قديش منجرّب
  final Duration? retryAfter;

  /// 429: إيمتى بينفتح الحد من جديد (وقت الجهاز)
  final DateTime? resetAt;

  /// `X-Request-ID` - للدعم والسجلات
  final String? requestId;

  /// ما في اتصال أو طوّل: الشاشات بتعرض حالة "غير متصل" يلي عندها
  bool get isOffline => kind == ApiErrorKind.network || kind == ApiErrorKind.timeout;

  /// يحوّل خطأ dio لـ [ApiException] ([now] للاختبارات - وقت حساب [resetAt])
  factory ApiException.fromDio(DioException error, {DateTime Function() now = DateTime.now}) {
    final inner = error.error;
    if (inner is ApiException) return inner;
    switch (error.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.transformTimeout:
        return const ApiException(ApiErrorKind.timeout);
      case DioExceptionType.connectionError:
        return const ApiException(ApiErrorKind.network);
      case DioExceptionType.cancel:
      case DioExceptionType.badCertificate:
        return ApiException(ApiErrorKind.unknown, message: error.message);
      case DioExceptionType.badResponse:
        final response = error.response;
        if (response == null) return const ApiException(ApiErrorKind.server);
        return ApiException.fromResponse(
          response.statusCode ?? 0,
          body: response.data,
          headers: response.headers,
          now: now,
        );
      case DioExceptionType.unknown:
        // SocketException / HandshakeException وصلوا هون بدون نوع: ما في وصول
        return ApiException(ApiErrorKind.network, message: inner?.toString());
    }
  }

  /// من رمز الحالة + جسم الخطأ + الـ headers
  factory ApiException.fromResponse(
    int status, {
    Object? body,
    Headers? headers,
    DateTime Function() now = DateTime.now,
  }) {
    final detail = body is Map ? body['detail'] : null;
    final message = detail is String ? detail : null;
    final requestId = headers?.value('x-request-id');
    final fields = status == 422 ? _fieldErrors(detail) : const <String, String>{};
    final retryAfter = (status == 429 || status == 503) ? _retryAfter(body, headers, now()) : null;

    final kind = switch (status) {
      401 => ApiErrorKind.unauthorized,
      403 => ApiErrorKind.forbidden,
      404 => ApiErrorKind.notFound,
      409 => ApiErrorKind.conflict,
      400 || 422 => ApiErrorKind.validation,
      429 => ApiErrorKind.rateLimited,
      >= 500 && < 600 => ApiErrorKind.server,
      _ => ApiErrorKind.unknown,
    };
    return ApiException(
      kind,
      statusCode: status,
      message: message ?? (fields.isNotEmpty ? fields.values.first : null),
      fieldErrors: fields,
      retryAfter: retryAfter,
      resetAt: kind == ApiErrorKind.rateLimited && retryAfter != null ? now().add(retryAfter) : null,
      requestId: requestId,
    );
  }

  /// 422 تبع FastAPI: [{"loc": ["body", "email"], "msg": "..."}]
  static Map<String, String> _fieldErrors(Object? detail) {
    if (detail is! List) return const {};
    final result = <String, String>{};
    for (final item in detail) {
      if (item is! Map) continue;
      final loc = item['loc'];
      final msg = item['msg'];
      if (msg is! String) continue;
      final field = loc is List && loc.isNotEmpty ? '${loc.last}' : '';
      result.putIfAbsent(field, () => msg);
    }
    return result;
  }

  /// الترتيب: Retry-After (ثواني أو تاريخ HTTP)، بعدين `retry_after` بالجسم،
  /// بعدين RateLimit-Reset (ثواني لحد ما ينفتح الحد)
  static Duration? _retryAfter(Object? body, Headers? headers, DateTime now) {
    final header = headers?.value('retry-after')?.trim();
    if (header != null && header.isNotEmpty) {
      final seconds = int.tryParse(header);
      if (seconds != null && seconds >= 0) return Duration(seconds: seconds);
      final date = _httpDate(header);
      if (date != null) {
        final wait = date.difference(now.toUtc());
        return wait.isNegative ? Duration.zero : wait;
      }
    }
    final fromBody = body is Map ? body['retry_after'] : null;
    if (fromBody is num && fromBody >= 0) return Duration(milliseconds: (fromBody * 1000).round());
    final reset = int.tryParse(headers?.value('ratelimit-reset')?.trim() ?? '');
    if (reset != null && reset >= 0) return Duration(seconds: reset);
    return null;
  }

  static DateTime? _httpDate(String value) {
    try {
      return parseHttpDate(value);
    } catch (_) {
      return null;
    }
  }

  @override
  String toString() =>
      'ApiException(${kind.name}${statusCode == null ? '' : ', $statusCode'}${message == null ? '' : ', $message'})';
}

/// تحويل network / timeout لاستثناء "غير متصل" تبع الميزة، حتى الشاشة تعرض
/// حالة الـ offline يلي عندها (ومتل ما هي بترجع تحمّل لما يرجع الاتصال):
///   repo.signals().offlineAs(() => const SignalsOfflineException())
extension ApiOfflineMapping<T> on Future<T> {
  Future<T> offlineAs(Object Function() offline) => catchError(
        (Object _) => throw offline(),
        test: (error) => error is ApiException && error.isOffline,
      );
}

/// تواريخ HTTP (RFC 7231): "Wed, 21 Oct 2026 14:05:00 GMT" → UTC (بدون dart:io)
@visibleForTesting
DateTime parseHttpDate(String value) {
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  final match = RegExp(r'^\w{3}, (\d{2}) (\w{3}) (\d{4}) (\d{2}):(\d{2}):(\d{2}) GMT$').firstMatch(value.trim());
  if (match == null) throw FormatException('Not an HTTP date', value);
  final month = months.indexOf(match.group(2)!) + 1;
  if (month == 0) throw FormatException('Bad month', value);
  return DateTime.utc(
    int.parse(match.group(3)!),
    month,
    int.parse(match.group(1)!),
    int.parse(match.group(4)!),
    int.parse(match.group(5)!),
    int.parse(match.group(6)!),
  );
}
