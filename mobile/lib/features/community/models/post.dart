import 'package:flutter/foundation.dart';

/// منشور بالمجتمع (immutable) - حقول `PostRead` بالـ backend يلي بيحتاجها
/// الموبايل. النص هو `body`؛ العنوان (`title`) مطلوب بالـ API بس الموبايل
/// ما بيعرضه لحالو (بينبني من أول سطر وقت النشر).
@immutable
final class Post {
  const Post({
    required this.id,
    required this.authorName,
    required this.body,
    required this.createdAt,
    required this.likesCount,
    required this.likedByMe,
    required this.commentsCount,
    required this.isOwn,
    this.symbol,
    this.reportedByMe = false,
  });

  final String id;
  final String authorName;

  final String body;
  final DateTime createdAt;

  /// الأداة المرتبطة (`instrument.symbol`) - من أدوات المنتج الـ 8 بس
  final String? symbol;
  final int likesCount;
  final bool likedByMe;
  final int commentsCount;

  /// منشور المستخدم نفسه (`can_edit`) - بيقدر يحذفه
  final bool isOwn;

  /// بلّغت عنه بهالجلسة (محلي - `PostRead` ما فيه هالحقل لسّا)
  final bool reportedByMe;

  Post copyWith({int? likesCount, bool? likedByMe, int? commentsCount, bool? reportedByMe}) => Post(
        id: id,
        authorName: authorName,
        body: body,
        createdAt: createdAt,
        symbol: symbol,
        likesCount: likesCount ?? this.likesCount,
        likedByMe: likedByMe ?? this.likedByMe,
        commentsCount: commentsCount ?? this.commentsCount,
        isOwn: isOwn,
        reportedByMe: reportedByMe ?? this.reportedByMe,
      );
}

/// سبب البلاغ - بينبعت كـ `reason` بـ `ReportCreate` (3-500 حرف)
enum ReportReason {
  spam,
  misleading,
  abusive,
  other;

  /// النص يلي بيوصل للمشرف (إنجليزي ثابت، مش بلغة الواجهة)
  String get apiReason => switch (this) {
        spam => 'spam or advertising',
        misleading => 'misleading or promises profits',
        abusive => 'abusive or hateful',
        other => 'other',
      };
}

/// نتيجة like / unlike - `LikeState` بالـ backend
typedef LikeState = ({bool liked, int likesCount});

/// أطول منشور بالموبايل (الـ API بيقبل لحد 20000 - الموبايل للأفكار القصيرة)
const int kPostMaxLength = 500;
