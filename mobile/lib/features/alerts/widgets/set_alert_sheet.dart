import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../l10n/app_localizations.dart';
import '../../markets/data/market_providers.dart';
import '../../markets/models/market_models.dart';
import '../data/alerts_repository.dart';
import '../models/price_alert.dart';
import '../view_models/alerts_view_model.dart';

/// "Set alert": bottom sheet لإنشاء تنبيه سعر. بيرجع التنبيه المنشأ (أو null)
Future<PriceAlert?> showSetAlertSheet(BuildContext context, {required Instrument instrument}) {
  AppHaptics.light();
  return showModalBottomSheet<PriceAlert>(
    useRootNavigator: true,
    context: context,
    sheetAnimationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
    isScrollControlled: true,
    useSafeArea: true,
    showDragHandle: true,
    builder: (_) => SetAlertSheet(instrument: instrument),
  );
}

/// الـ sheet + snackbar تأكيد بعد الإنشاء (شاشة الأداة وتفاصيل الإشارة)
Future<void> setAlertAndConfirm(BuildContext context, {required Instrument instrument}) async {
  final alert = await showSetAlertSheet(context, instrument: instrument);
  if (alert == null || !context.mounted) return;
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(
      content: Text(AppLocalizations.of(context)!.alertCreated(instrument.symbol, instrument.format(alert.value))),
    ));
}

class SetAlertSheet extends ConsumerStatefulWidget {
  const SetAlertSheet({super.key, required this.instrument});

  final Instrument instrument;

  @override
  ConsumerState<SetAlertSheet> createState() => _SetAlertSheetState();
}

class _SetAlertSheetState extends ConsumerState<SetAlertSheet> {
  // مرة وحدة (الـ sheet بيعيد البناء مع كل نبضة سعر)
  static final _priceFormatters = [FilteringTextInputFormatter.allow(RegExp(r'[0-9.,]'))];

  static const List<double> _steps = [-1, -0.5, 0.5, 1];

  late final TextEditingController _price;
  final TextEditingController _note = TextEditingController();
  /// مدة اختيارية: بعدها التنبيه بينتهي وما بيشتغل أبدًا
  AlertExpiry _expiry = AlertExpiry.none;
  bool _submitting = false;
  bool _showErrors = false;
  bool _saveFailed = false;

  @override
  void initState() {
    super.initState();
    final current = ref.read(quoteProvider(widget.instrument.symbol))?.price;
    // نقطة بداية منطقية: +0.5% فوق السعر الحالي (المستخدم بيعدّل)
    _price = TextEditingController(
      text: current == null ? '' : widget.instrument.format(current * 1.005),
    );
  }

  @override
  void dispose() {
    _price.dispose();
    _note.dispose();
    super.dispose();
  }

  double? get _value => double.tryParse(_price.text.trim().replaceAll(',', '.'));

  void _step(double percent, double current) {
    AppHaptics.selection();
    setState(() {
      _price.text = widget.instrument.format(current * (1 + percent / 100));
      _saveFailed = false;
    });
  }

  Future<void> _submit(double current) async {
    final error = validateAlertValue(_price.text, current: current, precision: widget.instrument.precision);
    if (error != null) {
      setState(() => _showErrors = true);
      return;
    }
    if (_submitting) return;
    final value = double.parse(_value!.toStringAsFixed(widget.instrument.precision));
    setState(() {
      _submitting = true;
      _saveFailed = false;
    });
    try {
      final alert = await ref.read(alertsViewModelProvider.notifier).create(AlertDraft(
            symbol: widget.instrument.symbol,
            condition: AlertDraft.conditionFor(target: value, current: current),
            value: value,
            note: _note.text.trim().isEmpty ? null : _note.text.trim(),
            expiresAt: _expiry.from(ref.read(alertsClockProvider)()),
          ));
      if (!mounted || alert == null) return;
      Navigator.of(context).pop(alert);
    } catch (_) {
      if (mounted) setState(() => _saveFailed = true);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  String? _errorText(AppLocalizations l10n, double current) {
    if (!_showErrors) return null;
    return switch (validateAlertValue(_price.text, current: current, precision: widget.instrument.precision)) {
      AlertValueError.empty => l10n.alertErrorEmpty,
      AlertValueError.invalid => l10n.alertErrorInvalid,
      AlertValueError.notPositive => l10n.alertErrorPositive,
      AlertValueError.equalsCurrent => l10n.alertErrorCurrent,
      null => null,
    };
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;
    final instrument = widget.instrument;
    final current = ref.watch(quoteProvider(instrument.symbol))?.price;
    final value = _value;

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
              child: Text('${l10n.priceAlert} · ${instrument.symbol}', style: text.titleLarge),
            ),
            if (current != null) ...[
              const SizedBox(height: AppSpacing.xxs),
              Text(
                l10n.alertNow(instrument.format(current)),
                style: context.type.numSmall,
              ),
            ],
            const SizedBox(height: AppSpacing.lg),
            TextField(
              controller: _price,
              enabled: current != null && !_submitting,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: _priceFormatters,
              textInputAction: TextInputAction.done,
              style: context.type.num,
              decoration: InputDecoration(
                labelText: l10n.alertTargetLabel,
                errorText: current == null ? null : _errorText(l10n, current),
              ),
              onChanged: (_) => setState(() => _saveFailed = false),
              onSubmitted: current == null ? null : (_) => _submit(current),
            ),
            if (current != null) ...[
              const SizedBox(height: AppSpacing.sm),
              Wrap(
                spacing: AppSpacing.xs,
                runSpacing: AppSpacing.xs,
                children: [
                  for (final step in _steps)
                    ActionChip(
                      materialTapTargetSize: MaterialTapTargetSize.padded,
                      label: Text(
                        '${step > 0 ? '+' : '−'}${step.abs() % 1 == 0 ? step.abs().toInt() : step.abs()}%',
                        style: context.type.numSmall,
                        textDirection: TextDirection.ltr,
                      ),
                      onPressed: _submitting ? null : () => _step(step, current),
                    ),
                ],
              ),
              if (value != null && value > 0) ...[
                const SizedBox(height: AppSpacing.md),
                Row(
                  children: [
                    Icon(
                      value >= current ? Icons.trending_up_rounded : Icons.trending_down_rounded,
                      size: AppSizes.iconMd,
                      color: c.accent,
                    ),
                    const SizedBox(width: AppSpacing.xs),
                    Expanded(
                      child: Text(
                        value >= current
                            ? l10n.alertRisesTo(instrument.format(value))
                            : l10n.alertFallsTo(instrument.format(value)),
                        style: text.bodyMedium!.copyWith(color: c.fg),
                      ),
                    ),
                  ],
                ),
              ],
            ],
            const SizedBox(height: AppSpacing.md),
            Semantics(header: true, child: Text(l10n.alertExpiryLabel, style: text.titleSmall)),
            const SizedBox(height: AppSpacing.xs),
            Wrap(
              spacing: AppSpacing.xs,
              runSpacing: AppSpacing.xs,
              children: [
                for (final option in AlertExpiry.values)
                  ChoiceChip(
                    materialTapTargetSize: MaterialTapTargetSize.padded,
                    label: Text(option.label(l10n)),
                    selected: _expiry == option,
                    onSelected: _submitting
                        ? null
                        : (_) {
                            AppHaptics.selection();
                            setState(() => _expiry = option);
                          },
                  ),
              ],
            ),
            const SizedBox(height: AppSpacing.xxs),
            Text(l10n.alertExpiryHint, style: text.bodySmall),
            const SizedBox(height: AppSpacing.sm),
            TextField(
              controller: _note,
              enabled: !_submitting,
              maxLength: 200,
              textCapitalization: TextCapitalization.sentences,
              decoration: InputDecoration(labelText: l10n.alertNote),
            ),
            if (_saveFailed) ...[
              Semantics(
                liveRegion: true,
                child: Text(l10n.alertCreateFailed, style: text.bodyMedium!.copyWith(color: c.danger)),
              ),
              const SizedBox(height: AppSpacing.sm),
            ],
            const SizedBox(height: AppSpacing.xs),
            AppButton(
              label: l10n.alertCreate,
              icon: Icons.add_alert_outlined,
              loading: _submitting,
              expand: true,
              onPressed: current == null ? null : () => _submit(current),
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(l10n.alertDelivery, style: text.bodySmall, textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }
}
