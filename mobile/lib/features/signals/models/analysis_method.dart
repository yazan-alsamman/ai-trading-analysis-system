import 'package:flutter/foundation.dart';

/// نوع طريقة التحليل. اليوم الطرق كلها فنية (مؤشر بقواعد ثابتة)؛ enum حتى
/// تنضاف أنواع تانية بعدين. النموذج مش نوع ولا طريقة: هو دايمًا شغّال (الاحتمال
/// والأسباب)، والطريقة بتحدّد كيف الإشارة بتنبني وبتنعرض.
enum AnalysisMethodKind { technical }

/// طريقة تحليل بالاستراتيجية ("Strategy" = طريقة + الفلاتر).
///
/// [name] و [description] جايين من الـ repository بلغة الطلب (متل الإشعارات)،
/// فالموديل ما فيه ترجمة.
@immutable
final class AnalysisMethod {
  const AnalysisMethod({required this.id, required this.name, required this.description, required this.kind});

  /// معرّفات ثابتة (المحرّك المحاكى والتخزين بيعتمدوا عليها)
  static const String maCrossoverId = 'ma_crossover';
  static const String rsiReversalId = 'rsi_reversal';

  /// معرّف قديم (قبل A3c كان "AI model" خيار): مش طريقة؛ بس للترحيل
  /// (استراتيجية محفوظة فيه بتنقرأ بالطريقة الافتراضية)
  static const String legacyAiModelId = 'ai_model';

  /// الطرق المعروفة بالترتيب يلي بينعرض فيه
  static const List<String> knownIds = [maCrossoverId, rsiReversalId];

  /// الافتراضي: MA Crossover
  static const String defaultId = maCrossoverId;

  static bool isKnown(String? id) => id != null && knownIds.contains(id);

  final String id;
  final String name;

  /// جملة وحدة بتشرح الطريقة
  final String description;
  final AnalysisMethodKind kind;

  @override
  bool operator ==(Object other) =>
      other is AnalysisMethod &&
      other.id == id &&
      other.name == name &&
      other.description == description &&
      other.kind == kind;

  @override
  int get hashCode => Object.hash(id, name, description, kind);
}
