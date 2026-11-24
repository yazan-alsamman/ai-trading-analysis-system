import 'package:flutter/material.dart';

import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/segment_label.dart';
import '../../../l10n/app_localizations.dart';

/// صف "المظهر" داخل مجموعة التفضيلات: عنوان + segmented فاتح/داكن/نظام
///
/// التغيير بيتطبّق فورًا وبينحفظ (راجع themeModeProvider).
class AppearanceSelector extends StatelessWidget {
  const AppearanceSelector({
    super.key,
    required this.mode,
    required this.onChanged,
  });

  final ThemeMode mode;
  final ValueChanged<ThemeMode> onChanged;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;

    return Padding(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: c.inset,
                  borderRadius: AppRadii.field,
                  border: Border.all(color: c.hairline),
                ),
                child: Icon(Icons.contrast_rounded, size: AppSizes.iconMd, color: c.fg2),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(l10n.appearance, style: text.titleSmall),
                    const SizedBox(height: 2),
                    Text(
                      l10n.appearanceSubtitle,
                      style: text.bodySmall!.copyWith(color: c.fg2),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Semantics(
            container: true,
            label: l10n.appearance,
            child: SegmentedButton<ThemeMode>(
              showSelectedIcon: false,
              segments: [
                ButtonSegment(
                  value: ThemeMode.light,
                  icon: const Icon(Icons.light_mode_outlined),
                  label: SegmentLabel(l10n.themeLight),
                ),
                ButtonSegment(
                  value: ThemeMode.dark,
                  icon: const Icon(Icons.dark_mode_outlined),
                  label: SegmentLabel(l10n.themeDark),
                ),
                ButtonSegment(
                  value: ThemeMode.system,
                  icon: const Icon(Icons.brightness_auto_outlined),
                  label: SegmentLabel(l10n.themeSystem),
                ),
              ],
              selected: {mode},
              onSelectionChanged: (selection) {
                AppHaptics.selection();
                onChanged(selection.first);
              },
            ),
          ),
        ],
      ),
    );
  }
}
