import 'dart:convert';

import 'package:drift/drift.dart';

import '../../../core/data/json.dart';
import '../../../core/database/app_database.dart';
import '../../../core/database/app_database_holder.dart';
import '../../../core/database/cache_support.dart';
import '../../../core/widgets/direction_badge.dart';
import '../../markets/data/market_cache.dart';
import '../models/analysis_method.dart';
import '../models/analysis_request.dart';
import '../models/model_accuracy.dart';
import '../models/opportunity.dart';
import '../models/signal_feed.dart';
import '../models/signal_profile.dart';
import 'opportunity_dto.dart';
import 'signals_repository.dart';

/// فرصة → نفس شكل الـ API (`OpportunitySchema`) حتى ترجع من نفس الـ DTO
Map<String, Object?> opportunityToJson(Opportunity o) => {
      'id': o.id,
      'symbol': o.symbol,
      'timeframe': o.timeframe.apiValue,
      'status': o.status == OpportunityStatus.detected ? 'detected' : 'not_detected',
      'direction': switch (o.direction) {
        SignalDirection.long => 'long',
        SignalDirection.short => 'short',
        SignalDirection.neutral => 'neutral',
      },
      'setupType': switch (o.setupType) {
        SetupType.trendFollowing => 'trend_following',
        SetupType.meanReversion => 'mean_reversion',
        SetupType.breakout => 'breakout',
        SetupType.scalping => 'scalping',
      },
      'riskLevel': o.riskLevel.name,
      'probability': o.probability,
      'entryZone': {'low': o.entryZone.low, 'high': o.entryZone.high},
      'stopLossZone': {'low': o.stopLossZone.low, 'high': o.stopLossZone.high},
      'takeProfitZone': {'low': o.takeProfitZone.low, 'high': o.takeProfitZone.high},
      'riskReward': o.riskReward,
      'generatedAt': o.generatedAt.millisecondsSinceEpoch,
      'validUntil': o.validUntil.millisecondsSinceEpoch,
      'methodId': o.methodId,
      if (o.indicator != null) 'indicator': o.indicator,
      if (o.requestedByYou) 'requestedByYou': true,
    };

Opportunity? _decode(String payload) {
  try {
    final json = Json.from(jsonDecode(payload));
    return json == null ? null : OpportunityDto.fromJson(json).toDomain();
  } on FormatException {
    return null;
  }
}

/// H5b: كاش الإشارات فوق [AppDatabaseHolder] (جدول `cached_signals`).
///
/// - قائمة (`feed` للمستخدم، `read:<SYMBOL>:<method>` عامة) بتنكتب كلها بـ
///   transaction وحدة (بتحلّ محل القديمة) + وقتها بـ `cache_meta`.
/// - إشارة لحالها (`item`): آخر [maxItems] بس، والأقدم بينشال.
/// - التقليم: أي صف صلاحيته خلصت من أكتر من [keepExpiredFor] بينشال.
class SignalsCache {
  SignalsCache(this._db, {this.maxItems = 50, this.maxListLength = 100, this.keepExpiredFor = const Duration(days: 7)});

  final AppDatabaseHolder _db;
  final int maxItems;
  final int maxListLength;
  final Duration keepExpiredFor;

  static const String feedScope = 'feed';
  static const String itemScope = 'item';

  static String readScope(String symbol, String methodId) => 'read:$symbol:$methodId';

  static String _metaKey(String scope, String owner) =>
      owner.isEmpty ? 'signals:$scope' : userMetaKey(owner, 'signals:$scope');

  Future<void> saveList(String scope, String owner, List<Opportunity> list, DateTime at) =>
      _db.run((db) => db.transaction(() async {
            await (db.delete(db.cachedSignals)..where((s) => s.scope.equals(scope) & s.owner.equals(owner))).go();
            final ms = at.toUtc().millisecondsSinceEpoch;
            await db.batch((b) {
              b.insertAll(db.cachedSignals, [
                for (final (i, o) in list.take(maxListLength).indexed)
                  CachedSignalsCompanion.insert(
                    scope: scope,
                    owner: owner,
                    id: o.id,
                    position: i,
                    payload: jsonEncode(opportunityToJson(o)),
                    savedAt: ms,
                    validUntil: o.validUntil.toUtc().millisecondsSinceEpoch,
                  ),
              ]);
            });
            await db.into(db.cacheMeta).insertOnConflictUpdate(
                  CacheMetaCompanion.insert(key: _metaKey(scope, owner), updatedAt: ms),
                );
            await _prune(db, at);
          }));

  /// null = ما في شي محفوظ لهالقائمة
  Future<Cached<List<Opportunity>>?> readList(String scope, String owner) => _db.run((db) async {
        final meta = await (db.select(db.cacheMeta)..where((m) => m.key.equals(_metaKey(scope, owner))))
            .getSingleOrNull();
        if (meta == null) return null;
        final rows = await (db.select(db.cachedSignals)
              ..where((s) => s.scope.equals(scope) & s.owner.equals(owner))
              ..orderBy([(s) => OrderingTerm.asc(s.position)]))
            .get();
        return Cached(
          [
            for (final r in rows)
              if (_decode(r.payload) case final o?) o,
          ],
          DateTime.fromMillisecondsSinceEpoch(meta.updatedAt, isUtc: true),
        );
      });

  Future<void> saveItem(Opportunity o, String owner, DateTime at) => _db.run((db) => db.transaction(() async {
        await db.into(db.cachedSignals).insertOnConflictUpdate(CachedSignalsCompanion.insert(
              scope: itemScope,
              owner: owner,
              id: o.id,
              position: 0,
              payload: jsonEncode(opportunityToJson(o)),
              savedAt: at.toUtc().millisecondsSinceEpoch,
              validUntil: o.validUntil.toUtc().millisecondsSinceEpoch,
            ));
        await _prune(db, at);
      }));

  /// إشارة بمعرّفها: إشارة محفوظة لحالها أول، بعدين أي قائمة محفوظة فيها
  /// (للمستخدم [owner] أو العامة بس - ولا مرة لحساب تاني)
  Future<Cached<Opportunity>?> readItem(String id, String owner) => _db.run((db) async {
        final rows = await (db.select(db.cachedSignals)
              ..where((s) => s.id.equals(id) & s.owner.isIn({owner, ''}))
              ..orderBy([
                (s) => OrderingTerm(expression: s.scope.equals(itemScope), mode: OrderingMode.desc),
                (s) => OrderingTerm.desc(s.savedAt),
              ]))
            .get();
        for (final r in rows) {
          final o = _decode(r.payload);
          if (o != null) return Cached(o, DateTime.fromMillisecondsSinceEpoch(r.savedAt, isUtc: true));
        }
        return null;
      });

  /// عدد الصفوف (الاختبارات) - [owner] null = الكل
  Future<int> count({String? scope, String? owner}) => _db.run((db) async {
        final query = db.select(db.cachedSignals)
          ..where((s) {
            Expression<bool> e = const Constant(true);
            if (scope != null) e = e & s.scope.equals(scope);
            if (owner != null) e = e & s.owner.equals(owner);
            return e;
          });
        return (await query.get()).length;
      });

  Future<void> _prune(AppDatabase db, DateTime now) async {
    final cutoff = now.toUtc().subtract(keepExpiredFor).millisecondsSinceEpoch;
    await (db.delete(db.cachedSignals)..where((s) => s.validUntil.isSmallerThanValue(cutoff))).go();
    // آخر [maxItems] إشارة لحالها (كل المستخدمين سوا)
    await db.customUpdate(
      'DELETE FROM cached_signals WHERE scope = ?1 AND rowid NOT IN ('
      'SELECT rowid FROM cached_signals WHERE scope = ?1 ORDER BY saved_at DESC LIMIT ?2)',
      variables: [Variable.withString(itemScope), Variable.withInt(maxItems)],
      updates: {db.cachedSignals},
      updateKind: UpdateKind.delete,
    );
  }
}

/// H5b: Decorator فوق أي [SignalsRepository] (محاكاة أو API) - نفس نمط
/// `CachingMarketDataRepository`: القراءات بتنحفظ بالخلفية وبترجع من الكاش
/// بدون اتصال أو لما المصدر يفشل. الأفعال (طلب تحليل) بتروح للمصدر دايمًا.
///
/// - قائمة Signals والإشارات المطلوبة خاصة بـ [owner] (فاضي = مش داخل = ما
///   بتنحفظ). آراء النموذج لكل أداة عامة.
/// - بدون اتصال: ما منطلب من المصدر، الكاش أو [NoSavedDataException].
/// - [savedAt]: `feed` / `item:<id>` / `read:<SYMBOL>:<method>` → وقت النسخة
///   المحفوظة المعروضة ("Last updated").
class CachingSignalsRepository with BackgroundCacheWrites implements SignalsRepository {
  CachingSignalsRepository({
    required this.source,
    required this.cache,
    required this.isOffline,
    required this.owner,
    this.ownerStillCurrent,
    DateTime Function()? clock,
  }) : _clock = clock ?? DateTime.now;

  final SignalsRepository source;
  final SignalsCache cache;
  final bool Function() isOffline;
  final String owner;

  /// H5c: الحساب لسّا داخل؟ جواب وصل بعد الخروج / التبديل ما بينحفظ إلو
  final bool Function()? ownerStillCurrent;

  bool get _personalWritesAllowed => owner.isNotEmpty && (ownerStillCurrent?.call() ?? true);
  final DateTime Function() _clock;

  final SavedAtTracker savedAt = SavedAtTracker();

  static const String feedKey = 'feed';

  static String itemKey(String id) => 'item:$id';

  static String readKey(String symbol, String methodId) => 'read:$symbol:$methodId';

  @override
  String get cacheLabel => 'SignalsCache';

  @override
  bool get isSimulated => source.isSimulated;

  @override
  Future<ModelAccuracy> accuracy() => source.accuracy();

  @override
  Future<List<Opportunity>> opportunities(String symbol, {String methodId = AnalysisMethod.defaultId}) async {
    final scope = SignalsCache.readScope(symbol, methodId);
    final key = readKey(symbol, methodId);
    Future<List<Opportunity>> fromCache(Object error) async {
      final cached = await readSafely(() => cache.readList(scope, ''));
      if (cached == null) throw error;
      savedAt.served([key, for (final o in cached.value) itemKey(o.id)], cached.updatedAt);
      return cached.value;
    }

    if (isOffline()) return fromCache(const NoSavedDataException());
    try {
      final list = await source.opportunities(symbol, methodId: methodId);
      savedAt.live([key, for (final o in list) itemKey(o.id)]);
      writeInBackground(() => cache.saveList(scope, '', list, _clock()));
      return list;
    } catch (error) {
      return fromCache(error);
    }
  }

  @override
  Future<List<Opportunity>> feed(SignalProfile profile) async {
    Future<List<Opportunity>> fromCache(Object error) async {
      if (owner.isEmpty) throw error;
      final cached = await readSafely(() => cache.readList(SignalsCache.feedScope, owner));
      if (cached == null) throw error;
      // الاستراتيجية تغيّرت من وقت الحفظ: بس يلي لسّا بيطابقوها
      final list = [
        for (final o in cached.value)
          if (o.requestedByYou || matchesSignalProfile(o, profile)) o,
      ];
      savedAt.served([feedKey, for (final o in list) itemKey(o.id)], cached.updatedAt);
      return list;
    }

    if (isOffline()) return fromCache(const NoSavedDataException());
    try {
      final list = await source.feed(profile);
      savedAt.live([feedKey, for (final o in list) itemKey(o.id)]);
      writeInBackground(() async {
        if (_personalWritesAllowed) await cache.saveList(SignalsCache.feedScope, owner, list, _clock());
      });
      return list;
    } catch (error) {
      return fromCache(error);
    }
  }

  @override
  Future<Opportunity?> opportunity(String id) async {
    Future<Opportunity?> fromCache(Object error) async {
      final cached = await readSafely(() => cache.readItem(id, owner));
      if (cached == null) throw error;
      savedAt.served([itemKey(id)], cached.updatedAt);
      return cached.value;
    }

    if (isOffline()) return fromCache(const NoSavedDataException());
    try {
      final o = await source.opportunity(id);
      savedAt.live([itemKey(id)]);
      if (o != null) _saveItem(o);
      return o;
    } catch (error) {
      return fromCache(error);
    }
  }

  /// فعل: بيحتاج اتصال (الشاشة بتفحص قبل)، والنتيجة المكتشفة بتنحفظ للمستخدم
  @override
  Future<Opportunity> requestAnalysis(
    AnalysisRequest request, {
    AnalysisCancelToken? cancel,
    void Function(AnalysisStage stage)? onStage,
  }) async {
    final result = await source.requestAnalysis(request, cancel: cancel, onStage: onStage);
    if (result.isDetected) _saveItem(result);
    return result;
  }

  /// المطلوبة خاصة بالمستخدم؛ غيرها عامة
  void _saveItem(Opportunity o) {
    final itemOwner = o.requestedByYou ? owner : '';
    if (o.requestedByYou && owner.isEmpty) return;
    writeInBackground(() async {
      if (o.requestedByYou && !_personalWritesAllowed) return;
      await cache.saveItem(o, itemOwner, _clock());
    });
  }
}
