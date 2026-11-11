import 'package:flutter/material.dart';

import '../theme/theme_context.dart';

enum IllustrationTone {
  /// حالات الفراغ: هادي (inset + رمادي)
  neutral,

  /// لحظات الهوية والنجاح: ذهبي خفيف
  accent,
}

/// الرسم التوضيحي الموحّد بالتطبيق (مبني بـ Flutter، بدون ملفات حركة):
/// قرص ناعم بالنص فيه أيقونة أو [child] - بدون حلقات ولا أقواس حواليه.
///
/// - نفس اللغة بكل مكان: حالات الفراغ (Notifications / Alerts / Signals /
///   Posts) وتأكيد النجاح. الشعار ما بيتحط جوّاه أبدًا (بيطلع لحالو).
/// - دخول مرة وحدة (fade + تكبير خفيف، 400ms كحد أقصى)، وبدون حركة مع
///   "تقليل الحركة".
/// - زخرفة بس: مخفي عن القارئ الصوتي (المعنى بالنص جنبه).
class AppIllustration extends StatelessWidget {
  const AppIllustration({
    super.key,
    this.icon,
    this.child,
    this.size = defaultSize,
    this.tone = IllustrationTone.neutral,
  }) : assert(icon != null || child != null, 'icon or child');

  final IconData? icon;
  final Widget? child;
  final double size;
  final IllustrationTone tone;

  static const double defaultSize = 120;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final accent = tone == IllustrationTone.accent;
    final disc = Container(
      width: size * 0.72,
      height: size * 0.72,
      alignment: Alignment.center,
      decoration: BoxDecoration(color: accent ? c.accentSoft : c.raised, shape: BoxShape.circle),
      child: child ?? Icon(icon, size: size * 0.28, color: accent ? c.accent : c.fg3),
    );

    return ExcludeSemantics(
      child: RepaintBoundary(
        child: SizedBox.square(
          dimension: size,
          child: Center(
            child: context.reduceMotion
                ? disc
                : TweenAnimationBuilder<double>(
                    tween: Tween(begin: 0, end: 1),
                    duration: AppMotion.emphasis,
                    curve: AppMotion.out,
                    child: disc,
                    builder: (context, t, child) => Opacity(
                      opacity: t.clamp(0.0, 1.0),
                      child: Transform.scale(scale: 0.92 + 0.08 * t, child: child),
                    ),
                  ),
          ),
        ),
      ),
    );
  }
}

/// تأكيد النجاح: نفس القرص بالذهبي، وعلامة الصح بتنرسم خط واحد
class SuccessIllustration extends StatelessWidget {
  const SuccessIllustration({super.key, this.size = AppIllustration.defaultSize});

  final double size;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final markSize = size * 0.36;
    Widget mark(double t) => CustomPaint(
          size: Size.square(markSize),
          painter: _CheckPainter(progress: t, color: c.accent, stroke: size * 0.035),
        );
    return AppIllustration(
      size: size,
      tone: IllustrationTone.accent,
      child: context.reduceMotion
          ? mark(1)
          : TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: 1),
              duration: AppMotion.emphasis,
              curve: AppMotion.inOut,
              builder: (context, t, _) => mark(t),
            ),
    );
  }
}

class _CheckPainter extends CustomPainter {
  _CheckPainter({required this.progress, required this.color, required this.stroke});

  final double progress;
  final Color color;
  final double stroke;

  @override
  void paint(Canvas canvas, Size size) {
    final path = Path()
      ..moveTo(size.width * 0.12, size.height * 0.54)
      ..lineTo(size.width * 0.4, size.height * 0.8)
      ..lineTo(size.width * 0.9, size.height * 0.24);
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    for (final metric in path.computeMetrics()) {
      canvas.drawPath(metric.extractPath(0, metric.length * progress), paint);
    }
  }

  @override
  bool shouldRepaint(_CheckPainter old) => old.progress != progress || old.color != color || old.stroke != stroke;
}
