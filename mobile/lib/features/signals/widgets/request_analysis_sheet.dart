import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/router/app_navigator.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/not_advice_notice.dart';
import '../../../l10n/app_localizations.dart';
import '../../markets/models/market_models.dart';
import '../data/signal_profile_repository.dart';
import '../models/analysis_method.dart';
import '../models/signal_rationale.dart';
import '../view_models/request_analysis_view_model.dart';
import 'method_picker.dart';

/// إشارة مكتشفة رجعت من الـ sheet: بتنفتح بشاشة التفاصيل
typedef RequestedSignal = ({String id, String symbol});

/// "Request analysis": sheet وحدة مشتركة (على الـ navigator الجذر).
///
/// - من شاشة الأداة: [symbol] محدّدة (وإطار القراءة المعروضة لو في)؛ من رأس
///   تبويب Signals: الأداة بتنختار جوّا الـ sheet.
/// - الطريقة = المحفوظة بالاستراتيجية، و"Change for this request" بيغيّرها
///   لهالطلب بس (ما بتنحفظ).
/// - نتيجة مكتشفة → الـ sheet بتتسكّر وبتنفتح التفاصيل الموجودة
///   (`context.pushSignalDetail`، نفس حماية الضغطة المزدوجة والـ Hero)؛
///   محايدة → "No clear setup right now" مع السبب جوّا الـ sheet (بدون تنقّل).
/// - إغلاق الـ sheet بيلغي الطلب (الـ ViewModel autoDispose بيلغي الـ token).
/// - ضغطتين ورا بعض على الزر يلي فتحها = sheet وحدة.
Future<void> showRequestAnalysisSheet(BuildContext context, {String? symbol, Timeframe? timeframe}) async {
  if (!context.isTopmostRoute) return;
  AppHaptics.light();
  final result = await showModalBottomSheet<RequestedSignal>(
    useRootNavigator: true,
    context: context,
    sheetAnimationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
    isScrollControlled: true,
    useSafeArea: true,
    showDragHandle: true,
    builder: (_) => RequestAnalysisSheet(symbol: symbol, timeframe: timeframe),
  );
  if (result == null || !context.mounted) return;
  await context.pushSignalDetail(result.id, symbol: result.symbol);
}

/// نص سبب "ما في إعداد واضح" حسب الطريقة (نفسه بالـ sheet وبالتفاصيل)
String noSetupReasonText(AppLocalizations l10n, NoSetupReason reason) => switch (reason.methodId) {
      AnalysisMethod.rsiReversalId =>
        l10n.reasonNoSetupRsi((reason.indicator ?? 50).toStringAsFixed(0), reason.timeframe.label),
      // MA Crossover (والافتراضي)
      _ => l10n.reasonNoSetupMa(reason.timeframe.label),
    };

class RequestAnalysisSheet extends ConsumerStatefulWidget {
  const RequestAnalysisSheet({super.key, this.symbol, this.timeframe});

  /// الأداة المحدّدة من الأول (شاشة الأداة)، null = بتنختار هون
  final String? symbol;
  final Timeframe? timeframe;

  @override
  ConsumerState<RequestAnalysisSheet> createState() => _RequestAnalysisSheetState();
}

class _RequestAnalysisSheetState extends ConsumerState<RequestAnalysisSheet> {
  late String? _symbol = kProductSymbols.contains(widget.symbol) ? widget.symbol : null;
  late Timeframe _timeframe = Timeframe.modelTimeframes.contains(widget.timeframe) ? widget.timeframe! : Timeframe.h1;

  /// طريقة لهالطلب بس (null = المحفوظة)
  String? _override;

  /// قسم "Change for this request" مفتوح
  bool _changing = false;

  /// أي تعديل بعد نتيجة أو فشل بيرجّع idle (ما في نتيجة قديمة على اختيار جديد)
  void _edit(VoidCallback change) {
    AppHaptics.selection();
    setState(change);
    final vm = ref.read(requestAnalysisViewModelProvider.notifier);
    if (ref.read(requestAnalysisViewModelProvider) is! RequestIdle) vm.reset();
  }

  void _analyze() {
    final symbol = _symbol;
    if (symbol == null) return;
    // الـ ViewModel بيتجاهل طلب تاني وهو شغّال (ضغطة مزدوجة = طلب واحد)
    ref
        .read(requestAnalysisViewModelProvider.notifier)
        .request(symbol: symbol, timeframe: _timeframe, methodOverride: _override);
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;
    final state = ref.watch(requestAnalysisViewModelProvider);
    final busy = state.isBusy;
    final savedId = ref.watch(signalProfileProvider.select((p) => p.methodId));
    final methodId = _override ?? savedId;
    final methodName = watchMethodName(ref, context, methodId) ?? '';

    // مكتشفة → سكّر وافتح التفاصيل (مرة وحدة: الحالة ما بترجع done لحالها)
    ref.listen(requestAnalysisViewModelProvider, (_, next) {
      if (next is RequestDone && !next.isNoClearSetup) {
        Navigator.of(context).pop<RequestedSignal>((id: next.detail.signal.id, symbol: next.detail.symbol));
      }
    });

    Widget label(String value) => Padding(
          padding: const EdgeInsets.only(top: AppSpacing.lg, bottom: AppSpacing.xs),
          child: Semantics(header: true, child: Text(value, style: text.titleSmall)),
        );

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(AppSpacing.lg, 0, AppSpacing.lg, AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Expanded(
                child: Semantics(header: true, child: Text(l10n.requestAnalysisTitle, style: text.titleLarge)),
              ),
              // الإغلاق (وكمان السحب لتحت والرجوع) بيلغي الطلب الشغّال
              CloseButton(color: c.fg2),
            ],
          ),
          const SizedBox(height: AppSpacing.xxs),
          Text(l10n.requestAnalysisIntro, style: text.bodyMedium),
          label(l10n.requestInstrument),
          Wrap(
            spacing: AppSpacing.xs,
            runSpacing: AppSpacing.xs,
            children: [
              for (final symbol in kProductSymbols)
                MergeSemantics(
                  child: Semantics(
                    label: l10n.instrumentName(symbol),
                    child: ChoiceChip(
                      label: Text(symbol, style: context.type.numSmall.copyWith(color: c.fg)),
                      selected: _symbol == symbol,
                      showCheckmark: false,
                      materialTapTargetSize: MaterialTapTargetSize.padded,
                      onSelected: busy ? null : (_) => _edit(() => _symbol = symbol),
                    ),
                  ),
                ),
            ],
          ),
          if (_symbol == null) ...[
            const SizedBox(height: AppSpacing.xs),
            Text(l10n.requestPickInstrument, style: text.bodySmall),
          ],
          label(l10n.requestTimeframe),
          Wrap(
            spacing: AppSpacing.xs,
            runSpacing: AppSpacing.xs,
            children: [
              for (final tf in Timeframe.modelTimeframes)
                ChoiceChip(
                  label: Text(tf.label, style: context.type.numSmall.copyWith(color: c.fg)),
                  selected: _timeframe == tf,
                  showCheckmark: false,
                  materialTapTargetSize: MaterialTapTargetSize.padded,
                  onSelected: busy ? null : (_) => _edit(() => _timeframe = tf),
                ),
            ],
          ),
          label(l10n.strategyMethodTitle),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ExcludeSemantics(
                child: Icon(
                  _override == null ? Icons.tune_rounded : Icons.swap_horiz_rounded,
                  size: AppSizes.iconMd,
                  color: c.accent,
                ),
              ),
              const SizedBox(width: AppSpacing.xs),
              Expanded(
                child: Semantics(
                  liveRegion: true,
                  child: Text(
                    _override == null ? l10n.requestMethodSaved(methodName) : l10n.requestMethodOverride(methodName),
                    style: text.bodyMedium!.copyWith(color: c.fg),
                  ),
                ),
              ),
            ],
          ),
          if (!_changing)
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: AppButton.ghost(
                label: l10n.requestChangeMethod,
                icon: Icons.swap_horiz_rounded,
                compact: true,
                onPressed: busy ? null : () => setState(() => _changing = true),
              ),
            )
          else ...[
            const SizedBox(height: AppSpacing.xs),
            Text(l10n.requestOverrideNote, style: text.bodySmall),
            const SizedBox(height: AppSpacing.xs),
            MethodPicker(
              selectedId: methodId,
              onSelected: busy ? null : (id) => _edit(() => _override = id == savedId ? null : id),
            ),
            if (_override != null)
              Align(
                alignment: AlignmentDirectional.centerStart,
                child: AppButton.ghost(
                  label: l10n.requestUseSaved,
                  icon: Icons.undo_rounded,
                  compact: true,
                  onPressed: busy ? null : () => _edit(() => _override = null),
                ),
              ),
          ],
          const SizedBox(height: AppSpacing.lg),
          _StatusArea(state: state),
          AppButton(
            label: state is RequestFailed ? l10n.tryAgain : l10n.requestAnalyze,
            icon: state is RequestFailed ? Icons.refresh_rounded : Icons.manage_search_rounded,
            expand: true,
            // التقدّم بكرت الخطوة فوق (مؤشّر واحد، ثابت مع تقليل الحركة)
            onPressed: _symbol == null || busy ? null : _analyze,
          ),
          if (busy) ...[
            const SizedBox(height: AppSpacing.xs),
            AppButton.ghost(
              label: l10n.cancel,
              expand: true,
              onPressed: () => ref.read(requestAnalysisViewModelProvider.notifier).cancel(),
            ),
          ],
          const SizedBox(height: AppSpacing.md),
          const NotAdviceNotice(),
        ],
      ),
    );
  }
}

/// تقدّم الطلب (خطوة قصيرة) / الفشل (ليش) / النتيجة المحايدة - فوق زر Analyze.
/// كلها live region: القارئ الصوتي بيسمع كل خطوة والنتيجة.
class _StatusArea extends ConsumerWidget {
  const _StatusArea({required this.state});

  final RequestAnalysisState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final text = context.textTheme;

    Widget spaced(Widget child) => Padding(padding: const EdgeInsets.only(bottom: AppSpacing.md), child: child);

    switch (state) {
      case RequestPending() || RequestAnalyzing():
        final analyzing = state is RequestAnalyzing;
        final request = switch (state) {
          RequestAnalyzing(:final request) || RequestPending(:final request) => request,
          _ => null,
        }!;
        final methodName = watchMethodName(ref, context, request.methodId) ?? '';
        final step = analyzing
            ? l10n.requestStepAnalyzing(request.symbol, request.timeframe.label, methodName)
            : l10n.requestStepPending;
        return spaced(Semantics(
          liveRegion: true,
          container: true,
          label: step,
          excludeSemantics: true,
          child: AppCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(step, style: text.bodyMedium!.copyWith(color: c.fg)),
                const SizedBox(height: AppSpacing.sm),
                // مع تقليل الحركة: شريط ثابت بخطوتين بدل المتحرّك
                LinearProgressIndicator(
                  value: context.reduceMotion ? (analyzing ? 0.66 : 0.33) : null,
                  color: c.accent,
                  backgroundColor: c.hairline,
                  borderRadius: AppRadii.badge,
                ),
              ],
            ),
          ),
        ));
      case RequestFailed(:final reason):
        final message = switch (reason) {
          RequestAnalysisFailure.offline => l10n.requestOffline,
          RequestAnalysisFailure.invalid => l10n.requestInvalid,
          RequestAnalysisFailure.error => l10n.requestFailed,
        };
        return spaced(Semantics(
          liveRegion: true,
          container: true,
          child: AppCard(
            color: c.warningSoft,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                ExcludeSemantics(
                  child: Icon(
                    reason == RequestAnalysisFailure.offline ? Icons.cloud_off_outlined : Icons.error_outline_rounded,
                    color: c.warning,
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(child: Text(message, style: text.bodyMedium!.copyWith(color: c.fg))),
              ],
            ),
          ),
        ));
      case RequestDone(:final detail) when detail.isNoClearSetup:
        final reason = detail.rationale.whereType<NoSetupReason>().firstOrNull;
        final methodName = watchMethodName(ref, context, detail.methodId) ?? '';
        return spaced(Semantics(
          liveRegion: true,
          container: true,
          child: AppCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    ExcludeSemantics(child: Icon(Icons.remove_circle_outline_rounded, color: c.fg2)),
                    const SizedBox(width: AppSpacing.xs),
                    Expanded(
                      child: Semantics(header: true, child: Text(l10n.analysisNoClearSetup, style: text.titleSmall)),
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  '${detail.symbol} · ${detail.signal.timeframe.label} · ${l10n.strategyUsed(methodName)}',
                  style: text.labelMedium!.copyWith(color: c.fg2),
                ),
                if (reason != null) ...[
                  const SizedBox(height: AppSpacing.xs),
                  Text(noSetupReasonText(l10n, reason), style: text.bodyMedium),
                ],
                const SizedBox(height: AppSpacing.xs),
                Text(l10n.requestNoSetupBody, style: text.bodySmall),
              ],
            ),
          ),
        ));
      case RequestIdle() || RequestDone():
        return const SizedBox.shrink();
    }
  }
}
