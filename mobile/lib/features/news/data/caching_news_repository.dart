import 'dart:convert';

import 'package:drift/drift.dart';

import '../../../core/data/json.dart';
import '../../../core/database/app_database.dart';
import '../../../core/database/app_database_holder.dart';
import '../../../core/database/cache_support.dart';
import '../../comments/models/comment.dart';
import '../../markets/data/market_cache.dart';
import '../models/news_models.dart';
import 'news_repository.dart';

/// خبر → شكل `ArticleRead` (حتى يرجع من [newsArticleFromJson] نفسه)
Map<String, Object?> newsArticleToJson(NewsArticle a) => {
      'id': a.id,
      'source': {'name': a.source},
      'title': a.title,
      'summary': a.summary,
      'body': a.body,
      'published_at': a.publishedAt.toUtc().toIso8601String(),
      'instruments': [for (final s in a.symbols) {'symbol': s}],
      'comments_count': a.commentsCount,
      if (a.sentiment != null) 'sentiment': {'label': a.sentiment!.name},
    };

/// مزاج السوق → شكل `SentimentAggregate`
Map<String, Object?> marketMoodToJson(MarketMood m) => {
      'overall': {
        'positive': m.positive,
        'neutral': m.neutral,
        'negative': m.negative,
        'mean_score': m.meanScore,
      },
    };

T? _decode<T>(String payload, T? Function(Json json) map) {
  try {
    final json = Json.from(jsonDecode(payload));
    return json == null ? null : map(json);
  } on FormatException {
    return null;
  }
}

/// H5b: آخر قائمة أخبار لكل لغة + آخر مزاج سوق (جدول `cached_news`). القائمة
/// بتنكتب كلها بـ transaction وحدة (بتحلّ محل القديمة، أول [maxArticles] بس).
/// الأخبار مش خاصة بمستخدم.
class NewsCache {
  NewsCache(this._db, {this.maxArticles = 50});

  final AppDatabaseHolder _db;
  final int maxArticles;

  static const String _article = 'article';
  static const String _mood = 'mood';

  Future<void> saveArticles(String language, List<NewsArticle> articles, DateTime at) =>
      _db.run((db) => db.transaction(() async {
            await (db.delete(db.cachedNews)..where((n) => n.language.equals(language) & n.kind.equals(_article))).go();
            final ms = at.toUtc().millisecondsSinceEpoch;
            await db.batch((b) {
              b.insertAll(db.cachedNews, [
                for (final (i, a) in articles.take(maxArticles).indexed)
                  CachedNewsCompanion.insert(
                    language: language,
                    kind: _article,
                    id: a.id,
                    position: i,
                    payload: jsonEncode(newsArticleToJson(a)),
                    savedAt: ms,
                  ),
              ]);
            });
            await db.into(db.cacheMeta).insertOnConflictUpdate(
                  CacheMetaCompanion.insert(key: 'news:$language', updatedAt: ms),
                );
          }));

  Future<Cached<List<NewsArticle>>?> readArticles(String language) => _db.run((db) async {
        final meta = await (db.select(db.cacheMeta)..where((m) => m.key.equals('news:$language'))).getSingleOrNull();
        if (meta == null) return null;
        final rows = await (db.select(db.cachedNews)
              ..where((n) => n.language.equals(language) & n.kind.equals(_article))
              ..orderBy([(n) => OrderingTerm.asc(n.position)]))
            .get();
        return Cached(
          [
            for (final r in rows)
              if (_decode(r.payload, newsArticleFromJson) case final a?) a,
          ],
          DateTime.fromMillisecondsSinceEpoch(meta.updatedAt, isUtc: true),
        );
      });

  Future<void> saveMood(MarketMood mood, DateTime at) => _db.run((db) => db.into(db.cachedNews).insertOnConflictUpdate(
        CachedNewsCompanion.insert(
          language: '',
          kind: _mood,
          id: 'overall',
          position: 0,
          payload: jsonEncode(marketMoodToJson(mood)),
          savedAt: at.toUtc().millisecondsSinceEpoch,
        ),
      ));

  Future<Cached<MarketMood>?> readMood() => _db.run((db) async {
        final row = await (db.select(db.cachedNews)..where((n) => n.kind.equals(_mood) & n.id.equals('overall')))
            .getSingleOrNull();
        final mood = row == null ? null : _decode(row.payload, marketMoodFromJson);
        return mood == null ? null : Cached(mood, DateTime.fromMillisecondsSinceEpoch(row!.savedAt, isUtc: true));
      });

  /// عدد الأخبار المحفوظة للغة (الاختبارات)
  Future<int> count(String language) => _db.run((db) async =>
      (await (db.select(db.cachedNews)..where((n) => n.language.equals(language) & n.kind.equals(_article))).get())
          .length);
}

/// H5b: Decorator فوق أي [NewsRepository] - نفس نمط H5a. الأخبار والمزاج
/// بينحفظوا وبيرجعوا من الكاش بدون اتصال أو لما المصدر يفشل. التعليقات
/// (قراءة وكتابة) بتروح للمصدر دايمًا: بدون اتصال الشاشة بتقول إنها بدها اتصال.
class CachingNewsRepository with BackgroundCacheWrites implements NewsRepository {
  CachingNewsRepository({
    required this.source,
    required this.cache,
    required this.isOffline,
    DateTime Function()? clock,
  }) : _clock = clock ?? DateTime.now;

  final NewsRepository source;
  final NewsCache cache;
  final bool Function() isOffline;
  final DateTime Function() _clock;

  /// `articles:<lang>` / `mood` → وقت النسخة المحفوظة المعروضة
  final SavedAtTracker savedAt = SavedAtTracker();

  static String articlesKey(String language) => 'articles:$language';

  static const String moodKey = 'mood';

  @override
  String get cacheLabel => 'NewsCache';

  @override
  Future<List<NewsArticle>> articles({required String languageCode}) async {
    final key = articlesKey(languageCode);
    Future<List<NewsArticle>> fromCache(Object error) async {
      final cached = await readSafely(() => cache.readArticles(languageCode));
      if (cached == null) throw error;
      savedAt.served([key], cached.updatedAt);
      return cached.value;
    }

    if (isOffline()) return fromCache(const NoSavedDataException());
    try {
      final list = await source.articles(languageCode: languageCode);
      savedAt.live([key]);
      writeInBackground(() => cache.saveArticles(languageCode, list, _clock()));
      return list;
    } catch (error) {
      return fromCache(error);
    }
  }

  @override
  Future<MarketMood> mood() async {
    Future<MarketMood> fromCache(Object error) async {
      final cached = await readSafely(cache.readMood);
      if (cached == null) throw error;
      savedAt.served([moodKey], cached.updatedAt);
      return cached.value;
    }

    if (isOffline()) return fromCache(const NoSavedDataException());
    try {
      final mood = await source.mood();
      savedAt.live([moodKey]);
      writeInBackground(() => cache.saveMood(mood, _clock()));
      return mood;
    } catch (error) {
      return fromCache(error);
    }
  }

  @override
  Future<List<Comment>> comments(String articleId, {required String languageCode}) =>
      source.comments(articleId, languageCode: languageCode);

  @override
  Future<Comment> addComment(String articleId, String body) => source.addComment(articleId, body);

  @override
  Future<void> deleteComment(String articleId, String commentId) => source.deleteComment(articleId, commentId);

  @override
  Future<void> restoreComment(String articleId, String commentId) => source.restoreComment(articleId, commentId);
}
