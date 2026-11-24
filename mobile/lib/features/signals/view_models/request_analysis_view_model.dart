import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/network_status.dart';
import '../../markets/data/market_providers.dart';
import '../../markets/models/market_models.dart';
import '../data/signal_profile_repository.dart';
import '../data/signals_repository.dart';
import '../models/analysis_request.dart';
import '../models/opportunity.dart';
import '../models/signal_detail.dart';
import 'signals_feed_view_model.dart';

/// ليش فشل الطلب (النص بالـ View)
enum RequestAnalysisFailure {
  /// الجهاز بدون اتصال: ما انبعت شي
  offline,

  /// الأداة أو الإطار أو الطريقة مش معروفين: ما انبعت شي
  invalid,

  /// المصدر فشل
  error,
}

/// حالات "Request analysis" (State pattern): كل حالة بتعرف إذا الطلب شغّال وشو
/// الحالات يلي بيصير ينتقل إلها.
///
/// idle → pending → analyzing → done | failed؛ وأي حالة شغّالة → idle (إلغاء).
/// done / failed → pending (طلب جديد) أو idle (reset).
@immutable
sealed class RequestAnalysisState {
  const RequestAnalysisState();

  /// الطلب شغّال (طلب تاني بينتجاهل، والإلغاء ممكن)
  bool get isBusy => false;

  /// الحالات المسموحة بعد هي
  bool canMoveTo(RequestAnalysisState next);
}

final class RequestIdle extends RequestAnalysisState {
  const RequestIdle();

  @override
  bool canMoveTo(RequestAnalysisState next) => next is RequestPending || next is RequestFailed;
}

/// انبعت وناطر دورو
final class RequestPending extends RequestAnalysisState {
  const RequestPending(this.request);

  final AnalysisRequest request;

  @override
  bool get isBusy => true;

  @override
  bool canMoveTo(RequestAnalysisState next) =>
      next is RequestAnalyzing || next is RequestDone || next is RequestFailed || next is RequestIdle;
}

/// الطريقة عم تحلّل
final class RequestAnalyzing extends RequestAnalysisState {
  const RequestAnalyzing(this.request);

  final AnalysisRequest request;

  @override
  bool get isBusy => true;

  @override
  bool canMoveTo(RequestAnalysisState next) => next is RequestDone || next is RequestFailed || next is RequestIdle;
}

/// خلص: [detail] = إشارة (أقوى 3 أسباب أول) أو نتيجة محايدة صالحة
/// ([SignalDetail.isNoClearSetup] = "No clear setup right now" مع السبب)
final class RequestDone extends RequestAnalysisState {
  const RequestDone(this.request, this.detail);

  final AnalysisRequest request;
  final SignalDetail detail;

  bool get isNoClearSetup => detail.isNoClearSetup;

  @override
  bool canMoveTo(RequestAnalysisState next) => next is RequestPending || next is RequestFailed || next is RequestIdle;
}

final class RequestFailed extends RequestAnalysisState {
  const RequestFailed(this.reason, {this.request});

  final RequestAnalysisFailure reason;
  final AnalysisRequest? request;

  @override
  bool canMoveTo(RequestAnalysisState next) => next is RequestPending || next is RequestFailed || next is RequestIdle;
}

/// ViewModel "Request analysis".
///
/// - الطريقة = طريقة الاستراتيجية المحفوظة، إلا لو انبعت [request] بـ
///   `methodOverride`: هاد للطلب بس وما بيغيّر الاستراتيجية المحفوظة أبدًا.
/// - طلب تاني وهو شغّال بينتجاهل (ضغطة مزدوجة = طلب واحد).
/// - [cancel] بيوقف الطلب ([AnalysisCancelToken]) وبيرجّع idle.
/// - كل طلب إلو رقم جيل: بعد كل `await` (وبكل مرحلة)، إذا انلغى أو في طلب أحدث
///   أو الـ ViewModel انحذف، النتيجة بتنرمى - آخر طلب بس بيحدّث الحالة.
/// - بدون اتصال: ما في طلب، والحالة failed(offline) بتقول ليش.
/// - نتيجة مكتشفة بتنضاف لقائمة Signals ("requested by you") فورًا لو محمّلة.
class RequestAnalysisViewModel extends AutoDisposeNotifier<RequestAnalysisState> {
  var _generation = 0;
  var _disposed = false;
  AnalysisCancelToken? _token;

  @override
  RequestAnalysisState build() {
    _disposed = false;
    ref.onDispose(() {
      _disposed = true;
      _cancelToken();
    });
    return const RequestIdle();
  }

  void _moveTo(RequestAnalysisState next) {
    assert(state.canMoveTo(next), 'invalid transition ${state.runtimeType} → ${next.runtimeType}');
    state = next;
  }

  Future<void> request({required String symbol, required Timeframe timeframe, String? methodOverride}) async {
    if (state.isBusy) return;
    final request = AnalysisRequest(
      symbol: symbol,
      timeframe: timeframe,
      methodId: methodOverride ?? ref.read(signalProfileProvider).methodId,
    );
    final generation = ++_generation;
    if (!request.isValid) {
      _moveTo(RequestFailed(RequestAnalysisFailure.invalid, request: request));
      return;
    }
    if (ref.read(networkStatusProvider) == NetworkStatus.offline) {
      _moveTo(RequestFailed(RequestAnalysisFailure.offline, request: request));
      return;
    }
    final token = _token = AnalysisCancelToken();
    bool current() => !_disposed && !token.isCancelled && generation == _generation;

    _moveTo(RequestPending(request));
    final repo = ref.read(signalsRepositoryProvider);
    try {
      final signal = await repo.requestAnalysis(
        request,
        cancel: token,
        onStage: (stage) {
          if (!current()) return;
          final next = switch (stage) {
            AnalysisStage.pending => RequestPending(request),
            AnalysisStage.analyzing => RequestAnalyzing(request),
          };
          if (next.runtimeType != state.runtimeType) _moveTo(next);
        },
      );
      if (!current()) return;

      await ref.read(instrumentsProvider.future);
      if (!current()) return;
      final instrument = ref.read(instrumentProvider(signal.symbol));
      if (instrument == null) throw StateError('unknown instrument ${signal.symbol}');

      final siblings = signal.isDetected ? await _siblings(repo, signal) : null;
      if (!current()) return;

      final now = ref.read(simulatedMarketSourceProvider).now();
      final detail = SignalDetail.of(signal, instrument: instrument, siblings: siblings, now: now);
      if (signal.isDetected && ref.exists(signalsFeedViewModelProvider)) {
        ref.read(signalsFeedViewModelProvider.notifier).insertRequested(signal);
      }
      _token = null;
      _moveTo(RequestDone(request, detail));
    } on AnalysisCancelledException {
      // انلغى عن قصد - الحالة انكتبت وقت الإلغاء
    } on Object {
      if (current()) {
        _token = null;
        _moveTo(RequestFailed(RequestAnalysisFailure.error, request: request));
      }
    }
  }

  /// بيوقف الطلب الشغّال (ونتيجته بتنرمى) وبيرجّع idle
  void cancel() {
    if (!state.isBusy) return;
    _generation++;
    _cancelToken();
    _moveTo(const RequestIdle());
  }

  /// بعد نتيجة أو فشل: رجوع لـ idle
  void reset() {
    if (state.isBusy) return cancel();
    if (state is! RequestIdle) _moveTo(const RequestIdle());
  }

  /// الطريقة يلي رح تنستعمل بدون override (طريقة الاستراتيجية المحفوظة)
  String get savedMethodId => ref.read(signalProfileProvider).methodId;

  void _cancelToken() {
    _token?.cancel();
    _token = null;
  }

  /// باقي أطر نفس الأداة بنفس الطريقة (سبب الاتفاق) - فشلها ما بيوقف النتيجة
  Future<List<Opportunity>?> _siblings(SignalsRepository repo, Opportunity signal) async {
    try {
      return await repo.opportunities(signal.symbol, methodId: signal.methodId);
    } on Object {
      return null;
    }
  }
}

final requestAnalysisViewModelProvider =
    NotifierProvider.autoDispose<RequestAnalysisViewModel, RequestAnalysisState>(RequestAnalysisViewModel.new);
