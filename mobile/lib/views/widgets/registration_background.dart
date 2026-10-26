import 'package:flutter/material.dart';
import 'star_field_painter.dart';

/// Full-screen background — Registration screen.
///
/// Layers (bottom → top):
///   1. Deep navy gradient
///   2. Starfield — space-like with bright, colored dots/halos
class RegistrationBackground extends StatelessWidget {
  const RegistrationBackground({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: [
        // 1 ── Base gradient ──────────────────────────────────
        _buildBaseGradient(),

        // 2 ── Stars ───────────────────────────────────────────
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
