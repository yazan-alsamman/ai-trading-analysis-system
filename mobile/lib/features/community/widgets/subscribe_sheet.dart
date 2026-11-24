import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/format/formatters.dart';
import '../../../app/router/app_navigator.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/source_tag.dart';
import '../../../l10n/app_localizations.dart';
import '../../profile/widgets/profile_identity_card.dart';
import '../models/expert.dart';
import '../models/expert_plan.dart';
import '../view_models/expert_subscriptions_view_model.dart';

/// السعر مع المدة: "USD 29.00 / month"
String planPriceLabel(AppLocalizations l10n, ExpertPlan plan) {
  final price = Formatters.money(plan.price, plan.currency);
  return plan.interval == PlanInterval.month ? l10n.expertPricePerMonth(price) : l10n.expertPricePerYear(price);
}

/// "Subscribe" بـ bottom sheet: خطة الخبير (السعر بالشهر، شو بتتضمن)، ملاحظة إنها
/// نصيحة من شخص مش نصيحة مالية، "Simulated" (ما في دفع ولا بيانات بطاقة)، وزر
/// تأكيد + Cancel. ضغطتين على Subscribe = sheet وحدة. بيرجّع true لما يشترك
/// (وبيطلع snackbar).
Future<bool> showSubscribeSheet(BuildContext context, Expert expert) async {
  if (expert.plan == null || !context.isTopmostRoute) return false;
  final l10n = AppLocalizations.of(context)!;
  final messenger = ScaffoldMessenger.of(context);
  AppHaptics.light();
  final subscribed = await showModalBottomSheet<bool>(
    useRootNavigator: true,
    context: context,
    sheetAnimationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
    isScrollControlled: true,
    useSafeArea: true,
    showDragHandle: true,
    builder: (_) => SubscribeSheet(expert: expert),
  );
  if (subscribed != true) return false;
  messenger
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(l10n.expertSubscribedSnack(expert.name))));
  return true;
}

class SubscribeSheet extends ConsumerStatefulWidget {
  const SubscribeSheet({super.key, required this.expert});

  final Expert expert;

  @override
  ConsumerState<SubscribeSheet> createState() => _SubscribeSheetState();
}

class _SubscribeSheetState extends ConsumerState<SubscribeSheet> {
  bool _busy = false;
  String? _error;

  Future<void> _confirm() async {
    if (_busy) return;
    final l10n = AppLocalizations.of(context)!;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final s = await ref.read(expertSubscriptionsProvider.notifier).subscribe(widget.expert);
      if (!mounted) return;
      if (s != null) {
        AppHaptics.confirm();
        Navigator.of(context).pop(true);
        return;
      }
    } on ExpertsOfflineException {
      if (mounted) setState(() => _error = l10n.subscribeOffline);
    } catch (_) {
      if (mounted) setState(() => _error = l10n.subscribeFailed);
    }
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final text = context.textTheme;
    final gutter = AppSpacing.gutter(context);
    final expert = widget.expert;
    final plan = expert.plan!;

    Widget included(IconData icon, String label) => Padding(
          padding: const EdgeInsets.only(top: AppSpacing.xs),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, size: AppSizes.iconMd, color: c.accent),
              const SizedBox(width: AppSpacing.sm),
              Expanded(child: Text(label, style: text.bodyMedium!.copyWith(color: c.fg))),
            ],
          ),
        );

    return SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(gutter, 0, gutter, AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ExcludeSemantics(child: ProfileAvatar(name: expert.name, path: null, size: 48)),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Semantics(
                  header: true,
                  child: Text(l10n.expertSubscribeTo(expert.name), style: text.titleLarge),
                ),
              ),
              IconButton(
                tooltip: MaterialLocalizations.of(context).closeButtonTooltip,
                constraints: const BoxConstraints(minWidth: AppSizes.minTap, minHeight: AppSizes.minTap),
                icon: Icon(Icons.close_rounded, color: c.fg2),
                onPressed: () => Navigator.of(context).pop(false),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          // الخطة والسعر
          DecoratedBox(
            decoration: BoxDecoration(
              color: c.inset,
              borderRadius: AppRadii.card,
              border: Border.all(color: c.hairline),
            ),
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(plan.name, style: text.titleMedium),
                  const SizedBox(height: AppSpacing.xxs),
                  Text(planPriceLabel(l10n, plan), style: context.type.numLarge),
                  const SizedBox(height: AppSpacing.xs),
                  const SourceTag(SourceKind.demo),
                  if (plan.description.isNotEmpty) ...[
                    const SizedBox(height: AppSpacing.sm),
                    Text(plan.description, style: text.bodyMedium),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          Semantics(header: true, child: Text(l10n.subscribeIncluded, style: text.labelLarge)),
          if (plan.includesChat && expert.chatEnabled)
            included(Icons.chat_bubble_outline_rounded, l10n.subscribeIncludesChat(expert.name)),
          if (expert.availability.isNotEmpty)
            included(Icons.schedule_rounded, l10n.subscribeAvailability(expert.availability)),
          included(Icons.event_busy_outlined, l10n.subscribeCancelAnytime),
          const SizedBox(height: AppSpacing.md),
          // نصيحة من شخص، مش نصيحة مالية
          DecoratedBox(
            decoration: BoxDecoration(color: c.warningSoft, borderRadius: AppRadii.card),
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.sm),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.info_outline_rounded, size: AppSizes.iconMd, color: c.fg),
                  const SizedBox(width: AppSpacing.xs),
                  Expanded(child: Text(l10n.subscribeNote, style: text.bodyMedium!.copyWith(color: c.fg))),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.credit_card_off_outlined, size: AppSizes.iconSm, color: c.fg3),
              const SizedBox(width: AppSpacing.xs),
              Expanded(child: Text(l10n.subscribeSimulated, style: text.bodySmall)),
            ],
          ),
          if (_error case final error?) ...[
            const SizedBox(height: AppSpacing.sm),
            Semantics(
              liveRegion: true,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.error_outline_rounded, size: AppSizes.iconMd, color: c.danger),
                  const SizedBox(width: AppSpacing.xs),
                  Expanded(child: Text(error, style: text.bodyMedium!.copyWith(color: c.fg))),
                ],
              ),
            ),
          ],
          const SizedBox(height: AppSpacing.lg),
          AppButton(
            label: l10n.subscribeConfirm,
            icon: Icons.check_rounded,
            expand: true,
            loading: _busy,
            onPressed: _confirm,
          ),
          const SizedBox(height: AppSpacing.xs),
          AppButton.ghost(
            label: l10n.cancel,
            expand: true,
            onPressed: _busy ? null : () => Navigator.of(context).pop(false),
          ),
        ],
      ),
    );
  }
}
