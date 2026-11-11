import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/clock.dart';
import '../data/chart_analysis_repository.dart';
import '../models/chart_analysis.dart';

/// عدّاد تحليل الصور اليومي (من الـ repository، محفوظ على الجهاز بالمحاكاة).
/// بيتحدّث بعد كل تحليل، وبالـ 429 ([DailyLimitReachedException]).
class ChartQuotaNotifier extends AsyncNotifier<ChartAnalysisQuota> {
  @override
  Future<ChartAnalysisQuota> build() => ref.watch(chartAnalysisRepositoryProvider).quota();

  void set(ChartAnalysisQuota quota) => state = AsyncData(quota);

  /// الحد خلص لحد [resetAt] (من الخادم)
  void reached(DateTime resetAt) {
    final limit = state.valueOrNull?.limit ?? ChartAnalysisQuota.simulatedDailyLimit;
    state = AsyncData(ChartAnalysisQuota(used: limit, limit: limit, resetAt: resetAt));
  }
}

final chartQuotaProvider =
    AsyncNotifierProvider<ChartQuotaNotifier, ChartAnalysisQuota>(ChartQuotaNotifier.new);

/// العدّاد كما بينعرض هلّق: بعد حدّ اليوم ([ChartAnalysisQuota.resetAt]) بيرجع
/// صفر لحاله مع [clockProvider] (بدون طلب). null = لسّا عم يتحمّل.
final chartQuotaNowProvider = Provider.autoDispose<ChartAnalysisQuota?>((ref) {
  final quota = ref.watch(chartQuotaProvider).valueOrNull;
  if (quota == null) return null;
  final now = ref.watch(clockProvider).valueOrNull ?? DateTime.now();
  return quota.at(now);
});
