import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';
import '../theme/theme_context.dart';

/// مصدر القيمة - كل رقم بالتطبيق لازم يكون واضح من وين جاي
enum SourceKind { live, historical, model, user, demo, unavailable }

/// شارة المصدر (نفس web SourceTag): أيقونة + كلمة، دايمًا.
/// "محاكاة" إلها حدّ متقطّع سماوي حتى تنعرف حتى بدون لون.
class SourceTag extends StatelessWidget {
  const SourceTag(this.kind, {super.key});

  final SourceKind kind;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;

    final (IconData icon, String label, Color fg, Color bg) = switch (kind) {
      SourceKind.live => (Icons.sensors_rounded, l10n.sourceLive, c.up, c.upSoft),
      SourceKind.historical =>
        (Icons.history_rounded, l10n.sourceHistorical, c.fg2, c.selected),
      SourceKind.model =>
        (Icons.auto_awesome_rounded, l10n.sourceModel, c.forecast, c.forecastSoft),
      SourceKind.user =>
        (Icons.edit_note_rounded, l10n.sourceUser, c.fg2, c.selected),
      SourceKind.demo => (Icons.science_outlined, l10n.sourceDemo, c.demo, c.demoSoft),
      SourceKind.unavailable =>
        (Icons.cloud_off_rounded, l10n.sourceUnavailable, c.warning, c.warningSoft),
    };

    final chip = Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.xs,
        vertical: AppSpacing.xxs / 2,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: AppSizes.iconSm - 2, color: fg),
          const SizedBox(width: AppSpacing.xxs),
          // بالخط الكبير بمكان ضيق الكلمة بتلف جوّا الشارة بدل ما تطلع برّا
          Flexible(child: Text(label, style: context.textTheme.labelSmall!.copyWith(color: fg))),
        ],
      ),
    );

    return Semantics(
      label: label,
      excludeSemantics: true,
      child: DecoratedBox(
        decoration: BoxDecoration(color: bg, borderRadius: AppRadii.badge),
        child: kind == SourceKind.demo
            ? CustomPaint(
                foregroundPainter: _DashedBorderPainter(color: fg),
                child: chip,
              )
            : chip,
      ),
    );
  }
}

class _DashedBorderPainter extends CustomPainter {
  _DashedBorderPainter({required this.color});

  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final rrect = RRect.fromRectAndRadius(
      Offset.zero & size,
      const Radius.circular(AppRadii.xs),
    ).deflate(0.5);
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    for (final metric in (Path()..addRRect(rrect)).computeMetrics()) {
      var d = 0.0;
      while (d < metric.length) {
        canvas.drawPath(metric.extractPath(d, d + 3), paint);
        d += 5;
      }
    }
  }

  @override
  bool shouldRepaint(_DashedBorderPainter old) => old.color != color;
}
