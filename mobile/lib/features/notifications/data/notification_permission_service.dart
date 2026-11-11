import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/storage/preferences_provider.dart';

/// إذن الإشعارات بالنظام (H4b):
/// - [notAsked]: ما انسأل لسّا (أول تشغيل لـ Push بيعرض "Why we ask" أول)
/// - [granted]: مسموح
/// - [denied]: انرفض مرة، فينا نسأل كمان مرة
/// - [blocked]: انرفض نهائيًا، بس من إعدادات الهاتف
enum PushPermission { notAsked, granted, denied, blocked }

/// إذن الإشعارات من النظام - واجهة حتى الاختبارات والمحاكاة ما يلمسوا المنصة.
/// TODO(FCM): التنفيذ الحقيقي (Android 13+ `POST_NOTIFICATIONS`، iOS
/// `requestPermission`) مع firebase_messaging بخطوة الـ FCM، مش هون.
abstract interface class NotificationPermissionService {
  Future<PushPermission> status();

  /// بيسأل النظام (إذا لسّا مسموح يسأل) وبيرجّع الحالة الجديدة
  Future<PushPermission> request();
}

/// محاكاة: الحالة محفوظة على الجهاز متل ما النظام بيحفظها. [allow] = جواب
/// المستخدم على سؤال النظام؛ رفض تاني بعد رفض = [PushPermission.blocked].
class SimulatedNotificationPermissionService implements NotificationPermissionService {
  SimulatedNotificationPermissionService(this.prefs, {this.allow = true, PushPermission? initial}) {
    if (initial != null) prefs.setString(storageKey, initial.name);
  }

  static const storageKey = 'push_permission_simulated';

  final SharedPreferences prefs;

  /// جواب المستخدم على سؤال النظام
  bool allow;

  /// كم مرة انسأل النظام فعليًا (للاختبارات)
  var requests = 0;

  @override
  Future<PushPermission> status() async => _read();

  PushPermission _read() {
    final raw = prefs.getString(storageKey);
    return PushPermission.values.firstWhere((p) => p.name == raw, orElse: () => PushPermission.notAsked);
  }

  @override
  Future<PushPermission> request() async {
    final current = _read();
    if (current == PushPermission.granted || current == PushPermission.blocked) return current;
    requests++;
    final next = allow
        ? PushPermission.granted
        : (current == PushPermission.denied ? PushPermission.blocked : PushPermission.denied);
    await prefs.setString(storageKey, next.name);
    return next;
  }
}

/// token الجهاز للإشعارات.
/// TODO(FCM): `FirebaseMessaging.instance.getToken()` + `onTokenRefresh` بخطوة الـ FCM.
abstract interface class PushTokenSource {
  Future<String> token();
}

/// token ثابت (محاكاة) - ما في Firebase بهالخطوة
class SimulatedPushTokenSource implements PushTokenSource {
  SimulatedPushTokenSource([this.value = 'simulated-device-token-1']);

  String value;

  @override
  Future<String> token() async => value;
}

final notificationPermissionServiceProvider = Provider<NotificationPermissionService>(
  (ref) => SimulatedNotificationPermissionService(ref.watch(sharedPreferencesProvider)),
);

final pushTokenSourceProvider = Provider<PushTokenSource>((ref) => SimulatedPushTokenSource());
