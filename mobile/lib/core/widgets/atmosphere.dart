import 'package:flutter/material.dart';

import '../theme/theme_context.dart';

/// "الجو" التحريري: شبكة 48dp خفيفة + توهّجين ناعمين (ذهبي فوق اليسار،
/// بنفسجي فوق اليمين) - نفس `.atmosphere` بالويب.
///
/// ⚠️ للـ splash وشاشات الدخول وهيدر Home بس. أبدًا ورا بيانات.
/// ثابت (بدون حركة)، ومعزول بـ RepaintBoundary.
class Atmosphere extends StatelessWidget {
  const Atmosphere({super.key, this.child});

  final Widget? child;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Stack(
      fit: StackFit.passthrough,
      children: [
        Positioned.fill(
          child: RepaintBoundary(
            child: CustomPaint(
              painter: _AtmospherePainter(
                canvas: c.canvas,
                aurum: c.atmosAurum,
                violet: c.atmosViolet,
                grid: c.gridLine,
              ),
            ),
          ),
        ),
        if (child != null) child!,
      ],
    );
  }
}

class _AtmospherePainter extends CustomPainter {
  _AtmospherePainter({
    required this.canvas,
    required this.aurum,
    required this.violet,
    required this.grid,
  });

  final Color canvas;
  final Color aurum;
  final Color violet;
  final Color grid;

  static const double _cell = 48;

  @override
  void paint(Canvas c, Size size) {
    final rect = Offset.zero & size;
    c.drawRect(rect, Paint()..color = canvas);

    final gridPaint = Paint()
      ..color = grid
      ..strokeWidth = 1;
    for (var x = 0.0; x <= size.width; x += _cell) {
      c.drawLine(Offset(x, 0), Offset(x, size.height), gridPaint);
    }
    for (var y = 0.0; y <= size.height; y += _cell) {
      c.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }

    void glow(Alignment center, double radius, Color color) {
      c.drawRect(
        rect,
        Paint()
          ..shader = RadialGradient(
            center: center,
            radius: radius,
            colors: [color, color.withValues(alpha: 0)],
          ).createShader(rect),
      );
    }

    glow(const Alignment(-0.8, -0.8), 0.9, aurum);
    glow(const Alignment(0.7, -1), 1.0, violet);
  }

  @override
  bool shouldRepaint(_AtmospherePainter old) =>
      old.canvas != canvas ||
      old.aurum != aurum ||
      old.violet != violet ||
      old.grid != grid;
}
