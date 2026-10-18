import 'package:flutter/material.dart';

/// نموذج عنصر في السوق (زوج عملات، ذهب، إلخ)
final class MarketItemModel {
  const MarketItemModel({
    required this.symbol,
    required this.displayName,
    required this.price,
    required this.changePercent,
    required this.icon,
  });
  
  /// الرمز (مثل EUR/USD)
  final String symbol;
  
  /// الاسم المعروض
  final String displayName;
  
  /// السعر الحالي
  final double price;
  
  /// نسبة التغيير
  final double changePercent;
  
  /// الأيقونة (مسار صورة PNG). قد تكون فارغة إذا ما في شعار جاهز
  /// للرمز - وقتها تُستخدم [fallbackIcon] بدلها.
  final String icon;
  
  /// هل التغيير إيجابي؟
  bool get isPositive => changePercent >= 0;
  
  /// النص المنسق للتغيير
  String get changeText {
    final sign = isPositive ? '+' : '';
    return '$sign${changePercent.toStringAsFixed(2)}%';
  }

  /// أيقونة احتياطية تُستخدم في كل مكان بالتطبيق (البطاقات، قائمة
  /// اختيار السوق، ...) عندما يكون [icon] فارغًا بدون شعار PNG جاهز.
  /// موجودة هون بمكان واحد بدل ما تتكرر بكل widget بيعرض عنصر سوق.
  IconData get fallbackIcon {
    if (symbol.contains('EUR')) {
      return Icons.euro_rounded;
    } else if (symbol.contains('GBP')) {
      return Icons.currency_pound_rounded;
    } else if (symbol.contains('GOLD')) {
      return Icons.diamond_outlined;
    }
    return Icons.show_chart_rounded;
  }
}

