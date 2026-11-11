import 'package:flutter/material.dart';

import '../../../core/theme/theme_context.dart';
import '../../../l10n/app_localizations.dart';
import '../models/track_record.dart';

extension InsightsPeriodLabel on InsightsPeriod {
  /// "7 days" / "7 أيام"
  String label(AppLocalizations l10n) => switch (this) {
        InsightsPeriod.d7 => l10n.insightsPeriod7,
        InsightsPeriod.d30 => l10n.insightsPeriod30,
        InsightsPeriod.d90 => l10n.insightsPeriod90,
      };
}

/// شرائح الفترة (7 / 30 / 90 يوم) - شغّالة حتى أثناء التحميل
class PeriodChips extends StatelessWidget {
  const PeriodChips({super.key, required this.selected, required this.onSelected});

  final InsightsPeriod selected;
  final ValueChanged<InsightsPeriod> onSelected;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return Semantics(
      container: true,
      label: l10n.insightsPeriodsLabel,
      child: Wrap(
        spacing: AppSpacing.xs,
        runSpacing: AppSpacing.xs,
        children: [
          for (final period in InsightsPeriod.values)
            ChoiceChip(
              selected: period == selected,
              showCheckmark: false,
              materialTapTargetSize: MaterialTapTargetSize.padded,
              onSelected: (_) {
                if (period != selected) onSelected(period);
              },
              label: Text(period.label(l10n)),
            ),
        ],
      ),
    );
  }
}
