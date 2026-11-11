import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/network_status.dart';
import '../../markets/data/market_providers.dart';
import '../../markets/models/market_models.dart';
import '../../markets/view_models/market_view_model.dart';
import '../../signals/data/signal_profile_repository.dart';
import '../data/forecast_repository.dart';
import '../models/forecast_config.dart';
import '../models/forecast_path.dart';

/// حالة توقّع النموذج على رسم الأداة
@immutable
sealed class ForecastState {
  const ForecastState();
}

/// المفتاح مطفى (ما في طلب)
final class ForecastOff extends ForecastState {
  const ForecastOff();
}

/// الطلب شغّال (المفتاح معطّل مع مؤشّر صغير)
final class ForecastLoading extends ForecastState {
  const ForecastLoading();
}

/// التوقّع جاهز وبينرسم
final class ForecastReady extends ForecastState {
  const ForecastReady(this.path);

  final ForecastPath path;
}

/// خلصت صلاحيته: ما بينرسم، والشرح بيقول "Outdated" مع تحديث
final class ForecastOutdated extends ForecastState {
  const ForecastOutdated(this.path);

  final ForecastPath path;
}

enum ForecastUnavailableReason {
  /// الاستراتيجية ما شايفة فرصة واضحة هلّق (جواب محايد صحيح، مش خطأ)
  noSetup,

  /// الإطار مش بـ [forecastSupportedTimeframes]: "Not available for this timeframe"، وما في طلب
  timeframe,
}

/// "No forecast right now"
final class ForecastUnavailable extends ForecastState {
  const ForecastUnavailable(this.reason);

  final ForecastUnavailableReason reason;
}

/// الطلب فشل (Try again)
final class ForecastFailed extends ForecastState {
  const ForecastFailed();
}

/// بدون اتصال: مخفي، والشرح بيقول ليش (بيرجع لحالو لما يرجع الاتصال)
final class ForecastOffline extends ForecastState {
  const ForecastOffline();
}

/// ViewModel توقّع النموذج لأداة (instance لكل رمز، بينحذف لما الشاشة تتسكّر).
///
/// - بيراقب المفتاح والإطار ([marketViewModelProvider])، طريقة الاستراتيجية
///   المحفوظة ([signalProfileProvider])، الأطر المدعومة
///   ([forecastSupportedTimeframesProvider]) والاتصال؛ أي تغيير = بناء جديد = طلب جديد.
/// - كل طلب إلو رقم جيل و [ForecastCancelToken]: الطلب الجديد بيلغي القديم،
///   ونتيجة أي طلب أقدم (أو بعد ما الشاشة تتسكّر) بتنرمى، فبينرسم آخر طلب بس
///   مهما رجعت الأجوبة بأي ترتيب. جواب لأداة / إطار / طريقة تانية = خطأ.
/// - ما بيراقب النبضات ولا الشموع: الرسم بيلحق آخر شمعة بنفسه
///   ([ForecastPath.followFrom])، فما في طلب ولا إعادة بناء هون مع كل نبضة.
/// - مؤقّت على [ForecastPath.validUntil] بيعلّمه "Outdated" والشاشة مفتوحة.
/// - تحديث تلقائي عند سكرة الشمعة ([forecastRefreshAt])، مش أسرع (على 1m: مرة
///   بالدقيقة): بيبقى المرسوم لحد ما يوصل الجديد (بلا تحميل ولا وميض)، وبيحدّث
///   آراء الأداة معو ([opportunitiesProvider]) حتى خلاصة الرأي والتوقّع يضلّوا
///   على نفس الإشارة.
class ForecastViewModel extends AutoDisposeFamilyNotifier<ForecastState, String> {
  var _generation = 0;
  ForecastCancelToken? _cancel;
  Timer? _expiry;
  Timer? _refresh;
  ({ForecastRepository repo, Timeframe timeframe, String methodId})? _request;

  /// آخر جيل بدأ (للاختبارات: كل طلب = جيل)
  @visibleForTesting
  int get generation => _generation;

  @override
  ForecastState build(String symbol) {
    final (on, timeframe) = ref.watch(marketViewModelProvider(symbol).select((s) => (s.showForecast, s.timeframe)));
    final methodId = ref.watch(signalProfileProvider.select((p) => p.methodId));
    final offline = ref.watch(networkStatusProvider) == NetworkStatus.offline;
    final supported = ref.watch(forecastSupportedTimeframesProvider);
    final repo = ref.watch(forecastRepositoryProvider);
    // بيتنادى قبل كل إعادة بناء كمان: الطلب القديم بينلغى ومؤقّتاته بتوقف
    ref.onDispose(_stop);
    _request = null;

    if (!on) return const ForecastOff();
    if (offline) return const ForecastOffline();
    if (!supported.contains(timeframe)) {
      return const ForecastUnavailable(ForecastUnavailableReason.timeframe);
    }
    _request = (repo: repo, timeframe: timeframe, methodId: methodId);
    _start();
    return const ForecastLoading();
  }

  /// Try again (بعد خطأ) و "Refresh forecast" (بعد ما يصير قديم)
  void retry() => ref.invalidateSelf();

  void _stop() {
    _cancel?.cancel();
    _cancel = null;
    _expiry?.cancel();
    _expiry = null;
    _refresh?.cancel();
    _refresh = null;
  }

  /// طلب جديد (جيل جديد، والقديم بينلغى). الحالة الحالية بتبقى لحد الجواب.
  void _start() {
    final request = _request;
    if (request == null) return;
    _cancel?.cancel();
    _refresh?.cancel();
    final generation = ++_generation;
    final cancel = _cancel = ForecastCancelToken();
    _load(request.repo, arg, request.timeframe, request.methodId, generation, cancel);
  }

  /// سكرة شمعة: آراء الأداة والتوقّع بيتحدّثوا سوا على نفس "الآن"
  void _refreshNow() {
    ref.invalidate(opportunitiesProvider(arg));
    _start();
  }

  bool _current(int generation, ForecastCancelToken cancel) => generation == _generation && !cancel.isCancelled;

  Future<void> _load(
    ForecastRepository repo,
    String symbol,
    Timeframe timeframe,
    String methodId,
    int generation,
    ForecastCancelToken cancel,
  ) async {
    try {
      final path = await repo.forecast(symbol, timeframe, methodId: methodId, cancel: cancel);
      if (!_current(generation, cancel)) return;
      // نفس "الآن" تبع رأي النموذج بشاشة السوق
      final now = ref.read(simulatedMarketSourceProvider).now();
      if (path == null) {
        _expiry?.cancel();
        state = const ForecastUnavailable(ForecastUnavailableReason.noSetup);
        _scheduleRefresh(timeframe, now, follows: true);
        return;
      }
      if (path.symbol != symbol || path.timeframe != timeframe || path.methodId != methodId) {
        _expiry?.cancel();
        state = const ForecastFailed();
        return;
      }
      _expiry?.cancel();
      _scheduleRefresh(timeframe, now, follows: path.follows);
      if (path.isOutdated(now)) {
        state = ForecastOutdated(path);
        return;
      }
      state = ForecastReady(path);
      _expiry = Timer(path.validUntil.difference(now), () {
        if (state case ForecastReady(path: final shown) when identical(shown, path)) state = ForecastOutdated(path);
      });
    } on ForecastCancelledException {
      // انلغى: طلب أحدث أخد مكانه
    } on Object {
      if (_current(generation, cancel)) {
        _expiry?.cancel();
        state = const ForecastFailed();
      }
    }
  }

  void _scheduleRefresh(Timeframe timeframe, DateTime now, {required bool follows}) {
    _refresh?.cancel();
    _refresh = Timer(forecastRefreshAt(timeframe, now, follows: follows).difference(now), _refreshNow);
  }
}

final forecastViewModelProvider =
    NotifierProvider.autoDispose.family<ForecastViewModel, ForecastState, String>(ForecastViewModel.new);
