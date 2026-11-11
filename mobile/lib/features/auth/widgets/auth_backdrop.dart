import 'package:flutter/material.dart';

import '../../../core/theme/theme_context.dart';

/// خلفية شاشات الدخول: "mesh" ناعم من 3 توهّجات (ذهبي فوق البداية، بنفسجي
/// فوق النهاية، ذهبي خافت تحت) فوق شبكة 48dp بتختفي تدريجيًا لتحت.
///
/// - زخرفة بس، أبدًا ورا بيانات. التوهّجات بتطلع مرة وحدة (fade 400ms)،
///   وبعدها ثابتة - ما في نبض ولا حلقات.
/// - الألوان من التوكنز (atmosAurum / atmosViolet / gridLine) فبتشتغل بالفاتح
///   والغامق، والاتجاه بينعكس بالعربي.
class AuthBackdrop extends StatelessWidget {
  const AuthBackdrop({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final rtl = Directionality.of(context) == TextDirection.rtl;

    Widget paint(double intensity) => CustomPaint(
          painter: _MeshPainter(
            canvas: c.canvas,
            aurum: c.atmosAurum,
            violet: c.atmosViolet,
            grid: c.gridLine,
            intensity: intensity,
            rtl: rtl,
          ),
        );

    return Stack(
      fit: StackFit.passthrough,
      children: [
        Positioned.fill(
          child: ExcludeSemantics(
            child: RepaintBoundary(
              child: context.reduceMotion
                  ? paint(1)
                  : TweenAnimationBuilder<double>(
                      tween: Tween(begin: 0, end: 1),
                      duration: AppMotion.emphasis,
                      curve: AppMotion.out,
                      builder: (context, t, _) => paint(t),
                    ),
            ),
          ),
        ),
        child,
      ],
    );
  }
}

class _MeshPainter extends CustomPainter {
  _MeshPainter({
    required this.canvas,
    required this.aurum,
    required this.violet,
    required this.grid,
    required this.intensity,
    required this.rtl,
  });

  final Color canvas;
  final Color aurum;
  final Color violet;
  final Color grid;
  final double intensity;
  final bool rtl;

  static const double _cell = 48;

  @override
  void paint(Canvas c, Size size) {
    final rect = Offset.zero & size;
    c.drawRect(rect, Paint()..color = canvas);

    // الشبكة: واضحة فوق وبتختفي بنص الشاشة
    final gridPaint = Paint()
      ..strokeWidth = 1
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [grid, grid.withValues(alpha: 0)],
        stops: const [0.15, 0.65],
      ).createShader(rect);
    for (var x = 0.0; x <= size.width; x += _cell) {
      c.drawLine(Offset(x, 0), Offset(x, size.height), gridPaint);
    }
    for (var y = 0.0; y <= size.height; y += _cell) {
      c.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }

    final side = rtl ? -1.0 : 1.0;
    void glow(Alignment center, double radius, Color color, double strength) {
      final tone = color.withValues(alpha: color.a * strength * intensity);
      c.drawRect(
        rect,
        Paint()
          ..shader = RadialGradient(
            center: center,
            radius: radius,
            colors: [tone, tone.withValues(alpha: 0)],
          ).createShader(rect),
      );
    }

    glow(Alignment(-0.9 * side, -0.95), 1.05, aurum, 1.3);
    glow(Alignment(0.95 * side, -0.55), 0.95, violet, 1.2);
    glow(Alignment(0.6 * side, 1.15), 0.9, aurum, 0.6);
  }

  @override
  bool shouldRepaint(_MeshPainter old) =>
      old.intensity != intensity ||
      old.canvas != canvas ||
      old.aurum != aurum ||
      old.violet != violet ||
      old.grid != grid ||
      old.rtl != rtl;
}
