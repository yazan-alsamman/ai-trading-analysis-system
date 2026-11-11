import 'package:flutter/foundation.dart';

import '../../../core/data/json.dart';

/// على شو التعليقات: خبر (News) أو منشور (Posts)
enum CommentTarget { article, post }

/// سلسلة تعليقات وحدة - مفتاح الـ family (record، فالمساواة بالقيمة)
typedef CommentThread = ({CommentTarget target, String id});

/// تعليق واحد (immutable) - حقول `CommentRead` بالـ backend (نفس الشكل
/// للأخبار والمنشورات)
@immutable
final class Comment {
  const Comment({
    required this.id,
    required this.author,
    required this.body,
    required this.createdAt,
    required this.isOwn,
  });

  final String id;
  final String author;
  final String body;
  final DateTime createdAt;

  /// تعليق المستخدم نفسه (`can_edit`) - بيقدر يحذفه
  final bool isOwn;
}

/// `CommentRead` → domain (المحذوف أو المخفي بيتشال). الاسم من `display_name`
/// (المنشورات) أو `name` (الأخبار).
Comment? commentFromJson(Json json) {
  final id = json.string('id');
  final body = json.string('body')?.trim();
  final createdAt = json.dateTime('created_at');
  final author = json.object('author');
  final name = (author?.string('display_name') ?? author?.string('name'))?.trim();
  if (id == null || body == null || body.isEmpty || createdAt == null || name == null || name.isEmpty) return null;
  final status = json.string('status');
  if (status != null && status != 'visible' && status != 'published') return null;
  return Comment(
    id: id,
    author: name,
    body: body,
    createdAt: createdAt,
    isOwn: json.boolean('can_edit') ?? false,
  );
}
