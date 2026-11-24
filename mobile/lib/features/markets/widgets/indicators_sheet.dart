import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../l10n/app_localizations.dart';
import '../view_models/market_view_model.dart';

Future<void> showIndicatorsSheet(BuildContext context, {required String symbol}) {
  AppHaptics.light();
  return showModalBottomSheet<void>(
    useRootNavigator: true,
    context: context,
    sheetAnimationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
    useSafeArea: true,
    showDragHandle: true,
    isScrollControlled: true,
    builder: (_) => IndicatorsSheet(symbol: symbol),
  );
}

/// المؤشرات: مفتاح لكل مؤشر، التغيير بيبيّن فورًا على الرسم ورا الـ sheet
class IndicatorsSheet extends ConsumerWidget {
  const IndicatorsSheet({super.key, required this.symbol});

  final String symbol;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final text = context.textTheme;
    final on = ref.watch(marketViewModelProvider(symbol).select((s) => s.indicators));
    final vm = ref.read(marketViewModelProvider(symbol).notifier);

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(AppSpacing.lg, 0, AppSpacing.lg, AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Semantics(header: true, child: Text(l10n.indicators, style: text.titleLarge)),
          const SizedBox(height: AppSpacing.xs),
          for (final indicator in ChartIndicator.values)
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              value: on.contains(indicator),
              onChanged: (_) {
                AppHaptics.selection();
                vm.toggleIndicator(indicator);
              },
              title: Text(
                switch (indicator) {
                  ChartIndicator.sma => l10n.indSma,
                  ChartIndicator.ema => l10n.indEma,
                  ChartIndicator.bollinger => l10n.indBollinger,
                  ChartIndicator.rsi => l10n.indRsi,
                  ChartIndicator.macd => l10n.indMacd,
                },
                style: text.titleSmall,
              ),
              subtitle: Text(
                switch (indicator) {
                  ChartIndicator.sma => l10n.indSmaHint,
                  ChartIndicator.ema => l10n.indEmaHint,
                  ChartIndicator.bollinger => l10n.indBollingerHint,
                  ChartIndicator.rsi => l10n.indRsiHint,
                  ChartIndicator.macd => l10n.indMacdHint,
                },
                style: text.bodySmall,
              ),
            ),
          const SizedBox(height: AppSpacing.xs),
          Text(l10n.indicatorsNote, style: text.bodySmall),
          const SizedBox(height: AppSpacing.md),
          AppButton.secondary(label: l10n.done, expand: true, onPressed: () => Navigator.of(context).pop()),
        ],
      ),
    );
  }
}
