import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';
import '../theme/theme_context.dart';

enum AppButtonVariant {
  /// الإجراء الرئيسي الوحيد بالشاشة (محايد معكوس، كبسولة)
  primary,

  /// إجراء ثانوي (حدّ رفيع)
  secondary,

  /// إجراء خفيف (نص ذهبي)
  ghost,
}

/// زر الهوية - فوق FilledButton / OutlinedButton / TextButton حتى ياخد
/// الشكل والحالات من الثيم. منطقة اللمس دايمًا ≥ 48dp.
///
/// - [loading]: بيعرض مؤشّر وبيعطّل الزر (وبيعلن "جارٍ التحميل" للقارئ).
/// - الزر الرئيسي بيعمل اهتزاز تأكيد خفيف ([AppHaptics.confirm]).
class AppButton extends StatelessWidget {
  const AppButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.variant = AppButtonVariant.primary,
    this.icon,
    this.trailingIcon,
    this.loading = false,
    this.expand = false,
    this.compact = false,
  });

  const AppButton.secondary({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.trailingIcon,
    this.loading = false,
    this.expand = false,
    this.compact = false,
  }) : variant = AppButtonVariant.secondary;

  const AppButton.ghost({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.trailingIcon,
    this.loading = false,
    this.expand = false,
    this.compact = false,
  }) : variant = AppButtonVariant.ghost;

  final String label;
  final VoidCallback? onPressed;
  final AppButtonVariant variant;
  final IconData? icon;
  final IconData? trailingIcon;
  final bool loading;

  /// بياخد كامل العرض المتاح
  final bool expand;

  /// ارتفاع 40 بدل 52 (منطقة اللمس بتضل 48)
  final bool compact;

  void _handlePressed() {
    if (variant == AppButtonVariant.primary) AppHaptics.confirm();
    onPressed?.call();
  }

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null && !loading;
    final callback = enabled ? _handlePressed : null;

    final content = loading
        ? SizedBox.square(
            dimension: AppSizes.iconMd,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              color: context.colors.fg2,
              semanticsLabel: '$label, ${AppLocalizations.of(context)!.loading}',
            ),
          )
        : Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[
                Icon(icon, size: AppSizes.iconMd),
                const SizedBox(width: AppSpacing.xs),
              ],
              Flexible(
                // التسمية أبدًا ما بتنقص: بتلتف لسطر تاني والزر بيطول
                child: Text(label, textAlign: TextAlign.center),
              ),
              if (trailingIcon != null) ...[
                const SizedBox(width: AppSpacing.xs),
                Icon(trailingIcon, size: AppSizes.iconMd),
              ],
            ],
          );

    final size = compact
        ? const Size(64, AppSizes.buttonHeightSm)
        : const Size(64, AppSizes.buttonHeight);
    final style = ButtonStyle(
      minimumSize: WidgetStatePropertyAll(
        expand ? Size(double.infinity, size.height) : size,
      ),
      tapTargetSize: MaterialTapTargetSize.padded,
    );

    final button = switch (variant) {
      AppButtonVariant.primary =>
        FilledButton(onPressed: callback, style: style, child: content),
      AppButtonVariant.secondary =>
        OutlinedButton(onPressed: callback, style: style, child: content),
      AppButtonVariant.ghost =>
        TextButton(onPressed: callback, style: style, child: content),
    };

    // زر Material بيعطي الدور والحالة والإجراء لحاله (Semantics إضافي فوقه
    // كان بيعمل عقدة "زر" فاضية بدون إجراء ضغط)
    return button;
  }
}
