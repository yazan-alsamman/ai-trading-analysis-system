import 'package:flutter/material.dart';

import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/direction_badge.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../core/widgets/source_tag.dart';
import '../../../l10n/app_localizations.dart';
import '../../markets/widgets/market_hero.dart';
import '../models/opportunity.dart';

/// صف فرصة بقائمة Signals: الرمز (Hero لشاشة التفاصيل) + الاتجاه بسهم وكلمة +
/// الإطار + عمرها + شارة "مخرجات النموذج" | الاحتمال (بنفسجي = النموذج).
///
/// [now] جاي من القائمة (ساعة وحدة لكل الصفوف). [onTap] بيفتح التفاصيل؛ null =
/// صف للعرض بس، فما في سهم ولا "زر" للقارئ الصوتي.
class SignalRow extends StatelessWidget {
  const SignalRow({super.key, required this.signal, required this.now, this.onTap});

  /// ارتفاع الصف بالخط العادي (بيكبر مع الخط)
  static const double minHeight = 72;

  /// tag الـ Hero على الرمز: لكل إشارة لحالها (نفس الأداة ممكن تطلع على كذا إطار)
  static String heroTag(String signalId) => 'signal-symbol-$signalId';

  final Opportunity signal;
  final DateTime now;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final probability = Formatters.percent(signal.probability);
    final age = relativeTime(l10n, signal.generatedAt, now);
    final label = [
      l10n.signalRowLabel(
        signal.symbol,
        l10n.instrumentName(signal.symbol),
        signal.direction.label(l10n),
        probability,
        signal.timeframe.label,
        age,
      ),
      l10n.sourceModel,
      if (signal.requestedByYou) l10n.requestedByYou,
    ].join('. ');

    return Semantics(
      container: true,
      button: onTap != null,
      label: label,
      hint: onTap == null ? null : l10n.signalRowHint,
      onTap: onTap,
      excludeSemantics: true,
      child: InkWell(
        onTap: onTap,
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: minHeight),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      MarketSymbolHero(
                        symbol: signal.symbol,
                        style: context.textTheme.titleSmall!,
                        heroTag: heroTag(signal.id),
                      ),
                      const SizedBox(height: AppSpacing.xxs),
                      Wrap(
                        spacing: AppSpacing.xs,
                        runSpacing: AppSpacing.xxs,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          DirectionBadge(signal.direction),
                          Text(
                            '${signal.timeframe.label} · $age',
                            style: context.textTheme.labelMedium!.copyWith(color: c.fg3),
                          ),
                          const SourceTag(SourceKind.model),
                          if (signal.requestedByYou) const RequestedTag(),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Text(
                  probability,
                  style: context.type.num.copyWith(color: c.forecast),
                  textDirection: TextDirection.ltr,
                ),
                if (onTap != null) ...[
                  const SizedBox(width: AppSpacing.xxs),
                  Icon(Icons.chevron_right_rounded, color: c.fg3, size: AppSizes.iconLg),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// شارة "Requested by you": إشارة طلبها المستخدم بـ "Request analysis"
/// (أيقونة + كلمة، مش اللون لحالو؛ بتلف جوّاها بالخط الكبير)
class RequestedTag extends StatelessWidget {
  const RequestedTag({super.key});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return DecoratedBox(
      decoration: BoxDecoration(color: c.accentSoft, borderRadius: AppRadii.badge),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xs, vertical: AppSpacing.xxs / 2),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.person_search_outlined, size: AppSizes.iconSm - 2, color: c.fg),
            const SizedBox(width: AppSpacing.xxs),
            Flexible(
              child: Text(
                AppLocalizations.of(context)!.requestedByYou,
                style: context.textTheme.labelSmall!.copyWith(color: c.fg),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// مكان صف أثناء التحميل (نفس ارتفاع [SignalRow])
class SignalRowSkeleton extends StatelessWidget {
  const SignalRowSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    return const SizedBox(
      height: SignalRow.minHeight,
      child: Padding(
        padding: EdgeInsets.symmetric(horizontal: AppSpacing.md),
        child: Row(
          children: [
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Skeleton(width: AppSpacing.huge * 1.5),
                  SizedBox(height: AppSpacing.xs),
                  Skeleton(width: AppSpacing.huge * 3, height: AppSpacing.sm),
                ],
              ),
            ),
            Skeleton(width: AppSpacing.huge),
          ],
        ),
      ),
    );
  }
}
