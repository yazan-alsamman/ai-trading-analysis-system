import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_card.dart';
import '../../../l10n/app_localizations.dart';
import '../../markets/models/market_models.dart';
import '../data/signal_profile_repository.dart';
import '../models/signal_profile.dart';
import 'method_picker.dart';
import 'strategy_sheet.dart';

/// الأدوات كنص قصير: "all instruments" للكل، وإلا "N instruments"
String strategyInstrumentsText(AppLocalizations l10n, SignalProfile profile) =>
    profile.symbols.length == kProductSymbols.length
        ? l10n.strategyAllInstruments
        : l10n.workspaceInstrumentCount(profile.symbols.length);

/// سطر الخلاصة الوحيد بالبطاقة:
/// محفوظة → "RSI Reversal · 3 instruments · above 65%" (الاحتمال بس لو في حد أدنى)؛
/// الافتراضي → "Default: MA Crossover · all instruments".
/// [methodName] null = الكتالوج لسّا ما وصل، فالطريقة بتغيب لحظة.
String strategySummaryLine(
  AppLocalizations l10n,
  SignalProfile profile, {
  required bool custom,
  required String? methodName,
}) {
  final instruments = strategyInstrumentsText(l10n, profile);
  if (!custom) {
    return methodName == null ? instruments : l10n.strategyCardDefault(methodName, instruments);
  }
  return [
    if (methodName != null) methodName,
    instruments,
    if (profile.minProbability > 0) l10n.strategyAboveProbability(Formatters.percent(profile.minProbability)),
  ].join(' · ');
}

/// بطاقة "Strategy" بتبويب Signals: العنوان + سطر خلاصة واحد (الطريقة، الأدوات،
/// الاحتمال الأدنى)، والضغط بيفتح الـ sheet. الحفظ جوّا الـ sheet (ما بتتسكّر)،
/// وبعد "Remove strategy" snackbar مع Undo.
class StrategyBar extends ConsumerWidget {
  const StrategyBar({super.key});

  /// بيفتح الـ sheet (كمان من زر الحالة الفاضية بالقائمة)؛ بعد الإزالة snackbar مع Undo
  static Future<void> open(BuildContext context) async {
    final container = ProviderScope.containerOf(context, listen: false);
    final result = await showStrategySheet(context);
    if (!context.mounted) return;
    switch (result) {
      case StrategyRemoved(:final previous):
        final l10n = AppLocalizations.of(context)!;
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(SnackBar(
            content: Text(l10n.strategyRemoved),
            action: SnackBarAction(
              label: l10n.undo,
              onPressed: () => container.read(signalProfileProvider.notifier).save(previous),
            ),
          ));
      case null:
        break;
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profile = ref.watch(signalProfileProvider);
    final custom = ref.watch(hasCustomStrategyProvider);
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final text = context.textTheme;
    final summary = strategySummaryLine(
      l10n,
      profile,
      custom: custom,
      methodName: watchMethodName(ref, context, profile.methodId),
    );

    return AppCard(
      onTap: () => open(context),
      highlight: custom,
      semanticLabel: '${l10n.strategyTitle}. $summary',
      child: ExcludeSemantics(
        child: Row(
          children: [
            Icon(Icons.tune_rounded, color: c.accent, size: AppSizes.iconLg),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(l10n.strategyTitle, style: text.titleSmall),
                  const SizedBox(height: 2),
                  // سطر واحد بالمعنى، بس بيلتف بالخط الكبير (ما في قص)
                  Text(summary, style: text.bodySmall!.copyWith(color: custom ? c.fg : c.fg2)),
                ],
              ),
            ),
            Icon(Icons.chevron_right_rounded, color: c.fg3, size: AppSizes.iconLg),
          ],
        ),
      ),
    );
  }
}
