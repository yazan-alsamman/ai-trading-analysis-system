import 'package:flutter/foundation.dart';

import '../../../core/data/json.dart';

/// قنوات التوصيل (نفس الويب + Push للموبايل). التوصيل نفسه شغل الـ backend.
enum NotificationChannel { push, inApp, email, telegram }

/// أنواع الإشعارات (نفس مركز الإشعارات): تنبيه سعر / فرصة / نظام
enum NotificationKind { priceAlert, opportunity, system }

@immutable
final class NotificationPreferences {
  const NotificationPreferences({required this.channels, required this.kinds});

  final Set<NotificationChannel> channels;
  final Set<NotificationKind> kinds;

  /// الافتراضي: Push + داخل التطبيق، وكل الأنواع
  static const NotificationPreferences defaults = NotificationPreferences(
    channels: {NotificationChannel.push, NotificationChannel.inApp},
    kinds: {NotificationKind.priceAlert, NotificationKind.opportunity, NotificationKind.system},
  );

  /// بدون ولا قناة ما في شي بيوصل (الشاشة بتنبّه)
  bool get isMuted => channels.isEmpty;

  /// H4b: إشعار داخل التطبيق من هالنوع بيوصل؟ (قناة "داخل التطبيق" + النوع مفعّلين)
  bool deliversInApp(NotificationKind kind) => channels.contains(NotificationChannel.inApp) && kinds.contains(kind);

  NotificationPreferences toggleChannel(NotificationChannel channel, bool on) => NotificationPreferences(
        channels: on ? {...channels, channel} : ({...channels}..remove(channel)),
        kinds: kinds,
      );

  NotificationPreferences toggleKind(NotificationKind kind, bool on) => NotificationPreferences(
        channels: channels,
        kinds: on ? {...kinds, kind} : ({...kinds}..remove(kind)),
      );

  Map<String, Object?> toJson() => {
        'channels': [for (final c in channels) c.name],
        'kinds': [for (final k in kinds) k.name],
      };

  static NotificationPreferences fromJson(Json json) {
    Set<T> read<T extends Enum>(String key, List<T> values) => switch (json.raw[key]) {
          final List<Object?> list => {
              for (final v in values)
                if (list.contains(v.name)) v,
            },
          _ => const {},
        };
    if (json.raw['channels'] is! List || json.raw['kinds'] is! List) return defaults;
    return NotificationPreferences(
      channels: read('channels', NotificationChannel.values),
      kinds: read('kinds', NotificationKind.values),
    );
  }

  @override
  bool operator ==(Object other) =>
      other is NotificationPreferences && setEquals(other.channels, channels) && setEquals(other.kinds, kinds);

  @override
  int get hashCode => Object.hash(Object.hashAllUnordered(channels), Object.hashAllUnordered(kinds));
}
