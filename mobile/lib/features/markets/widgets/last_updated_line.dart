import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/clock.dart';
import '../../../core/theme/theme_context.dart';
import '../../../l10n/app_localizations.dart';
import '../data/market_cache.dart';

/// H5a: "Last updated 14:05" (+ "Old data" إذا أقدم من [kCacheOldAfter]) لما
/// الأسعار المعروضة محفوظة مش حيّة. Semantics: منطقة حيّة (Android = polite)،
/// فبيتقرا مرة لما يظهر أو لما الوقت يتغيّر، مش مع كل إطار.
class LastUpdatedLine extends ConsumerWidget {
  const LastUpdatedLine({super.key, required this.updatedAt});

  final DateTime updatedAt;

  /// نفس اليوم = الساعة بس؛ يوم تاني = التاريخ + الساعة (وقت الجهاز)
  static String format(BuildContext context, DateTime time, DateTime now) {
    final local = time.toLocal();
    final today = now.toLocal();
    final ml = MaterialLocalizations.of(context);
    final clock = ml.formatTimeOfDay(
      TimeOfDay.fromDateTime(local),
      alwaysUse24HourFormat: MediaQuery.alwaysUse24HourFormatOf(context),
    );
    final sameDay = local.year == today.year && local.month == today.month && local.day == today.day;
    return sameDay ? clock : '${ml.formatShortMonthDay(local)} $clock';
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final now = ref.watch(clockProvider).valueOrNull ?? DateTime.now();
    final old = isOldData(updatedAt, now);
    final text = l10n.lastUpdated(format(context, updatedAt, now));

    return Semantics(
      container: true,
      liveRegion: true,
      label: old ? '$text, ${l10n.oldData}' : text,
      excludeSemantics: true,
      child: Wrap(
        spacing: AppSpacing.xs,
        runSpacing: AppSpacing.xxs,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          Text(text, style: context.textTheme.bodySmall!.copyWith(color: c.fg2)),
          if (old) const _OldDataTag(),
        ],
      ),
    );
  }
}

/// شارة "Old data": أيقونة + كلمة (مش اللون لحالو)
class _OldDataTag extends StatelessWidget {
  const _OldDataTag();

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return DecoratedBox(
      decoration: BoxDecoration(color: c.warningSoft, borderRadius: AppRadii.pillAll),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xs, vertical: AppSpacing.xxs / 2),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.history_rounded, size: AppSizes.iconSm - 2, color: c.warning),
            const SizedBox(width: AppSpacing.xxs),
            Flexible(
              child: Text(
                AppLocalizations.of(context)!.oldData,
                style: context.textTheme.labelSmall!.copyWith(color: c.warning),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
