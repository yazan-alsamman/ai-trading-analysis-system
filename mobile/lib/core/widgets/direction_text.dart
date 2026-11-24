import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';
import '../theme/theme_context.dart';

/// قيمة اتجاه السوق: سهم + إشارة (+/−) + رقم mono + لون up/down
///
/// ⚠️ أبدًا ما تعرض اتجاه باللون لحالو: الأخضر والأحمر إلهن تقريبًا نفس
/// السطوع (1.01:1 بالفاتح) فالمصاب بعمى الألوان ما بيفرّق بيناتهن إلا
/// بالسهم والإشارة. القارئ الصوتي بيقول "صعود 1.24%".
class DirectionText extends StatelessWidget {
  const DirectionText({
    super.key,
    required this.value,
    this.decimals = 2,
    this.suffix = '%',
    this.style,
    this.showArrow = true,
  });

  final double value;
  final int decimals;
  final String suffix;

  /// الافتراضي `context.type.num`
  final TextStyle? style;
  final bool showArrow;

  /// علامة الناقص الطباعية (U+2212) بعرض الأرقام بدل الواصلة
  static const String _minus = '−';

  static String format(double value, {int decimals = 2, String suffix = ''}) {
    final abs = value.abs().toStringAsFixed(decimals);
    if (double.parse(abs) == 0) return '$abs$suffix';
    return '${value > 0 ? '+' : _minus}$abs$suffix';
  }

  /// النص المقروء للقارئ الصوتي: "Up 0.45%" / "Down 0.96%" / "Unchanged 0.00%"
  static String semanticLabel(
    AppLocalizations l10n,
    double value, {
    int decimals = 2,
    String suffix = '%',
  }) {
    final abs = value.abs().toStringAsFixed(decimals);
    final direction = double.parse(abs) == 0
        ? l10n.directionFlat
        : value > 0
            ? l10n.directionUp
            : l10n.directionDown;
    return '$direction $abs$suffix';
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final rounded = double.parse(value.abs().toStringAsFixed(decimals));
    final isFlat = rounded == 0;
    final color = isFlat ? c.fg2 : c.direction(value);
    final base = (style ?? context.type.num).copyWith(color: color);

    final text = format(value, decimals: decimals, suffix: suffix);

    return Semantics(
      label: semanticLabel(l10n, value, decimals: decimals, suffix: suffix),
      excludeSemantics: true,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (showArrow && !isFlat)
            Icon(
              value > 0 ? Icons.arrow_upward_rounded : Icons.arrow_downward_rounded,
              size: (base.fontSize ?? 16) * 0.9,
              color: color,
            ),
          Text(text, style: base, textDirection: TextDirection.ltr),
        ],
      ),
    );
  }
}
