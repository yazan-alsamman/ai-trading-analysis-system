import 'dart:async' as async;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/shell/shell_tab.dart';
import '../../../core/data/low_data_mode.dart';
import '../../../core/data/network_status.dart';
import '../../../core/database/cache_support.dart';
import '../../../providers/locale_provider.dart';
import '../data/caching_news_repository.dart';
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
    final repo = ref.watch(newsRepositoryProvider);
    // H5b: رجع الاتصال وإحنا على نسخة محفوظة أو حالة الـ offline → تحميل من
    // جديد (بالـ Low data mode بيستنّى لحد ما تبويب Community يبيّن)
    reloadWhenBackOnline(
      ref,
      tab: ShellTab.community,
      needed: () =>
          state.error is NoSavedDataException ||
          (repo is CachingNewsRepository && repo.savedAt[CachingNewsRepository.articlesKey(language)] != null),
      reload: ref.invalidateSelf,
    );
    _generation++;
    return _load(language);
  }

  Future<NewsFeed> _load(String language) async {
    final repo = ref.read(newsRepositoryProvider);
    try {
      final (articles, mood) = await (repo.articles(languageCode: language), repo.mood()).wait;
      return NewsFeed(articles: articles, mood: mood);
    } on ParallelWaitError catch (e) {
      // أول خطأ حقيقي (مثلًا [NoSavedDataException] بدون اتصال) بدل الغلاف
      // (`AsyncError` تبع dart:async، مش تبع Riverpod)
      if (e.errors case (final async.AsyncError? a, final async.AsyncError? b) when (a ?? b) != null) {
        final first = (a ?? b)!;
        Error.throwWithStackTrace(first.error, first.stackTrace);
      }
      rethrow;
    }
  }

  /// بدون اتصال (H5b، فوق الكاش) ما في شي يتحدّث: الشاشة بتقول ليش
  Future<void> refresh() async {
    if (ref.read(newsRepositoryProvider) is CachingNewsRepository &&
        ref.read(networkStatusProvider) == NetworkStatus.offline) {
      throw const NoSavedDataException();
    }
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
