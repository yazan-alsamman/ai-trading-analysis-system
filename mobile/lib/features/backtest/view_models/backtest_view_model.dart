import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/network_status.dart';
import '../../signals/data/signal_profile_repository.dart';
import '../../signals/models/analysis_method.dart';
import '../../signals/models/signal_profile.dart';
import '../data/backtest_repository.dart';
import '../models/backtest.dart';

/// حالة الاختبار تحت الإعدادات
sealed class BacktestStatus {
  const BacktestStatus();
}

/// لسّا ما انشغّل (أو تغيّرت الإعدادات بعد آخر نتيجة)
final class BacktestIdle extends BacktestStatus {
  const BacktestIdle();
}

/// شغّال: [progress] بين 0 و 1
final class BacktestRunning extends BacktestStatus {
  const BacktestRunning(this.progress);

  final double progress;
}

/// خلص: [result] (فاضية = ما في إشارات طابقت الاستراتيجية)
final class BacktestDone extends BacktestStatus {
  const BacktestDone(this.result);

  final BacktestResult result;
}

/// فشل، أو ما انبعت لأنو الجهاز بدون اتصال ([offline])
final class BacktestFailed extends BacktestStatus {
  const BacktestFailed({this.offline = false});

  final bool offline;
}

@immutable
final class BacktestState {
  BacktestState({
    required this.strategy,
    required this.symbols,
    required this.period,
    required this.status,
    String? methodId,
  }) : methodId = methodId ?? strategy.methodId;

  /// الاستراتيجية المحفوظة وقت فتح الشاشة (الطريقة، الأطر، الاتجاهات، الحدود)
  final SignalProfile strategy;

  /// الطريقة يلي بتنختبر: من الاستراتيجية المحفوظة، وتغييرها هون للجلسة بس
  final String methodId;
  final Set<String> symbols;
  final BacktestPeriod period;
  final BacktestStatus status;

  bool get isRunning => status is BacktestRunning;

  BacktestRequest get request => BacktestRequest.from(strategy, symbols: symbols, period: period, methodId: methodId);

  /// "Run" شغّال: في أداة وحدة عالأقل وما في اختبار شغّال
  bool get canRun => request.isValid && !isRunning;

  BacktestState copyWith({Set<String>? symbols, BacktestPeriod? period, BacktestStatus? status, String? methodId}) =>
      BacktestState(
        strategy: strategy,
        methodId: methodId ?? this.methodId,
        symbols: symbols ?? this.symbols,
        period: period ?? this.period,
        status: status ?? this.status,
      );
}

/// ViewModel شاشة Backtest: الأدوات والفترة + تشغيل الاختبار.
///
/// - بيبلّش من الاستراتيجية المحفوظة الحالية (أدواتها مختارة، 90 يوم)، بدون
///   تشغيل. autoDispose: كل فتحة للشاشة بتبلّش من جديد (ولا نتيجة قديمة)، وحفظ
///   أو إزالة الاستراتيجية بيعيد البناء عليها.
/// - تعديل الأدوات والطريقة هون للجلسة بس: ما بيكتب على الاستراتيجية المحفوظة أبدًا.
/// - "Run" مرتين ما بيشغّل اختبارين: التانية بتنتجاهل طالما في واحد شغّال.
/// - تغيير الأدوات أو الفترة أثناء الشغل بيلغيه، وبعد نتيجة بيرجّع idle (ما
///   منعرض نتيجة إعدادات قديمة تحت إعدادات جديدة).
/// - كل تشغيل إلو رقم جيل: بعد كل `await` (وبكل تقدّم) إذا انلغى أو في تشغيل
///   أحدث أو الشاشة تسكّرت، النتيجة بتنرمى - آخر تشغيل بس بيحدّث الشاشة.
/// - بدون اتصال: ما في طلب، وبيشغّل لحالو لما يرجع الاتصال.
class BacktestViewModel extends AutoDisposeNotifier<BacktestState> {
  var _generation = 0;
  BacktestCancelToken? _token;

  @override
  BacktestState build() {
    final strategy = ref.watch(signalProfileProvider);
    // سكّرت الشاشة أو انعاد البناء: التشغيل الجاري بيوقف ونتيجته بتنرمى
    ref.onDispose(_cancel);
    ref.listen(networkStatusProvider, (_, status) {
      final failed = state.status;
      if (status == NetworkStatus.online && failed is BacktestFailed && failed.offline) run();
    });
    return BacktestState(
      strategy: strategy,
      symbols: strategy.symbols,
      period: BacktestPeriod.d90,
      status: const BacktestIdle(),
    );
  }

  void toggleSymbol(String symbol, bool on) {
    final symbols = on ? {...state.symbols, symbol} : ({...state.symbols}..remove(symbol));
    _cancel();
    state = state.copyWith(symbols: symbols, status: const BacktestIdle());
  }

  /// طريقة تانية للجلسة بس (الاستراتيجية المحفوظة ما بتتغيّر)
  void selectMethod(String methodId) {
    if (methodId == state.methodId || !AnalysisMethod.isKnown(methodId)) return;
    _cancel();
    state = state.copyWith(methodId: methodId, status: const BacktestIdle());
  }

  void selectPeriod(BacktestPeriod period) {
    if (period == state.period) return;
    _cancel();
    state = state.copyWith(period: period, status: const BacktestIdle());
  }

  Future<void> run() async {
    if (!state.canRun) return;
    final request = state.request;
    final generation = ++_generation;
    if (ref.read(networkStatusProvider) == NetworkStatus.offline) {
      state = state.copyWith(status: const BacktestFailed(offline: true));
      return;
    }
    final token = _token = BacktestCancelToken();
    bool current() => !token.isCancelled && generation == _generation;

    state = state.copyWith(status: const BacktestRunning(0));
    try {
      final result = await ref.read(backtestRepositoryProvider).run(
        request,
        cancel: token,
        onProgress: (p) {
          if (current()) state = state.copyWith(status: BacktestRunning(p.clamp(0, 1)));
        },
      );
      if (!current()) return;
      // جواب لفترة تانية ما بينعرض تحت الشريحة
      if (result.period != request.period) throw StateError('backtest for ${result.period}, asked ${request.period}');
      state = state.copyWith(status: BacktestDone(result));
    } on BacktestCancelledException {
      // انلغى عن قصد - الحالة الجديدة انكتبت وقت الإلغاء
    } on Object {
      if (current()) state = state.copyWith(status: const BacktestFailed());
    }
  }

  void _cancel() {
    _generation++;
    _token?.cancel();
    _token = null;
  }
}

final backtestViewModelProvider = NotifierProvider.autoDispose<BacktestViewModel, BacktestState>(BacktestViewModel.new);
