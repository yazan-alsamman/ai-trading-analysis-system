import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_text_styles.dart';

/// رسم بياني مصغّر لحركة السعر داخل شاشة التداول
///
/// يُرسم بالكامل عبر CustomPainter (بدون صور خارجية) حتى يبقى خفيفًا
/// ويتكيّف تلقائيًا مع أي رمز/سعر يُمرَّر إليه.
class TradePriceChart extends StatelessWidget {
  const TradePriceChart({
    super.key,
    required this.isPositive,
    this.seed = 0,
  });

  /// هل الاتجاه العام صاعد؟ (يحدد لون الخط والتدرج)
  final bool isPositive;

  /// بذرة عشوائية ثابتة لرسم نفس الشكل في كل مرة لنفس الرمز
  final int seed;

  @override
  Widget build(BuildContext context) {
    final lineColor = isPositive ? AppColors.success : AppColors.error;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 24),
      decoration: BoxDecoration(
        color: AppColors.bgSurface,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                isPositive
                    ? Icons.trending_up_rounded
                    : Icons.trending_down_rounded,
                size: 18,
                color: lineColor,
              ),
              const SizedBox(width: 6),
              Text(
                '1D',
                style: AppTextStyles.labelSmall.copyWith(
                  color: AppColors.textHint,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Expanded(
            child: CustomPaint(
              size: Size.infinite,
              painter: _PriceChartPainter(
                lineColor: lineColor,
                seed: seed,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _PriceChartPainter extends CustomPainter {
  _PriceChartPainter({required this.lineColor, required this.seed});

  final Color lineColor;
  final int seed;

  @override
  void paint(Canvas canvas, Size size) {
    final points = _generatePoints(size);

    final linePath = Path()..moveTo(points.first.dx, points.first.dy);
    for (final p in points.skip(1)) {
      linePath.lineTo(p.dx, p.dy);
    }

    // منطقة التدرج أسفل الخط
    final fillPath = Path.from(linePath)
      ..lineTo(points.last.dx, size.height)
      ..lineTo(points.first.dx, size.height)
      ..close();

    final fillPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [lineColor.withOpacity(0.28), lineColor.withOpacity(0.0)],
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height));
    canvas.drawPath(fillPath, fillPaint);

    final linePaint = Paint()
      ..color = lineColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.5
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    canvas.drawPath(linePath, linePaint);

    // نقطة آخر سعر
    final dotPaint = Paint()..color = lineColor;
    canvas.drawCircle(points.last, 4, dotPaint);
    canvas.drawCircle(
      points.last,
      7,
      Paint()..color = lineColor.withOpacity(0.25),
    );

    // خطوط شبكة أفقية خفيفة
    final gridPaint = Paint()
      ..color = AppColors.fieldBorder.withOpacity(0.18)
      ..strokeWidth = 1;
    for (var i = 1; i < 4; i++) {
      final y = size.height / 4 * i;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }
  }

  List<Offset> _generatePoints(Size size) {
    final random = math.Random(seed);
    const count = 24;
    final values = <double>[];
    var value = 0.5;
    for (var i = 0; i < count; i++) {
      value += (random.nextDouble() - 0.45) * 0.18;
      value = value.clamp(0.08, 0.92);
      values.add(value);
    }

    return List.generate(count, (i) {
      final x = size.width / (count - 1) * i;
      final y = size.height * (1 - values[i]);
      return Offset(x, y);
    });
  }

  @override
  bool shouldRepaint(covariant _PriceChartPainter oldDelegate) {
    return oldDelegate.lineColor != lineColor || oldDelegate.seed != seed;
  }
}
