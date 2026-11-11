import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/network_status.dart';
import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../l10n/app_localizations.dart';
import '../data/chart_image_picker.dart';
import '../models/chart_analysis.dart';
import '../view_models/assistant_view_model.dart';
import '../view_models/chart_quota_view_model.dart';

/// "Daily limit reached. Resets at 00:00." (وقت الجهاز)
String chartLimitText(AppLocalizations l10n, ChartAnalysisQuota quota) =>
    l10n.chartLimitReached(Formatters.clock(quota.resetAt.toLocal()));

/// هل زر الإرفاق شغّال؟ (مش بدون اتصال، مش عم يحلّل، والحد ما خلص)
bool canAttachChart(WidgetRef ref) {
  final offline = ref.watch(networkStatusProvider) == NetworkStatus.offline;
  final analyzing = ref.watch(assistantViewModelProvider.select((s) => s.analyzing));
  final reached = ref.watch(chartQuotaNowProvider)?.reached ?? false;
  return !offline && !analyzing && !reached;
}

/// اختيار صورة الشارت: sheet (كاميرا / معرض + العدّاد)، وبعدها المعاينة. صورة
/// مرفوضة = snackbar بالسبب.
Future<void> pickChartImage(BuildContext context, WidgetRef ref) async {
  final l10n = AppLocalizations.of(context)!;
  AppHaptics.light();
  final quota = ref.read(chartQuotaNowProvider);
  final source = await showModalBottomSheet<ChartImageSource>(
    useRootNavigator: true,
    context: context,
    isScrollControlled: true,
    sheetAnimationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
    showDragHandle: true,
    builder: (context) => SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.only(bottom: AppSpacing.md),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: EdgeInsets.symmetric(horizontal: AppSpacing.gutter(context)),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Semantics(header: true, child: Text(l10n.asstAttachTitle, style: context.textTheme.titleLarge)),
                  const SizedBox(height: AppSpacing.xxs),
                  Text(l10n.asstAttachBody, style: context.textTheme.bodyMedium),
                  if (quota != null) ...[
                    const SizedBox(height: AppSpacing.xxs),
                    Text(
                      l10n.chartQuotaCount('${quota.used}', '${quota.limit}'),
                      style: context.textTheme.bodySmall,
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            ListTile(
              contentPadding: EdgeInsets.symmetric(horizontal: AppSpacing.gutter(context)),
              minTileHeight: 56,
              leading: const Icon(Icons.photo_library_outlined),
              title: Text(l10n.chooseFromGallery),
              onTap: () => Navigator.of(context).pop(ChartImageSource.gallery),
            ),
            ListTile(
              contentPadding: EdgeInsets.symmetric(horizontal: AppSpacing.gutter(context)),
              minTileHeight: 56,
              leading: const Icon(Icons.photo_camera_outlined),
              title: Text(l10n.takeAPhoto),
              onTap: () => Navigator.of(context).pop(ChartImageSource.camera),
            ),
          ],
        ),
      ),
    ),
  );
  if (source == null || !context.mounted) return;
  final problem = await ref.read(assistantViewModelProvider.notifier).pickChart(source);
  if (problem == null || !context.mounted) return;
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(
      content: Text(switch (problem) {
        ChartImageProblem.type => l10n.asstImageType,
        ChartImageProblem.size => l10n.asstImageSize,
        ChartImageProblem.unreadable => l10n.asstImageUnreadable,
      }),
    ));
}

/// تحليل صورة الشارت: بدون صورة = الزر الرئيسي الكبير ("Analyze a chart image")
/// مع العدّاد ([showAction] بحالة المحادثة الفاضية بس)؛ مع صورة = المعاينة.
class ChartAnalyzePanel extends ConsumerWidget {
  const ChartAnalyzePanel({super.key, this.showAction = true});

  final bool showAction;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final hasDraft = ref.watch(assistantViewModelProvider.select((s) => s.draft != null));
    if (hasDraft) return const _DraftCard();
    if (!showAction) return const SizedBox.shrink();
    return const _ActionCard();
  }
}

class _PanelFrame extends StatelessWidget {
  const _PanelFrame({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Semantics(
      container: true,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: c.card,
          borderRadius: AppRadii.heroCard,
          border: Border.all(color: c.hairline),
        ),
        child: Padding(padding: const EdgeInsets.all(AppSpacing.md), child: child),
      ),
    );
  }
}

/// الزر الرئيسي + سطر العدّاد (أو الحد / بدون اتصال)
class _ActionCard extends ConsumerWidget {
  const _ActionCard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final quota = ref.watch(chartQuotaNowProvider);
    final enabled = canAttachChart(ref);

    return _PanelFrame(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ExcludeSemantics(
                child: Container(
                  width: AppSizes.minTap,
                  height: AppSizes.minTap,
                  decoration: BoxDecoration(color: c.selected, shape: BoxShape.circle),
                  child: Icon(Icons.candlestick_chart_outlined, color: c.fg, size: AppSizes.iconLg),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(child: Text(l10n.chartActionBody, style: context.textTheme.bodyMedium)),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          AppButton(
            label: l10n.chartActionTitle,
            icon: Icons.add_photo_alternate_outlined,
            expand: true,
            onPressed: enabled ? () => pickChartImage(context, ref) : null,
          ),
          const SizedBox(height: AppSpacing.sm),
          _QuotaLine(quota: quota),
        ],
      ),
    );
  }
}

/// سطر تحت الزر: العدّاد، أو الحد خلص (مع إن المحادثة شغّالة). الحد بينعلن
/// للقارئ الصوتي (live region). بدون اتصال: السطر فوق حقل الكتابة بيشرح (ما منكرّره).
class _QuotaLine extends StatelessWidget {
  const _QuotaLine({required this.quota, this.ignoreLimit = false});

  final ChartAnalysisQuota? quota;

  /// الصورة محفوظة: الحد ما بيأثر عليها
  final bool ignoreLimit;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final text = context.textTheme;
    final quota = this.quota;
    if (quota == null) return const SizedBox.shrink();
    if (quota.reached && !ignoreLimit) {
      return Semantics(
        liveRegion: true,
        container: true,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ExcludeSemantics(child: Icon(Icons.hourglass_bottom_rounded, size: AppSizes.iconSm, color: c.warning)),
            const SizedBox(width: AppSpacing.xs),
            Expanded(
              child: Text(
                '${chartLimitText(l10n, quota)} ${l10n.chartLimitChat}',
                style: text.bodySmall!.copyWith(color: c.fg),
              ),
            ),
          ],
        ),
      );
    }
    return Text(
      l10n.chartQuotaCount('${quota.used}', '${quota.limit}'),
      style: text.bodySmall,
      textAlign: TextAlign.center,
    );
  }
}

/// المعاينة: الصورة، النوع والحجم، Remove، وAnalyze. أثناء التحليل: تقدّم +
/// Cancel (بينعلن). فشل = Try again. بدون اتصال = السبب، وما بينبعت شي.
class _DraftCard extends ConsumerWidget {
  const _DraftCard();

  static const double previewHeight = 160;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final text = context.textTheme;
    final draft = ref.watch(assistantViewModelProvider.select((s) => s.draft));
    final status = ref.watch(assistantViewModelProvider.select((s) => s.chartStatus));
    final quota = ref.watch(chartQuotaNowProvider);
    final offline = ref.watch(networkStatusProvider) == NetworkStatus.offline;
    if (draft == null) return const SizedBox.shrink();
    final vm = ref.read(assistantViewModelProvider.notifier);
    final analyzing = status == ChartStatus.analyzing;
    final limited = (quota?.reached ?? false) && !draft.cached;
    final canAnalyze = !analyzing && !offline && !limited;
    // 0.1 MB أقل شي (ملف صغير ما بينعرض "0 MB")
    final mb = draft.sizeBytes / (1024 * 1024);
    final sizeMb = Formatters.trimZeros((mb < 0.1 ? 0.1 : mb).toStringAsFixed(1));

    final placeholder = Container(
      height: previewHeight,
      color: c.inset,
      alignment: Alignment.center,
      child: Icon(Icons.image_outlined, color: c.fg3, size: AppSizes.iconLg),
    );

    return _PanelFrame(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Semantics(
            image: true,
            label: l10n.chartPreviewLabel,
            child: ClipRRect(
              borderRadius: AppRadii.card,
              child: Image.memory(
                draft.bytes,
                height: previewHeight,
                width: double.infinity,
                // فكّ الصورة على حجم العرض بس
                cacheHeight: (previewHeight * MediaQuery.devicePixelRatioOf(context)).round(),
                fit: BoxFit.cover,
                gaplessPlayback: true,
                errorBuilder: (_, __, ___) => placeholder,
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.xs),
          Row(
            children: [
              Expanded(
                child: Text(l10n.chartFileSize(draft.typeLabel, sizeMb), style: text.bodySmall),
              ),
              AppButton.ghost(
                label: l10n.chartRemove,
                icon: Icons.close_rounded,
                onPressed: () {
                  AppHaptics.selection();
                  vm.removeChart();
                },
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          if (analyzing) ...[
            Semantics(
              container: true,
              liveRegion: true,
              label: l10n.chartAnalyzing,
              excludeSemantics: true,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // تقليل الحركة: نص بس، بدون شريط بيتحرّك
                  if (!context.reduceMotion) ...[
                    ClipRRect(
                      borderRadius: AppRadii.card,
                      child: LinearProgressIndicator(color: c.forecast, backgroundColor: c.forecastSoft),
                    ),
                    const SizedBox(height: AppSpacing.xs),
                  ],
                  Text(l10n.chartAnalyzing, style: text.bodyMedium),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            AppButton.secondary(
              label: l10n.cancel,
              icon: Icons.stop_circle_outlined,
              expand: true,
              onPressed: () {
                AppHaptics.selection();
                vm.cancelChart();
              },
            ),
          ] else ...[
            if (status == ChartStatus.failed) ...[
              Semantics(
                liveRegion: true,
                container: true,
                child: Row(
                  children: [
                    ExcludeSemantics(child: Icon(Icons.error_outline_rounded, size: AppSizes.iconMd, color: c.danger)),
                    const SizedBox(width: AppSpacing.xs),
                    Expanded(child: Text(l10n.chartFailed, style: text.bodyMedium)),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
            ],
            AppButton(
              label: status == ChartStatus.failed ? l10n.tryAgain : l10n.chartAnalyze,
              icon: status == ChartStatus.failed ? Icons.refresh_rounded : Icons.query_stats_rounded,
              expand: true,
              onPressed: canAnalyze ? vm.analyzeChart : null,
            ),
          ],
          const SizedBox(height: AppSpacing.sm),
          // ضغط Analyze بدون اتصال: السبب، وما انبعت شي
          if (offline && status == ChartStatus.offline)
            Semantics(
              liveRegion: true,
              container: true,
              child: Text(l10n.chartOffline, style: text.bodySmall!.copyWith(color: c.warning)),
            )
          else
            _QuotaLine(quota: quota, ignoreLimit: draft.cached),
        ],
      ),
    );
  }
}
