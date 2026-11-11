import 'package:flutter/material.dart';

import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_card.dart';
import '../../../l10n/app_localizations.dart';
import '../../signals/models/model_accuracy.dart';
import '../models/track_record.dart';

/// بطاقة تقسيم (حسب الأداة / حسب الإطار): عنوان + صف لكل عنصر
class AccuracyBreakdownCard extends StatelessWidget {
  const AccuracyBreakdownCard({super.key, required this.title, required this.rows});

  final String title;
  final List<AccuracyRow> rows;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Semantics(header: true, child: Text(title, style: context.textTheme.titleMedium)),
          for (final row in rows) ...[
            const SizedBox(height: AppSpacing.sm),
            row,
          ],
        ],
      ),
    );
  }
}

/// صف دقة: الاسم + النسبة، شريط النسبة، وعدد الإشارات (+ "عيّنة صغيرة").
///
/// الشريط محايد (مش أخضر/أحمر: النسبة مش اتجاه، ومش ذهبي: مش اختيار).
class AccuracyRow extends StatelessWidget {
  const AccuracyRow({super.key, required this.title, required this.semanticName, required this.accuracy});

  final String title;

  /// الاسم الكامل للقارئ الصوتي ("EUR/USD, Euro / US Dollar")
  final String semanticName;
  final ModelAccuracy accuracy;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final rate = accuracy.hitRate;
    final rateText = rate == null ? '—' : Formatters.percent(rate);
    final small = accuracy.isSmallSample;
    final count = l10n.insightsSignalsCount('${accuracy.resolved}');

    return Semantics(
      container: true,
      excludeSemantics: true,
      label: [
        rate == null
            ? l10n.insightsRowEmptyLabel(semanticName)
            : l10n.insightsRowLabel(semanticName, rateText, '${accuracy.hits}', '${accuracy.resolved}'),
        if (small && rate != null) l10n.insightsSmallSample,
      ].join(' '),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(child: Text(title, style: context.type.numSmall.copyWith(color: c.fg))),
              const SizedBox(width: AppSpacing.xs),
              Text(rateText, style: context.type.numSmall.copyWith(color: small ? c.fg3 : c.fg)),
            ],
          ),
          const SizedBox(height: AppSpacing.xxs),
          ClipRRect(
            borderRadius: AppRadii.pillAll,
            child: SizedBox(
              height: AppSpacing.xs - 2,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  ColoredBox(color: c.pressed),
                  if (rate != null)
                    FractionallySizedBox(
                      alignment: AlignmentDirectional.centerStart,
                      widthFactor: rate,
                      child: ColoredBox(color: small ? c.fg3 : c.fg2),
                    ),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.xxs),
          Text(
            small && rate != null ? '$count · ${l10n.insightsSmallSample}' : count,
            style: context.textTheme.labelSmall!.copyWith(color: c.fg3),
          ),
        ],
      ),
    );
  }
}
