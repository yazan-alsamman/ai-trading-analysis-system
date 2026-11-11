import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers/locale_provider.dart';
import '../data/news_repository.dart';
import '../models/news_models.dart';

/// ViewModel قسم News: الأخبار + مزاج السوق مع بعض.
///
/// - تبديل اللغة بيعيد التحميل (العناوين من الخادم بلغة الحساب).
/// - سحب للتحديث مرتين ورا بعض: نتيجة الطلب الأقدم بتنرمى (عدّاد أجيال).
class NewsViewModel extends AsyncNotifier<NewsFeed> {
  var _generation = 0;

  @override
  Future<NewsFeed> build() {
    final language = ref.watch(localeProvider.select((l) => l.languageCode));
    _generation++;
    return _load(language);
  }

  Future<NewsFeed> _load(String language) async {
    final repo = ref.read(newsRepositoryProvider);
    final (articles, mood) = await (repo.articles(languageCode: language), repo.mood()).wait;
    return NewsFeed(articles: articles, mood: mood);
  }

  Future<void> refresh() async {
    final generation = ++_generation;
    final feed = await _load(ref.read(localeProvider).languageCode);
    if (generation == _generation) state = AsyncData(feed);
  }

  /// عدد التعليقات بعد إضافة / حذف (بيتحدّث بالقائمة وبصفحة الخبر سوا)
  void setCommentsCount(String articleId, int count) {
    final feed = state.valueOrNull;
    if (feed == null) return;
    state = AsyncData(NewsFeed(
      mood: feed.mood,
      articles: [
        for (final a in feed.articles) a.id == articleId ? a.withCommentsCount(count) : a,
      ],
    ));
  }
}

final newsViewModelProvider = AsyncNotifierProvider<NewsViewModel, NewsFeed>(NewsViewModel.new);

/// خبر واحد من القائمة (صفحة الخبر) - null لو ما عاد موجود
final newsArticleProvider = Provider.family<NewsArticle?, String>((ref, id) {
  final articles = ref.watch(newsViewModelProvider.select((v) => v.valueOrNull?.articles));
  for (final a in articles ?? const <NewsArticle>[]) {
    if (a.id == id) return a;
  }
  return null;
});
