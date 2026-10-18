import 'dart:math' as math;
import 'package:flutter/material.dart';

/// Starfield painter — space-like with bright halos.
/// 3 star sizes: tiny dim, medium, bright large with wide glow.
class StarFieldPainter extends CustomPainter {
  const StarFieldPainter({this.seed = 42});
  final int seed;

  static const Color _yellow  = Color(0xFFCCFF66);
  static const Color _cyan    = Color(0xFF66EEFF);
  static const Color _white   = Color(0xFFDDEEFF);
  static const Color _blue    = Color(0xFF4499DD);

  @override
  void paint(Canvas canvas, Size size) {
    final rng = math.Random(seed);

    // ── Tiny background stars (many, very dim) ────────────
    for (int i = 0; i < 400; i++) {
      final x  = rng.nextDouble() * size.width;
      final y  = rng.nextDouble() * size.height;
      final r  = rng.nextDouble() * 0.8 + 0.3;
      final op = rng.nextDouble() * 0.35 + 0.10;
      final c  = rng.nextBool() ? _white : _blue;
      canvas.drawCircle(Offset(x, y), r, Paint()..color = c.withOpacity(op));
    }

    // ── Medium stars with small halo ──────────────────────
    final rng2 = math.Random(seed + 1);
    for (int i = 0; i < 160; i++) {
      final x   = rng2.nextDouble() * size.width;
      final y   = rng2.nextDouble() * size.height;
      final r   = rng2.nextDouble() * 1.4 + 0.8;
      final op  = rng2.nextDouble() * 0.45 + 0.25;
      final isCyan = rng2.nextBool();
      final c   = isCyan ? _cyan : _yellow;

      // halo
      canvas.drawCircle(Offset(x, y), r * 3.5,
          Paint()
            ..color = c.withOpacity(op * 0.18)
            ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4));
      // core
      canvas.drawCircle(Offset(x, y), r,
          Paint()..color = c.withOpacity(op));
    }

    // ── Bright large stars with wide glow (like PNG) ──────
    final rng3 = math.Random(seed + 2);
    const brightPositions = [
      (0.08, 0.06), (0.85, 0.10), (0.50, 0.04),
      (0.22, 0.32), (0.78, 0.28), (0.12, 0.55),
      (0.65, 0.48), (0.90, 0.60), (0.35, 0.72),
      (0.55, 0.85), (0.18, 0.88),
    ];
    for (final (xf, yf) in brightPositions) {
      final x  = xf * size.width;
      final y  = yf * size.height;
      final r  = rng3.nextDouble() * 1.5 + 1.8;
      final c  = rng3.nextBool() ? _yellow : _cyan;

      // outer wide glow
      canvas.drawCircle(Offset(x, y), r * 7,
          Paint()
            ..color = c.withOpacity(0.10)
            ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 10));
      // mid glow
      canvas.drawCircle(Offset(x, y), r * 3.5,
          Paint()
            ..color = c.withOpacity(0.25)
            ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 5));
      // bright core
      canvas.drawCircle(Offset(x, y), r,
          Paint()..color = c.withOpacity(0.95));
    }
  }

  @override
  bool shouldRepaint(covariant StarFieldPainter old) => old.seed != seed;
}
