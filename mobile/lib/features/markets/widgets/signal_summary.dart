import 'package:flutter/material.dart';

import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/direction_badge.dart';
import '../../../core/widgets/headings.dart';
import '../../../core/widgets/not_advice_notice.dart';
import '../../../core/widgets/source_tag.dart';
import '../../../l10n/app_localizations.dart';
import '../../signals/models/opportunity.dart';
import '../models/market_models.dart';

/// خلاصة رأي النموذج تحت الرسم: الاتجاه + الاحتمال + العائد/المخاطرة،
/// شرائح الأطر (15m / 1h / 4h - الضغط بيرسم مناطقها)، المستويات، والتحذير.
class SignalSummary extends StatelessWidget {
  const SignalSummary({
    super.key,
    required this.instrument,
    required this.opportunities,
    required this.shown,
    required this.agreeing,
    required this.simulated,
    required this.onShowRead,
    required this.onSizeTrade,
    this.onRequestAnalysis,
  });

  final Instrument instrument;

  /// رأي النموذج لكل إطار (بترتيب 15m / 1h / 4h)
  final List<Opportunity> opportunities;

  /// الرأي المرسوم حاليًا (null = ما في فرصة)
  final Opportunity? shown;
  final int agreeing;
  final bool simulated;
  final ValueChanged<Timeframe> onShowRead;

  /// "Size this trade" على الرأي المرسوم
  final ValueChanged<Opportunity> onSizeTrade;

  /// "Request analysis" (sheet مع هالأداة محدّدة)؛ null = بدون الزر
  final VoidCallback? onRequestAnalysis;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;
    final read = shown;

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(child: Semantics(header: true, child: Eyebrow(l10n.modelRead))),
              SourceTag(simulated ? SourceKind.demo : SourceKind.model),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          if (read == null) ...[
            Text(l10n.noSetupTitle, style: text.titleMedium),
            const SizedBox(height: AppSpacing.xxs),
            Text(l10n.noSetupBody, style: text.bodyMedium),
          ] else ...[
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.xs,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                DirectionBadge(read.direction),
                Text(
                  Formatters.percent(read.probability),
                  style: context.type.numLarge.copyWith(color: c.forecast),
                  textDirection: TextDirection.ltr,
                ),
                Text(read.timeframe.label, style: context.type.numSmall),
              ],
            ),
            Text(l10n.probabilityCaption, style: text.bodySmall),
            const SizedBox(height: AppSpacing.md),
            _Levels(read: read, instrument: instrument),
            const SizedBox(height: AppSpacing.sm),
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: AppButton.secondary(
                label: l10n.sizeTrade,
                icon: Icons.calculate_outlined,
                compact: true,
                onPressed: () => onSizeTrade(read),
              ),
            ),
          ],
          const SizedBox(height: AppSpacing.md),
          _TimeframeChips(opportunities: opportunities, shown: read, onTap: onShowRead),
          if (read != null) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(
              '${l10n.timeframesAgree('$agreeing', '${opportunities.length}')} · '
              '${l10n.validUntil(Formatters.clock(read.validUntil.toLocal()))}',
              style: text.labelMedium,
            ),
          ],
          if (onRequestAnalysis != null) ...[
            const SizedBox(height: AppSpacing.sm),
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: AppButton.secondary(
                label: l10n.requestAnalysisTitle,
                icon: Icons.manage_search_rounded,
                compact: true,
                onPressed: onRequestAnalysis,
              ),
            ),
          ],
          const SizedBox(height: AppSpacing.xs),
          Text(l10n.signalDisclaimer, style: text.bodySmall),
          const SizedBox(height: AppSpacing.xs),
          const NotAdviceNotice(),
        ],
      ),
    );
  }
}

/// الدخول / الهدف / الوقف: علامة + كلمة + سعر (مش اللون لحالو)
class _Levels extends StatelessWidget {
  const _Levels({required this.read, required this.instrument});

  final Opportunity read;
  final Instrument instrument;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final items = [
      (l10n.zoneTarget, read.takeProfitZone, c.up),
      (l10n.zoneEntry, read.entryZone, c.accent),
      (l10n.zoneStop, read.stopLossZone, c.down),
    ];
    // بالخط الكبير القيمة بتنزل تحت التسمية بدل ما تطلع برا الكرت
    Widget line(Color? marker, String label, String value) => Padding(
          padding: const EdgeInsets.symmetric(vertical: AppSpacing.xxs),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: AppSpacing.xxs,
                height: AppSpacing.md,
                margin: const EdgeInsets.only(top: 2),
                decoration: BoxDecoration(color: marker, borderRadius: AppRadii.badge),
              ),
              const SizedBox(width: AppSpacing.xs),
              Expanded(
                child: Wrap(
                  alignment: WrapAlignment.spaceBetween,
                  spacing: AppSpacing.sm,
                  children: [
                    Text(label, style: context.textTheme.bodyMedium),
                    Text(
                      value,
                      style: context.type.numSmall.copyWith(color: c.fg),
                      textDirection: TextDirection.ltr,
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
    return Column(
      children: [
        for (final (label, zone, color) in items)
          line(color, label, '${instrument.format(zone.low)} – ${instrument.format(zone.high)}'),
        line(null, l10n.riskRewardLabel, '1 : ${read.riskReward.toStringAsFixed(1)}'),
      ],
    );
  }
}

/// شريحة لكل إطار: الإطار + سهم الاتجاه (أو "—"). الضغط بيرسم مناطقه.
class _TimeframeChips extends StatelessWidget {
  const _TimeframeChips({required this.opportunities, required this.shown, required this.onTap});

  final List<Opportunity> opportunities;
  final Opportunity? shown;
  final ValueChanged<Timeframe> onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    return Wrap(
      spacing: AppSpacing.xs,
      runSpacing: AppSpacing.xs,
      children: [
        for (final o in opportunities)
          Semantics(
            button: true,
            enabled: o.isDetected,
            onTap: o.isDetected ? () => onTap(o.timeframe) : null,
            selected: shown?.timeframe == o.timeframe,
            label: o.isDetected
                ? '${o.timeframe.label}, ${o.direction.label(l10n)} ${Formatters.percent(o.probability)}. '
                    '${l10n.showReadOnChart(o.timeframe.label)}'
                : l10n.readNoSetup(o.timeframe.label),
            excludeSemantics: true,
            child: ChoiceChip(
              selected: shown?.timeframe == o.timeframe,
              showCheckmark: false,
              materialTapTargetSize: MaterialTapTargetSize.padded,
              onSelected: o.isDetected ? (_) => onTap(o.timeframe) : null,
              label: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(o.timeframe.label, style: context.type.numSmall),
                  const SizedBox(width: AppSpacing.xxs),
                  if (o.isDetected)
                    Icon(
                      o.direction == SignalDirection.long ? Icons.arrow_upward_rounded : Icons.arrow_downward_rounded,
                      size: AppSizes.iconSm,
                      color: o.direction == SignalDirection.long ? c.up : c.down,
                    ),
                  // الاتجاه بكلمة كمان، مش بس سهم ملوّن
                  if (o.isDetected)
                    Text(' ${o.direction.label(l10n)}', style: context.textTheme.labelSmall)
                  else
                    Text('—', style: context.textTheme.labelSmall),
                ],
              ),
            ),
          ),
      ],
    );
  }
}
