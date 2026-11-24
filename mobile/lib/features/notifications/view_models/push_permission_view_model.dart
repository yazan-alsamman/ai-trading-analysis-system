import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/app_lifecycle.dart';
import '../../../core/data/network_status.dart';
import '../../../core/storage/preferences_provider.dart';
import '../data/notification_permission_service.dart';
import '../data/notification_preferences_repository.dart';
import '../data/push_device_repository.dart';
import '../models/notification_preferences.dart';

/// إذن الإشعارات (H4b). بيرجع يقرأ لما التطبيق يرجع للواجهة (المستخدم ممكن
/// غيّرو من إعدادات الهاتف).
class PushPermissionViewModel extends AsyncNotifier<PushPermission> {
  var _busy = false;

  NotificationPermissionService get _service => ref.read(notificationPermissionServiceProvider);

  @override
  Future<PushPermission> build() {
    ref.listen<bool>(appActiveProvider, (previous, active) {
      if (previous == false && active) unawaited(_reload());
    });
    return ref.watch(notificationPermissionServiceProvider).status();
  }

  Future<void> _reload() async {
    final next = await AsyncValue.guard(_service.status);
    if (next.hasValue && next.value != state.valueOrNull) state = next;
  }

  /// تشغيل Push. أول مرة ([PushPermission.notAsked]) بيعرض [explain] ("Why we
  /// ask") قبل سؤال النظام؛ رفض سابق = سؤال النظام مباشرة؛ محظور = ما في سؤال.
  /// ضغطة مكرّرة وهو شغّال = null.
  Future<PushPermission?> enable({required Future<bool> Function() explain}) async {
    if (_busy) return null;
    _busy = true;
    try {
      final preferences = ref.read(notificationPreferencesProvider.notifier);
      var permission = state.valueOrNull ?? await future;
      if (permission == PushPermission.notAsked && !await explain()) {
        // "Not now": المحفوظ متل المعروض (مطفي)
        await preferences.setChannel(NotificationChannel.push, false);
        return permission;
      }
      // محظور = ما في سؤال (من إعدادات الهاتف بس)
      if (permission == PushPermission.notAsked || permission == PushPermission.denied) {
        permission = await _service.request();
        state = AsyncData(permission);
      }
      await preferences.setChannel(NotificationChannel.push, permission == PushPermission.granted);
      return permission;
    } finally {
      _busy = false;
    }
  }

  Future<void> disable() =>
      ref.read(notificationPreferencesProvider.notifier).setChannel(NotificationChannel.push, false);
}

final pushPermissionProvider =
    AsyncNotifierProvider<PushPermissionViewModel, PushPermission>(PushPermissionViewModel.new);

/// Push فعليًا شغّال؟ (مفعّل **و** مسموح بالنظام)
final pushChannelActiveProvider = Provider<bool>((ref) {
  final on = ref.watch(notificationPreferencesProvider.select((p) => p.channels.contains(NotificationChannel.push)));
  return on && ref.watch(pushPermissionProvider).valueOrNull == PushPermission.granted;
});

// ── تسجيل token الجهاز ──────────────────────────────────────

enum PushRegistration {
  /// Push مطفي أو مش مسموح: ما في أي محاولة تسجيل
  off,

  /// بانتظار اتصال (أو فشل): بينبعت لما يرجع الاتصال
  pending,

  /// الـ token الحالي انبعت
  registered,
}

/// بيسجّل token الجهاز مرة وحدة لكل token، بس لما Push شغّال ومسموح. بدون
/// اتصال الـ token بيضل pending (محفوظ) وبينبعت لما يرجع الاتصال أو بالتشغيل الجاي.
class PushRegistrationController extends Notifier<PushRegistration> {
  static const registeredKey = 'push_token_registered';
  static const pendingKey = 'push_token_pending';

  var _running = false;
  var _again = false;

  @override
  PushRegistration build() {
    ref.listen<bool>(pushChannelActiveProvider, (_, __) => unawaited(sync()));
    ref.listen<NetworkStatus>(networkStatusProvider, (previous, next) {
      if (next == NetworkStatus.online && previous != next) unawaited(sync());
    });
    scheduleMicrotask(() => unawaited(sync()));
    final prefs = ref.read(sharedPreferencesProvider);
    if (prefs.getString(pendingKey) != null) return PushRegistration.pending;
    return PushRegistration.off;
  }

  /// فحص واحد بنفس الوقت؛ تغيير بالنص بيعيد الفحص بعدو
  Future<void> sync() async {
    if (_running) {
      _again = true;
      return;
    }
    _running = true;
    try {
      do {
        _again = false;
        await _syncOnce();
      } while (_again);
    } finally {
      _running = false;
    }
  }

  Future<void> _syncOnce() async {
    if (!ref.read(pushChannelActiveProvider)) {
      state = ref.read(sharedPreferencesProvider).getString(pendingKey) == null
          ? PushRegistration.off
          : PushRegistration.pending;
      return;
    }
    final prefs = ref.read(sharedPreferencesProvider);
    final String token;
    try {
      token = await ref.read(pushTokenSourceProvider).token();
    } catch (_) {
      return;
    }
    if (prefs.getString(registeredKey) == token) {
      await prefs.remove(pendingKey);
      state = PushRegistration.registered;
      return;
    }
    if (ref.read(networkStatusProvider) == NetworkStatus.offline) {
      await prefs.setString(pendingKey, token);
      state = PushRegistration.pending;
      return;
    }
    try {
      await ref.read(pushDeviceRepositoryProvider).registerDeviceToken(token);
      await prefs.setString(registeredKey, token);
      await prefs.remove(pendingKey);
      state = PushRegistration.registered;
    } catch (_) {
      // فشل/انقطع: بيضل pending وبينعاد لما يرجع الاتصال
      await prefs.setString(pendingKey, token);
      state = PushRegistration.pending;
    }
  }
}

final pushRegistrationProvider =
    NotifierProvider<PushRegistrationController, PushRegistration>(PushRegistrationController.new);
