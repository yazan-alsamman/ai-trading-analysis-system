import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/router/app_navigator.dart';
import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/direction_badge.dart';
import '../../../l10n/app_localizations.dart';
import '../../markets/models/market_models.dart';
import '../../risk/data/risk_limits_repository.dart';
import '../data/signal_profile_repository.dart';
import '../models/signal_profile.dart';
import 'method_picker.dart';

/// شو صار بالـ sheet (null = سكّرها المستخدم؛ الحفظ ما بيسكّرها)
sealed class StrategySheetResult {
  const StrategySheetResult();
}

/// "Remove strategy": [previous] لزر Undo
final class StrategyRemoved extends StrategySheetResult {
  const StrategyRemoved(this.previous);

  final SignalProfile previous;
}

/// "Strategy": bottom sheet الاستراتيجية = طريقة التحليل (أول قسم) + فلاتر الإشارات.
///
/// Save بيحفظ وبيضل بالـ sheet (الزر بيصير "Saved" + إعلان للقارئ الصوتي)،
/// والقائمة والبطاقة وراها بيتحدّثوا فورًا. الـ sheet بتتسكّر بس لما المستخدم
/// يسكّرها (زر الإغلاق، سحب لتحت، رجوع)، والتعديلات غير المحفوظة بتنرمى.
/// "Test on past data" بيفتح Backtest على الاستراتيجية المحفوظة (فوق الـ sheet،
/// والرجوع بيرجّع لها). "Remove strategy" (بس لما في استراتيجية خاصة محفوظة)
/// بيرجّع الافتراضي وبيسكّر الـ sheet - الـ Undo بالـ snackbar عند يلي فتحها.
Future<StrategySheetResult?> showStrategySheet(BuildContext context) {
  AppHaptics.light();
  return showModalBottomSheet<StrategySheetResult>(
    useRootNavigator: true,
    context: context,
    sheetAnimationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
    isScrollControlled: true,
    useSafeArea: true,
    showDragHandle: true,
    builder: (_) => const StrategySheet(),
  );
}

/// قيمة الاحتمال الأدنى كنص ("Any" أو "60%")
String minProbabilityText(AppLocalizations l10n, double value) =>
    value <= 0 ? l10n.strategyAny : '≥ ${Formatters.percent(value)}';

/// قيمة العائد : المخاطرة الأدنى كنص ("Any" أو "1 : 1.5")
String minRiskRewardText(AppLocalizations l10n, double value) =>
    value <= 0 ? l10n.strategyAny : '≥ 1 : ${Formatters.trimZeros(value.toStringAsFixed(1))}';

class StrategySheet extends ConsumerStatefulWidget {
  const StrategySheet({super.key});

  @override
  ConsumerState<StrategySheet> createState() => _StrategySheetState();
}

class _StrategySheetState extends ConsumerState<StrategySheet> {
  late SignalProfile _draft = ref.read(signalProfileProvider);
  bool _saving = false;

  /// انحفظت بهالجلسة وما في تعديل بعدها → الزر "Saved"
  bool _justSaved = false;

  void _update(SignalProfile next) {
    AppHaptics.selection();
    setState(() {
      _draft = next;
      _justSaved = false;
    });
  }

  Set<T> _toggle<T>(Set<T> set, T value, bool on) => on ? {...set, value} : ({...set}..remove(value));

  /// بيحفظ وبيضل هون (ما في pop ولا تنقّل). ضغطة مزدوجة = حفظة وحدة.
  Future<void> _save() async {
    final draft = _draft;
    if (!draft.isValid || _saving || draft == ref.read(signalProfileProvider)) return;
    setState(() => _saving = true);
    try {
      await ref.read(signalProfileProvider.notifier).save(draft);
      if (!mounted) return;
      setState(() => _justSaved = _draft == draft);
      final l10n = AppLocalizations.of(context)!;
      SemanticsService.sendAnnouncement(View.of(context), l10n.strategySaved, Directionality.of(context));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _remove() async {
    if (_saving) return;
    setState(() => _saving = true);
    try {
      final previous = await ref.read(signalProfileProvider.notifier).remove();
      if (mounted) Navigator.of(context).pop(StrategyRemoved(previous));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;
    final hasCapital = ref.watch(riskLimitsProvider.select((l) => l.hasCapital));
    final unsaved = _draft != ref.watch(signalProfileProvider);
    final hasCustom = ref.watch(hasCustomStrategyProvider);
    final draft = _draft;

    Widget label(String value) => Padding(
          padding: const EdgeInsets.only(top: AppSpacing.lg, bottom: AppSpacing.xs),
          child: Semantics(header: true, child: Text(value, style: text.titleSmall)),
        );

    Widget chip(
            {required String label, required bool selected, required ValueChanged<bool> onSelected, Widget? avatar}) =>
        FilterChip(
          label: Text(label, style: context.type.numSmall.copyWith(color: c.fg)),
          avatar: avatar,
          selected: selected,
          showCheckmark: avatar == null,
          materialTapTargetSize: MaterialTapTargetSize.padded,
          onSelected: _saving ? null : onSelected,
        );

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(AppSpacing.lg, 0, AppSpacing.lg, AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Expanded(child: Semantics(header: true, child: Text(l10n.strategyTitle, style: text.titleLarge))),
              // إغلاق صريح (كمان سحب لتحت والرجوع) - بيرمي التعديلات غير المحفوظة
              CloseButton(color: c.fg2),
            ],
          ),
          const SizedBox(height: AppSpacing.xxs),
          Text(l10n.strategyIntro, style: text.bodyMedium),
          // أول قسم: كيف بتنلاقى الإشارات (الفلاتر تحت بتختار أيّها بتشوف)
          label(l10n.strategyMethodTitle),
          MethodPicker(
            selectedId: draft.methodId,
            onSelected: _saving ? null : (id) => _update(_draft.copyWith(methodId: id)),
          ),
          label(l10n.strategyInstruments),
          Wrap(
            spacing: AppSpacing.xs,
            runSpacing: AppSpacing.xs,
            children: [
              for (final symbol in kProductSymbols)
                MergeSemantics(
                  child: Semantics(
                    label: l10n.instrumentName(symbol),
                    child: chip(
                      label: symbol,
                      selected: draft.symbols.contains(symbol),
                      onSelected: (on) => _update(_draft.copyWith(symbols: _toggle(_draft.symbols, symbol, on))),
                    ),
                  ),
                ),
            ],
          ),
          label(l10n.strategyTimeframes),
          Wrap(
            spacing: AppSpacing.xs,
            runSpacing: AppSpacing.xs,
            children: [
              for (final tf in Timeframe.modelTimeframes)
                chip(
                  label: tf.label,
                  selected: draft.timeframes.contains(tf),
                  onSelected: (on) => _update(_draft.copyWith(timeframes: _toggle(_draft.timeframes, tf, on))),
                ),
            ],
          ),
          label(l10n.strategyDirections),
          Wrap(
            spacing: AppSpacing.xs,
            runSpacing: AppSpacing.xs,
            children: [
              for (final (direction, icon, color) in [
                (SignalDirection.long, Icons.arrow_upward_rounded, c.up),
                (SignalDirection.short, Icons.arrow_downward_rounded, c.down),
              ])
                chip(
                  label: direction.label(l10n),
                  avatar: Icon(icon, size: AppSizes.iconSm, color: color),
                  selected: draft.directions.contains(direction),
                  onSelected: (on) => _update(_draft.copyWith(directions: _toggle(_draft.directions, direction, on))),
                ),
            ],
          ),
          label(l10n.strategyMinProbability),
          _SliderRow(
            value: draft.minProbability,
            max: SignalProfile.maxMinProbability,
            divisions: 18,
            valueText: minProbabilityText(l10n, draft.minProbability),
            onChanged: _saving ? null : (v) => _update(_draft.copyWith(minProbability: _round(v, 0.05))),
          ),
          label(l10n.strategyMinRiskReward),
          _SliderRow(
            value: draft.minRiskReward,
            max: SignalProfile.maxMinRiskReward,
            divisions: 6,
            valueText: minRiskRewardText(l10n, draft.minRiskReward),
            onChanged: _saving ? null : (v) => _update(_draft.copyWith(minRiskReward: _round(v, 0.5))),
          ),
          const SizedBox(height: AppSpacing.sm),
          MergeSemantics(
            child: SwitchListTile(
              contentPadding: EdgeInsets.zero,
              value: draft.requireRiskFit,
              onChanged: _saving ? null : (v) => _update(_draft.copyWith(requireRiskFit: v)),
              title: Text(l10n.strategyRiskFit, style: text.titleSmall),
              subtitle: Text(
                hasCapital ? l10n.strategyRiskFitHint : l10n.strategyRiskFitNoCapital,
                style: text.bodySmall,
              ),
            ),
          ),
          if (!draft.isValid) ...[
            const SizedBox(height: AppSpacing.xs),
            Semantics(
              liveRegion: true,
              child: Text(l10n.strategyPickOne, style: text.bodyMedium!.copyWith(color: c.danger)),
            ),
          ],
          const SizedBox(height: AppSpacing.lg),
          // في تعديل → "Save" شغّال؛ بعد الحفظ "Saved" (أيقونة + كلمة) ومطفي
          AppButton(
            label: _justSaved && !unsaved ? l10n.strategySavedState : l10n.save,
            icon: _justSaved && !unsaved ? Icons.check_rounded : null,
            expand: true,
            loading: _saving,
            onPressed: draft.isValid && unsaved ? _save : null,
          ),
          const SizedBox(height: AppSpacing.xs),
          AppButton.secondary(
            label: l10n.strategyTestPast,
            icon: Icons.history_rounded,
            expand: true,
            onPressed: _saving ? null : context.pushBacktest,
          ),
          if (unsaved) ...[
            const SizedBox(height: AppSpacing.xxs),
            Text(l10n.strategyTestUsesSaved, style: text.bodySmall, textAlign: TextAlign.center),
          ],
          const SizedBox(height: AppSpacing.xs),
          AppButton.ghost(
            label: l10n.strategyReset,
            expand: true,
            onPressed: _saving || draft == SignalProfile.defaults ? null : () => _update(SignalProfile.defaults),
          ),
          if (hasCustom) ...[
            const SizedBox(height: AppSpacing.xs),
            AppButton.ghost(
              label: l10n.strategyRemove,
              icon: Icons.delete_outline_rounded,
              expand: true,
              onPressed: _saving ? null : _remove,
            ),
          ],
        ],
      ),
    );
  }

  /// بيلغي أخطاء الفاصلة العائمة (0.6000000001)
  static double _round(double value, double step) => double.parse(((value / step).round() * step).toStringAsFixed(2));
}

/// Slider + قيمته المكتوبة جنبه (القارئ الصوتي بيسمع القيمة المكتوبة)
class _SliderRow extends StatelessWidget {
  const _SliderRow({
    required this.value,
    required this.max,
    required this.divisions,
    required this.valueText,
    required this.onChanged,
  });

  final double value;
  final double max;
  final int divisions;
  final String valueText;
  final ValueChanged<double>? onChanged;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Slider(
            value: value.clamp(0, max),
            max: max,
            divisions: divisions,
            semanticFormatterCallback: (_) => valueText,
            onChanged: onChanged,
          ),
        ),
        ConstrainedBox(
          constraints: const BoxConstraints(minWidth: 72),
          child: Text(
            valueText,
            style: context.type.numSmall.copyWith(color: context.colors.fg),
            textAlign: TextAlign.end,
            textDirection: TextDirection.ltr,
          ),
        ),
      ],
    );
  }
}
