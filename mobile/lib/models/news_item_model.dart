/// مستوى تأثير الخبر على السوق
///
/// الدور المعماري: **Model (نموذج)**
enum NewsImpactLevel {
  /// تأثير مرتفع - غالبًا بيحرّك السوق بشكل ملحوظ (مثلاً قرارات الفائدة)
  high,

  /// تأثير متوسط
  medium,

  /// تأثير منخفض - خبر عادي بدون تأثير كبير متوقع
  low,
}

/// نموذج خبر في السوق
///
/// الدور المعماري: **Model (نموذج)**
/// - بيانات نقية فقط، بدون أي منطق عرض أو ألوان
final class NewsItemModel {
  const NewsItemModel({
    required this.id,
    required this.title,
    required this.source,
    required this.timeAgo,
    required this.impact,
    required this.description,
    required this.commentsCount,
    required this.content,
  });

  /// معرّف فريد وثابت للخبر - أساسي لمطابقة نفس الخبر بكل الشاشات
  /// ([HomeScreen] / [MarketNewsScreen] / [DiscussionScreen]) وتحديث
  /// عدد تعليقاته بمكان واحد يعكس نفسه بكل مكان تاني يظهر فيه.
  final String id;

  /// عنوان الخبر
  final String title;

  /// المصدر (مثلاً Bloomberg, ForexLive)
  final String source;

  /// الوقت منذ النشر (نص جاهز للعرض، مثلاً "2 hours ago")
  final String timeAgo;

  /// مستوى تأثير الخبر على السوق
  final NewsImpactLevel impact;

  /// ملخص/وصف قصير عن الخبر (يُعرض بالكارد المصغّر)
  final String description;

  /// عدد التعليقات على الخبر
  final int commentsCount;

  /// نص الخبر الكامل (يُعرض بشاشة تفاصيل الخبر [NewsDetailScreen])
  final String content;

  /// نسخة جديدة من نفس الخبر مع تحديث عدد التعليقات فقط (الموديل ثابت
  /// [immutable] فلازم نسخة جديدة كل ما يتغيّر عدد التعليقات)
  NewsItemModel copyWith({int? commentsCount}) {
    return NewsItemModel(
      id: id,
      title: title,
      source: source,
      timeAgo: timeAgo,
      impact: impact,
      description: description,
      commentsCount: commentsCount ?? this.commentsCount,
      content: content,
    );
  }
}
