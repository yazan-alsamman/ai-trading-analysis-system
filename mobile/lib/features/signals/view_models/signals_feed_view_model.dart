import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/clock.dart';
import '../../../core/data/network_status.dart';
import '../../../app/shell/shell_tab.dart';
import '../../../core/data/low_data_mode.dart';
import '../../../core/database/cache_support.dart';
import '../../../core/database/user_cache_guard.dart';
import '../../markets/data/market_providers.dart';
import '../data/caching_signals_repository.dart';
import '../data/signal_profile_repository.dart';
import '../data/signals_repository.dart';
import '../models/opportunity.dart';

/// الطلب ما انبعت لأنو الجهاز بدون اتصال (القائمة أو التفاصيل)
final class SignalsOfflineException implements Exception {
  const SignalsOfflineException();
}

/// ViewModel قائمة Signals: الفرص يلي بتطابق "Strategy" المحفوظة.
///
/// - تغيير الاستراتيجية (حتى أثناء التحميل) بيعيد البناء، ونتيجة الطلب القديم بتنرمى.
/// - سحب للتحديث مرتين ورا بعض: الأقدم بينرمى (رقم جيل). أي إعادة بناء أو
///   dispose بتلغي التحديث الجاري كمان.
/// - تحديث فاشل بيخلّي القائمة الحالية وبيرمي الخطأ للشاشة (snackbar).
/// - بدون اتصال: ما في طلب ([SignalsOfflineException])؛ أول تحميل بيطلع حالة
///   "offline" وبيرجع يحمّل لحالو لما يرجع الاتصال.
/// - H5b (فوق الكاش): بدون اتصال آخر قائمة محفوظة للحساب (+ "Last updated")؛
///   ما في شي محفوظ = نفس حالة الـ offline. السحب للتحديث بدون اتصال بيقول ليش.
class SignalsFeedViewModel extends AsyncNotifier<List<Opportunity>> {
  var _generation = 0;

  @override
  Future<List<Opportunity>> build() async {
    final profile = ref.watch(signalProfileProvider);
    final repo = ref.watch(signalsRepositoryProvider);
    // H5c: حساب تاني (أو خروج): القائمة القديمة بتنمسح من الذاكرة قبل إعادة
    // البناء (Riverpod بيحمل القيمة السابقة لقدّام، حتى بالخطأ / offline)
    ref.watch(cacheOwnerProvider);
    ref.listen<String>(cacheOwnerProvider, (_, __) => state = const AsyncData([]));
    // رجع الاتصال: حالة الـ offline أو نسخة محفوظة (H5b) → تحميل من جديد
    // (بالـ Low data mode بيستنّى لحد ما تبويب Signals يبيّن)
    reloadWhenBackOnline(
      ref,
      tab: ShellTab.signals,
      needed: () =>
          state.error is SignalsOfflineException ||
          (repo is CachingSignalsRepository && repo.savedAt[CachingSignalsRepository.feedKey] != null),
      reload: ref.invalidateSelf,
    );
    ref.onDispose(() => _generation++);
    _generation++;
    // H5b: فوق الكاش بدون اتصال الـ repository بيرجّع النسخة المحفوظة
    if (repo is! CachingSignalsRepository) _requireOnline();
    try {
      return await repo.feed(profile);
    } on NoSavedDataException {
      throw const SignalsOfflineException();
    }
  }

  void _requireOnline() {
    if (ref.read(networkStatusProvider) == NetworkStatus.offline) throw const SignalsOfflineException();
  }

  Future<void> refresh() async {
    _requireOnline();
    final generation = ++_generation;
    try {
      final list = await ref.read(signalsRepositoryProvider).feed(ref.read(signalProfileProvider));
      if (generation == _generation) state = AsyncData(list);
    } on Object {
      // فشل طلب قديم (انرمى أو انعاد البناء) ما بيوصل للشاشة
      if (generation == _generation) rethrow;
    }
  }

  /// إشارة مطلوبة خلصت ("requested by you"): بتطلع فوق القائمة المحمّلة فورًا
  /// (بدون طلب)، وبتحلّ محل نفس الإشارة لو كانت موجودة. التحديث الجاي من
  /// الـ repository بيرجّعها بنفس المكان.
  void insertRequested(Opportunity signal) {
    final list = state.valueOrNull;
    if (list == null || !signal.requestedByYou) return;
    final base = signal.id.startsWith(SimulatedSignalsRepository.requestedPrefix)
        ? signal.id.substring(SimulatedSignalsRepository.requestedPrefix.length)
        : signal.id;
    state = AsyncData([
      signal,
      for (final o in list)
        if (o.id != signal.id && o.id != base) o
    ]);
  }

  Future<void> retry() async {
    ref.invalidateSelf();
    await future;
  }
}

final signalsFeedViewModelProvider =
    AsyncNotifierProvider<SignalsFeedViewModel, List<Opportunity>>(SignalsFeedViewModel.new);

/// القائمة الظاهرة: إشارة بتخلص صلاحيتها والقائمة مفتوحة بتختفي مع دقة الساعة
final visibleSignalsProvider = Provider.autoDispose<AsyncValue<List<Opportunity>>>((ref) {
  final feed = ref.watch(signalsFeedViewModelProvider);
  final now = ref.watch(clockProvider).valueOrNull;
  if (now == null) return feed;
  return feed.whenData((list) => [
        for (final o in list)
          if (!o.isStale(now)) o
      ]);
});
