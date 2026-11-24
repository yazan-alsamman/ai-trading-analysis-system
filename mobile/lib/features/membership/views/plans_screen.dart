import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../core/widgets/headings.dart';
import '../../../core/widgets/motion.dart';
import '../../../core/widgets/page_header.dart';
import '../../../l10n/app_localizations.dart';
import '../models/membership_models.dart';
import '../view_models/membership_view_model.dart';
import '../widgets/activation_sheet.dart';
import '../widgets/membership_faq.dart';
import '../widgets/plan_card.dart';
import '../widgets/plan_comparison.dart';

/// شاشة "Plans": سطر السعر (مرة وحدة)، الخطط الثلاث، زر "Compare plans"
/// (بيفتح المقارنة الكاملة بـ bottom sheet)، والأسئلة مطويّة تحت.
///
/// ما في أسعار ولا دفع؛ كل "Choose …" بيشرح إنو التفعيل المدفوع مش متاح بعد.
class PlansScreen extends ConsumerWidget {
  const PlansScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final membership = ref.watch(membershipViewModelProvider);

    return Scaffold(
      // H5c: شريط "غير متصل" واحد بس = تبع الـ shell (هالشاشة جوّا فرع)
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            PageHeader(title: l10n.toolPlans, back: const PageBackButton()),
            Expanded(
              child: membership.when(
                loading: () => const LoadingRegion(child: _PlansSkeleton()),
                error: (_, __) => Center(
                  child: ErrorState(onRetry: () => ref.invalidate(membershipViewModelProvider)),
                ),
                data: (state) => _PlansBody(state: state),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PlansBody extends StatelessWidget {
  const _PlansBody({required this.state});

  final MembershipState state;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final text = context.textTheme;
    final gutter = AppSpacing.gutter(context);

    final sections = <Widget>[
      // ── السعر: مرة وحدة فوق، مش مكرّر بكل بطاقة ──
      Semantics(
        container: true,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Icon(Icons.info_outline_rounded, size: AppSizes.iconMd, color: c.info),
            ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Text.rich(
                TextSpan(children: [
                  TextSpan(text: '${l10n.memPricingTba}. ', style: text.titleSmall),
                  TextSpan(text: l10n.memNoPayment, style: text.bodyMedium!.copyWith(color: c.fg2)),
                ]),
              ),
            ),
          ],
        ),
      ),
      for (final (i, plan) in PlanId.values.indexed)
        PlanCard(
          plan: plan,
          index: i,
          isCurrent: state.currentPlan == plan,
          onChoose: () => showActivationSheet(context, catalog: state.catalog, plan: plan),
        ),
      AppButton.secondary(
        label: l10n.memCompareEyebrow,
        icon: Icons.compare_arrows_rounded,
        expand: true,
        onPressed: () => showPlanComparisonSheet(
          context,
          catalog: state.catalog,
          initialPlan: state.currentPlan ?? PlanId.professional,
        ),
      ),
      Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsetsDirectional.only(start: AppSpacing.xxs, bottom: AppSpacing.xs),
            child: Semantics(header: true, child: Eyebrow(l10n.memFaqEyebrow)),
          ),
          const MembershipFaq(),
        ],
      ),
    ];

    return ListView.separated(
      padding: EdgeInsets.fromLTRB(gutter, AppSpacing.sm, gutter, AppSpacing.huge),
      itemCount: sections.length,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.lg),
      itemBuilder: (_, i) => FadeRise(index: i, child: sections[i]),
    );
  }
}

class _PlansSkeleton extends StatelessWidget {
  const _PlansSkeleton();

  @override
  Widget build(BuildContext context) {
    final gutter = AppSpacing.gutter(context);
    return ListView(
      physics: const NeverScrollableScrollPhysics(),
      padding: EdgeInsets.fromLTRB(gutter, AppSpacing.sm, gutter, 0),
      children: [
        const Skeleton(height: AppSpacing.xl, width: AppSpacing.huge * 5),
        for (var i = 0; i < 3; i++) ...[
          const SizedBox(height: AppSpacing.lg),
          const Skeleton(height: AppSpacing.huge * 5, radius: AppRadii.card),
        ],
      ],
    );
  }
}
