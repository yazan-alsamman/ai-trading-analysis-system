import 'package:flutter/material.dart';

import '../../../core/theme/theme_context.dart';
import '../../../l10n/app_localizations.dart';
import '../models/membership_models.dart';
import 'membership_copy.dart';

/// شارة "شو بتشتغل عليه الميزة اليوم" - نفس ألوان الويب:
/// Works now = ذهبي، Demo data = أزرق، Needs backend = برتقالي، Planned = محايد
class StatusChip extends StatelessWidget {
  const StatusChip(this.status, {super.key});

  final FeatureStatus status;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final (Color fg, Color bg) = switch (status) {
      FeatureStatus.available => (c.accent, c.accentSoft),
      FeatureStatus.demo => (c.demo, c.demoSoft),
      FeatureStatus.backend => (c.warning, c.warningSoft),
      FeatureStatus.planned => (c.fg2, c.selected),
    };
    return Tooltip(
      message: l10n.statusDescription(status),
      child: DecoratedBox(
        decoration: BoxDecoration(color: bg, borderRadius: AppRadii.badge),
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.xs,
            vertical: AppSpacing.xxs / 2,
          ),
          child: Text(
            l10n.statusLabel(status),
            style: context.textTheme.labelSmall!.copyWith(color: fg),
          ),
        ),
      ),
    );
  }
}

/// شرح الحالات الأربع (فوق جدول المقارنة)
class StatusLegend extends StatelessWidget {
  const StatusLegend({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    return Semantics(
      container: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final status in FeatureStatus.values)
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              // الشارة فوق الشرح (مش جنبه) - بتضل مقروءة بأكبر خط
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  StatusChip(status),
                  const SizedBox(height: AppSpacing.xxs),
                  Text(
                    l10n.statusDescription(status),
                    style: context.textTheme.bodySmall!.copyWith(color: c.fg3),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
