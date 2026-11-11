import 'package:flutter/material.dart';

import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/headings.dart';
import '../../../l10n/app_localizations.dart';
import '../models/membership_models.dart';
import 'membership_copy.dart';
import 'status_chip.dart';

/// "اختيارك" - بيشرح بصراحة إنو التفعيل المدفوع مش متاح بعد
///
/// نفس PlanConfirmSheet بالويب: الخطة + تنبيه "Paid activation is not
/// available yet" + المشمول وغير المشمول. ما في checkout ولا دفع.
Future<void> showActivationSheet(
  BuildContext context, {
  required MembershipCatalog catalog,
  required PlanId plan,
}) {
  return showModalBottomSheet<void>(
    useRootNavigator: true,
    context: context,
    sheetAnimationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (context) => DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.75,
      minChildSize: 0.4,
      maxChildSize: 0.95,
      builder: (context, controller) =>
          _ActivationSheet(catalog: catalog, plan: plan, controller: controller),
    ),
  );
}

class _ActivationSheet extends StatelessWidget {
  const _ActivationSheet({
    required this.catalog,
    required this.plan,
    required this.controller,
  });

  final MembershipCatalog catalog;
  final PlanId plan;
  final ScrollController controller;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final text = context.textTheme;
    final gutter = AppSpacing.gutter(context);
    final access = catalog.plan(plan);
    final included = catalog.includedIn(plan);
    final excluded = catalog.excludedFrom(plan);

    return SafeArea(
      top: false,
      child: Column(
        children: [
          Expanded(
            child: ListView(
              controller: controller,
              padding: EdgeInsets.fromLTRB(gutter, 0, gutter, AppSpacing.lg),
              children: [
                Semantics(header: true, child: Text(l10n.memSheetTitle, style: text.titleLarge)),
                const SizedBox(height: AppSpacing.lg),
                Eyebrow(l10n.memSheetSelectedPlan),
                const SizedBox(height: AppSpacing.xxs),
                Text(l10n.planName(plan), style: text.displaySmall),
                const SizedBox(height: AppSpacing.xxs),
                Text(l10n.planTagline(plan), style: text.bodyLarge!.copyWith(color: c.fg2)),
                const SizedBox(height: AppSpacing.sm),
                Text(l10n.memPricingTba, style: text.titleSmall),
                const SizedBox(height: AppSpacing.lg),
                _NoticeBox(
                  title: l10n.memActivationTitle,
                  body: l10n.memActivationBody,
                ),
                const SizedBox(height: AppSpacing.xl),
                Eyebrow(l10n.memIncluded),
                const SizedBox(height: AppSpacing.xs),
                for (final f in included)
                  _FeatureLine(
                    included: true,
                    label: l10n.featureLabel(f.id),
                    scope: switch (access.accessTo(f.id)) {
                      Scoped(:final scope) => l10n.scopeLabel(scope),
                      _ => null,
                    },
                    status: f.status,
                  ),
                if (excluded.isNotEmpty) ...[
                  const SizedBox(height: AppSpacing.lg),
                  Eyebrow(l10n.memNotIncluded),
                  const SizedBox(height: AppSpacing.xs),
                  for (final f in excluded)
                    _FeatureLine(included: false, label: l10n.featureLabel(f.id)),
                ],
              ],
            ),
          ),
          Padding(
            padding: EdgeInsets.fromLTRB(gutter, AppSpacing.sm, gutter, AppSpacing.md),
            child: AppButton.secondary(
              label: l10n.memClose,
              expand: true,
              onPressed: () => Navigator.of(context).pop(),
            ),
          ),
        ],
      ),
    );
  }
}

class _NoticeBox extends StatelessWidget {
  const _NoticeBox({required this.title, required this.body});

  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;
    return Semantics(
      container: true,
      liveRegion: true,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: c.infoSoft,
          borderRadius: AppRadii.card,
          border: Border.all(color: c.info.withValues(alpha: 0.4)),
        ),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.info_outline_rounded, size: AppSizes.iconMd, color: c.info),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Text.rich(
                  TextSpan(children: [
                    TextSpan(text: '$title ', style: text.titleSmall),
                    TextSpan(text: body, style: text.bodyMedium!.copyWith(color: c.fg2)),
                  ]),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _FeatureLine extends StatelessWidget {
  const _FeatureLine({
    required this.included,
    required this.label,
    this.scope,
    this.status,
  });

  final bool included;
  final String label;
  final String? scope;
  final FeatureStatus? status;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            included ? Icons.check_rounded : Icons.remove_rounded,
            size: AppSizes.iconMd,
            color: included ? c.accent : c.fg3,
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text.rich(
                  TextSpan(children: [
                    TextSpan(
                      text: label,
                      style: text.bodyMedium!.copyWith(color: included ? c.fg : c.fg3),
                    ),
                    if (scope != null)
                      TextSpan(
                        text: ' · $scope',
                        style: text.bodyMedium!.copyWith(color: c.fg3),
                      ),
                  ]),
                ),
                if (status != null) ...[
                  const SizedBox(height: AppSpacing.xxs),
                  StatusChip(status!),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
