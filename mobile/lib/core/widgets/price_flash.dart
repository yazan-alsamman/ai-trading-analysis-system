import 'package:flutter/material.dart';

import '../theme/theme_context.dart';

/// سعر حي: الرقم بيتحدّث فورًا، ووراه وميض لوني خفيف (صعود/هبوط) بيختفي
/// خلال 300ms. مع تقليل الحركة: بدون وميض.
///
/// الوميض مش المعنى الوحيد: التغيّر دايمًا معروض جنبه بسهم وإشارة.
class PriceFlash extends StatefulWidget {
  const PriceFlash({super.key, required this.price, required this.text, this.style});

  final double price;

  /// السعر منسّق بدقة الأداة
  final String text;
  final TextStyle? style;

  @override
  State<PriceFlash> createState() => _PriceFlashState();
}

class _PriceFlashState extends State<PriceFlash> with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 300),
    value: 1,
  );
  bool _up = true;

  @override
  void didUpdateWidget(PriceFlash old) {
    super.didUpdateWidget(old);
    if (widget.price != old.price && widget.text != old.text && !context.reduceMotion) {
      _up = widget.price > old.price;
      _controller.forward(from: 0);
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final flash = _up ? c.upSoft : c.downSoft;
    final text = Text(
      widget.text,
      style: widget.style ?? context.type.num,
      textDirection: TextDirection.ltr,
      maxLines: 1,
    );
    // الوميض بيعيد رسم السعر بس، مش كل القائمة / الشاشة
    return RepaintBoundary(
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, child) => DecoratedBox(
          decoration: BoxDecoration(
            color: Color.lerp(flash, flash.withValues(alpha: 0), Curves.easeOut.transform(_controller.value)),
            borderRadius: AppRadii.badge,
          ),
          child: child,
        ),
        // السعر سطر واحد دايمًا: إذا ما وسع (خط كبير) بيصغر شوي بدل ما ينقص
        child: FittedBox(
          fit: BoxFit.scaleDown,
          alignment: AlignmentDirectional.centerStart,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xxs / 2),
            child: text,
          ),
        ),
      ),
    );
  }
}
