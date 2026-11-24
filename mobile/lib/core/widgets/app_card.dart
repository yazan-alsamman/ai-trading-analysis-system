import 'package:flutter/material.dart';

import '../theme/theme_context.dart';

/// البطاقة الأساسية: درجة سطح + خط رفيع (بدون ظل)
///
/// - [onTap] / [onLongPress]: بتصير البطاقة زر (ripple + semantics)،
///   والضغطة المطوّلة بتعمل اهتزاز خفيف.
/// - [highlight]: البطاقة البطل الوحيدة بالشاشة - زوايا 16 + توهّج ذهبي
///   خفيف (نفس shadow-glow-aurum بالويب). استخدمها مرة وحدة بالشاشة بس.
class AppCard extends StatelessWidget {
  const AppCard({
    super.key,
    required this.child,
    this.onTap,
    this.onLongPress,
    this.padding = const EdgeInsets.all(AppSpacing.md),
    this.highlight = false,
    this.color,
    this.semanticLabel,
  });

  final Widget child;
  final VoidCallback? onTap;
  final VoidCallback? onLongPress;
  final EdgeInsetsGeometry padding;
  final bool highlight;
  final Color? color;
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final radius = highlight ? AppRadii.heroCard : AppRadii.card;
    final border = BorderSide(
      color: highlight ? c.accent.withValues(alpha: 0.22) : c.hairline,
    );

    final card = Material(
      color: color ?? c.card,
      shape: RoundedRectangleBorder(borderRadius: radius, side: border),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        onLongPress: onLongPress == null
            ? null
            : () {
                AppHaptics.light();
                onLongPress!();
              },
        child: Padding(padding: padding, child: child),
      ),
    );

    final decorated = highlight
        ? DecoratedBox(
            decoration: BoxDecoration(
              borderRadius: radius,
              boxShadow: [
                BoxShadow(
                  color: c.accent.withValues(alpha: context.isDark ? 0.18 : 0.14),
                  blurRadius: 32,
                  spreadRadius: -12,
                  offset: const Offset(0, 12),
                ),
              ],
            ),
            child: card,
          )
        : card;

    if (onTap == null && onLongPress == null) return decorated;
    return Semantics(
      button: true,
      label: semanticLabel,
      child: decorated,
    );
  }
}
