import 'package:flutter/material.dart';

import '../../../core/theme/theme_context.dart';
import '../../../l10n/app_localizations.dart';
import '../../../utils/validators.dart';

/// شروط كلمة المرور وهي عم تنكتب: 8+ أحرف، حرف، رقم (نفس الـ backend).
/// كل شرط أيقونة + كلمة (مش لون بس)، والقارئ الصوتي بيسمع "تحقّق / لم يتحقّق".
class PasswordChecks extends StatelessWidget {
  const PasswordChecks({super.key, required this.password});

  final String password;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final checks = [
      (l10n.passwordCheckLength, password.length >= Validators.passwordMinLength),
      (l10n.passwordCheckLetter, Validators.hasLetter(password)),
      (l10n.passwordCheckNumber, Validators.hasDigit(password)),
    ];
    return Wrap(
      spacing: AppSpacing.md,
      runSpacing: AppSpacing.xxs,
      children: [
        for (final (label, ok) in checks) _Check(label: label, ok: ok),
      ],
    );
  }
}

class _Check extends StatelessWidget {
  const _Check({required this.label, required this.ok});

  final String label;
  final bool ok;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    return Semantics(
      label: '$label, ${ok ? l10n.checkMet : l10n.checkNotMet}',
      excludeSemantics: true,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            ok ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded,
            size: AppSizes.iconSm,
            color: ok ? c.accent : c.fg3,
          ),
          const SizedBox(width: AppSpacing.xxs),
          Flexible(child: Text(label, style: context.textTheme.bodySmall!.copyWith(color: ok ? c.fg : c.fg2))),
        ],
      ),
    );
  }
}
