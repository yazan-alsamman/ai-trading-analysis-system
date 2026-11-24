import 'package:flutter/material.dart';

import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/headings.dart';
import '../../../l10n/app_localizations.dart';
import '../models/membership_models.dart';
import 'membership_copy.dart';

/// بطاقة خطة واحدة: الاسم، لمين، أبرز 4 مزايا، والزر.
/// (السعر "لاحقًا" مكتوب مرة وحدة فوق الخطط، مش بكل بطاقة)
///
/// زر "Choose …" شكله معطّل (التفعيل المدفوع مش متاح) بس قابل للضغط:
/// بيفتح شرح السبب عبر [onChoose].
class PlanCard extends StatelessWidget {
  const PlanCard({
    super.key,
    required this.plan,
    required this.index,
    required this.isCurrent,
    required this.onChoose,
  });

  final PlanId plan;
  final int index;
  final bool isCurrent;
  final VoidCallback onChoose;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final text = context.textTheme;

    return AppCard(
      highlight: isCurrent,
      padding: const EdgeInsets.all(AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Eyebrow('0${index + 1}'),
                    const SizedBox(height: AppSpacing.xxs),
                    Text(l10n.planName(plan), style: text.displaySmall),
                  ],
                ),
              ),
              if (isCurrent)
                DecoratedBox(
                  decoration: BoxDecoration(color: c.accentSoft, borderRadius: AppRadii.badge),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.xs,
                      vertical: AppSpacing.xxs / 2,
                    ),
                    child: Text(
                      l10n.memCurrentPlan,
                      style: text.labelSmall!.copyWith(color: c.accent),
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(l10n.planTagline(plan), style: text.bodyLarge),
          const SizedBox(height: AppSpacing.xxs),
          Text(l10n.planAudience(plan), style: text.bodySmall!.copyWith(color: c.fg3)),
          const SizedBox(height: AppSpacing.md),
          Divider(height: 1, color: c.hairline),
          const SizedBox(height: AppSpacing.md),
          for (final highlight in l10n.planHighlights(plan))
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Icon(Icons.check_rounded, size: AppSizes.iconSm, color: c.accent),
                  ),
                  const SizedBox(width: AppSpacing.xs),
                  Expanded(
                    child: Text(highlight, style: text.bodyMedium!.copyWith(color: c.fg2)),
                  ),
                ],
              ),
            ),
          const SizedBox(height: AppSpacing.sm),
          UnavailableButton(label: l10n.planCta(plan), onPressed: onChoose),
        ],
      ),
    );
  }
}

/// زر بشكل "معطّل" بس قابل للضغط للشرح - للأفعال المدفوعة الغير متاحة بعد
///
/// القارئ الصوتي بيسمع "Choose Essential, Not available yet".
class UnavailableButton extends StatelessWidget {
  const UnavailableButton({super.key, required this.label, required this.onPressed});

  final String label;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    return Semantics(
      container: true,
      button: true,
      label: label,
      hint: l10n.memCtaHint,
      onTap: onPressed,
      excludeSemantics: true,
      child: OutlinedButton.icon(
        onPressed: onPressed,
        style: OutlinedButton.styleFrom(
          minimumSize: const Size.fromHeight(AppSizes.minTap),
          foregroundColor: c.fg3,
          side: BorderSide(color: c.hairline),
          shape: const StadiumBorder(),
        ),
        icon: const Icon(Icons.lock_outline_rounded, size: AppSizes.iconSm),
        label: Text(label),
      ),
    );
  }
}
