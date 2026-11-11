import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';
import '../theme/theme_context.dart';

/// شعار التطبيق: 3 شموع ذهبية صاعدة (السوق الملاحَظ) بيكمّلها خط بنفسجي
/// متقطّع بينتهي بنقطة (توقّع النموذج) - نفس web BrandGlyph بالضبط.
/// بيعبّر عن القاعدة الأساسية: الملاحَظ والمتوقَّع دايمًا مميَّزين.
///
/// [progress] من 0 لـ 1 بيستخدمه الـ splash لبناء الشعار تدريجيًا
/// (الشموع، بعدين الخط، بعدين النقطة). القيمة الافتراضية 1 = شعار كامل.
///
/// الشعار بدون أي إطار أو حلقة أو قوس أو خط حواليه (بكل الشاشات). مع
/// [glow]: هالة ذهبية ناعمة وراه بس ([BrandGlow]) - Splash / Welcome / راس
/// شاشات الدخول.
class BrandGlyph extends StatelessWidget {
  const BrandGlyph({super.key, this.size = 32, this.progress = 1, this.glow = false, this.glowSpread});

  final double size;
  final double progress;
  final bool glow;

  /// قديش بتمتد الهالة برا الشعار (الافتراضي نص حجمه)
  final double? glowSpread;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final glyph = ExcludeSemantics(
      child: RepaintBoundary(
        child: CustomPaint(
          size: Size.square(size),
          painter: _BrandGlyphPainter(
            tile: c.raised,
            candle: c.accent,
            forecast: c.forecast,
            progress: progress,
          ),
        ),
      ),
    );
    return glow ? BrandGlow(spread: glowSpread ?? size / 2, child: glyph) : glyph;
  }
}

/// هالة الشعار: تدرّج دائري (RadialGradient) من ذهبي خفيف بالنص لشفاف تمامًا
/// عند الطرف - ما في حلقة ولا خط ولا نقطة ولا حافة قاسية.
///
/// - ورا [child] وبتمتد [spread] برا حدوده بدون ما تغيّر الـ layout (الشاشة
///   بتترك مسافة كافية حتى ما تنقص).
/// - ثابتة (بدون نبض)، فما في شي يتوقّف مع "تقليل الحركة".
/// - أخف بالفاتح (الذهبي الغامق أقوى على الورق)، والنص جنبها بيضل AA لأنها
///   شبه شفافة عند الأطراف.
class BrandGlow extends StatelessWidget {
  const BrandGlow({super.key, required this.child, required this.spread});

  final Widget child;
  final double spread;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final peak = Theme.of(context).brightness == Brightness.dark ? 0.22 : 0.16;
    return Stack(
      clipBehavior: Clip.none,
      alignment: Alignment.center,
      children: [
        Positioned(
          left: -spread,
          top: -spread,
          right: -spread,
          bottom: -spread,
          child: IgnorePointer(
            child: ExcludeSemantics(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  gradient: RadialGradient(
                    colors: [
                      c.accent.withValues(alpha: peak),
                      c.accent.withValues(alpha: peak * 0.45),
                      c.accent.withValues(alpha: 0),
                    ],
                    stops: const [0, 0.5, 1],
                  ),
                ),
              ),
            ),
          ),
        ),
        child,
      ],
    );
  }
}

class _BrandGlyphPainter extends CustomPainter {
  _BrandGlyphPainter({
    required this.tile,
    required this.candle,
    required this.forecast,
    required this.progress,
  });

  final Color tile;
  final Color candle;
  final Color forecast;
  final double progress;

  // الهندسة الأصلية على شبكة 32×32 (web/src/components/brand/BrandMark.tsx)
  static const _wicks = [
    [8.0, 15.0, 25.0],
    [14.0, 11.0, 22.0],
    [20.0, 7.5, 18.0],
  ];
  static const _bodies = [
    [6.0, 17.5, 5.5],
    [12.0, 13.5, 6.0],
    [18.0, 10.0, 5.5],
  ];

  /// تقدّم مرحلة وحدة ضمن [start, end] من الـ progress الكلّي
  double _segment(double start, double end) => ((progress - start) / (end - start)).clamp(0.0, 1.0);

  @override
  void paint(Canvas canvas, Size size) {
    canvas.scale(size.width / 32, size.height / 32);

    final tileRect = RRect.fromRectAndRadius(
      const Rect.fromLTWH(0.5, 0.5, 31, 31),
      const Radius.circular(9),
    );
    canvas.drawRRect(tileRect, Paint()..color = tile);

    final wickPaint = Paint()
      ..color = candle
      ..strokeWidth = 1.5
      ..strokeCap = StrokeCap.round;
    final bodyPaint = Paint()..color = candle;

    // الشموع بتطلع وحدة ورا التانية (0 → 0.6)، كل شمعة "بتطلع" من تحت
    for (var i = 0; i < 3; i++) {
      final t = AppMotion.out.transform(_segment(i * 0.2, i * 0.2 + 0.3));
      if (t == 0) continue;
      final rise = (1 - t) * 3;
      bodyPaint.color = candle.withValues(alpha: candle.a * t);
      wickPaint.color = bodyPaint.color;
      final w = _wicks[i];
      canvas.drawLine(Offset(w[0], w[1] + rise), Offset(w[0], w[2] + rise), wickPaint);
      final b = _bodies[i];
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(b[0], b[1] + rise, 4, b[2]),
          const Radius.circular(1),
        ),
        bodyPaint,
      );
    }

    // الخط المتقطّع البنفسجي بينرسم (0.6 → 0.85)
    final dash = _segment(0.6, 0.85);
    if (dash > 0) {
      final dashPaint = Paint()
        ..color = forecast
        ..strokeWidth = 1.5
        ..strokeCap = StrokeCap.round;
      const start = Offset(22.6, 9.6);
      const end = Offset(25.9, 6.6);
      final total = (end - start).distance;
      final direction = (end - start) / total;
      var drawn = 0.0;
      final limit = total * dash;
      while (drawn < limit) {
        final to = (drawn + 1.4).clamp(0.0, limit);
        canvas.drawLine(start + direction * drawn, start + direction * to, dashPaint);
        drawn += 1.4 + 1.8;
      }
    }

    // النقطة (التوقّع) بتظهر بالآخر (0.85 → 1) بتجاوز خفيف
    final node = _segment(0.85, 1);
    if (node > 0) {
      final r = 1.9 * AppMotion.spring.transform(node);
      canvas.drawCircle(const Offset(26.6, 6), r, Paint()..color = forecast);
    }
  }

  @override
  bool shouldRepaint(_BrandGlyphPainter old) =>
      old.progress != progress || old.tile != tile || old.candle != candle || old.forecast != forecast;
}

/// الشعار + الاسم: "AI Trading" عريض + "Assistance" خافت،
/// وتحتهن سطر mono صغير "GOLD & FX RESEARCH"
class BrandMark extends StatelessWidget {
  const BrandMark({super.key, this.glyphSize = 32, this.showTagline = true});

  final double glyphSize;
  final bool showTagline;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final title = context.textTheme.titleSmall!;
    final tagline = context.type.eyebrow.copyWith(letterSpacing: 12 * 0.08);

    return Semantics(
      label: l10n.appName,
      container: true,
      child: ExcludeSemantics(
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            BrandGlyph(size: glyphSize),
            const SizedBox(width: AppSpacing.sm),
            Flexible(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text.rich(
                    TextSpan(children: [
                      const TextSpan(text: 'AI Trading '),
                      TextSpan(
                        text: 'Assistance',
                        style: title.copyWith(
                          fontWeight: FontWeight.w400,
                          color: c.fg2,
                        ),
                      ),
                    ]),
                    style: title,
                  ),
                  if (showTagline)
                    Text(
                      context.type.eyebrowUppercase ? l10n.appTagline.toUpperCase() : l10n.appTagline,
                      style: context.type.eyebrowUppercase ? tagline : context.type.eyebrow,
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
