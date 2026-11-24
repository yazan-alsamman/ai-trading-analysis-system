import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/database/user_cache_guard.dart';
import '../../../core/data/network_status.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';

import '../../markets/models/market_models.dart';
import '../data/alerts_repository.dart';
import '../models/price_alert.dart';

/// H5b: التنبيهات على الخادم (API حقيقي) والجهاز بدون اتصال: الإنشاء والحذف
/// والإيقاف بيقولوا إنهن بدهن اتصال، وما في طابور مخفي. التنبيهات المحلية
/// (`LocalAlertsRepository`، اليوم) بتشتغل بدون اتصال متل قبل.
final class AlertsOfflineException implements Exception {
  const AlertsOfflineException();
}

/// التنبيهات محفوظة على الخادم؟ (`USE_REAL_API=alerts`؛ غير هيك محلية بالجهاز)
final alertsNeedConnectionProvider = Provider<bool>((ref) => ref.watch(useRealApiProvider(ApiFeature.alerts)));

/// ViewModel التنبيهات (مشترك: شاشة السوق تنشئ، والإشعارات بتعرض الكل).
///
/// - الإنشاء محمي من الضغط المزدوج (طلب واحد بنفس الوقت).
/// - الحذف والإيقاف متفائلين (الواجهة بتتحدّث فورًا)، وبيرجعوا لو فشل الطلب.
/// - كل الطلبات بالدور (طابور): فحص الأسعار بيستنّى أي تعديل جاري، فبيشتغل
///   على النسخة المحفوظة (التعديل بيربح)، والحذف بعد ما اشتغل بيرجّع (Undo)
///   حالته الحقيقية.
/// - أول تحميل بينهي يلي انتهت مدتهم والتطبيق مسكّر.
class AlertsViewModel extends AsyncNotifier<List<PriceAlert>> {
  bool _creating = false;
  Future<void> _queue = Future.value();

  /// تنبيهات عم تنفحص هلق (نبضات سريعة ورا بعض ما بتكرّر الطلب)
  final Set<String> _checking = {};

  AlertsRepository get _repo => ref.read(alertsRepositoryProvider);

  DateTime _now() => ref.read(alertsClockProvider)();

  @override
  Future<List<PriceAlert>> build() async {
    final repo = ref.watch(alertsRepositoryProvider);
    // H5d: حساب تاني / خروج: القائمة القديمة بتنمسح من الذاكرة قبل إعادة البناء
    ref.listen<String>(cacheOwnerProvider, (_, __) => state = const AsyncData([]));
    await repo.expireDue(ref.read(alertsClockProvider)());
    return repo.list();
  }

  bool get isCreating => _creating;

  void _requireOnline() {
    if (ref.read(alertsNeedConnectionProvider) && ref.read(networkStatusProvider) == NetworkStatus.offline) {
      throw const AlertsOfflineException();
    }
  }

  /// بيشغّل [op] بعد يلي قبلها
  Future<T> _serial<T>(Future<T> Function() op) {
    final run = _queue.then((_) => op());
    _queue = run.then<void>((_) {}, onError: (Object _) {});
    return run;
  }

  /// null = في طلب إنشاء جاري أصلًا (ضغطة مزدوجة). الخطأ بيوصل للمنادي.
  Future<PriceAlert?> create(AlertDraft draft) async {
    if (_creating) return null;
    _requireOnline();
    _creating = true;
    try {
      final alert = await _serial(() => _repo.create(draft));
      final current = state.valueOrNull ?? const <PriceAlert>[];
      state = AsyncData([alert, ...current.where((a) => a.id != alert.id)]);
      return alert;
    } finally {
      _creating = false;
    }
  }

  /// "Set again" لتنبيه اشتغل: تنبيه Active جديد بنفس المستوى والاتجاه.
  /// [current] = السعر هلق (إذا أصلًا ورا المستوى بيستنّى عبور جديد).
  Future<PriceAlert?> setAgain(PriceAlert alert, {Quote? current}) {
    if (!alert.state.actions.contains(AlertAction.setAgain)) return Future.value();
    return create(AlertDraft.again(alert, now: _now(), current: current?.price));
  }

  /// بيرجّع التنبيه المحذوف بحالته المحفوظة (لزر Undo)، أو null إذا مش موجود
  Future<PriceAlert?> remove(String id) async {
    final current = state.valueOrNull ?? const <PriceAlert>[];
    final index = current.indexWhere((a) => a.id == id);
    if (index < 0) return null;
    _requireOnline();
    final removed = current[index];
    state = AsyncData([...current]..removeAt(index));
    try {
      return await _serial(() => _repo.delete(id)) ?? removed;
    } catch (_) {
      _insert(removed, at: index);
      rethrow;
    }
  }

  Future<void> undoRemove(PriceAlert alert) async {
    final restored = await _serial(() => _repo.restore(alert));
    _insert(restored);
  }

  Future<void> setActive(String id, {required bool active}) async {
    final current = state.valueOrNull ?? const <PriceAlert>[];
    final index = current.indexWhere((a) => a.id == id);
    if (index < 0) return;
    _requireOnline();
    final before = current[index];
    final optimistic = before.moveTo(active ? AlertStatus.active : AlertStatus.paused);
    if (optimistic == null) return;
    state = AsyncData([...current]..[index] = optimistic);
    try {
      // الـ repository بيرجّع النسخة المحفوظة (إذا اشتغل قبل الإيقاف بيضل Triggered)
      final saved = await _serial(() => _repo.setActive(id, active: active));
      _replace(saved);
    } catch (_) {
      _replace(before);
      rethrow;
    }
  }

  /// فحص الأسعار (من النبضات، ولما التطبيق يرجع للواجهة): بينهي يلي انتهت
  /// مدتهم، وبيشغّل يلي السعر عبر مستواهم. بيرجّع يلي اشتغلوا **هلق** (كل
  /// تنبيه مرة وحدة بس، حتى مع نبضات كتير ورا بعض حوالين المستوى).
  Future<List<PriceAlert>> checkQuotes(Map<String, Quote> quotes) async {
    List<PriceAlert> list;
    try {
      list = state.valueOrNull ?? await future;
    } catch (_) {
      return const [];
    }
    final now = _now();
    final due = list.any((a) => a.isDue(now));
    final hits = <(String, Quote)>[
      for (final a in list)
        if (quotes[a.symbol] case final q? when !_checking.contains(a.id) && a.reactsTo(q.price)) (a.id, q),
    ];
    if (!due && hits.isEmpty) return const [];
    _checking.addAll(hits.map((h) => h.$1));
    try {
      return await _serial(() async {
        final triggered = <PriceAlert>[];
        if (due) (await _repo.expireDue(now)).forEach(_replace);
        for (final (id, quote) in hits) {
          final changed = await _repo.applyPrice(id, price: quote.price, at: quote.time);
          if (changed == null) continue;
          _replace(changed);
          if (changed.status == AlertStatus.triggered) triggered.add(changed);
        }
        return triggered;
      });
    } finally {
      _checking.removeAll(hits.map((h) => h.$1));
    }
  }

  void _insert(PriceAlert alert, {int? at}) {
    final current = [...?state.valueOrNull]..removeWhere((a) => a.id == alert.id);
    final position = (at ?? current.indexWhere((a) => a.createdAt.isBefore(alert.createdAt)))
        .clamp(-1, current.length);
    if (position < 0) {
      current.add(alert);
    } else {
      current.insert(position, alert);
    }
    state = AsyncData(current);
  }

  /// بس إذا لسّا بالقائمة (تنبيه انحذف ما بيرجع من فحص قديم)
  void _replace(PriceAlert alert) {
    final current = state.valueOrNull;
    if (current == null || !current.any((a) => a.id == alert.id)) return;
    state = AsyncData([for (final a in current) a.id == alert.id ? alert : a]);
  }
}

final alertsViewModelProvider =
    AsyncNotifierProvider<AlertsViewModel, List<PriceAlert>>(AlertsViewModel.new);

/// تنبيهات أداة وحدة (شاشة السوق)
final alertsForSymbolProvider = Provider.family<AsyncValue<List<PriceAlert>>, String>(
  (ref, symbol) => ref
      .watch(alertsViewModelProvider)
      .whenData((list) => [for (final a in list) if (a.symbol == symbol) a]),
);

/// عدد التنبيهات بقسم "Active" (نشطة + موقوفة) - تسمية قسم Alerts بالإشعارات
final activeAlertCountProvider = Provider<int>(
  (ref) => ref.watch(alertsViewModelProvider.select(
    (v) => v.valueOrNull?.where((a) => !a.status.isHistory).length ?? 0,
  )),
);
