import '../models/comment.dart';

/// مصدر تعليقات سلسلة وحدة. `NewsRepository` (`/news/{id}/comments`) و
/// `PostsRepository` (`/posts/{id}/comments`) بينفّذوه، فالـ sheet والـ
/// ViewModel نفسهن للاتنين.
abstract interface class CommentsSource {
  /// الأحدث أول
  Future<List<Comment>> comments(String threadId, {required String languageCode});
  Future<Comment> addComment(String threadId, String body);
  Future<void> deleteComment(String threadId, String commentId);

  /// يرجّع تعليق انحذف (Undo)
  Future<void> restoreComment(String threadId, String commentId);
}
