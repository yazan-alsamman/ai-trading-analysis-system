import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../theme/theme_context.dart';

/// دخول عنصر بالقائمة: fade + طلوع 10dp، متدرّج حسب [index]
///
/// - أول [AppMotion.staggerMaxItems] عناصر بس بيتحرّكوا، والباقي بيظهروا
///   فورًا (ما في حركة على عناصر بتنعاد بنائها أثناء السكرول).
/// - مع تقليل الحركة: العنصر بيظهر بحالته النهائية مباشرة.
/// - لا تستخدمها على خلايا الأسعار الحيّة.
class FadeRise extends StatelessWidget {
  const FadeRise({super.key, required this.child, this.index = 0});

  final Widget child;
  final int index;

  @override
  Widget build(BuildContext context) {
    final delay = AppMotion.staggerDelay(index);
    if (context.reduceMotion || delay == null) return child;
    return child
        .animate(delay: delay)
        .fadeIn(duration: AppMotion.medium, curve: AppMotion.out)
        .moveY(
          begin: AppMotion.rise,
          end: 0,
          duration: AppMotion.medium,
          curve: AppMotion.out,
        );
  }
}

/// رقم بيعمل tween لما تتغيّر قيمته (400ms) - للإجماليات ونتائج التحليل بس
///
/// ⚠️ الأسعار الحيّة ما بتستخدم هاد الـ widget: بتتحدّث فورًا بدون حركة.
/// القارئ الصوتي بيسمع القيمة النهائية بس (مش الأرقام الوسطية).
class AnimatedNumber extends StatefulWidget {
  const AnimatedNumber({
    super.key,
    required this.value,
    required this.format,
    this.style,
    this.animateOnFirstBuild = true,
  });

  final double value;
  final String Function(double value) format;

  /// الافتراضي `context.type.numHero`
  final TextStyle? style;

  /// أول ظهور بيعد من 0 للقيمة (عند التحميل)
  final bool animateOnFirstBuild;

  @override
  State<AnimatedNumber> createState() => _AnimatedNumberState();
}

class _AnimatedNumberState extends State<AnimatedNumber> {
  late double _from = widget.animateOnFirstBuild ? 0 : widget.value;

  @override
  void didUpdateWidget(AnimatedNumber old) {
    super.didUpdateWidget(old);
    if (old.value != widget.value) _from = old.value;
  }

  @override
  Widget build(BuildContext context) {
    final style = widget.style ?? context.type.numHero;
    final finalText = widget.format(widget.value);

    final Widget text = context.reduceMotion
        ? Text(finalText, style: style)
        : TweenAnimationBuilder<double>(
            key: ValueKey(widget.value),
            tween: Tween(begin: _from, end: widget.value),
            duration: AppMotion.emphasis,
            curve: AppMotion.out,
            builder: (context, v, _) => Text(widget.format(v), style: style),
          );

    return Semantics(
      label: finalText,
      excludeSemantics: true,
      child: text,
    );
  }
}
