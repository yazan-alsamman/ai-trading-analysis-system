import 'package:flutter/foundation.dart';

/// دقة النموذج بصراحة: كم إشارة سابقة وصلت للهدف قبل الوقف
///
/// الإشارات يلي لسّا مفتوحة أو انتهت صلاحيتها بدون نتيجة ما بتنحسب.
@immutable
final class ModelAccuracy {
  const ModelAccuracy({
    required this.resolved,
    required this.hits,
    required this.windowDays,
  });

  /// كم إشارة إلها نتيجة (هدف أو وقف) بالفترة
  final int resolved;

  /// كم وحدة منهن وصلت للهدف
  final int hits;
  final int windowDays;

  /// null لما ما في ولا نتيجة (ما منعرض 0%)
  double? get hitRate => resolved == 0 ? null : hits / resolved;
}
