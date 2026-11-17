import 'package:drift/drift.dart';
import 'package:flutter/foundation.dart';

import '../../../core/database/app_database.dart';
import '../../../core/database/app_database_holder.dart';
import '../models/market_models.dart';

/// بعد هالمدة البيانات المحفوظة بتنعلّم "Old data"
const Duration kCacheOldAfter = Duration(hours: 24);

/// البيانات المحفوظة أقدم من [kCacheOldAfter]؟ (الحد نفسه لسّا مش قديم)
bool isOldData(DateTime updatedAt, DateTime now) => now.difference(updatedAt) > kCacheOldAfter;

/// شي محفوظ + متى انكتب آخر مرة
@immutable
final class Cached<T> {
  const Cached(this.value, this.updatedAt);

  final T value;
  final DateTime updatedAt;
}

/// كاش السوق فوق [AppDatabaseHolder]: أسعار وشموع ووقت آخر كتابة.
///
/// كل كتابة بـ transaction وحدة (upsert + تقليم + meta)، فقراءة بالنص ما
/// بتشوف نص كتابة. الشموع محدودة: آخر [maxCandlesPerSeries] لكل (أداة، إطار).
class MarketCache {
  MarketCache(this._db, {this.maxCandlesPerSeries = 300});

  final AppDatabaseHolder _db;
  final int maxCandlesPerSeries;

  static const String quotesKey = 'quotes';

  static String candlesKey(String symbol, Timeframe timeframe) => 'candles:$symbol:${timeframe.apiValue}';

  // ── أسعار ──────────────────────────────────────────────────

  Future<void> saveQuotes(Iterable<Quote> quotes, DateTime at) async {
    final list = quotes.toList();
    if (list.isEmpty) return;
    await _db.run((db) => db.transaction(() async {
          await db.batch((b) {
            b.insertAllOnConflictUpdate(db.cachedQuotes, [
              for (final q in list)
                CachedQuotesCompanion.insert(
                  symbol: q.symbol,
                  price: q.price,
                  change: q.price - q.reference,
                  updatedAt: q.time.toUtc().millisecondsSinceEpoch,
                ),
            ]);
          });
          await _touch(db, quotesKey, at);
        }));
  }

  /// null = ما في أسعار محفوظة
  Future<Cached<List<Quote>>?> readQuotes() => _db.run((db) async {
        final rows = await db.select(db.cachedQuotes).get();
        if (rows.isEmpty) return null;
        final quotes = [
          for (final r in rows)
            Quote(
              symbol: r.symbol,
              price: r.price,
              reference: r.price - r.change,
              time: DateTime.fromMillisecondsSinceEpoch(r.updatedAt, isUtc: true),
            ),
        ];
        final at = await _metaTime(db, quotesKey) ?? _latest(quotes.map((q) => q.time));
        return Cached(quotes, at);
      });

  // ── شموع ───────────────────────────────────────────────────

  Future<void> saveCandles(String symbol, Timeframe timeframe, List<Candle> candles, DateTime at) async {
    if (candles.isEmpty) return;
    final tf = timeframe.apiValue;
    await _db.run((db) => db.transaction(() async {
          await db.batch((b) {
            b.insertAll(
              db.cachedCandles,
              [
                for (final c in candles)
                  CachedCandlesCompanion.insert(
                    symbol: symbol,
                    timeframe: tf,
                    openTime: c.time.toUtc().millisecondsSinceEpoch,
                    open: c.open,
                    high: c.high,
                    low: c.low,
                    close: c.close,
                    volume: c.volume,
                  ),
              ],
              mode: InsertMode.insertOrReplace,
            );
          });
          await _prune(db, symbol, tf);
          await _touch(db, candlesKey(symbol, timeframe), at);
        }));
  }

  /// آخر [limit] شمعة تصاعديًا - null = ما في شي محفوظ لهالإطار
  Future<Cached<List<Candle>>?> readCandles(String symbol, Timeframe timeframe, {int limit = 300}) =>
      _db.run((db) async {
        final query = db.select(db.cachedCandles)
          ..where((c) => c.symbol.equals(symbol) & c.timeframe.equals(timeframe.apiValue))
          ..orderBy([(c) => OrderingTerm.desc(c.openTime)])
          ..limit(limit);
        final rows = await query.get();
        if (rows.isEmpty) return null;
        final candles = [
          for (final r in rows.reversed)
            Candle(
              time: DateTime.fromMillisecondsSinceEpoch(r.openTime, isUtc: true),
              open: r.open,
              high: r.high,
              low: r.low,
              close: r.close,
              volume: r.volume,
            ),
        ];
        final at = await _metaTime(db, candlesKey(symbol, timeframe)) ?? candles.last.time;
        return Cached(candles, at);
      });

  /// عدد الشموع المحفوظة لسلسلة (الاختبارات)
  Future<int> candleCount(String symbol, Timeframe timeframe) => _db.run((db) async {
        final count = db.cachedCandles.id.count();
        final query = db.selectOnly(db.cachedCandles)
          ..addColumns([count])
          ..where(db.cachedCandles.symbol.equals(symbol) & db.cachedCandles.timeframe.equals(timeframe.apiValue));
        return (await query.getSingle()).read(count) ?? 0;
      });

  Future<void> clear() => _db.run((db) => db.clearAll());

  // ── داخلي ──────────────────────────────────────────────────

  /// بيشيل الأقدم من آخر [maxCandlesPerSeries] (نفس الـ transaction)
  Future<void> _prune(AppDatabase db, String symbol, String tf) => db.customUpdate(
        'DELETE FROM cached_candles WHERE symbol = ?1 AND timeframe = ?2 AND open_time < ('
        'SELECT open_time FROM cached_candles WHERE symbol = ?1 AND timeframe = ?2 '
        'ORDER BY open_time DESC LIMIT 1 OFFSET ?3)',
        variables: [Variable.withString(symbol), Variable.withString(tf), Variable.withInt(maxCandlesPerSeries - 1)],
        updates: {db.cachedCandles},
        updateKind: UpdateKind.delete,
      );

  Future<void> _touch(AppDatabase db, String key, DateTime at) => db
      .into(db.cacheMeta)
      .insertOnConflictUpdate(CacheMetaCompanion.insert(key: key, updatedAt: at.toUtc().millisecondsSinceEpoch));

  Future<DateTime?> _metaTime(AppDatabase db, String key) async {
    final row = await (db.select(db.cacheMeta)..where((m) => m.key.equals(key))).getSingleOrNull();
    return row == null ? null : DateTime.fromMillisecondsSinceEpoch(row.updatedAt, isUtc: true);
  }

  static DateTime _latest(Iterable<DateTime> times) => times.reduce((a, b) => a.isAfter(b) ? a : b);
}
