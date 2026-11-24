import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/network_status.dart';
import '../../markets/data/market_providers.dart';
import '../data/insights_repository.dart';
import '../models/track_record.dart';

/// الطلب ما انبعت لأنو الجهاز بدون اتصال
final class InsightsOfflineException implements Exception {
  const InsightsOfflineException();
}

/// الفترة المختارة بـ Insights. أول فتحة = نفس فترة سطر الدقة يلي انضغط
/// ([modelAccuracyProvider])، فالرقم الكبير بيطابق السطر؛ غير هيك 90 يوم.
class InsightsPeriodViewModel extends AutoDisposeNotifier<InsightsPeriod> {
  @override
  InsightsPeriod build() =>
      InsightsPeriod.fromDays(ref.read(modelAccuracyProvider).valueOrNull?.windowDays) ?? InsightsPeriod.d90;

  void select(InsightsPeriod period) => state = period;
}

final insightsPeriodProvider =
    NotifierProvider.autoDispose<InsightsPeriodViewModel, InsightsPeriod>(InsightsPeriodViewModel.new);

/// ViewModel شاشة Insights: سجل النموذج للفترة المختارة.
///
/// - تبديل الفترة بيعيد البناء (تحميل). تبديل سريع (7 → 30 → 90): كل بناء إلو
///   رقم جيل، ونتيجة أي طلب أقدم (أو بعد ما الشاشة تتسكّر) بتنرمى بعد الـ `await`،
///   فبيبيّن آخر فترة بس مهما رجعت الطلبات بأي ترتيب.
/// - جواب لفترة غير المطلوبة = خطأ (ما منعرض أرقام فترة تانية تحت الشريحة).
/// - بدون اتصال: ما في طلب ([InsightsOfflineException])، وبيرجع يحمّل لحالو لما
///   يرجع الاتصال.
class InsightsViewModel extends AutoDisposeAsyncNotifier<TrackRecord> {
  var _generation = 0;

  @override
  Future<TrackRecord> build() async {
    final period = ref.watch(insightsPeriodProvider);
    final repo = ref.watch(insightsRepositoryProvider);
    final generation = ++_generation;
    var disposed = false;
    // بيتنادى كمان قبل كل إعادة بناء (فترة جديدة) - يعني هالطلب صار قديم
    ref.onDispose(() => disposed = true);
    ref.listen(networkStatusProvider, (_, status) {
      if (status == NetworkStatus.online && state.error is InsightsOfflineException) ref.invalidateSelf();
    });

    if (ref.read(networkStatusProvider) == NetworkStatus.offline) throw const InsightsOfflineException();
    final record = await repo.trackRecord(period);
    if (disposed || generation != _generation) throw const _Superseded();
    if (record.period != period) throw StateError('track record for ${record.period}, asked $period');
    return record;
  }

  Future<void> retry() async {
    ref.invalidateSelf();
    await future;
  }
}

/// نتيجة طلب قديم (Riverpod بيتجاهلها، ما بتوصل للشاشة أبدًا)
final class _Superseded implements Exception {
  const _Superseded();
}

final insightsViewModelProvider =
    AsyncNotifierProvider.autoDispose<InsightsViewModel, TrackRecord>(InsightsViewModel.new);
