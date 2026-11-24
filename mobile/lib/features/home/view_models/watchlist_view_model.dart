import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../markets/data/market_providers.dart';
import '../../markets/models/market_models.dart';
import '../../workspaces/models/workspace.dart';
import '../../workspaces/view_models/workspaces_view_model.dart';

/// ViewModel قائمة المتابعة بالـ Home: الأدوات بالترتيب، والسحب للتحديث.
///
/// - كل صف بيقرأ سعره ورسمه ورأي النموذج من providers صغيرة خاصة فيه، فنبضة
///   سعر بتعيد بناء صف واحد بس.
/// - تحديثين ورا بعض: نتيجة الأقدم بتنرمى (رقم جيل)، فما بترجع بيانات قديمة.
/// - تحديث فاشل بيخلّي البيانات الحالية ظاهرة وبيرمي الخطأ للشاشة (snackbar).
class WatchlistViewModel extends AsyncNotifier<List<Instrument>> {
  int _generation = 0;

  @override
  Future<List<Instrument>> build() => ref.watch(instrumentsProvider.future);

  Future<void> refresh() async {
    final generation = ++_generation;
    final repo = ref.read(marketDataRepositoryProvider);
    final (instruments, _) = await (
      repo.instruments(),
      ref.read(liveQuotesProvider.notifier).refresh(),
    ).wait;
    if (generation != _generation) return; // في تحديث أحدث
    ref.invalidate(sparklineProvider);
    ref.invalidate(opportunitiesProvider);
    state = AsyncData(instruments);
  }

  Future<void> retry() async {
    ref.invalidate(instrumentsProvider);
    ref.invalidateSelf();
    await future;
  }
}

final watchlistViewModelProvider =
    AsyncNotifierProvider<WatchlistViewModel, List<Instrument>>(WatchlistViewModel.new);

/// الأدوات يلي بتبيّن بالـ Home: أدوات المساحة الفعّالة بس، بترتيب الـ repository.
///
/// تبديل المساحة فلترة فورية (بدون تحميل جديد ولا skeleton)؛ الأسعار والرسوم
/// من نفس providers كل أداة، فبتضل متطابقة. لحد ما تنقرأ المساحة = تحميل.
final homeWatchlistProvider = Provider<AsyncValue<List<Instrument>>>((ref) {
  final workspace = ref.watch(activeWorkspaceProvider);
  if (!workspace.hasValue) return const AsyncLoading();
  final symbols = (workspace.valueOrNull ?? Workspace.all).symbols.toSet();
  return ref
      .watch(watchlistViewModelProvider)
      .whenData((instruments) => [for (final i in instruments) if (symbols.contains(i.symbol)) i]);
});
