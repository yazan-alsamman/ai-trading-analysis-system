import 'package:flutter/material.dart';

import '../../../core/theme/app_motion.dart';

/// رمز الأداة كـ Hero: من صف قائمة المتابعة لعنوان شاشة الأداة
///
/// FittedBox حتى النص يكبر/يصغر بنعومة أثناء الانتقال بدل ما يلتف.
class MarketSymbolHero extends StatelessWidget {
  const MarketSymbolHero({super.key, required this.symbol, required this.style, this.heroTag});

  final String symbol;
  final TextStyle style;

  /// tag تاني بدل [tag] (صف إشارة → تفاصيلها)
  final Object? heroTag;

  static String tag(String symbol) => 'market-symbol-$symbol';

  @override
  Widget build(BuildContext context) {
    // مع تقليل الحركة الرمز ما بيطير بين الشاشتين
    return HeroMode(
      enabled: !context.reduceMotion,
      child: Hero(
        tag: heroTag ?? tag(symbol),
        child: Material(
          type: MaterialType.transparency,
          child: FittedBox(
            fit: BoxFit.scaleDown,
            alignment: AlignmentDirectional.centerStart,
            child: Text(symbol, style: style, maxLines: 1, textDirection: TextDirection.ltr),
          ),
        ),
      ),
    );
  }
}
