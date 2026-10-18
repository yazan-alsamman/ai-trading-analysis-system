/// نموذج تعليق واحد على خبر بشاشة Market News
///
/// الدور المعماري: **Model (نموذج)**
/// - بيانات نقية فقط، بدون أي منطق عرض
final class CommentModel {
  const CommentModel({
    required this.authorName,
    required this.text,
    required this.timeAgo,
    this.id = '',
    this.isOwn = false,
  });

  /// معرّف فريد للتعليق - لازم يكون موجود (غير فاضي) للتعليقات يلي
  /// المستخدم بيقدر يحذفها (التعليقات يلي هو ضافها [isOwn])
  final String id;

  /// اسم صاحب التعليق
  final String authorName;

  /// نص التعليق
  final String text;

  /// الوقت منذ نشر التعليق (نص جاهز للعرض، مثلاً "10m ago")
  final String timeAgo;

  /// هل هاد التعليق ضافه المستخدم الحالي؟ (بيتحكم بظهور زر الحذف)
  final bool isOwn;
}
