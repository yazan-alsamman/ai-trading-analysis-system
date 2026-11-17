import 'package:drift/drift.dart';

part 'app_database.g.dart';

// ═══════════════════════════════════════════════════════════
// App Database (H5a) - كاش محلي بـ Drift (SQLite)
// ═══════════════════════════════════════════════════════════
//
// كاش بس، مش مصدر حقيقة: إذا انضرب الملف بينمسح وبينعمل من جديد
// ([AppDatabaseHolder]). بيانات السوق مش خاصة بمستخدم، فما بتنمسح مع
// تسجيل الخروج. H5b: الصفوف الخاصة بمستخدم (owner) بتنمسح مع تسجيل الخروج
// ([AppDatabase.clearUserRows]).
//
// الأوقات أعداد صحيحة (ميلي ثانية UTC) بدل DateTime تبع Drift (هيداك
// بيخزّن ثواني بس وبيضيّع الدقة).
//
// بعد أي تعديل على الجداول: dart run build_runner build

/// آخر سعر لكل أداة
@DataClassName('CachedQuoteRow')
class CachedQuotes extends Table {
  TextColumn get symbol => text()();

  RealColumn get price => real()();

  /// التغيّر خلال 24 ساعة (السعر - سعر قبل 24 ساعة)
  RealColumn get change => real()();

  /// وقت السعر نفسه (ms UTC) = "Last updated"
  IntColumn get updatedAt => integer()();

  @override
  Set<Column> get primaryKey => {symbol};
}

/// شموع (أداة، إطار) - الفهرس الفريد هو نفسه مفتاح الـ upsert وترتيب القراءة
@DataClassName('CachedCandleRow')
@TableIndex(name: 'idx_cached_candles_series', columns: {#symbol, #timeframe, #openTime}, unique: true)
class CachedCandles extends Table {
  IntColumn get id => integer().autoIncrement()();

  TextColumn get symbol => text()();

  /// `Timeframe.apiValue` (1m، 15m، 1h، 4h، 1d)
  TextColumn get timeframe => text()();

  /// بداية الشمعة (ms UTC)
  IntColumn get openTime => integer()();

  RealColumn get open => real()();

  RealColumn get high => real()();

  RealColumn get low => real()();

  RealColumn get close => real()();

  RealColumn get volume => real()();
}

/// متى انكتب كل جزء من الكاش آخر مرة (`quotes`، `candles:EUR/USD:1h`)
@DataClassName('CacheMetaRow')
class CacheMeta extends Table {
  TextColumn get key => text()();

  /// ms UTC
  IntColumn get updatedAt => integer()();

  @override
  Set<Column> get primaryKey => {key};
}

/// H5b: إشارات محفوظة. [scope] = `feed` (قائمة Signals للاستراتيجية المحفوظة)،
/// `item` (إشارة انفتحت أو انطلبت)، `read:<SYMBOL>:<method>` (آخر رأي نموذج
/// للأداة). [owner] = معرّف المستخدم للصفوف الخاصة فيه (القائمة والمطلوبة)،
/// `''` = مش خاص بحدا (آراء النموذج). [payload] = JSON بشكل الـ API.
@DataClassName('CachedSignalRow')
class CachedSignals extends Table {
  TextColumn get scope => text()();

  TextColumn get owner => text()();

  TextColumn get id => text()();

  /// الترتيب جوّا القائمة
  IntColumn get position => integer()();

  TextColumn get payload => text()();

  /// ms UTC
  IntColumn get savedAt => integer()();

  /// صلاحية الإشارة (ms UTC) - التقليم بيشيل يلي خلصت من زمان
  IntColumn get validUntil => integer()();

  @override
  Set<Column> get primaryKey => {scope, owner, id};
}

/// H5b: آخر قائمة أخبار لكل لغة + مزاج السوق ([kind] = `article` أو `mood`)
@DataClassName('CachedNewsRow')
class CachedNews extends Table {
  TextColumn get language => text()();

  TextColumn get kind => text()();

  TextColumn get id => text()();

  IntColumn get position => integer()();

  TextColumn get payload => text()();

  /// ms UTC
  IntColumn get savedAt => integer()();

  @override
  Set<Column> get primaryKey => {language, kind, id};
}

/// H5b: آخر صندوق إشعارات لكل (مستخدم، لغة) - خاص بالمستخدم دايمًا
@DataClassName('CachedNotificationRow')
class CachedNotifications extends Table {
  TextColumn get owner => text()();

  TextColumn get language => text()();

  TextColumn get id => text()();

  IntColumn get position => integer()();

  TextColumn get payload => text()();

  /// ms UTC
  IntColumn get savedAt => integer()();

  @override
  Set<Column> get primaryKey => {owner, language, id};
}

/// مفاتيح [CacheMeta] الخاصة بمستخدم بتبلّش هيك (بتنمسح مع تسجيل الخروج)
const String kUserMetaPrefix = 'user:';

@DriftDatabase(tables: [CachedQuotes, CachedCandles, CacheMeta, CachedSignals, CachedNews, CachedNotifications])
class AppDatabase extends _$AppDatabase {
  AppDatabase(super.executor);

  /// 1 = H5a (أسعار، شموع، meta). 2 = H5b (+ إشارات، أخبار، إشعارات).
  @override
  int get schemaVersion => 2;

  @override
  MigrationStrategy get migration => MigrationStrategy(
        onCreate: (m) => m.createAll(),
        onUpgrade: (m, from, to) async {
          // ترحيل حقيقي لقدّام: البيانات الموجودة (أسعار وشموع) بتضل
          if (from >= 1 && from < to && to == schemaVersion) {
            if (from < 2) {
              await m.createTable(cachedSignals);
              await m.createTable(cachedNews);
              await m.createTable(cachedNotifications);
            }
            return;
          }
          // نسخة مش معروفة (أو رجوع لنسخة أقدم): كاش، فمنبنيه من جديد
          for (final table in allTables.toList().reversed) {
            await m.deleteTable(table.actualTableName);
          }
          await m.createAll();
        },
      );

  /// بيمسح كل الكاش (Settings → Developer)
  Future<void> clearAll() => transaction(() async {
        for (final table in allTables) {
          await delete(table).go();
        }
      });

  /// H5b: تسجيل الخروج - بيمسح كل شي خاص بمستخدم (قائمة Signals والإشارات
  /// المطلوبة، الإشعارات، وأوقاتهن). بيانات السوق والأخبار والآراء العامة بتضل.
  /// H5c: [keep] = الحساب الداخل هلق (صفوفه بتضل، صفوف أي حساب تاني بتروح).
  Future<void> clearUserRows({String? keep}) => transaction(() async {
        Expression<bool> notKept(GeneratedColumn<String> owner) =>
            keep == null ? const Constant(true) : owner.equals(keep).not();
        await (delete(cachedSignals)..where((s) => s.owner.equals('').not() & notKept(s.owner))).go();
        await (delete(cachedNotifications)..where((n) => notKept(n.owner))).go();
        await (delete(cacheMeta)
              ..where((m) =>
                  m.key.like('$kUserMetaPrefix%') &
                  (keep == null ? const Constant(true) : m.key.like('$kUserMetaPrefix$keep:%').not())))
            .go();
      });
}
