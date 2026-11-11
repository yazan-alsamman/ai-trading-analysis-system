import 'package:flutter/material.dart';

import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/headings.dart';
import '../../../core/widgets/segment_label.dart';
import '../../../l10n/app_localizations.dart';
import '../models/membership_models.dart';
import 'membership_copy.dart';
import 'status_chip.dart';

/// "Compare plans": المقارنة الكاملة بـ bottom sheet (بتبلش بـ [initialPlan])
Future<void> showPlanComparisonSheet(
  BuildContext context, {
  required MembershipCatalog catalog,
  required PlanId initialPlan,
}) {
  return showModalBottomSheet<void>(
    useRootNavigator: true,
    context: context,
    sheetAnimationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
    isScrollControlled: true,
    useSafeArea: true,
    showDragHandle: true,
    builder: (context) => DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.85,
      minChildSize: 0.5,
      maxChildSize: 1,
      builder: (context, controller) => _ComparisonSheet(
        catalog: catalog,
        initialPlan: initialPlan,
        controller: controller,
      ),
    ),
  );
}

class _ComparisonSheet extends StatefulWidget {
  const _ComparisonSheet({
    required this.catalog,
    required this.initialPlan,
    required this.controller,
  });

  final MembershipCatalog catalog;
  final PlanId initialPlan;
  final ScrollController controller;

  @override
  State<_ComparisonSheet> createState() => _ComparisonSheetState();
}

class _ComparisonSheetState extends State<_ComparisonSheet> {
  // اختيار عرض بس (أي خطة معروضة) - حالة الـ sheet نفسه
  late PlanId _plan = widget.initialPlan;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    return ListView(
      controller: widget.controller,
      padding: EdgeInsets.fromLTRB(gutter, 0, gutter, AppSpacing.xl),
      children: [
        Semantics(
          header: true,
          child: Text(l10n.memCompareEyebrow, style: context.textTheme.titleLarge),
        ),
        const SizedBox(height: AppSpacing.md),
        PlanComparison(
          catalog: widget.catalog,
          plan: _plan,
          onPlanChanged: (plan) => setState(() => _plan = plan),
        ),
        const SizedBox(height: AppSpacing.xs),
        Padding(
          padding: const EdgeInsetsDirectional.only(start: AppSpacing.xxs, bottom: AppSpacing.sm),
          child: Semantics(header: true, child: Eyebrow(l10n.memStatusLegend)),
        ),
        const StatusLegend(),
      ],
    );
  }
}

/// المقارنة: خطة وحدة بكل مرة (segmented)، والميزات الـ 15 مجمّعة بأربع
/// مجموعات - بطاقات مكدّسة بدل جدول بسكرول أفقي، فكل صف بيضل مقروء كامل
/// على 375dp وبخط كبير.
class PlanComparison extends StatelessWidget {
  const PlanComparison({
    super.key,
    required this.catalog,
    required this.plan,
    required this.onPlanChanged,
  });

  final MembershipCatalog catalog;
  final PlanId plan;
  final ValueChanged<PlanId> onPlanChanged;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final shown = catalog.plan(plan);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Semantics(
          label: l10n.memComparePlan,
          container: true,
          child: SegmentedButton<PlanId>(
            showSelectedIcon: false,
            segments: [
              for (final p in PlanId.values)
                ButtonSegment(value: p, label: SegmentLabel(l10n.planName(p))),
            ],
            selected: {plan},
            onSelectionChanged: (selection) {
              AppHaptics.selection();
              onPlanChanged(selection.first);
            },
          ),
        ),
        const SizedBox(height: AppSpacing.lg),
        for (final group in FeatureGroup.values) ...[
          Padding(
            padding: const EdgeInsetsDirectional.only(start: AppSpacing.xxs, bottom: AppSpacing.xs),
            child: Semantics(header: true, child: Eyebrow(l10n.groupLabel(group))),
          ),
          _GroupCard(
            children: [
              for (final feature in catalog.featuresIn(group))
                _FeatureRow(feature: feature, access: shown.accessTo(feature.id)),
            ],
          ),
          const SizedBox(height: AppSpacing.lg),
        ],
      ],
    );
  }
}

class _GroupCard extends StatelessWidget {
  const _GroupCard({required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Material(
      color: c.card,
      shape: RoundedRectangleBorder(
        borderRadius: AppRadii.card,
        side: BorderSide(color: c.hairline),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          for (var i = 0; i < children.length; i++) ...[
            if (i > 0) Divider(height: 1, thickness: 1, color: c.hairline),
            children[i],
          ],
        ],
      ),
    );
  }
}

class _FeatureRow extends StatelessWidget {
  const _FeatureRow({required this.feature, required this.access});

  final PlanFeature feature;
  final Access access;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final text = context.textTheme;
    final label = l10n.featureLabel(feature.id);

    final Widget accessWidget = switch (access) {
      Included() => Icon(Icons.check_rounded, size: AppSizes.iconMd, color: c.accent),
      NotIncluded() => Text(l10n.memNotIncluded, style: text.bodySmall!.copyWith(color: c.fg3)),
      Scoped(:final scope) => Text(
          l10n.scopeLabel(scope),
          style: text.bodySmall!.copyWith(color: c.fg),
          textAlign: TextAlign.end,
        ),
    };

    return Semantics(
      container: true,
      label: '$label, ${l10n.accessLabel(access)}, ${l10n.statusLabel(feature.status)}',
      excludeSemantics: true,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
        child: Row(
          children: [
            Expanded(
              flex: 3,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label, style: text.bodyMedium),
                  const SizedBox(height: AppSpacing.xxs),
                  StatusChip(feature.status),
                ],
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            Flexible(
              flex: 2,
              child: Align(alignment: AlignmentDirectional.centerEnd, child: accessWidget),
            ),
          ],
        ),
      ),
    );
  }
}
