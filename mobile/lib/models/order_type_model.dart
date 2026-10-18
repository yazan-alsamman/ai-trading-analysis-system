/// نوع أمر التداول - Market / Limit / Stop
enum OrderType {
  market,
  limit,
  stop;

  /// هل حقل السعر مطلوب لهذا النوع؟
  /// (أمر السوق ينفّذ بالسعر الحالي مباشرة، فلا حاجة لسعر يدوي)
  bool get requiresPrice => this != OrderType.market;
}
