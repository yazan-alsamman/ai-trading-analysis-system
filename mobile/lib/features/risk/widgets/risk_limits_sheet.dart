import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/source_tag.dart';
import '../../../l10n/app_localizations.dart';
import '../models/risk_limits.dart';

/// "Capital & risk limits": bottom sheet بتعدّل رأس المال والحدود.
/// بترجع القيم الجديدة (الحفظ عند يلي فتحها) أو null لو انسكّرت.
Future<RiskLimits?> showRiskLimitsSheet(BuildContext context, {required RiskLimits current}) {
  AppHaptics.light();
  return showModalBottomSheet<RiskLimits>(
    useRootNavigator: true,
    context: context,
    sheetAnimationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
    isScrollControlled: true,
    useSafeArea: true,
    showDragHandle: true,
    builder: (_) => RiskLimitsSheet(current: current),
  );
}

class RiskLimitsSheet extends StatefulWidget {
  const RiskLimitsSheet({super.key, required this.current});

  final RiskLimits current;

  @override
  State<RiskLimitsSheet> createState() => _RiskLimitsSheetState();
}

class _RiskLimitsSheetState extends State<RiskLimitsSheet> {
  late final TextEditingController _capital = TextEditingController(
    text: widget.current.capital == null ? '' : Formatters.trimZeros(widget.current.capital!.toStringAsFixed(2)),
  );
  late final TextEditingController _perTrade =
      TextEditingController(text: Formatters.trimZeros(widget.current.maxRiskPerTradePct.toStringAsFixed(2)));
  late final TextEditingController _daily =
      TextEditingController(text: Formatters.trimZeros(widget.current.dailyLossLimitPct.toStringAsFixed(2)));
  bool _showErrors = false;

  static final _numberOnly = [FilteringTextInputFormatter.allow(RegExp(r'[0-9.٫]'))];

  @override
  void dispose() {
    _capital.dispose();
    _perTrade.dispose();
    _daily.dispose();
    super.dispose();
  }

  /// القيم المكتوبة → حدود (نص مش رقم بيصير -1 حتى يطلع خطأ)
  RiskLimits get _draft => RiskLimits(
        capital: _capital.text.trim().isEmpty ? null : (parseUserNumber(_capital.text) ?? -1),
        maxRiskPerTradePct: parseUserNumber(_perTrade.text) ?? -1,
        dailyLossLimitPct: parseUserNumber(_daily.text) ?? -1,
      );

  void _save() {
    final draft = _draft;
    if (validateRiskLimits(draft).isNotEmpty) {
      setState(() => _showErrors = true);
      return;
    }
    Navigator.of(context).pop(draft);
  }

  String? _error(AppLocalizations l10n, RiskLimitsField field) {
    if (!_showErrors) return null;
    return switch (validateRiskLimits(_draft)[field]) {
      RiskLimitsError.capitalInvalid => l10n.riskErrCapital,
      RiskLimitsError.perTradeOutOfRange => l10n.riskErrRange(
          Formatters.plainPercent(RiskLimits.minPerTradePct),
          Formatters.plainPercent(RiskLimits.maxPerTradePct),
        ),
      RiskLimitsError.dailyOutOfRange => l10n.riskErrRange(
          Formatters.plainPercent(RiskLimits.minDailyPct),
          Formatters.plainPercent(RiskLimits.maxDailyPct),
        ),
      RiskLimitsError.dailyBelowPerTrade => l10n.riskErrDailyBelow,
      null => null,
    };
  }

  @override
  Widget build(BuildContext context) {
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;

    Widget field(TextEditingController controller, RiskLimitsField which, String label,
            {String? prefix, String? suffix, String? helper, TextInputAction action = TextInputAction.next}) =>
        TextField(
          controller: controller,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          inputFormatters: _numberOnly,
          textInputAction: action,
          style: context.type.num,
          decoration: InputDecoration(
            labelText: label,
            prefixText: prefix,
            suffixText: suffix,
            helperText: helper,
            helperMaxLines: 3,
            errorMaxLines: 3,
            errorText: _error(l10n, which),
          ),
          onChanged: (_) {
            if (_showErrors) setState(() {});
          },
          onSubmitted: action == TextInputAction.done ? (_) => _save() : null,
        );

    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(AppSpacing.lg, 0, AppSpacing.lg, AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                Expanded(
                  child: Semantics(header: true, child: Text(l10n.riskLimits, style: text.titleLarge)),
                ),
                const SourceTag(SourceKind.user),
              ],
            ),
            const SizedBox(height: AppSpacing.xxs),
            Text(l10n.riskLimitsIntro, style: text.bodyMedium),
            const SizedBox(height: AppSpacing.lg),
            field(_capital, RiskLimitsField.capital, l10n.riskCapitalLabel,
                prefix: '${RiskLimits.currency} ', helper: l10n.riskCapitalHelper),
            const SizedBox(height: AppSpacing.md),
            field(_perTrade, RiskLimitsField.perTrade, l10n.riskPerTradeLabel, suffix: '%'),
            const SizedBox(height: AppSpacing.md),
            field(_daily, RiskLimitsField.daily, l10n.riskDailyLabel,
                suffix: '%', action: TextInputAction.done),
            const SizedBox(height: AppSpacing.xl),
            AppButton(label: l10n.save, expand: true, onPressed: _save),
          ],
        ),
      ),
    );
  }
}
