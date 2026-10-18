/// نوع الإشعار - بيحدد الأيقونة واللون يلي بتتعرض فيه
///
/// الدور المعماري: **Model (نموذج)**
enum NotificationType {
  /// إشارة شراء - السوق طالع / فرصة دخول (أخضر، نفس لغة "شراء" بالتطبيق)
  buySignal,

  /// إشارة بيع - السوق نازل / فرصة خروج (أحمر، نفس لغة "بيع" بالتطبيق)
  sellSignal,

  /// تنبيه سعر - وصول سعر معيّن لمستوى محدَّد مسبقًا
  priceAlert,

  /// معلومة عامة (تحديث حساب، رسالة ترحيب، إلخ) - بدون توصية تداول
  general,
}

/// نموذج إشعار واحد
///
/// الدور المعماري: **Model (نموذج)**
/// - بيانات نقية فقط، بدون أي منطق عرض أو ألوان
final class NotificationModel {
  const NotificationModel({
    required this.id,
    required this.type,
    required this.title,
    required this.message,
    required this.timeAgo,
    this.symbol,
    this.isRead = false,
  });

  /// معرّف فريد وثابت للإشعار
  final String id;

  /// نوع الإشعار (شراء/بيع/تنبيه سعر/عام)
  final NotificationType type;

  /// عنوان قصير للإشعار
  final String title;

  /// نص الإشعار الكامل - التوصية أو المعلومة بلغة التطبيق
  /// (مثلاً: "XAU/USD up 2.1% — this could be a good time to buy.")
  final String message;

  /// الوقت منذ وصول الإشعار (نص جاهز للعرض، مثلاً "10m ago")
  final String timeAgo;

  /// رمز السوق المرتبط بالإشعار إن وجد (مثلاً "XAU/USD") - اختياري،
  /// بيُعرض كشارة صغيرة فوق العنوان لما يكون موجود
  final String? symbol;

  /// هل تمت قراءة الإشعار؟ - بيتحكم بعرض نقطة "غير مقروء"
  final bool isRead;

  /// نسخة جديدة من نفس الإشعار مع تحديث حالة القراءة فقط
  NotificationModel copyWith({bool? isRead}) {
    return NotificationModel(
      id: id,
      type: type,
      title: title,
      message: message,
      timeAgo: timeAgo,
      symbol: symbol,
      isRead: isRead ?? this.isRead,
    );
  }
}
