import 'package:dio/dio.dart';

/// H5b: بيقيس مدة كل طلب (نجح أو فشل بجواب) لاقتراح الـ Low data mode
/// على اتصال بطيء. طلب انقطع بدون جواب ما بينحسب (هيداك offline).
class LatencyInterceptor extends Interceptor {
  LatencyInterceptor(this.onSample, {DateTime Function()? clock}) : _clock = clock ?? DateTime.now;

  final void Function(Duration elapsed) onSample;
  final DateTime Function() _clock;

  static const String _startKey = 'latency_start';

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    options.extra[_startKey] = _clock();
    handler.next(options);
  }

  @override
  void onResponse(Response<dynamic> response, ResponseInterceptorHandler handler) {
    _sample(response.requestOptions);
    handler.next(response);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    if (err.response != null) _sample(err.requestOptions);
    handler.next(err);
  }

  void _sample(RequestOptions options) {
    final start = options.extra[_startKey];
    if (start is DateTime) onSample(_clock().difference(start));
  }
}
