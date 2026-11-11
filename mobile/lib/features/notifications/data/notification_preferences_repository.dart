import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/data/json.dart';
import '../../../core/storage/preferences_provider.dart';
import '../models/notification_preferences.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';

/// مصدر تفضيلات الإشعارات - بيتبدّل بـ API (NotificationHub) بعدين
abstract interface class NotificationPreferencesRepository {
  NotificationPreferences read();

  Future<void> save(NotificationPreferences preferences);
}

final class LocalNotificationPreferencesRepository implements NotificationPreferencesRepository {
  const LocalNotificationPreferencesRepository(this.prefs);

  static const storageKey = 'notification_preferences';

  final SharedPreferences prefs;

  @override
  NotificationPreferences read() {
    final raw = prefs.getString(storageKey);
    if (raw == null) return NotificationPreferences.defaults;
    try {
      final json = Json.from(jsonDecode(raw));
      return json == null ? NotificationPreferences.defaults : NotificationPreferences.fromJson(json);
    } on FormatException {
      return NotificationPreferences.defaults;
    }
  }

  @override
  Future<void> save(NotificationPreferences preferences) =>
      prefs.setString(storageKey, jsonEncode(preferences.toJson()));
}

final notificationPreferencesRepositoryProvider = Provider<NotificationPreferencesRepository>(
  (ref) => apiSource(
    ref,
    ApiFeature.notificationPreferences,
    simulated: () => LocalNotificationPreferencesRepository(ref.watch(sharedPreferencesProvider)),
  ),
);

/// كل مفتاح بيتطبّق وبينحفظ فورًا (ما في زر حفظ)
class NotificationPreferencesNotifier extends Notifier<NotificationPreferences> {
  @override
  NotificationPreferences build() => ref.watch(notificationPreferencesRepositoryProvider).read();

  Future<void> setChannel(NotificationChannel channel, bool on) => _save(state.toggleChannel(channel, on));

  Future<void> setKind(NotificationKind kind, bool on) => _save(state.toggleKind(kind, on));

  Future<void> _save(NotificationPreferences next) async {
    state = next;
    await ref.read(notificationPreferencesRepositoryProvider).save(next);
  }
}

final notificationPreferencesProvider =
    NotifierProvider<NotificationPreferencesNotifier, NotificationPreferences>(
  NotificationPreferencesNotifier.new,
);
