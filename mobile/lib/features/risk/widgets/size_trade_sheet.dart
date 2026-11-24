import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/direction_badge.dart';
import '../../../core/widgets/source_tag.dart';
import '../../../l10n/app_localizations.dart';
import '../../markets/models/market_models.dart';
import '../../signals/models/opportunity.dart';
import '../data/risk_limits_repository.dart';
import '../models/risk_limits.dart';
import '../models/trade_sizing.dart';

/// "Size this trade": حساب حجم صفقة من خطة النموذج ورأس مال المستخدم.
/// حساب بس - التطبيق ما بينفّذ ولا بيبعت أي أمر.
Future<void> showSizeTradeSheet(
  BuildContext context, {
  required Instrument instrument,
  required Opportunity read,
}) {
  AppHaptics.light();
  return showModalBottomSheet<void>(
    useRootNavigator: true,
    context: context,
    sheetAnimationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
    isScrollControlled: true,
    useSafeArea: true,
    showDragHandle: true,
    builder: (_) => SizeTradeSheet(instrument: instrument, read: read),
  );
}

class SizeTradeSheet extends ConsumerStatefulWidget {
  const SizeTradeSheet({super.key, required this.instrument, required this.read});

  final Instrument instrument;
  final Opportunity read;

  @override
  ConsumerState<SizeTradeSheet> createState() => _SizeTradeSheetState();
}

class _SizeTradeSheetState extends ConsumerState<SizeTradeSheet> {
  static const List<double> _riskSteps = [0.5, 1, 2];
  static final _numberOnly = [FilteringTextInputFormatter.allow(RegExp(r'[0-9.٫]'))];

  late final RiskLimits _limits = ref.read(riskLimitsProvider);
  late final TextEditingController _capital = TextEditingController(
    text: _limits.capital == null ? '' : Formatters.trimZeros(_limits.capital!.toStringAsFixed(2)),
  );
  late final TextEditingController _risk =
      TextEditingController(text: Formatters.trimZeros(_limits.maxRiskPerTradePct.toStringAsFixed(2)));
  late final TextEditingController _entry =
      TextEditingController(text: widget.instrument.format(widget.read.entryZone.mid));
  late final TextEditingController _stop =
      TextEditingController(text: widget.instrument.format(widget.read.stopLossZone.mid));
  late final TextEditingController _target =
      TextEditingController(text: widget.instrument.format(widget.read.takeProfitZone.mid));

  @override
  void dispose() {
    for (final c in [_capital, _risk, _entry, _stop, _target]) {
      c.dispose();
    }
    super.dispose();
  }

  SizingResult get _result => computeTradeSize(
        instrument: widget.instrument,
        capital: parseUserNumber(_capital.text),
        riskPct: parseUserNumber(_risk.text),
        entry: parseUserNumber(_entry.text),
        stop: parseUserNumber(_stop.text),
        target: parseUserNumber(_target.text),
        maxRiskPerTradePct: _limits.maxRiskPerTradePct,
      );

  void _setRisk(double pct) {
    AppHaptics.selection();
    setState(() => _risk.text = Formatters.trimZeros(pct.toStringAsFixed(2)));
  }

  @override
  Widget build(BuildContext context) {
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;
    final instrument = widget.instrument;
    final read = widget.read;

    Widget field(TextEditingController controller, String label, {String? prefix, String? suffix, String? helper}) =>
        TextField(
          controller: controller,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          inputFormatters: _numberOnly,
          textInputAction: TextInputAction.next,
          style: context.type.num,
          decoration: InputDecoration(
            labelText: label,
            prefixText: prefix,
            suffixText: suffix,
            helperText: helper,
            helperMaxLines: 3,
          ),
          onChanged: (_) => setState(() {}),
        );

    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(AppSpacing.lg, 0, AppSpacing.lg, AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min,
          children: [
            Semantics(
              header: true,
              child: Text('${l10n.sizeTrade} · ${instrument.symbol}', style: text.titleLarge),
            ),
            const SizedBox(height: AppSpacing.xs),
            Wrap(
              spacing: AppSpacing.xs,
              runSpacing: AppSpacing.xxs,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                DirectionBadge(read.direction),
                Text(l10n.sizeFromRead(read.timeframe.label), style: text.bodyMedium),
              ],
            ),
            const SizedBox(height: AppSpacing.lg),
            _ResultCard(result: _result, instrument: instrument, limitPct: _limits.maxRiskPerTradePct),
            const SizedBox(height: AppSpacing.lg),
            field(
              _capital,
              l10n.riskCapitalLabel,
              prefix: '${RiskLimits.currency} ',
              helper: _limits.hasCapital ? null : l10n.sizeCapitalHint,
            ),
            const SizedBox(height: AppSpacing.md),
            field(_risk, l10n.sizeRiskLabel, suffix: '%'),
            const SizedBox(height: AppSpacing.xs),
            Wrap(
              spacing: AppSpacing.xs,
              runSpacing: AppSpacing.xs,
              children: [
                for (final step in _riskSteps)
                  ChoiceChip(
                    selected: parseUserNumber(_risk.text) == step,
                    showCheckmark: false,
                    materialTapTargetSize: MaterialTapTargetSize.padded,
                    label: Text(Formatters.plainPercent(step), style: context.type.numSmall),
                    onSelected: (_) => _setRisk(step),
                  ),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            field(_entry, l10n.zoneEntry),
            const SizedBox(height: AppSpacing.md),
            field(_stop, l10n.zoneStop),
            const SizedBox(height: AppSpacing.md),
            field(_target, l10n.sizeTargetLabel),
            const SizedBox(height: AppSpacing.md),
            Text(l10n.sizeNote, style: text.bodySmall),
            const SizedBox(height: AppSpacing.md),
            AppButton.secondary(label: l10n.done, expand: true, onPressed: () => Navigator.of(context).pop()),
          ],
        ),
      ),
    );
  }
}

/// النتيجة فوق الحقول: الحجم، المبلغ المعرّض، مسافة الوقف، الربح المحتمل،
/// وحالة الحد (أيقونة + كلمة، مش اللون لحالو). أو سبب غياب النتيجة.
class _ResultCard extends StatelessWidget {
  const _ResultCard({required this.result, required this.instrument, required this.limitPct});

  final SizingResult result;
  final Instrument instrument;
  final double limitPct;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;

    final Widget body = switch (result) {
      SizingProblem(:final issue) => Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.info_outline_rounded, size: AppSizes.iconMd, color: c.fg2),
            const SizedBox(width: AppSpacing.xs),
            Expanded(
              child: Text(
                switch (issue) {
                  SizingIssue.incomplete => l10n.sizeIncomplete,
                  SizingIssue.stopEqualsEntry => l10n.sizeErrStopEqual,
                  SizingIssue.targetWrongSide => l10n.sizeErrTarget,
                  SizingIssue.riskTooHigh => l10n.sizeErrRisk,
                },
                style: text.bodyMedium!.copyWith(color: c.fg),
              ),
            ),
          ],
        ),
      final TradeSize size => _SizeDetails(size: size, instrument: instrument, limitPct: limitPct),
    };

    return Semantics(
      container: true,
      child: AppCard(
        color: c.inset,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(child: Text(l10n.sizePosition, style: text.titleSmall)),
                const SourceTag(SourceKind.user),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            body,
          ],
        ),
      ),
    );
  }
}

class _SizeDetails extends StatelessWidget {
  const _SizeDetails({required this.size, required this.instrument, required this.limitPct});

  final TradeSize size;
  final Instrument instrument;
  final double limitPct;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;
    final gold = instrument.base == 'XAU';
    final units = Formatters.grouped(size.units, decimals: gold ? 2 : 0);
    String money(double v) => Formatters.money(v, RiskLimits.currency);

    final (IconData icon, String status, Color tone) = switch (size.limitStatus) {
      LimitStatus.within => (Icons.check_circle_outline_rounded, l10n.limitWithin, c.fg2),
      LimitStatus.near => (Icons.warning_amber_rounded, l10n.limitNear, c.warning),
      LimitStatus.breach => (Icons.report_outlined, l10n.limitBreach, c.danger),
    };

    Widget row(String label, String value) => Padding(
          padding: const EdgeInsets.symmetric(vertical: AppSpacing.xxs),
          child: Wrap(
            alignment: WrapAlignment.spaceBetween,
            spacing: AppSpacing.sm,
            children: [
              Text(label, style: text.bodyMedium),
              Text(value, style: context.type.numSmall.copyWith(color: c.fg), textDirection: TextDirection.ltr),
            ],
          ),
        );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Semantics(
          liveRegion: true,
          child: Text(
            gold ? l10n.sizeOunces(units) : l10n.sizeUnits(units, instrument.base),
            style: context.type.numLarge,
            textDirection: TextDirection.ltr,
            textAlign: Directionality.of(context) == TextDirection.rtl ? TextAlign.right : TextAlign.left,
          ),
        ),
        const SizedBox(height: AppSpacing.sm),
        row(l10n.sizeMoneyAtRisk, '${money(size.moneyAtRisk)} · ${Formatters.plainPercent(size.riskPct)}'),
        row(
          l10n.sizeStopDistance,
          '${instrument.format(size.stopDistance)} · ${l10n.sizePips(Formatters.grouped(size.pips, decimals: 1))}',
        ),
        if (size.potentialReward != null)
          row(
            l10n.sizeReward,
            '${money(size.potentialReward!)} · 1 : ${size.riskReward!.toStringAsFixed(1)}',
          ),
        const SizedBox(height: AppSpacing.sm),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, size: AppSizes.iconMd, color: tone),
            const SizedBox(width: AppSpacing.xs),
            Expanded(
              child: Text(
                '$status. ${l10n.limitDetail(Formatters.plainPercent(size.riskPct), Formatters.plainPercent(limitPct))}',
                style: text.bodyMedium!.copyWith(color: c.fg),
              ),
            ),
          ],
        ),
      ],
    );
  }
}
