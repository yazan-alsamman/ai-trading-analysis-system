import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../l10n/app_localizations.dart';
import '../data/low_data_mode.dart';
import '../theme/theme_context.dart';

/// H5b: شارة "Low data mode" (أيقونة + كلمة) - الوضع ما بيخبّي شي بدون ما
/// يقول. مطفي = ولا شي. Semantics: منطقة حيّة (polite) بتشرح شو تغيّر.
class LowDataPill extends ConsumerWidget {
  const LowDataPill({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (!ref.watch(lowDataModeProvider)) return const SizedBox.shrink();
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    return Semantics(
      container: true,
      liveRegion: true,
      label: l10n.lowDataPillLabel,
      excludeSemantics: true,
      child: DecoratedBox(
        decoration: BoxDecoration(
          borderRadius: AppRadii.pillAll,
          border: Border.all(color: c.hairline),
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xs, vertical: AppSpacing.xxs / 2),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.data_saver_on_rounded, size: AppSizes.iconSm - 2, color: c.fg2),
              const SizedBox(width: AppSpacing.xxs),
              Flexible(
                child: Text(l10n.lowDataMode, style: context.textTheme.labelSmall!.copyWith(color: c.fg2)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
