import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/json.dart';
import '../../auth/auth_state.dart';
import '../../comments/data/comments_source.dart';
import '../../comments/models/comment.dart';
import '../../markets/models/market_models.dart';
import '../models/post.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';

/// `PostRead` (backend/app/schemas/posts.py) → domain. المخفي والمحذوف
/// بينشالوا، والأداة لازم تكون من أدوات المنتج (غير هيك بتنشال الأداة بس).
/// `author.role` بينتجاهل: كل المنشورات شكلها واحد.
Post? postFromJson(Json json) {
  final id = json.string('id');
  final author = json.object('author');
  final name = author?.string('display_name')?.trim();
  final body = json.string('body')?.trim();
  final createdAt = json.dateTime('created_at');
  if (id == null || name == null || name.isEmpty || body == null || body.isEmpty || createdAt == null) return null;
  final status = json.string('status');
  if (status != null && status != 'published') return null;
  final symbol = json.object('instrument')?.string('symbol')?.toUpperCase();
  return Post(
    id: id,
    authorName: name,
    body: body,
    createdAt: createdAt,
    symbol: kProductSymbols.contains(symbol) ? symbol : null,
    likesCount: (json.integer('likes_count') ?? 0).clamp(0, 1 << 31),
    likedByMe: json.boolean('liked_by_me') ?? false,
    commentsCount: (json.integer('comments_count') ?? 0).clamp(0, 1 << 31),
    isOwn: json.boolean('can_edit') ?? false,
  );
}

/// `title` مطلوب بـ `PostCreate` (1-140 حرف) والموبايل بيكتب نص بس: العنوان
/// = أول سطر، مقصوص على 140.
String postTitleFrom(String body) {
  final firstLine = body.trim().split('\n').first.trim();
  return firstLine.length <= 140 ? firstLine : '${firstLine.substring(0, 139)}…';
}

/// مصدر المنشورات - بيتبدّل بتنفيذ API (`/posts`, `/posts/{id}/like`,
/// `/posts/{id}/comments`). التعليقات: [CommentsSource].
abstract interface class PostsRepository implements CommentsSource {
  /// الأحدث أول (`GET /posts?scope=all`)
  Future<List<Post>> posts({required String languageCode});

  /// `POST /posts` - [symbol] اختياري (من الأدوات الـ 8)
  Future<Post> create({required String body, String? symbol});

  /// `DELETE /posts/{id}` (منشوراتك بس)
  Future<void> delete(String postId);

  /// يرجّع منشور انحذف (Undo)
  Future<void> restore(String postId);

  Future<LikeState> like(String postId);
  Future<LikeState> unlike(String postId);

  /// `POST /reports` (`ReportCreate`: target_type = post) - منشورات غيرك بس
  Future<void> report(String postId, ReportReason reason);
}

/// منشورات محاكاة: 5 منشورات ثابتة (أسماء وهمية، EN/AR)، ومنشورات المستخدم
/// وإعجاباته وتعليقاته بالذاكرة. كل شي بيطلع كـ JSON حتى الـ mapper ينفحص.
/// اسم كاتب منشوراتك بينقرا وقت القراءة (متل الخادم: من الحساب).
///
/// قاعدة المنتج: أي حساب مسجّل بينشر، وكل المنشورات شكلها واحد.
/// TODO(B02): الـ backend حاليًا بيسمح بالنشر للمحلل والخبير والمدير بس
/// (`create_post`) - صاحب الـ backend لازم يسمح للكل قبل ربط الـ API.
class SimulatedPostsRepository implements PostsRepository {
  SimulatedPostsRepository({
    required String Function() author,
    DateTime Function()? clock,
    this.latency = Duration.zero,
  })  : _author = author,
        _clock = clock ?? DateTime.now;

  final String Function() _author;
  final DateTime Function() _clock;
  final Duration latency;
  late final DateTime _created = _clock().toUtc();

  final List<Map<String, Object?>> _ownPosts = [];
  final Set<String> _deletedPosts = {};

  /// الإعجاب بعد ما المستخدم غيّرو (المنشورات الثابتة بتبلّش بلا إعجاب)
  final Map<String, bool> _liked = {};

  final Map<String, List<Map<String, Object?>>> _ownComments = {};

  /// البلاغات المبعوتة (`ReportCreate` بشكل JSON) - للاختبارات والمحاكاة
  final List<Map<String, Object?>> reports = [];
  final Map<String, Set<String>> _deletedComments = {};
  var _nextId = 1;

  Future<void> _wait() async {
    if (latency > Duration.zero) await Future<void>.delayed(latency);
  }

  static const _seeded = [
    _Seed(
        'post-gold-breakout',
        'Lina Haddad',
        'لينا حداد',
        'XAU/USD',
        Duration(minutes: 50),
        24,
        3,
        'Gold is holding above last week’s high. I’m watching the 1h close: a close back below it would cancel the breakout idea.',
        'الذهب يتماسك فوق قمة الأسبوع الماضي. أراقب إغلاق الساعة: إغلاق تحتها يلغي فكرة الاختراق.'),
    _Seed(
        'post-eurusd-range',
        'Omar Saleh',
        'عمر صالح',
        'EUR/USD',
        Duration(hours: 3),
        15,
        2,
        'EUR/USD has moved less than 20 pips in five hours. In a range this tight I wait for the London and New York overlap before reading anything into it.',
        'تحرّك EUR/USD أقل من 20 نقطة خلال خمس ساعات. في نطاق ضيق كهذا أنتظر تداخل لندن ونيويورك قبل أن أستنتج شيئًا.'),
    _Seed(
        'post-risk-week',
        'Rami Khoury',
        'رامي خوري',
        'USD/JPY',
        Duration(hours: 4),
        9,
        1,
        'First week with a fixed 1% risk per trade. Fewer trades, and much calmer evenings.',
        'أول أسبوع بمخاطرة ثابتة 1% لكل صفقة. صفقات أقل، وأمسيات أهدأ بكثير.'),
    _Seed(
        'post-cpi-question',
        'Sara Mansour',
        'سارة منصور',
        null,
        Duration(hours: 6),
        4,
        2,
        'Question for everyone here: do you size down before CPI, or just stay out until the release?',
        'سؤال للجميع هنا: هل تقلّلون حجم الصفقة قبل بيانات التضخم، أم تبقون خارج السوق حتى صدورها؟'),
    _Seed(
        'post-uk-data',
        'Nadia Farouk',
        'نادية فاروق',
        'GBP/USD',
        Duration(hours: 9),
        31,
        0,
        'UK data is out tomorrow at 07:00 GMT. Spreads usually widen around the release, so plan entries away from it.',
        'بيانات بريطانيا تصدر غدًا الساعة 07:00 بتوقيت غرينتش. الفروقات تتّسع عادةً حول الصدور، فخطّط لدخولك بعيدًا عنه.'),
  ];

  static const _replyAuthors = ['Ahmad_Trader', 'Omar Saleh', 'GoldBull22'];
  static const _repliesEn = [
    'Same read here, waiting for the close.',
    'Thanks, a useful level to watch.',
    'Which timeframe are you using for this?',
  ];
  static const _repliesAr = [
    'نفس القراءة عندي، أنتظر الإغلاق.',
    'شكرًا، مستوى مفيد للمتابعة.',
    'ما الإطار الزمني الذي تستخدمه لهذا؟',
  ];

  _Seed? _seed(String id) {
    for (final s in _seeded) {
      if (s.id == id) return s;
    }
    return null;
  }

  int _commentsCount(String postId) {
    final deleted = _deletedComments[postId] ?? const {};
    final seeded = _seed(postId)?.comments ?? 0;
    final seededLeft = [for (var i = 0; i < seeded; i++) '$postId-c$i'].where((id) => !deleted.contains(id)).length;
    final own = (_ownComments[postId] ?? const []).where((c) => !deleted.contains(c['id'])).length;
    return seededLeft + own;
  }

  Map<String, Object?> _seedRow(_Seed s, {required bool arabic}) {
    final liked = _liked[s.id] ?? false;
    return {
      'id': s.id,
      'author': {'id': 'user-${s.id}', 'display_name': arabic ? s.nameAr : s.nameEn},
      'title': postTitleFrom(arabic ? s.bodyAr : s.bodyEn),
      'body': arabic ? s.bodyAr : s.bodyEn,
      'locked': false,
      'instrument': s.symbol == null ? null : {'id': 'instrument-${s.symbol}', 'symbol': s.symbol},
      'timeframe': null,
      'direction': null,
      'attachments': const [],
      'visibility': 'public',
      'status': 'published',
      'comments_count': _commentsCount(s.id),
      'likes_count': s.likes + (liked ? 1 : 0),
      'liked_by_me': liked,
      'can_edit': false,
      'edited_at': null,
      'created_at': _created.subtract(s.age).toIso8601String(),
    };
  }

  Map<String, Object?> _withCounts(Map<String, Object?> row) {
    final id = row['id']! as String;
    final liked = _liked[id] ?? false;
    return {
      ...row,
      'author': _me(),
      'comments_count': _commentsCount(id),
      'likes_count': liked ? 1 : 0,
      'liked_by_me': liked,
    };
  }

  /// `AuthorRead` للمستخدم الحالي
  Map<String, Object?> _me() {
    return {'id': 'me', 'display_name': _author()};
  }

  @override
  Future<List<Post>> posts({required String languageCode}) async {
    await _wait();
    final arabic = languageCode == 'ar';
    return mapValid(
      [
        for (final row in _ownPosts)
          if (!_deletedPosts.contains(row['id'])) _withCounts(row),
        for (final s in _seeded)
          if (!_deletedPosts.contains(s.id)) _seedRow(s, arabic: arabic),
      ],
      (m) => postFromJson(Json(m)),
    );
  }

  @override
  Future<Post> create({required String body, String? symbol}) async {
    await _wait();
    final trimmed = body.trim();
    if (trimmed.isEmpty || trimmed.length > kPostMaxLength) throw ArgumentError.value(body, 'body');
    if (symbol != null && !kProductSymbols.contains(symbol)) throw ArgumentError.value(symbol, 'symbol');
    final row = <String, Object?>{
      'id': 'own-post-${_nextId++}',
      'author': _me(),
      'title': postTitleFrom(trimmed),
      'body': trimmed,
      'instrument': symbol == null ? null : {'id': 'instrument-$symbol', 'symbol': symbol},
      'visibility': 'public',
      'status': 'published',
      'comments_count': 0,
      'likes_count': 0,
      'liked_by_me': false,
      'can_edit': true,
      'created_at': DateTime.now().toUtc().toIso8601String(),
    };
    _ownPosts.insert(0, row);
    return postFromJson(Json(row))!;
  }

  @override
  Future<void> delete(String postId) async {
    await _wait();
    _deletedPosts.add(postId);
  }

  @override
  Future<void> restore(String postId) async => _deletedPosts.remove(postId);

  LikeState _likeState(String postId) {
    final liked = _liked[postId] ?? false;
    final base = _seed(postId)?.likes ?? 0;
    return (liked: liked, likesCount: base + (liked ? 1 : 0));
  }

  @override
  Future<LikeState> like(String postId) async {
    await _wait();
    _liked[postId] = true;
    return _likeState(postId);
  }

  @override
  Future<LikeState> unlike(String postId) async {
    await _wait();
    _liked[postId] = false;
    return _likeState(postId);
  }

  @override
  Future<void> report(String postId, ReportReason reason) async {
    await _wait();
    if (_ownPosts.any((p) => p['id'] == postId)) throw ArgumentError.value(postId, 'postId', 'own post');
    reports.add({'target_type': 'post', 'target_id': postId, 'reason': reason.apiReason});
  }

  // ── التعليقات ──

  @override
  Future<List<Comment>> comments(String threadId, {required String languageCode}) async {
    await _wait();
    final arabic = languageCode == 'ar';
    final seed = _seed(threadId);
    final deleted = _deletedComments[threadId] ?? const {};
    final seeded = [
      if (seed != null)
        for (var i = 0; i < seed.comments; i++)
          {
            'id': '$threadId-c$i',
            'post_id': threadId,
            'parent_id': null,
            'author': {
              'id': 'reply-$i',
              'display_name': _replyAuthors[i % _replyAuthors.length],
            },
            'body': (arabic ? _repliesAr : _repliesEn)[i % _repliesEn.length],
            'status': 'published',
            'created_at':
                _created.subtract(seed.age).add(Duration(minutes: 10 * (seed.comments - i))).toIso8601String(),
            'edited_at': null,
            'can_edit': false,
          },
    ];
    return mapValid(
      [
        for (final c in _ownComments[threadId] ?? const <Map<String, Object?>>[]) {...c, 'author': _me()},
        ...seeded,
      ].where((c) => !deleted.contains(c['id'])),
      (m) => commentFromJson(Json(m)),
    );
  }

  @override
  Future<Comment> addComment(String threadId, String body) async {
    await _wait();
    final trimmed = body.trim();
    if (trimmed.isEmpty) throw ArgumentError.value(body, 'body', 'empty');
    final row = <String, Object?>{
      'id': 'own-comment-${_nextId++}',
      'post_id': threadId,
      'parent_id': null,
      'author': _me(),
      'body': trimmed,
      'status': 'published',
      'created_at': DateTime.now().toUtc().toIso8601String(),
      'can_edit': true,
    };
    (_ownComments[threadId] ??= []).insert(0, row);
    return commentFromJson(Json(row))!;
  }

  @override
  Future<void> deleteComment(String threadId, String commentId) async =>
      (_deletedComments[threadId] ??= {}).add(commentId);

  @override
  Future<void> restoreComment(String threadId, String commentId) async => _deletedComments[threadId]?.remove(commentId);
}

final class _Seed {
  const _Seed(
      this.id, this.nameEn, this.nameAr, this.symbol, this.age, this.likes, this.comments, this.bodyEn, this.bodyAr);

  final String id;
  final String nameEn;
  final String nameAr;
  final String? symbol;
  final Duration age;
  final int likes;
  final int comments;
  final String bodyEn;
  final String bodyAr;
}

/// اسم المستخدم للمنشورات المحاكاة (الخادم الحقيقي بيعرفه من الجلسة)
String postAuthorOf(AuthState auth) {
  if (auth is! SignedIn) return 'You';
  final user = auth.user;
  final name = user.displayName?.trim();
  return name == null || name.isEmpty ? user.email.split('@').first : name;
}

/// اسم كاتب المنشورات والتعليقات الحالي. كل حساب مسجّل بينشر، وكل المنشورات
/// شكلها واحد (ما في أدوار ولا شارات).
final postAuthorProvider = Provider<String>((ref) => postAuthorOf(ref.watch(authStateProvider)));

final postsRepositoryProvider = Provider<PostsRepository>(
  (ref) => apiSource(
    ref,
    ApiFeature.posts,
    simulated: () => SimulatedPostsRepository(
      author: () => ref.read(postAuthorProvider),
      latency: const Duration(milliseconds: 350),
    ),
  ),
);
