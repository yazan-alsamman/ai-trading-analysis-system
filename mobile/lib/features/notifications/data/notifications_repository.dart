import 'dart:convert';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/data/json.dart';
import '../../../core/storage/preferences_provider.dart';
import '../../../l10n/app_localizations.dart';
import '../models/app_notification.dart';
import '../../../core/data/network_status.dart';
import '../../../core/database/cache_support.dart';
import '../../../core/database/database_providers.dart';
import '../../../core/database/user_cache_guard.dart';
import '../../markets/data/market_providers.dart';
import 'caching_notifications_repository.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';

/// `NotificationRead` (backend/app/schemas/notifications.py) → domain
final class NotificationDto {
  const NotificationDto(this.json);

  final Json json;

  AppNotification? toDomain() {
    final id = json.string('id');
    final kind = NotificationKind.fromApi(json.string('type'));
    final title = json.string('title')?.trim();
    final createdAt = json.dateTime('created_at');
    if (id == null || kind == null || title == null || title.isEmpty || createdAt == null) return null;
    final symbol = json.object('data')?.string('symbol')?.trim().toUpperCase();
    return AppNotification(
      id: id,
      kind: kind,
      title: title,
      body: json.string('body')?.trim() ?? '',
      createdAt: createdAt,
      symbol: symbol == null || symbol.isEmpty ? null : symbol,
      readAt: json.dateTime('read_at'),
    );
  }
}

/// مصدر الإشعارات - بيتبدّل بتنفيذ API (`/notifications`).
/// النص جاي من الخادم بلغة الحساب، فـ [languageCode] بيوصل مع الطلب.
abstract interface class NotificationsRepository {
  Future<List<AppNotification>> list({required String languageCode});
  Future<void> setRead(String id, {required bool read});
  Future<void> markAllRead();
  Future<void> delete(String id);

  /// يرجّع إشعار انحذف (Undo)
  Future<void> restore(String id);

  /// H4a: إشعار داخل التطبيق لتنبيه سعر اشتغل (نوع `price_alert`، `data.symbol`
  /// بيفتح الأداة). مرة وحدة لكل تنبيه: نفس [PriceAlertNotice.notificationId]
  /// تاني مرة = false وما بينضاف شي.
  /// TODO(API): الخادم بينشئه لما التنبيه يشتغل و`GET /me/notifications` بيرجّعه
  /// (`type: price_alert`، `data: {symbol, alert_id, value, price}`)؛ التطبيق ما بيبعتو.
  Future<bool> addPriceAlert(PriceAlertNotice notice);
}

/// إشعارات محاكاة بالذاكرة: نفس شكل الـ JSON حتى طبقة الـ DTO تنفحص، والنص
/// بيتبنى بلغة الطلب (فتبديل اللغة بيترجم الإشعارات وبيحافظ على المقروء).
/// إشعارات التنبيهات (H4a) بتنحفظ بـ [prefs] (مفتاح [alertsStorageKey]) إذا
/// موجود، فبتضل بعد إعادة التشغيل.
class SimulatedNotificationsRepository implements NotificationsRepository {
  SimulatedNotificationsRepository({DateTime Function()? clock, this.latency = Duration.zero, this.prefs})
      : _clock = clock ?? DateTime.now,
        _created = (clock ?? DateTime.now)().toUtc() {
    _rows = [
      for (final (i, seed) in _seeds.indexed)
        _Row(
          id: 'notif-${i + 1}',
          seed: seed,
          createdAt: _created.subtract(seed.age),
          readAt: seed.read ? _created.subtract(seed.age) : null,
        ),
      ..._readAlertRows(),
    ];
  }

  static const alertsStorageKey = 'alert_notifications';

  final DateTime Function() _clock;
  final DateTime _created;
  final Duration latency;
  final SharedPreferences? prefs;
  late final List<_Row> _rows;

  static const _seeds = [
    _Seed('signal', 'EUR/USD', Duration(minutes: 12), read: false),
    _Seed('price_alert', 'XAU/USD', Duration(minutes: 47), read: false),
    _Seed('signal', 'GBP/USD', Duration(hours: 2, minutes: 10), read: false),
    _Seed('system', null, Duration(hours: 5), read: true),
    _Seed('price_alert', 'USD/JPY', Duration(days: 1, hours: 2), read: true),
    _Seed('system', null, Duration(days: 2), read: true),
  ];

  Map<String, Object?> _json(_Row row, AppLocalizations l10n) {
    if (row.notice case final n?) {
      return {
        'id': row.id,
        'type': 'price_alert',
        'title': l10n.notifAlertTriggeredTitle(n.symbol, n.level),
        'body': l10n.notifAlertTriggeredBody(n.price),
        'data': {'symbol': n.symbol, 'alert_id': n.alertId},
        'severity': 'info',
        'created_at': row.createdAt.toIso8601String(),
        'read_at': row.readAt?.toIso8601String(),
      };
    }
    final seed = row.seed!;
    final (title, body) = switch (row.id) {
      'notif-1' => (l10n.notifOpportunityTitle('EUR/USD', l10n.directionLong, '1h'), l10n.notifOpportunityBody('64%')),
      'notif-2' => (l10n.notifAlertAboveTitle('XAU/USD'), l10n.notifAlertAboveBody),
      'notif-3' => (l10n.notifOpportunityTitle('GBP/USD', l10n.directionShort, '4h'), l10n.notifOpportunityBody('58%')),
      'notif-4' => (l10n.notifSimulatedTitle, l10n.notifSimulatedBody),
      'notif-5' => (l10n.notifAlertBelowTitle('USD/JPY'), l10n.notifAlertBelowBody),
      _ => (l10n.notifWelcomeTitle, l10n.notifWelcomeBody),
    };
    return {
      'id': row.id,
      'type': seed.type,
      'title': title,
      'body': body,
      'data': {if (seed.symbol != null) 'symbol': seed.symbol},
      'severity': 'info',
      'created_at': row.createdAt.toIso8601String(),
      'read_at': row.readAt?.toIso8601String(),
    };
  }

  @override
  Future<List<AppNotification>> list({required String languageCode}) async {
    if (latency > Duration.zero) await Future<void>.delayed(latency);
    final l10n = AppLocalizations(Locale(languageCode));
    // الأحدث أول (إشعارات التنبيهات بتنضاف بآخر القائمة)
    final visible = [for (final r in _rows) if (!r.deleted) r]..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return mapValid(
      [for (final r in visible) _json(r, l10n)],
      (m) => NotificationDto(Json(m)).toDomain(),
    );
  }

  _Row _row(String id) => _rows.firstWhere((r) => r.id == id, orElse: () => throw StateError('notification $id not found'));

  @override
  Future<void> setRead(String id, {required bool read}) async {
    final row = _row(id);
    row.readAt = read ? (row.readAt ?? _clock().toUtc()) : null;
    await _saveAlertRows();
  }

  @override
  Future<void> markAllRead() async {
    final now = _clock().toUtc();
    for (final r in _rows) {
      r.readAt ??= now;
    }
    await _saveAlertRows();
  }

  @override
  Future<void> delete(String id) async {
    _row(id).deleted = true;
    await _saveAlertRows();
  }

  @override
  Future<void> restore(String id) async {
    _row(id).deleted = false;
    await _saveAlertRows();
  }

  @override
  Future<bool> addPriceAlert(PriceAlertNotice notice) async {
    // حتى لو انحذف: نفس التنبيه ما بيعمل إشعار تاني
    if (_rows.any((r) => r.id == notice.notificationId)) return false;
    _rows.add(_Row(id: notice.notificationId, notice: notice, createdAt: notice.at.toUtc()));
    await _saveAlertRows();
    return true;
  }

  List<_Row> _readAlertRows() {
    try {
      final raw = jsonDecode(prefs?.getString(alertsStorageKey) ?? '[]');
      if (raw is! List) return const [];
      return [
        for (final item in raw)
          if (item is Map<String, Object?>)
            if (_Row.fromJson(Json(item)) case final row?) row,
      ];
    } catch (_) {
      return const [];
    }
  }

  Future<void> _saveAlertRows() async {
    final store = prefs;
    if (store == null) return;
    await store.setString(alertsStorageKey, jsonEncode([for (final r in _rows) if (r.notice != null) r.toJson()]));
  }
}

final class _Seed {
  const _Seed(this.type, this.symbol, this.age, {required this.read});

  final String type;
  final String? symbol;
  final Duration age;
  final bool read;
}

/// صف واحد: إشعار تجريبي ثابت ([seed]) أو إشعار تنبيه اشتغل ([notice])
final class _Row {
  _Row({required this.id, required this.createdAt, this.seed, this.notice, this.readAt, this.deleted = false});

  final String id;
  final _Seed? seed;
  final PriceAlertNotice? notice;
  final DateTime createdAt;
  DateTime? readAt;
  bool deleted;

  static _Row? fromJson(Json json) {
    final id = json.string('id');
    final alertId = json.string('alert_id');
    final symbol = json.string('symbol');
    final level = json.string('level');
    final price = json.string('price');
    final at = json.dateTime('created_at');
    if (id == null || alertId == null || symbol == null || level == null || price == null || at == null) return null;
    final notice = PriceAlertNotice(alertId: alertId, symbol: symbol, level: level, price: price, at: at);
    if (id != notice.notificationId) return null;
    return _Row(
      id: id,
      notice: notice,
      createdAt: at,
      readAt: json.dateTime('read_at'),
      deleted: json.boolean('deleted') ?? false,
    );
  }

  Map<String, Object?> toJson() => {
        'id': id,
        'alert_id': notice!.alertId,
        'symbol': notice!.symbol,
        'level': notice!.level,
        'price': notice!.price,
        'created_at': createdAt.toUtc().toIso8601String(),
        'read_at': readAt?.toUtc().toIso8601String(),
        'deleted': deleted,
      };
}

/// مصدر الإشعارات نفسه (محاكاة أو API) - يلي بيتبدّل بالـ API
final notificationsSourceRepositoryProvider = Provider<NotificationsRepository>((ref) {
  // H5c: المحاكاة بتحفظ المقروء / المحذوف بالذاكرة → نسخة جديدة لكل حساب
  ref.watch(cacheOwnerProvider);
  return apiSource(
    ref,
    ApiFeature.notifications,
    simulated: () => SimulatedNotificationsRepository(
      latency: const Duration(milliseconds: 300),
      prefs: ref.watch(sharedPreferencesProvider),
    ),
  );
});

/// H5b: كاش الإشعارات (نفس قاعدة Drift)
final notificationsCacheProvider =
    Provider<NotificationsCache>((ref) => NotificationsCache(ref.watch(appDatabaseProvider)));

/// يلي بتقرأه الشاشات: المصدر، وفوقه طبقة الكاش (H5b، نفس مفتاح
/// `kMarketOfflineCache`). خاص بالحساب الداخل.
final notificationsRepositoryProvider = Provider<NotificationsRepository>(createNotificationsRepository);

/// منطق [notificationsRepositoryProvider] (الاختبارات بترجّعه)
NotificationsRepository createNotificationsRepository(Ref ref) {
  final source = ref.watch(notificationsSourceRepositoryProvider);
  if (!ref.watch(marketCacheEnabledProvider)) return source;
  final caching = CachingNotificationsRepository(
    source: source,
    cache: ref.watch(notificationsCacheProvider),
    isOffline: () => ref.read(networkStatusProvider) == NetworkStatus.offline,
    owner: ref.watch(cacheOwnerProvider),
    ownerStillCurrent: ownerStillCurrent(ref, ref.read(cacheOwnerProvider)),
    clock: ref.watch(marketCacheClockProvider),
  );
  ref.onDispose(caching.savedAt.dispose);
  return caching;
}

/// H5b: وقت النسخة المحفوظة المعروضة (`inbox:<lang>`) - null = حيّة
final notificationsSavedAtProvider = Provider.family<DateTime?, String>((ref, key) {
  final repo = ref.watch(notificationsRepositoryProvider);
  return watchSavedAt(ref, repo is CachingNotificationsRepository ? repo.savedAt : null, key);
});
