import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/network_status.dart';
import '../../../providers/locale_provider.dart';
import '../../community/data/posts_repository.dart';
import '../../community/view_models/posts_view_model.dart';
import '../../news/data/news_repository.dart';
import '../../news/view_models/news_view_models.dart';
import '../data/comments_source.dart';
import '../models/comment.dart';

/// بدون اتصال: التعليقات بتحتاج الخادم (H5b: مش محفوظة، وما في طابور مخفي)
final class CommentsOfflineException implements Exception {
  const CommentsOfflineException();
}

/// تعليقات سلسلة وحدة (خبر أو منشور) - الـ sheet نفسه للاتنين.
/// الإضافة والحذف متفائلين، والحذف بيرجع بالـ Undo. العدد بيتحدّث بالقائمة
/// يلي فاتحة السلسلة (بطاقة الخبر / المنشور) فورًا.
///
/// H5b: بدون اتصال ما في طلب: التحميل بيطلع حالة الـ offline (وبيرجع يحمّل
/// لحالو لما يرجع الاتصال)، والإضافة / الحذف بيقولوا إنهن بدهن اتصال
/// ([CommentsOfflineException]) والمسودة بتضل بالخانة.
class CommentsViewModel extends AutoDisposeFamilyAsyncNotifier<List<Comment>, CommentThread> {
  bool _sending = false;
  late CommentsSource _source;

  @override
  Future<List<Comment>> build(CommentThread thread) {
    final language = ref.watch(localeProvider.select((l) => l.languageCode));
    _source = switch (thread.target) {
      CommentTarget.article => ref.watch(newsRepositoryProvider),
      CommentTarget.post => ref.watch(postsRepositoryProvider),
    };
    ref.listen(networkStatusProvider, (_, status) {
      if (status == NetworkStatus.online && state.error is CommentsOfflineException) ref.invalidateSelf();
    });
    _requireOnline();
    return _source.comments(thread.id, languageCode: language);
  }

  void _requireOnline() {
    if (ref.read(networkStatusProvider) == NetworkStatus.offline) throw const CommentsOfflineException();
  }

  bool get isSending => _sending;

  /// false = فاضي أو في إرسال جاري (ضغطة مزدوجة). الخطأ بيوصل للمنادي.
  Future<bool> add(String body) async {
    if (_sending || body.trim().isEmpty) return false;
    _requireOnline();
    _sending = true;
    try {
      final comment = await _source.addComment(arg.id, body);
      _set([comment, ...?state.valueOrNull]);
      return true;
    } finally {
      _sending = false;
    }
  }

  Future<Comment?> remove(String commentId) async {
    final current = state.valueOrNull ?? const <Comment>[];
    final index = current.indexWhere((c) => c.id == commentId);
    if (index < 0) return null;
    _requireOnline();
    final removed = current[index];
    _set([...current]..removeAt(index));
    try {
      await _source.deleteComment(arg.id, commentId);
      return removed;
    } catch (_) {
      _set([...current]);
      rethrow;
    }
  }

  Future<void> undoRemove(Comment comment) async {
    await _source.restoreComment(arg.id, comment.id);
    final current = [...?state.valueOrNull]..removeWhere((c) => c.id == comment.id);
    final at = current.indexWhere((c) => c.createdAt.isBefore(comment.createdAt));
    current.insert(at < 0 ? current.length : at, comment);
    _set(current);
  }

  void _set(List<Comment> comments) {
    state = AsyncData(comments);
    switch (arg.target) {
      case CommentTarget.article:
        ref.read(newsViewModelProvider.notifier).setCommentsCount(arg.id, comments.length);
      case CommentTarget.post:
        ref.read(postsViewModelProvider.notifier).setCommentsCount(arg.id, comments.length);
    }
  }
}

final commentsViewModelProvider =
    AsyncNotifierProvider.autoDispose.family<CommentsViewModel, List<Comment>, CommentThread>(CommentsViewModel.new);
