import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';
import '../theme/theme_context.dart';

/// حقل الإدخال: label ظاهر دايمًا فوق الحقل (مش placeholder بس)،
/// والخطأ تحت الحقل نفسه. حقول كلمة المرور فيها زر إظهار/إخفاء
/// بتسمية مقروءة، وبتسمح بالـ paste ومديري كلمات المرور (autofillHints).
///
/// - الـ label بيصير ذهبي وقت التركيز (مع الحدّ الذهبي من الثيم).
class AppTextField extends StatefulWidget {
  const AppTextField({
    super.key,
    required this.label,
    this.controller,
    this.hint,
    this.helper,
    this.errorText,
    this.prefixIcon,
    this.obscure = false,
    this.keyboardType,
    this.textInputAction,
    this.autofillHints,
    this.validator,
    this.onChanged,
    this.onSubmitted,
    this.enabled = true,
    this.maxLines = 1,
    this.textCapitalization = TextCapitalization.none,
    this.maxLength,
  });

  final String label;
  final TextEditingController? controller;
  final String? hint;
  final String? helper;
  final String? errorText;
  final IconData? prefixIcon;
  final bool obscure;
  final TextInputType? keyboardType;
  final TextInputAction? textInputAction;
  final Iterable<String>? autofillHints;
  final FormFieldValidator<String>? validator;
  final ValueChanged<String>? onChanged;
  final ValueChanged<String>? onSubmitted;
  final bool enabled;
  final int maxLines;
  final TextCapitalization textCapitalization;

  /// حدّ الأحرف (مع عدّاد تحت الحقل)
  final int? maxLength;

  @override
  State<AppTextField> createState() => _AppTextFieldState();
}

class _AppTextFieldState extends State<AppTextField> {
  late bool _hidden = widget.obscure;
  bool _focused = false;

  /// إظهار/إخفاء كلمة المرور بس (ما في زر مسح)
  Widget? _suffix(AppLocalizations l10n) {
    if (widget.obscure) {
      return IconButton(
        tooltip: _hidden ? l10n.showPassword : l10n.hidePassword,
        icon: Icon(_hidden ? Icons.visibility_outlined : Icons.visibility_off_outlined),
        onPressed: () => setState(() => _hidden = !_hidden),
      );
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final labelStyle = context.textTheme.labelLarge!;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        AnimatedDefaultTextStyle(
          duration: context.motion(AppMotion.fast),
          curve: AppMotion.out,
          style: labelStyle.copyWith(color: _focused ? c.accent : labelStyle.color),
          // التسمية المرئية مخفية عن القارئ: نفس النص اسم للحقل نفسه (تحت)
          child: ExcludeSemantics(child: Text(widget.label)),
        ),
        const SizedBox(height: AppSpacing.xs),
        Focus(
          canRequestFocus: false,
          skipTraversal: true,
          onFocusChange: (focused) => setState(() => _focused = focused),
          child: Semantics(
            label: widget.label,
            child: TextFormField(
              controller: widget.controller,
              maxLength: widget.maxLength,
              enabled: widget.enabled,
              obscureText: _hidden,
              keyboardType: widget.keyboardType,
              textInputAction: widget.textInputAction,
              textCapitalization: widget.textCapitalization,
              autofillHints: widget.autofillHints,
              validator: widget.validator,
              onChanged: widget.onChanged,
              onFieldSubmitted: widget.onSubmitted,
              maxLines: widget.obscure ? 1 : widget.maxLines,
              style: context.textTheme.bodyLarge,
              decoration: InputDecoration(
                hintText: widget.hint,
                hintMaxLines: 3,
                helperText: widget.helper,
                helperMaxLines: 3,
                errorText: widget.errorText,
                errorMaxLines: 3,
                prefixIcon: widget.prefixIcon == null ? null : Icon(widget.prefixIcon),
                suffixIcon: _suffix(l10n),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
