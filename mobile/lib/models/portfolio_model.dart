/// نموذج بيانات المحفظة
/// 
/// يمثل معلومات محفظة المستخدم الاستثمارية
final class PortfolioModel {
  const PortfolioModel({
    required this.name,
    required this.totalEquity,
    required this.dailyChange,
    required this.dailyChangePercent,
    required this.availableBalance,
    required this.marginUsed,
    required this.profitLoss,
    required this.profitLossPercent,
  });
  
  /// اسم المحفظة
  final String name;
  
  /// إجمالي رأس المال
  final double totalEquity;
  
  /// التغيير اليومي
  final double dailyChange;
  
  /// نسبة التغيير اليومي
  final double dailyChangePercent;
  
  /// الرصيد المتاح
  final double availableBalance;
  
  /// الهامش المستخدم
  final double marginUsed;
  
  /// الربح/الخسارة
  final double profitLoss;
  
  /// نسبة الربح/الخسارة
  final double profitLossPercent;
  
  /// هل التغيير إيجابي؟
  bool get isPositiveChange => dailyChange >= 0;
  
  /// هل الربح/الخسارة إيجابي؟
  bool get isPositivePL => profitLoss >= 0;
}
