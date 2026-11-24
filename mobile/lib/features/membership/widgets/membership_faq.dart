import 'package:flutter/material.dart';

import '../../../core/theme/theme_context.dart';
import '../../../l10n/app_localizations.dart';

/// أسئلة العضوية كـ accordion - نفس MEMBERSHIP_FAQ بالويب
class MembershipFaq extends StatelessWidget {
  const MembershipFaq({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final entries = [
      (l10n.memFaqCostQ, l10n.memFaqCostA),
      (l10n.memFaqSubscribeQ, l10n.memFaqSubscribeA),
      (l10n.memFaqDemoQ, l10n.memFaqDemoA),
      (l10n.memFaqLimitQ, l10n.memFaqLimitA),
      (l10n.memFaqRiskQ, l10n.memFaqRiskA),
    ];
    final animation = context.reduceMotion
        ? AnimationStyle.noAnimation
        : const AnimationStyle(duration: AppMotion.medium, curve: AppMotion.out);

    return Material(
      color: c.card,
      shape: RoundedRectangleBorder(
        borderRadius: AppRadii.card,
        side: BorderSide(color: c.hairline),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          for (var i = 0; i < entries.length; i++) ...[
            if (i > 0) Divider(height: 1, thickness: 1, color: c.hairline),
            ExpansionTile(
              expansionAnimationStyle: animation,
              shape: const Border(),
              collapsedShape: const Border(),
              tilePadding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
              childrenPadding: const EdgeInsets.fromLTRB(
                AppSpacing.md,
                0,
                AppSpacing.md,
                AppSpacing.md,
              ),
              expandedCrossAxisAlignment: CrossAxisAlignment.start,
              title: Text(entries[i].$1, style: context.textTheme.titleSmall),
              children: [
                Text(
                  entries[i].$2,
                  style: context.textTheme.bodyMedium!.copyWith(color: c.fg2),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}
