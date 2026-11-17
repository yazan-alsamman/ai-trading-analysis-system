import 'dart:convert';

import 'package:drift/drift.dart';

import '../../../core/data/json.dart';
import '../../../core/database/app_database.dart';
import '../../../core/database/app_database_holder.dart';
import '../../../core/database/cache_support.dart';
import '../../markets/data/market_cache.dart';
import '../models/app_notification.dart';
import 'notifications_repository.dart';

/// إشعار → شكل `NotificationRead` (حتى يرجع من [NotificationDto] نفسه)
Map<String, Object?> notificationToJson(AppNotification n) => {
      'id': n.id,
      'type': switch (n.kind) {
        NotificationKind.priceAlert => 'price_alert',
        NotificationKind.opportunity => 'signal',
        NotificationKind.system => 'system',
      },
      'title': n.title,
      'body': n.body,
      'data': {if (n.symbol != null) 'symbol': n.symbol},
      'created_at': n.createdAt.toUtc().toIso8601String(),
      'read_at': n.readAt?.toUtc().toIso8601String(),
    };

/// H5b: آخر صندوق إشعارات لكل (مستخدم، لغة) - جدول `cached_notifications`.
/// خاص بالمستخدم دايمًا: بينقرأ بمعرّفه بس وبينمسح مع تسجيل الخروج. القائمة
/// بتنكتب كلها بـ transaction وحدة (بتحلّ محل القديمة، أول [maxItems] بس).
class NotificationsCache {
  NotificationsCache(this._db, {this.maxItems = 100});

  final AppDatabaseHolder _db;
  final int maxItems;

  static String _metaKey(String owner, String language) => userMetaKey(owner, 'notifications:$language');

  Future<void> save(String owner, String language, List<AppNotification> list, DateTime at) =>
      _db.run((db) => db.transaction(() async {
            await (db.delete(db.cachedNotifications)
                  ..where((n) => n.owner.equals(owner) & n.language.equals(language)))
                .go();
            final ms = at.toUtc().millisecondsSinceEpoch;
            await db.batch((b) {
              b.insertAll(db.cachedNotifications, [
                for (final (i, n) in list.take(maxItems).indexed)
                  CachedNotificationsCompanion.insert(
                    owner: owner,
                    language: language,
                    id: n.id,
                    position: i,
                    payload: jsonEncode(notificationToJson(n)),
                    savedAt: ms,
                  ),
              ]);
            });
            await db.into(db.cacheMeta).insertOnConflictUpdate(
                  CacheMetaCompanion.insert(key: _metaKey(owner, language), updatedAt: ms),
                );
          }));

  Future<Cached<List<AppNotification>>?> read(String owner, String language) => _db.run((db) async {
        final meta =
            await (db.select(db.cacheMeta)..where((m) => m.key.equals(_metaKey(owner, language)))).getSingleOrNull();
        if (meta == null) return null;
        final rows = await (db.select(db.cachedNotifications)
              ..where((n) => n.owner.equals(owner) & n.language.equals(language))
              ..orderBy([(n) => OrderingTerm.asc(n.position)]))
            .get();
        return Cached(
          [
            for (final r in rows)
              if (_decode(r.payload) case final n?) n,
          ],
          DateTime.fromMillisecondsSinceEpoch(meta.updatedAt, isUtc: true),
        );
      });

  /// عدد الصفوف (الاختبارات) - [owner] null = الكل
  Future<int> count({String? owner}) => _db.run((db) async {
        final query = db.select(db.cachedNotifications);
        if (owner != null) query.where((n) => n.owner.equals(owner));
        return (await query.get()).length;
      });

  static AppNotification? _decode(String payload) {
    try {
      final json = Json.from(jsonDecode(payload));
      return json == null ? null : NotificationDto(json).toDomain();
    } on FormatException {
      return null;
    }
  }
}

/// H5b: Decorator فوق أي [NotificationsRepository] - نفس نمط H5a. القائمة
/// بتنحفظ للمستخدم [owner] وبترجع من الكاش بدون اتصال أو لما المصدر يفشل؛
/// مش داخل ([owner] فاضي) = ما في حفظ ولا قراءة. الأفعال (مقروء، حذف، ...)
/// بتروح للمصدر دايمًا.
class CachingNotificationsRepository with BackgroundCacheWrites implements NotificationsRepository {
  CachingNotificationsRepository({
    required this.source,
    required this.cache,
    required this.isOffline,
    required this.owner,
    this.ownerStillCurrent,
    DateTime Function()? clock,
  }) : _clock = clock ?? DateTime.now;

  final NotificationsRepository source;
  final NotificationsCache cache;
  final bool Function() isOffline;
  final String owner;

  /// H5c: الحساب لسّا داخل؟ جواب وصل بعد الخروج / التبديل ما بينحفظ إلو
  final bool Function()? ownerStillCurrent;
  final DateTime Function() _clock;

  /// `inbox:<lang>` → وقت النسخة المحفوظة المعروضة
  final SavedAtTracker savedAt = SavedAtTracker();

  static String inboxKey(String language) => 'inbox:$language';

  @override
  String get cacheLabel => 'NotificationsCache';

  @override
  Future<List<AppNotification>> list({required String languageCode}) async {
    final key = inboxKey(languageCode);
    Future<List<AppNotification>> fromCache(Object error) async {
      if (owner.isEmpty) throw error;
      final cached = await readSafely(() => cache.read(owner, languageCode));
      if (cached == null) throw error;
      savedAt.served([key], cached.updatedAt);
      return cached.value;
    }

    if (isOffline()) return fromCache(const NoSavedDataException());
    try {
      final list = await source.list(languageCode: languageCode);
      savedAt.live([key]);
      writeInBackground(() async {
        if (owner.isNotEmpty && (ownerStillCurrent?.call() ?? true)) {
          await cache.save(owner, languageCode, list, _clock());
        }
      });
      return list;
    } catch (error) {
      return fromCache(error);
    }
  }

  @override
  Future<void> setRead(String id, {required bool read}) => source.setRead(id, read: read);

  @override
  Future<void> markAllRead() => source.markAllRead();

  @override
  Future<void> delete(String id) => source.delete(id);

  @override
  Future<void> restore(String id) => source.restore(id);

  @override
  Future<bool> addPriceAlert(PriceAlertNotice notice) => source.addPriceAlert(notice);
}
