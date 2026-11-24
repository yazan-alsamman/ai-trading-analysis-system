import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/network_status.dart';
import '../data/expert_subscriptions_repository.dart';
import '../models/expert.dart';
import '../models/expert_subscription.dart';

/// الطلب ما انبعت لأنو الجهاز بدون اتصال (اشتراك، إلغاء، تراجع) - ما تغيّر شي
final class ExpertsOfflineException implements Exception {
  const ExpertsOfflineException();
}

/// اشتراكاتك عند الخبراء: آخر اشتراك لكل خبير (`expertId` → اشتراك).
///
/// - مش autoDispose: البطاقات وشاشة المحادثة بيقروا نفس الحالة.
/// - ضغطتين ورا بعض (اشتراك / إلغاء / تراجع لنفس الخبير) = طلب واحد.
/// - بدون اتصال: ما في طلب ([ExpertsOfflineException]) وما تغيّر شي.
class ExpertSubscriptionsViewModel extends AsyncNotifier<Map<String, ExpertSubscription>> {
  final Set<String> _busy = {};

  ExpertSubscriptionsRepository get _repo => ref.read(expertSubscriptionsRepositoryProvider);

  @override
  Future<Map<String, ExpertSubscription>> build() async {
    final list = await ref.watch(expertSubscriptionsRepositoryProvider).mine();
    // القائمة الأحدث أول: أول اشتراك لكل خبير هو الحالي
    final out = <String, ExpertSubscription>{};
    for (final s in list) {
      out.putIfAbsent(s.expertId, () => s);
    }
    return out;
  }

  bool isBusy(String expertId) => _busy.contains(expertId);

  void _requireOnline() {
    if (ref.read(networkStatusProvider) == NetworkStatus.offline) throw const ExpertsOfflineException();
  }

  void _put(ExpertSubscription s) {
    state = AsyncData({...?state.valueOrNull, s.expertId: s});
  }

  /// null = ما في خطة / في طلب جاري لنفس الخبير. مشترك أصلًا = نفس الاشتراك.
  Future<ExpertSubscription?> subscribe(Expert expert) async {
    final plan = expert.plan;
    if (plan == null || _busy.contains(expert.id)) return null;
    final existing = state.valueOrNull?[expert.id];
    if (existing != null && existing.isEntitled) return existing;
    _requireOnline();
    _busy.add(expert.id);
    try {
      final s = await _repo.subscribe(expert: expert, plan: plan);
      _put(s);
      return s;
    } finally {
      _busy.remove(expert.id);
    }
  }

  /// بيرجّع الاشتراك قبل الإلغاء (للـ Undo). null = مش مشترك / في طلب جاري.
  Future<ExpertSubscription?> unsubscribe(String expertId) async {
    final current = state.valueOrNull?[expertId];
    if (current == null || !current.isEntitled || _busy.contains(expertId)) return null;
    _requireOnline();
    _busy.add(expertId);
    try {
      _put(await _repo.cancel(current.id));
      return current;
    } finally {
      _busy.remove(expertId);
    }
  }

  /// Undo الإلغاء: نفس الاشتراك بيرجع فعّال
  Future<void> undoUnsubscribe(ExpertSubscription previous) async {
    if (_busy.contains(previous.expertId)) return;
    _requireOnline();
    _busy.add(previous.expertId);
    try {
      _put(await _repo.resume(previous.id));
    } finally {
      _busy.remove(previous.expertId);
    }
  }
}

final expertSubscriptionsProvider =
    AsyncNotifierProvider<ExpertSubscriptionsViewModel, Map<String, ExpertSubscription>>(
        ExpertSubscriptionsViewModel.new);

/// اشتراكك الحالي عند خبير (null = ما في). تحميل / خطأ متل [expertSubscriptionsProvider].
final expertSubscriptionProvider = Provider.autoDispose.family<AsyncValue<ExpertSubscription?>, String>(
  (ref, expertId) => ref.watch(expertSubscriptionsProvider).whenData((m) => m[expertId]),
);
