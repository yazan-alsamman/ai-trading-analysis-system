/// الجهة المرسلة للرسالة داخل شات AI Strategy Assistant
enum ChatMessageSender { user, ai }

/// نموذج بيانات رسالة واحدة داخل الشات
///
/// هذا الكلاس immutable (غير قابل للتعديل)
/// يمثل رسالة واحدة، سواء من المستخدم أو من الـ AI
final class ChatMessageModel {
  const ChatMessageModel({
    required this.id,
    required this.text,
    required this.sender,
    required this.timestamp,
  });

  /// معرف الرسالة الفريد
  final String id;

  /// محتوى الرسالة
  final String text;

  /// الجهة المرسلة (مستخدم / AI)
  final ChatMessageSender sender;

  /// وقت إرسال الرسالة
  final DateTime timestamp;

  /// هل الرسالة من المستخدم؟ (بدل مقارنة enum بكل مكان بالواجهة)
  bool get isUser => sender == ChatMessageSender.user;

  @override
  String toString() =>
      'ChatMessageModel(id: $id, sender: $sender, text: $text)';

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is ChatMessageModel && other.id == id;
  }

  @override
  int get hashCode => id.hashCode;
}
