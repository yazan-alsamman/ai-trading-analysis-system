import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import 'api_exception.dart';
import 'token_store.dart';

// ═══════════════════════════════════════════════════════════
// Auth Interceptor - الـ token عكل طلب + refresh مرة وحدة عند 401
// ═══════════════════════════════════════════════════════════
//
// - كل طلب بياخد `Authorization: Bearer <access>` من التخزين الآمن.
// - 401 → refresh واحد بس بنفس الوقت (`POST /auth/refresh`): الطلبات التانية
//   يلي رجعت 401 بتستنّى نفس الـ refresh، والطلبات الجديدة بتستنّاه قبل ما
//   تنبعت، بعدين كل طلب بيتعاد **مرة وحدة** بالـ token الجديد.
// - الـ refresh انرفض (أو الطلب المُعاد رجع 401 كمان) = نهاية الجلسة:
//   [onSessionExpired] (AuthController.endSession: بيمسح الجلسة المحفوظة
//   وبيطلّع المستخدم، والـ router بيرجّعه لـ Welcome). ما في حلقات: طلب الـ
//   refresh نفسه ما بيمرّ من هالمنطق، والطلب المُعاد ما بيعمل refresh.
// - ما في اتصال / السيرفر واقع / 429 أثناء الـ refresh = الجلسة بتضل (مش ذنب
//   المستخدم)، والطلب الأصلي بيفشل بخطأه.

enum _Outcome { ok, failed, unavailable }

/// نتيجة الـ refresh؛ [error] = سبب "unavailable" (بيطلع للطلب الأصلي بدل الـ 401،
/// حتى الشاشة تعرف إنو ما في اتصال مثلًا)
typedef _Refresh = ({_Outcome outcome, DioException? error});

const _Refresh _ok = (outcome: _Outcome.ok, error: null);
const _Refresh _failed = (outcome: _Outcome.failed, error: null);

class AuthInterceptor extends Interceptor {
  AuthInterceptor({
    required Dio dio,
    required TokenStore tokens,
    required Future<void> Function() onSessionExpired,
    this.refreshPath = '/auth/refresh',
  })  : _dio = dio,
        _tokens = tokens,
        _onSessionExpired = onSessionExpired;

  /// `Options(extra: {AuthInterceptor.skipAuth: true})`: بدون token وبدون refresh
  /// (تسجيل الدخول، إنشاء حساب، الـ refresh نفسه)
  static const String skipAuth = 'auth.skip';
  static const String _retried = 'auth.retried';
  static const String _sentToken = 'auth.sentToken';

  final Dio _dio;
  final TokenStore _tokens;
  final Future<void> Function() _onSessionExpired;
  final String refreshPath;

  /// الـ refresh الجاري (واحد بس بنفس الوقت)
  Future<_Refresh>? _refreshing;
  Future<void>? _expiring;

  /// للاختبارات: هل في refresh جاري؟
  @visibleForTesting
  bool get isRefreshing => _refreshing != null;

  @override
  Future<void> onRequest(RequestOptions options, RequestInterceptorHandler handler) async {
    if (options.extra[skipAuth] == true) return handler.next(options);
    try {
      // طلب جديد أثناء refresh: بيستنّى حتى ينبعت بالـ token الجديد
      final pending = _refreshing;
      if (pending != null) await pending;
      final token = await _tokens.accessToken();
      if (token != null && token.isNotEmpty) {
        options.headers['Authorization'] = 'Bearer $token';
      } else {
        options.headers.remove('Authorization');
      }
      options.extra[_sentToken] = token;
      handler.next(options);
    } catch (error, stack) {
      handler.reject(DioException(requestOptions: options, error: error, stackTrace: stack));
    }
  }

  @override
  Future<void> onError(DioException err, ErrorInterceptorHandler handler) async {
    final options = err.requestOptions;
    if (err.response?.statusCode != 401 || options.extra[skipAuth] == true) return handler.next(err);

    if (options.extra[_retried] == true) {
      // حتى الـ token الجديد انرفض: الجلسة خلصت (بدون refresh تاني)
      await _expire();
      return handler.next(err);
    }

    final result = await _refreshFor(options.extra[_sentToken] as String?);
    if (result.outcome != _Outcome.ok) {
      final cause = result.error;
      return handler.next(cause == null
          ? err
          : DioException(
              requestOptions: options,
              response: cause.response,
              type: cause.type,
              error: cause.error,
              message: cause.message,
            ));
    }

    try {
      final retry = await _dio.fetch<dynamic>(options.copyWith(extra: {...options.extra, _retried: true}));
      handler.resolve(retry);
    } on DioException catch (e) {
      handler.next(e);
    }
  }

  Future<_Refresh> _refreshFor(String? sentToken) =>
      _refreshing ??= _refresh(sentToken).whenComplete(() => _refreshing = null);

  Future<_Refresh> _refresh(String? sentToken) async {
    final String? refreshToken;
    try {
      // 401 لطلب انبعت قبل refresh خلص: الـ token تغيّر، بس منعيد الطلب
      final current = await _tokens.accessToken();
      if (current != null && current.isNotEmpty && current != sentToken) return _ok;
      refreshToken = await _tokens.refreshToken();
    } catch (error) {
      debugPrint('AuthInterceptor: could not read tokens: $error');
      return (outcome: _Outcome.unavailable, error: null);
    }
    if (refreshToken == null || refreshToken.isEmpty) {
      await _expire();
      return _failed;
    }

    try {
      final response = await _dio.post<Object?>(
        refreshPath,
        data: {'refresh_token': refreshToken},
        options: Options(extra: {skipAuth: true}),
      );
      final pair = TokenPair.tryParse(response.data);
      if (pair == null) {
        await _expire();
        return _failed;
      }
      // المستخدم طلع أثناء الـ refresh: ما منرجّع tokens انمسحت
      if (await _tokens.refreshToken() != refreshToken) return _failed;
      await _tokens.save(pair);
      return _ok;
    } on DioException catch (e) {
      final error = ApiException.fromDio(e);
      final keepSession = error.isOffline ||
          error.kind == ApiErrorKind.server ||
          error.kind == ApiErrorKind.rateLimited ||
          error.kind == ApiErrorKind.unknown;
      if (keepSession) return (outcome: _Outcome.unavailable, error: e);
      await _expire();
      return _failed;
    } catch (error) {
      debugPrint('AuthInterceptor: refresh failed: $error');
      return (outcome: _Outcome.unavailable, error: null);
    }
  }

  /// نهاية الجلسة مرة وحدة حتى لو كذا طلب فشل سوا
  Future<void> _expire() => _expiring ??= _runExpire().whenComplete(() => _expiring = null);

  Future<void> _runExpire() async {
    try {
      await _tokens.clear();
    } catch (error) {
      debugPrint('AuthInterceptor: could not clear tokens: $error');
    }
    await _onSessionExpired();
  }
}
