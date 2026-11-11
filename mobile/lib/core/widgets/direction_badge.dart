import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';
import '../theme/theme_context.dart';

/// اتجاه رأي النموذج (مش أمر شراء/بيع): Long / Short / Neutral
/// (بالعربي: صعود / هبوط / محايد) - قرار المنتج، أبدًا "اشترِ الآن".
enum SignalDirection { long, short, neutral }

extension SignalDirectionLabel on SignalDirection {
  String label(AppLocalizations l10n) => switch (this) {
        SignalDirection.long => l10n.directionLong,
        SignalDirection.short => l10n.directionShort,
        SignalDirection.neutral => l10n.directionNeutral,
      };
}

/// شارة الاتجاه (نفس web DirectionBadge): سهم + كلمة على خلفية ناعمة
///
/// up/down للاتجاه بس، ودايمًا مع سهم وكلمة - أبدًا اللون لحالو.
class DirectionBadge extends StatelessWidget {
  const DirectionBadge(this.direction, {super.key});

  final SignalDirection direction;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final (IconData icon, Color fg, Color bg) = switch (direction) {
      SignalDirection.long => (Icons.arrow_upward_rounded, c.up, c.upSoft),
      SignalDirection.short => (Icons.arrow_downward_rounded, c.down, c.downSoft),
      SignalDirection.neutral => (Icons.remove_rounded, c.fg2, c.selected),
    };

    return DecoratedBox(
      decoration: BoxDecoration(color: bg, borderRadius: AppRadii.badge),
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.xs,
          vertical: AppSpacing.xxs / 2,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: AppSizes.iconSm - 2, color: fg),
            const SizedBox(width: AppSpacing.xxs),
            Text(
              direction.label(l10n),
              style: context.textTheme.labelSmall!.copyWith(color: fg),
            ),
          ],
        ),
      ),
    );
  }
}
