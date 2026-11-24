import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/shell/shell_tab.dart';
import '../../../core/data/low_data_mode.dart';
import '../../../core/data/network_status.dart';
import '../../../core/database/cache_support.dart';
import '../../../core/database/user_cache_guard.dart';
import '../../../providers/locale_provider.dart';
import '../data/caching_notifications_repository.dart';
import '../data/notification_preferences_repository.dart';
import '../data/notifications_repository.dart';
import '../models/app_notification.dart';
import '../models/notification_preferences.dart' as prefs;

/// ViewModel مركز الإشعارات (مشترك: الجرس بالـ Home بيقرأ عدد غير المقروء).
///
/// - تبديل اللغة بيعيد التحميل (النص من الخادم بلغة الحساب).
/// - مقروء / حذف متفائلين (الواجهة فورًا) وبيرجعوا لو فشل الطلب.
/// - سحب للتحديث مرتين ورا بعض: نتيجة الطلب الأقدم بتنرمى (عدّاد أجيال).
/// - H4b: تنبيهات السعر والفرص بتتبع التفضيلات (قناة "داخل التطبيق" + النوع)؛
///   المطفي ما بيظهر بالقائمة ولا بالجرس. TODO(API): الخادم ما بينشئها أصلًا.
class NotificationsViewModel extends AsyncNotifier<List<AppNotification>> {
  var _generation = 0;

  NotificationsRepository get _repo => ref.read(notificationsRepositoryProvider);

  String get _language => ref.read(localeProvider).languageCode;

  @override
  Future<List<AppNotification>> build() async {
    final language = ref.watch(localeProvider.select((l) => l.languageCode));
    ref.watch(_inAppKindsProvider);
    final repo = ref.watch(notificationsRepositoryProvider);
    // H5c: حساب تاني (أو خروج): الصندوق والعدّاد القديمين بينمسحوا من الذاكرة
    // قبل إعادة البناء (Riverpod بيحمل القيمة السابقة لقدّام، حتى offline)
    ref.watch(cacheOwnerProvider);
    ref.listen<String>(cacheOwnerProvider, (_, __) => state = const AsyncData([]));
    // H5b: رجع الاتصال وإحنا على نسخة محفوظة أو حالة الـ offline → تحميل من
    // جديد (الجرس بالـ Home: بالـ Low data mode بيستنّى لحد ما الـ Home يبيّن)
    reloadWhenBackOnline(
      ref,
      tab: ShellTab.home,
      needed: () =>
          state.error is NoSavedDataException ||
          (repo is CachingNotificationsRepository &&
              repo.savedAt[CachingNotificationsRepository.inboxKey(language)] != null),
      reload: ref.invalidateSelf,
    );
    _generation++;
    return _delivered(await repo.list(languageCode: language));
  }

  /// بدون اتصال (H5b، فوق الكاش) ما في شي يتحدّث: الشاشة بتقول ليش
  Future<void> refresh() async {
    if (_repo is CachingNotificationsRepository && ref.read(networkStatusProvider) == NetworkStatus.offline) {
      throw const NoSavedDataException();
    }
    final generation = ++_generation;
    final list = await _repo.list(languageCode: _language);
    if (generation == _generation) state = AsyncData(_delivered(list));
  }

  List<AppNotification> _delivered(List<AppNotification> list) {
    final allowed = ref.read(_inAppKindsProvider);
    return [
      for (final n in list)
        if (switch (n.kind) {
          NotificationKind.priceAlert => allowed.priceAlert,
          NotificationKind.opportunity => allowed.opportunity,
          NotificationKind.system => true,
        })
          n,
    ];
  }

  Future<void> setRead(String id, {required bool read}) async {
    final before = _find(id);
    if (before == null || before.isRead == read) return;
    _replace(before.withRead(read));
    try {
      await _repo.setRead(id, read: read);
    } catch (_) {
      _replace(before);
      rethrow;
    }
  }

  Future<void> markAllRead() async {
    final before = state.valueOrNull;
    if (before == null || before.every((n) => n.isRead)) return;
    state = AsyncData([for (final n in before) n.withRead(true)]);
    try {
      await _repo.markAllRead();
    } catch (_) {
      state = AsyncData(before);
      rethrow;
    }
  }

  /// بيرجّع الإشعار المحذوف (لزر Undo)
  Future<AppNotification?> remove(String id) async {
    final current = state.valueOrNull ?? const <AppNotification>[];
    final index = current.indexWhere((n) => n.id == id);
    if (index < 0) return null;
    final removed = current[index];
    state = AsyncData([...current]..removeAt(index));
    try {
      await _repo.delete(id);
      return removed;
    } catch (_) {
      _insert(removed);
      rethrow;
    }
  }

  Future<void> undoRemove(AppNotification notification) async {
    await _repo.restore(notification.id);
    _insert(notification);
  }

  AppNotification? _find(String id) {
    for (final n in state.valueOrNull ?? const <AppNotification>[]) {
      if (n.id == id) return n;
    }
    return null;
  }

  void _replace(AppNotification notification) {
    final current = state.valueOrNull;
    if (current == null) return;
    state = AsyncData([for (final n in current) n.id == notification.id ? notification : n]);
  }

  /// بيرجع لمكانه حسب الوقت (الأحدث فوق)
  void _insert(AppNotification notification) {
    final current = [...?state.valueOrNull]..removeWhere((n) => n.id == notification.id);
    final at = current.indexWhere((n) => n.createdAt.isBefore(notification.createdAt));
    current.insert(at < 0 ? current.length : at, notification);
    state = AsyncData(current);
  }
}

/// أنواع بتوصل داخل التطبيق (H4b) - تغيير غيرها ما بيعيد التحميل
final _inAppKindsProvider = Provider<({bool priceAlert, bool opportunity})>((ref) {
  final p = ref.watch(notificationPreferencesProvider);
  return (
    priceAlert: p.deliversInApp(prefs.NotificationKind.priceAlert),
    opportunity: p.deliversInApp(prefs.NotificationKind.opportunity),
  );
});

final notificationsViewModelProvider =
    AsyncNotifierProvider<NotificationsViewModel, List<AppNotification>>(NotificationsViewModel.new);

/// عدد غير المقروء (شارة الجرس) - 0 لحد ما توصل القائمة
final unreadNotificationsProvider = Provider<int>(
  (ref) => ref.watch(notificationsViewModelProvider.select(
    (v) => v.valueOrNull?.where((n) => !n.isRead).length ?? 0,
  )),
);
