import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'star_field_painter.dart';

/// Full-screen background — Auth screens (Login / Registration / OTP).
///
/// نفس خلفية شاشات الدخول والتسجيل والتحقق، بشكل موحّد بينها الثلاثة.
/// (لا تُستخدم في Home/Trade، وهناك تبقى [RegistrationBackground] الأبسط)
///
/// Layers (bottom → top):
///   1. Deep navy gradient
///   2. OHLC candlesticks — repeated twice (top + bottom), very transparent
///   3. Small secondary dollar sign (left-center, deep background)
///   4. Main dollar sign — large, top-right, 3D blue glow
///   5. Starfield — space-like with bright halos
///   6. Logo tight glow ring
///   7. Logo underline green streak (under logo circle only)
///   8. Nebula glow — bottom-right soft green-yellow cloud
class AuthBackground extends StatelessWidget {
  const AuthBackground({super.key, required this.child});

  final Widget child;
  static const List<(double,double,double)> _smallDollars=[
    (0.02, 0.12, 0.055),
    (0.70, 0.18, 0.048),
    (0.10, 0.42, 0.042),
    (0.80, 0.45, 0.060),
    (0.25, 0.68, 0.038),
    (0.60, 0.72, 0.045),
    (0.88, 0.75, 0.035),
    (0.05, 0.80, 0.040),
  ];

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.sizeOf(context);

    return Stack(
      fit: StackFit.expand,
      children: [
        // 1 ── Base gradient ──────────────────────────────────
        _buildBaseGradient(),

        // 2a ── OHLC top half ──────────────────────────────────
        Positioned(
          left: 0, right: 0,
          top: 0,
          height: size.height * 0.52,
          child: Opacity(
            opacity: 0.14,
            child: CustomPaint(painter: _CandlestickChartPainter(seed: 10)),
          ),
        ),

        // 2b ── OHLC bottom half ───────────────────────────────
        Positioned(
          left: 0, right: 0,
          top: size.height * 0.3,
          height: size.height * 0.59,
          child: Opacity(
            opacity: 0.12,
            child: CustomPaint(painter: _CandlestickChartPainter(seed: 77)),
          ),
        ),
        Positioned(
          left: 0, right: 120,
          top: size.height * 0.6,
          height: size.height * 0.59,
          child: Opacity(
            opacity: 0.12,
            child: CustomPaint(painter: _CandlestickChartPainter(seed: 50)),
          ),
        ),

        // 3 ── Small secondary dollar (left, background depth) ─
        Positioned(
          left: -size.width * 0.08,
          top: size.height * 0.28,
          child: _DollarSign(
            fontSize: size.width * 0.36,
            baseOpacity: 0.09,
            glowColor: const Color(0xFF1A7FAA),
          ),
        ),
// 3 ── Small scattered dollar signs ───────────────────
        for (final (xf, yf, sizef) in _smallDollars)
          Positioned(
            left: size.width  * xf,
            top:  size.height * yf,
            child: _DollarSign(
              fontSize:    size.width * sizef,
              baseOpacity: 0.13,
              glowColor:   const Color(0xFF1A7FAA),
            ),
          ),

        // 4 ── Main dollar — top-right ─────────────────────────
        Positioned(
          right: -size.width * 0.06,
          top: -size.height * 0.04,
          child: _DollarSign(
            fontSize: size.width * 0.79,
            baseOpacity: 0.22,
            glowColor: const Color(0xFF1A7FAA),
          ),
        ),

        // 5 ── Stars ───────────────────────────────────────────
        const CustomPaint(painter: StarFieldPainter()),

        // ── Foreground content ────────────────────────────────
        child,
      ],
    );
  }

  Widget _buildBaseGradient() => Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Color(0xFF040D1A),
              Color(0xFF061828),
              Color(0xFF061828),
              Color(0xFF040D1A),
            ],
            stops: [0.0, 0.35, 0.70, 1.0],
          ),
        ),
      );
}

// ══════════════════════════════════════════════════════════════
//  Reusable Dollar Sign
// ══════════════════════════════════════════════════════════════
class _DollarSign extends StatelessWidget {
  const _DollarSign({
    required this.fontSize,
    required this.baseOpacity,
    required this.glowColor,
  });
  final double fontSize;
  final double baseOpacity;
  final Color  glowColor;

  @override
  Widget build(BuildContext context) {
    return Stack(alignment: Alignment.center, children: [
      Text('\$', style: TextStyle(
        fontSize: fontSize, fontWeight: FontWeight.w900,
        foreground: Paint()
          ..color = glowColor.withOpacity(baseOpacity * 0.80)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 36),
      )),
      Text('\$', style: TextStyle(
        fontSize: fontSize, fontWeight: FontWeight.w900,
        foreground: Paint()
          ..color = glowColor.withOpacity(baseOpacity * 1.30)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 14),
      )),
      ShaderMask(
        shaderCallback: (bounds) => const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Color(0xFF2E7FA8),
            Color(0xFF1B5C7A),
            Color(0xFF0E3A52),
            Color(0xFF1A6080),
          ],
          stops: [0.0, 0.30, 0.65, 1.0],
        ).createShader(bounds),
        child: Text('\$', style: TextStyle(
          fontSize: fontSize, fontWeight: FontWeight.w900,
          color: Colors.white.withOpacity(baseOpacity),
        )),
      ),
    ]);
  }
}

// ══════════════════════════════════════════════════════════════
//  OHLC Candlestick Painter
// ══════════════════════════════════════════════════════════════
const List<(double, double, double, double)> _kOHLC = [
  (0.55, 0.65, 0.48, 0.60), (0.60, 0.72, 0.57, 0.69),
  (0.69, 0.74, 0.58, 0.61), (0.61, 0.64, 0.44, 0.47),
  (0.47, 0.56, 0.44, 0.53), (0.53, 0.67, 0.50, 0.65),
  (0.65, 0.78, 0.62, 0.75), (0.75, 0.80, 0.68, 0.70),
  (0.70, 0.72, 0.55, 0.58), (0.58, 0.66, 0.54, 0.63),
  (0.63, 0.75, 0.60, 0.72), (0.72, 0.86, 0.70, 0.83),
  (0.83, 0.88, 0.76, 0.78), (0.78, 0.82, 0.66, 0.68),
  (0.68, 0.76, 0.65, 0.73), (0.73, 0.90, 0.71, 0.87),
  (0.87, 0.92, 0.80, 0.83), (0.83, 0.86, 0.70, 0.72),
  (0.72, 0.80, 0.68, 0.78), (0.78, 0.94, 0.76, 0.91),
];

class _CandlestickChartPainter extends CustomPainter {
  const _CandlestickChartPainter({this.seed = 0});
  final int seed;

  static const Color _bull = Color(0xFF0DBFCF);
  static const Color _bear = Color(0xFF0A6FA8);
  static const double _cw  = 2.8;

  @override
  void paint(Canvas canvas, Size size) {
    final rng    = math.Random(seed);
    final offset = seed == 0 ? 0.0 : rng.nextDouble() * 8 - 4;
    final count  = _kOHLC.length;
    final gap    = size.width / (count + 1);

    for (int i = 0; i < count; i++) {
      final (open, high, low, close) = _kOHLC[i];
      final isBull = close >= open;

      final x      = gap * (i + 1) + offset;
      final highY  = size.height - high  * size.height;
      final lowY   = size.height - low   * size.height;
      final openY  = size.height - open  * size.height;
      final closeY = size.height - close * size.height;

      final bodyTop    = math.min(openY, closeY);
      final bodyHeight = (openY - closeY).abs().clamp(1.5, double.infinity);
      final color      = isBull ? _bull : _bear;

      canvas.drawLine(Offset(x, highY), Offset(x, lowY),
          Paint()..color = color.withOpacity(0.70)..strokeWidth = 0.7);

      canvas.drawRect(
        Rect.fromLTWH(x - _cw, bodyTop, _cw * 2, bodyHeight),
        Paint()
          ..color = color.withOpacity(isBull ? 0.65 : 0.45)
          ..style = PaintingStyle.fill,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _CandlestickChartPainter old) =>
      old.seed != seed;
}
