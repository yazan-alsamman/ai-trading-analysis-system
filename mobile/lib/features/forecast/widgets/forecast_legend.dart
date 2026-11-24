import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/direction_badge.dart';
import '../../../core/widgets/not_advice_notice.dart';
import '../../../core/widgets/source_tag.dart';
import '../../../l10n/app_localizations.dart';
import '../../markets/models/market_models.dart';
import '../data/forecast_repository.dart';
import '../models/forecast_config.dart';
import '../models/forecast_path.dart';
import '../view_models/forecast_view_model.dart';

extension ForecastLikelihoodLabel on ForecastLikelihood {
  /// صفة الاحتمال ("high" / "مرتفع") - "high probability"، احتمال وليس وعد
  String label(AppLocalizations l10n) => switch (this) {
        ForecastLikelihood.high => l10n.forecastLikelihoodHigh,
        ForecastLikelihood.moderate => l10n.forecastLikelihoodModerate,
        ForecastLikelihood.low => l10n.forecastLikelihoodLow,
      };
}

/// "Model forecast · 72% · Long"
String forecastTitle(AppLocalizations l10n, ForecastPath path) =>
    l10n.forecastLabel(Formatters.percent(path.probability), path.direction.label(l10n));

/// وقت بالتوقّع: الساعة بس إذا بنفس يوم الشمعة يلي انبنى عليها، وإلا التاريخ
/// كمان ("Nov 12 14:00"): على 4h و 1D المسار والصلاحية بيقطعوا أيام.
String forecastTime(BuildContext context, ForecastPath path, DateTime time) {
  final local = time.toLocal();
  final anchor = path.anchorTime.toLocal();
  final clock = Formatters.clock(local);
  if (local.year == anchor.year && local.month == anchor.month && local.day == anchor.day) return clock;
  return '${MaterialLocalizations.of(context).formatShortMonthDay(local)} $clock';
}

/// الملخّص للقارئ الصوتي (ملخّص الرسم): الاتجاه، الاحتمال، المستوى المتوقّع
/// (على كل إطار، ومع الإطار يلي بيلحقه لما ما في خطة على إطار الرسم)
String forecastSummary(BuildContext context, ForecastPath path, Instrument instrument, {required double level}) {
  final l10n = AppLocalizations.of(context)!;
  final summary = l10n.forecastChartLabel(
    path.direction.label(l10n),
    path.likelihood.label(l10n),
    Formatters.percent(path.probability),
    instrument.format(level),
    forecastTime(context, path, path.endTime),
  );
  return path.follows ? '$summary ${forecastFollowsNote(l10n, path)}' : summary;
}

/// "Follows your strategy’s 1h signal, with a lower probability on 1m."
String forecastFollowsNote(AppLocalizations l10n, ForecastPath path) =>
    l10n.forecastFollows(path.basisTimeframe.label, path.timeframe.label);

/// شرح التوقّع تحت الرسم (بس لما المفتاح شغّال): العنوان مع عيّنة الخط المتقطّع
/// + كلمة الاتجاه، المستوى المتوقّع والوقت، الإطار يلي بيلحقه (لما ما في خطة
/// على إطار الرسم)، الصلاحية، "Simulated"، وتنبيه
/// "ليست نصيحة استثمارية". أو حالة: قديم، ما في توقّع، خطأ، بدون اتصال.
/// ما بيراقب النبضات (بس حالة التوقّع)، فما بينبني مع كل سعر.
class ForecastLegend extends ConsumerWidget {
  const ForecastLegend({super.key, required this.instrument});

  final Instrument instrument;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final symbol = instrument.symbol;
    final state = ref.watch(forecastViewModelProvider(symbol));
    final simulated = ref.watch(forecastRepositoryProvider).isSimulated;
    final l10n = AppLocalizations.of(context)!;
    final text = context.textTheme;
    final c = context.colors;
    void retry() => ref.read(forecastViewModelProvider(symbol).notifier).retry();

    final Widget? body = switch (state) {
      ForecastOff() => null,
      // المؤشّر بالمفتاح نفسه (مؤشّر واحد بس)
      ForecastLoading() => const SizedBox.shrink(),
      ForecastReady(:final path) => _Ready(path: path, instrument: instrument, simulated: simulated),
      ForecastOutdated(:final path) => Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Wrap(
              spacing: AppSpacing.xs,
              runSpacing: AppSpacing.xxs,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Text(forecastTitle(l10n, path), style: text.titleSmall!.copyWith(color: c.fg2)),
                _OutdatedBadge(label: l10n.forecastOutdated),
              ],
            ),
            const SizedBox(height: AppSpacing.xxs),
            Text(l10n.forecastOutdatedBody, style: text.bodySmall),
            const SizedBox(height: AppSpacing.xs),
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: AppButton.secondary(
                label: l10n.forecastRefresh,
                icon: Icons.refresh_rounded,
                compact: true,
                onPressed: retry,
              ),
            ),
          ],
        ),
      ForecastUnavailable(:final reason) => _Message(
          icon: Icons.remove_rounded,
          title: l10n.forecastNone,
          body: switch (reason) {
            ForecastUnavailableReason.noSetup => l10n.forecastNoneBody,
            ForecastUnavailableReason.timeframe => l10n.forecastTimeframeBody(
                [
                  for (final tf in Timeframe.values)
                    if (ref.watch(forecastSupportedTimeframesProvider).contains(tf)) tf.label,
                ].join(l10n.forecastListSeparator),
              ),
          },
        ),
      ForecastFailed() => _Message(
          icon: Icons.error_outline_rounded,
          title: l10n.forecastError,
          action: AppButton.secondary(
            label: l10n.tryAgain,
            icon: Icons.refresh_rounded,
            compact: true,
            onPressed: retry,
          ),
        ),
      ForecastOffline() => _Message(icon: Icons.cloud_off_rounded, title: l10n.forecastOffline),
    };
    if (body == null) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.sm),
      child: Semantics(
        container: true,
        liveRegion: state is! ForecastReady,
        child: Column(
          key: const ValueKey('forecast-legend'),
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            body,
            const SizedBox(height: AppSpacing.xs),
            const NotAdviceNotice(),
          ],
        ),
      ),
    );
  }
}

class _Ready extends StatelessWidget {
  const _Ready({required this.path, required this.instrument, required this.simulated});

  final ForecastPath path;
  final Instrument instrument;
  final bool simulated;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final text = context.textTheme;
    final c = context.colors;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            const _DashedSwatch(),
            const SizedBox(width: AppSpacing.xs),
            Expanded(
              child: Text(
                forecastTitle(l10n, path),
                style: text.titleSmall!.copyWith(color: c.forecast),
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.xxs),
        Text(
          l10n.forecastDetail(
            instrument.format(path.expectedLevel),
            forecastTime(context, path, path.endTime),
            '${path.points.length}',
            path.likelihood.label(l10n),
            Formatters.percent(path.probability),
          ),
          style: text.bodySmall,
        ),
        if (path.follows) ...[
          const SizedBox(height: AppSpacing.xxs),
          Text(forecastFollowsNote(l10n, path), style: text.bodySmall),
        ],
        const SizedBox(height: AppSpacing.xxs),
        Text(l10n.validUntil(forecastTime(context, path, path.validUntil)), style: text.labelMedium),
        const SizedBox(height: AppSpacing.xs),
        Wrap(
          spacing: AppSpacing.xs,
          runSpacing: AppSpacing.xs,
          children: [
            const SourceTag(SourceKind.model),
            if (simulated) const SourceTag(SourceKind.demo),
          ],
        ),
      ],
    );
  }
}

/// عيّنة الخط المتقطّع (نفس شكل الخط على الرسم: الشكل مش اللون بس)
class _DashedSwatch extends StatelessWidget {
  const _DashedSwatch();

  @override
  Widget build(BuildContext context) {
    final color = context.colors.forecast;
    return ExcludeSemantics(
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          for (var i = 0; i < 3; i++) ...[
            if (i > 0) const SizedBox(width: 3),
            Container(width: 6, height: 2, color: color),
          ],
        ],
      ),
    );
  }
}

class _OutdatedBadge extends StatelessWidget {
  const _OutdatedBadge({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return DecoratedBox(
      decoration: BoxDecoration(color: c.warningSoft, borderRadius: AppRadii.badge),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xs, vertical: AppSpacing.xxs / 2),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.history_rounded, size: AppSizes.iconSm - 2, color: c.warning),
            const SizedBox(width: AppSpacing.xxs),
            Flexible(child: Text(label, style: context.textTheme.labelSmall!.copyWith(color: c.warning))),
          ],
        ),
      ),
    );
  }
}

class _Message extends StatelessWidget {
  const _Message({required this.icon, required this.title, this.body, this.action});

  final IconData icon;
  final String title;
  final String? body;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ExcludeSemantics(child: Icon(icon, size: AppSizes.iconSm, color: c.fg2)),
            const SizedBox(width: AppSpacing.xs),
            Expanded(child: Text(title, style: text.titleSmall)),
          ],
        ),
        if (body != null) ...[
          const SizedBox(height: AppSpacing.xxs),
          Text(body!, style: text.bodySmall),
        ],
        if (action != null) ...[
          const SizedBox(height: AppSpacing.xs),
          Align(alignment: AlignmentDirectional.centerStart, child: action),
        ],
      ],
    );
  }
}
