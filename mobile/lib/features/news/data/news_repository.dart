import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/json.dart';
import '../../../l10n/app_localizations.dart';
import '../../comments/data/comments_source.dart';
import '../../comments/models/comment.dart';
import '../../markets/models/market_models.dart';
import '../models/news_models.dart';
import '../../../core/data/network_status.dart';
import '../../../core/database/cache_support.dart';
import '../../../core/database/database_providers.dart';
import '../../markets/data/market_providers.dart';
import 'caching_news_repository.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';

/// `ArticleRead` (backend/app/schemas/news.py) → domain.
/// `body` و `comments_count` مش بـ ArticleRead لسّا (الملخص بس) - لما
/// ينضافوا بالـ API بيوصلوا بنفس الأسماء.
NewsArticle? newsArticleFromJson(Json json) {
  final id = json.string('id');
  final title = json.string('title')?.trim();
  final publishedAt = json.dateTime('published_at');
  if (id == null || title == null || title.isEmpty || publishedAt == null) return null;
  final summary = json.string('summary')?.trim() ?? '';
  return NewsArticle(
    id: id,
    source: json.object('source')?.string('name') ?? '',
    title: title,
    summary: summary,
    body: json.string('body')?.trim() ?? summary,
    publishedAt: publishedAt,
    symbols: [
      for (final tag in json.objects('instruments'))
        if (tag.string('symbol')?.toUpperCase() case final s? when kProductSymbols.contains(s)) s,
    ],
    commentsCount: json.integer('comments_count') ?? 0,
    sentiment: Sentiment.fromApi(json.object('sentiment')?.string('label')),
  );
}

/// `SentimentAggregate.overall` → domain (null لو ناقص أو غير منطقي)
MarketMood? marketMoodFromJson(Json json) {
  final overall = json.object('overall');
  if (overall == null) return null;
  final positive = overall.integer('positive');
  final neutral = overall.integer('neutral');
  final negative = overall.integer('negative');
  if (positive == null || neutral == null || negative == null) return null;
  if (positive < 0 || neutral < 0 || negative < 0) return null;
  final mean = overall.number('mean_score');
  return MarketMood(
    positive: positive,
    neutral: neutral,
    negative: negative,
    meanScore: mean?.clamp(-1.0, 1.0),
  );
}

/// مصدر الأخبار والتعليقات - بيتبدّل بتنفيذ API (`/news`, `/news/sentiment`)
/// (التعليقات: [CommentsSource] - `/news/{id}/comments`).
abstract interface class NewsRepository implements CommentsSource {
  Future<List<NewsArticle>> articles({required String languageCode});

  /// مزاج آخر 24 ساعة
  Future<MarketMood> mood();
}

/// أخبار محاكاة: 4 أخبار ثابتة، تعليقات تجريبية، وتعليقات المستخدم بالذاكرة
/// (بتضل طول ما التطبيق شغّال). كل شي بيطلع كـ JSON حتى الـ mappers تنفحص.
class SimulatedNewsRepository implements NewsRepository {
  SimulatedNewsRepository({DateTime Function()? clock, this.latency = Duration.zero})
      : _clock = clock ?? DateTime.now;

  final DateTime Function() _clock;
  final Duration latency;
  late final DateTime _created = _clock().toUtc();

  /// تعليقات المستخدم لكل خبر (الأحدث أول)
  final Map<String, List<Map<String, Object?>>> _own = {};

  /// تعليقات (تجريبية أو للمستخدم) انحذفت - بترجع بالـ Undo
  final Map<String, Set<String>> _deleted = {};
  var _nextId = 1;

  static const _articles = [
    _Article('fed-rate-decision', 'ForexLive', Duration(hours: 2), ['EUR/USD', 'XAU/USD', 'USD/JPY'], 'negative', -0.42, 5),
    _Article('ecb-rate-cuts', 'ForexLive', Duration(hours: 3), ['EUR/USD'], 'positive', 0.38, 3),
    _Article('gold-prices-steady', 'Kitco News', Duration(hours: 5), ['XAU/USD'], 'neutral', 0.02, 2),
    _Article('uk-retail-sales', 'ForexLive', Duration(hours: 7), ['GBP/USD'], 'positive', 0.51, 1),
  ];

  static const _authors = ['Ahmad_Trader', 'Sara.Fx', 'GoldBull22', 'Khaled_M', 'Nour_Invest'];

  Future<void> _wait() async {
    if (latency > Duration.zero) await Future<void>.delayed(latency);
  }

  int _count(_Article a) {
    final deleted = _deleted[a.id] ?? const {};
    final seeded = [for (var i = 0; i < a.seededComments; i++) '${a.id}-c$i'].where((id) => !deleted.contains(id));
    final own = (_own[a.id] ?? const []).where((c) => !deleted.contains(c['id']));
    return seeded.length + own.length;
  }

  @override
  Future<List<NewsArticle>> articles({required String languageCode}) async {
    await _wait();
    final l10n = AppLocalizations(Locale(languageCode));
    return mapValid(
      [
        for (final a in _articles)
          {
            'id': a.id,
            'source': {'key': a.source.toLowerCase(), 'name': a.source},
            'url': 'https://example.com/${a.id}',
            'title': _title(l10n, a.id),
            'summary': _summary(l10n, a.id),
            'body': _body(l10n, a.id),
            'language': languageCode,
            'published_at': _created.subtract(a.age).toIso8601String(),
            'sentiment': {'label': a.sentiment, 'score': a.score, 'model': 'simulated'},
            'instruments': [for (final s in a.symbols) {'symbol': s, 'relevance': 1.0}],
            'comments_count': _count(a),
          },
      ],
      (m) => newsArticleFromJson(Json(m)),
    );
  }

  @override
  Future<MarketMood> mood() async {
    await _wait();
    int count(String label) => _articles.where((a) => a.sentiment == label).length;
    final mean = _articles.map((a) => a.score).reduce((a, b) => a + b) / _articles.length;
    final parsed = marketMoodFromJson(Json({
      'window': '24h',
      'overall': {
        'articles': _articles.length,
        'scored': _articles.length,
        'positive': count('positive'),
        'neutral': count('neutral'),
        'negative': count('negative'),
        'mean_score': mean,
      },
      'instruments': const [],
    }));
    if (parsed == null) throw StateError('invalid sentiment payload');
    return parsed;
  }

  @override
  Future<List<Comment>> comments(String articleId, {required String languageCode}) async {
    await _wait();
    final article = _articles.firstWhere((a) => a.id == articleId, orElse: () => throw StateError('no article $articleId'));
    final l10n = AppLocalizations(Locale(languageCode));
    final texts = [l10n.commentText1, l10n.commentText2, l10n.commentText3, l10n.commentText4, l10n.commentText5];
    final deleted = _deleted[articleId] ?? const {};
    final seeded = [
      for (var i = 0; i < article.seededComments; i++)
        {
          'id': '$articleId-c$i',
          'author': {'name': _authors[(i + article.symbols.length) % _authors.length]},
          'body': texts[(i + article.age.inHours) % texts.length],
          'status': 'visible',
          'created_at': _created.subtract(article.age).add(Duration(minutes: 20 * (article.seededComments - i))).toIso8601String(),
          'can_edit': false,
        },
    ];
    return mapValid(
      [...?_own[articleId], ...seeded].where((c) => !deleted.contains(c['id'])),
      (m) => commentFromJson(Json(m)),
    );
  }

  @override
  Future<Comment> addComment(String articleId, String body) async {
    await _wait();
    final trimmed = body.trim();
    if (trimmed.isEmpty) throw ArgumentError.value(body, 'body', 'empty');
    final row = <String, Object?>{
      'id': 'own-${_nextId++}',
      'author': {'name': 'You'},
      'body': trimmed,
      'status': 'visible',
      'created_at': DateTime.now().toUtc().toIso8601String(),
      'can_edit': true,
    };
    (_own[articleId] ??= []).insert(0, row);
    return commentFromJson(Json(row))!;
  }

  @override
  Future<void> deleteComment(String articleId, String commentId) async =>
      (_deleted[articleId] ??= {}).add(commentId);

  @override
  Future<void> restoreComment(String articleId, String commentId) async =>
      _deleted[articleId]?.remove(commentId);

  static String _title(AppLocalizations l10n, String id) => switch (id) {
        'fed-rate-decision' => l10n.newsFedTitle,
        'ecb-rate-cuts' => l10n.newsEcbTitle,
        'gold-prices-steady' => l10n.newsGoldTitle,
        _ => l10n.newsUkTitle,
      };

  static String _summary(AppLocalizations l10n, String id) => switch (id) {
        'fed-rate-decision' => l10n.newsFedDescription,
        'ecb-rate-cuts' => l10n.newsEcbDescription,
        'gold-prices-steady' => l10n.newsGoldDescription,
        _ => l10n.newsUkDescription,
      };

  static String _body(AppLocalizations l10n, String id) => switch (id) {
        'fed-rate-decision' => l10n.newsFedContent,
        'ecb-rate-cuts' => l10n.newsEcbContent,
        'gold-prices-steady' => l10n.newsGoldContent,
        _ => l10n.newsUkContent,
      };
}

final class _Article {
  const _Article(this.id, this.source, this.age, this.symbols, this.sentiment, this.score, this.seededComments);

  final String id;
  final String source;
  final Duration age;
  final List<String> symbols;
  final String sentiment;
  final double score;
  final int seededComments;
}

/// مصدر الأخبار نفسه (محاكاة أو API) - يلي بيتبدّل بالـ API
final newsSourceRepositoryProvider = Provider<NewsRepository>(
  (ref) => apiSource(
    ref,
    ApiFeature.news,
    simulated: () => SimulatedNewsRepository(latency: const Duration(milliseconds: 350)),
  ),
);

/// H5b: كاش الأخبار (نفس قاعدة Drift)
final newsCacheProvider = Provider<NewsCache>((ref) => NewsCache(ref.watch(appDatabaseProvider)));

/// يلي بتقرأه الشاشات: المصدر، وفوقه طبقة الكاش (H5b، نفس مفتاح `kMarketOfflineCache`)
final newsRepositoryProvider = Provider<NewsRepository>(createNewsRepository);

/// منطق [newsRepositoryProvider] (الاختبارات بترجّعه)
NewsRepository createNewsRepository(Ref ref) {
  final source = ref.watch(newsSourceRepositoryProvider);
  if (!ref.watch(marketCacheEnabledProvider)) return source;
  final caching = CachingNewsRepository(
    source: source,
    cache: ref.watch(newsCacheProvider),
    isOffline: () => ref.read(networkStatusProvider) == NetworkStatus.offline,
    clock: ref.watch(marketCacheClockProvider),
  );
  ref.onDispose(caching.savedAt.dispose);
  return caching;
}

/// H5b: وقت النسخة المحفوظة المعروضة (`articles:<lang>`، `mood`) - null = حيّة
final newsSavedAtProvider = Provider.family<DateTime?, String>((ref, key) {
  final repo = ref.watch(newsRepositoryProvider);
  return watchSavedAt(ref, repo is CachingNewsRepository ? repo.savedAt : null, key);
});
