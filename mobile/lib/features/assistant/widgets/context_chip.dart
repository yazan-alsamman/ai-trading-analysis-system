import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/theme_context.dart';
import '../../../l10n/app_localizations.dart';
import '../../markets/models/market_models.dart';
import '../view_models/assistant_view_model.dart';

/// شريحة السياق: "Context · EUR/USD ▾" - المساعد بيعرف بس هالأداة (سعرها،
/// رأي النموذج عليها) وحدودك. الضغط بيفتح اختيار الأداة.
class ContextChip extends ConsumerWidget {
  const ContextChip({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final symbol = ref.watch(assistantViewModelProvider.select((s) => s.contextSymbol));
    final label = symbol ?? l10n.asstContextNone;

    return Semantics(
      button: true,
      label: l10n.asstContextLabel(label),
      hint: l10n.asstContextHint,
      onTap: () => _pick(context, ref, symbol),
      excludeSemantics: true,
      child: ActionChip(
        materialTapTargetSize: MaterialTapTargetSize.padded,
        avatar: Icon(Icons.candlestick_chart_outlined, size: AppSizes.iconSm, color: c.accent),
        label: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(l10n.asstContext, style: context.textTheme.labelLarge!.copyWith(color: c.fg2)),
            const SizedBox(width: AppSpacing.xxs),
            Flexible(
              child: Text(
                label,
                style: symbol == null ? context.textTheme.labelLarge : context.type.numSmall.copyWith(color: c.fg),
                textDirection: symbol == null ? null : TextDirection.ltr,
              ),
            ),
            const SizedBox(width: AppSpacing.xxs),
            Icon(Icons.arrow_drop_down_rounded, size: AppSizes.iconMd, color: c.fg2),
          ],
        ),
        onPressed: () => _pick(context, ref, symbol),
      ),
    );
  }

  Future<void> _pick(BuildContext context, WidgetRef ref, String? current) async {
    AppHaptics.light();
    final choice = await showModalBottomSheet<_Choice>(
      useRootNavigator: true,
      context: context,
      sheetAnimationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
      useSafeArea: true,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => _ContextSheet(current: current),
    );
    if (choice != null) ref.read(assistantViewModelProvider.notifier).setContext(choice.symbol);
  }
}

/// غلاف حتى "بدون أداة" (null) ينفرق عن "سكّر الـ sheet بدون اختيار"
final class _Choice {
  const _Choice(this.symbol);

  final String? symbol;
}

class _ContextSheet extends StatelessWidget {
  const _ContextSheet({required this.current});

  final String? current;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final text = context.textTheme;
    final c = context.colors;
    final gutter = AppSpacing.gutter(context);
    final options = <String?>[...kProductSymbols, null];

    return SingleChildScrollView(
      padding: const EdgeInsets.only(bottom: AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Padding(
            padding: EdgeInsets.fromLTRB(gutter, 0, gutter, AppSpacing.xxs),
            child: Semantics(header: true, child: Text(l10n.asstContextTitle, style: text.titleLarge)),
          ),
          Padding(
            padding: EdgeInsets.fromLTRB(gutter, 0, gutter, AppSpacing.sm),
            child: Text(l10n.asstContextBody, style: text.bodyMedium),
          ),
          for (final symbol in options)
            Semantics(
              inMutuallyExclusiveGroup: true,
              checked: symbol == current,
              child: ListTile(
                contentPadding: EdgeInsets.symmetric(horizontal: gutter),
                minTileHeight: 56,
                title: Text(
                  symbol ?? l10n.asstContextNone,
                  style: text.titleSmall!.copyWith(color: symbol == current ? c.fg : c.fg2),
                ),
                subtitle: Text(
                  symbol == null ? l10n.asstContextNoneHint : l10n.instrumentName(symbol),
                  style: text.bodySmall,
                ),
                trailing: symbol == current ? Icon(Icons.check_rounded, color: c.accent, size: AppSizes.iconLg) : null,
                onTap: () => Navigator.of(context).pop(_Choice(symbol)),
              ),
            ),
        ],
      ),
    );
  }
}
