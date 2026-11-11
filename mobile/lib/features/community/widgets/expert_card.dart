import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/router/app_navigator.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../l10n/app_localizations.dart';
import '../../../models/user_model.dart';
import '../../profile/widgets/profile_identity_card.dart';
import '../models/expert.dart';
import '../models/expert_subscription.dart';
import '../view_models/expert_subscriptions_view_model.dart';
import 'subscribe_sheet.dart';

/// بطاقة خبير: الاسم + شارة الدور، النبذة، التخصصات، الأدوات، اللغات، الأوقات،
/// وتحت حالة الاشتراك:
/// - مش مشترك: السعر بالشهر + "Subscribe" (بيفتح sheet الخطة).
/// - مشترك: "Subscribed" (أيقونة + كلمة، مش لون بس) + "Chat" + "Unsubscribe"
///   (تأكيد خفيف، بعدها snackbar مع Undo).
class ExpertCard extends ConsumerWidget {
  const ExpertCard({super.key, required this.expert});

  final Expert expert;

  Future<void> _unsubscribe(BuildContext context, WidgetRef ref) async {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final messenger = ScaffoldMessenger.of(context);
    final confirmed = await showDialog<bool>(
      context: context,
      animationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
      builder: (dialogContext) => AlertDialog(
        title: Text(l10n.expertUnsubscribeTitle(expert.name)),
        content: Text(l10n.expertUnsubscribeBody(expert.name)),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: Text(l10n.cancel),
          ),
          TextButton(
            style: TextButton.styleFrom(foregroundColor: c.danger),
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: Text(l10n.expertUnsubscribe),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    void show(String message, {SnackBarAction? action}) => messenger
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message), action: action));

    final vm = ref.read(expertSubscriptionsProvider.notifier);
    final ExpertSubscription? previous;
    try {
      previous = await vm.unsubscribe(expert.id);
    } on ExpertsOfflineException {
      show(l10n.expertOffline);
      return;
    } catch (_) {
      show(l10n.expertActionFailed);
      return;
    }
    if (previous == null) return;
    show(
      l10n.expertUnsubscribed(expert.name),
      action: SnackBarAction(
        label: l10n.undo,
        onPressed: () async {
          try {
            await vm.undoUnsubscribe(previous!);
          } on ExpertsOfflineException {
            show(l10n.expertOffline);
          } catch (_) {
            show(l10n.expertActionFailed);
          }
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;

    Widget tag(String label, {bool mono = false}) => DecoratedBox(
          decoration: BoxDecoration(color: c.selected, borderRadius: AppRadii.badge),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xs, vertical: AppSpacing.xxs / 2),
            child: Text(
              label,
              style: mono ? context.type.numSmall.copyWith(color: c.fg2) : text.labelMedium!.copyWith(color: c.fg2),
            ),
          ),
        );

    Widget line(IconData icon, String value) => Padding(
          padding: const EdgeInsets.only(top: AppSpacing.xs),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, size: AppSizes.iconSm, color: c.fg3),
              const SizedBox(width: AppSpacing.xs),
              Expanded(child: Text(value, style: text.bodySmall!.copyWith(color: c.fg2))),
            ],
          ),
        );

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              ExcludeSemantics(child: ProfileAvatar(name: expert.name, path: null, size: 48)),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Semantics(header: true, child: Text(expert.name, style: text.titleMedium)),
                    const SizedBox(height: AppSpacing.xxs),
                    const RoleBadge(role: UserRole.expert),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(expert.headline, style: text.bodyMedium!.copyWith(color: c.fg)),
          if (expert.specialties.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            Wrap(
              spacing: AppSpacing.xs,
              runSpacing: AppSpacing.xs,
              children: [for (final s in expert.specialties) tag(s)],
            ),
          ],
          if (expert.markets.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.xs),
            Semantics(
              label: l10n.expertMarkets(expert.markets.map(l10n.instrumentName).join(', ')),
              excludeSemantics: true,
              child: Wrap(
                spacing: AppSpacing.xs,
                runSpacing: AppSpacing.xs,
                children: [for (final m in expert.markets) tag(m, mono: true)],
              ),
            ),
          ],
          if (expert.languages.isNotEmpty) line(Icons.translate_rounded, expert.languages.join(', ')),
          line(Icons.schedule_rounded, expert.availability),
          if (expert.plan != null) ...[
            const SizedBox(height: AppSpacing.md),
            _SubscriptionArea(expert: expert, onUnsubscribe: () => _unsubscribe(context, ref)),
          ],
        ],
      ),
    );
  }
}

/// أسفل البطاقة حسب حالة الاشتراك (تحميل / مش مشترك / مشترك)
class _SubscriptionArea extends ConsumerWidget {
  const _SubscriptionArea({required this.expert, required this.onUnsubscribe});

  final Expert expert;
  final VoidCallback onUnsubscribe;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;
    final plan = expert.plan!;
    final subscription = ref.watch(expertSubscriptionProvider(expert.id));
    final price = planPriceLabel(l10n, plan);

    // الحالة ما انقرت بعد: مكان الزر محجوز، بدون زر بيكذب. فشلت: "Try again".
    final current = subscription.valueOrNull;
    if (subscription.hasError && !subscription.isLoading) {
      return AppButton.ghost(
        label: l10n.tryAgain,
        icon: Icons.refresh_rounded,
        expand: true,
        compact: true,
        onPressed: () => ref.invalidate(expertSubscriptionsProvider),
      );
    }
    if (!subscription.hasValue) {
      return const Skeleton(height: AppSizes.buttonHeightSm, radius: AppRadii.pillAll);
    }

    if (current == null || !current.isEntitled) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(l10n.expertPlanLine(plan.name, price), style: text.bodySmall!.copyWith(color: c.fg2)),
          const SizedBox(height: AppSpacing.xs),
          _hinted(
            l10n.expertSubscribeTo(expert.name),
            AppButton.secondary(
              label: l10n.expertSubscribe,
              icon: Icons.add_rounded,
              expand: true,
              compact: true,
              onPressed: () => showSubscribeSheet(context, expert),
            ),
          ),
        ],
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // الحالة: أيقونة + كلمة (مش لون بس)، وتحتها الخطة
        Semantics(
          container: true,
          label: '${l10n.expertSubscribedLabel(expert.name)}. ${l10n.expertPlanLine(current.planName, price)}',
          excludeSemantics: true,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.check_circle_rounded, size: AppSizes.iconMd, color: c.accent),
              const SizedBox(width: AppSpacing.xs),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(l10n.expertSubscribed, style: text.labelLarge!.copyWith(color: c.fg)),
                    Text(l10n.expertPlanLine(current.planName, price), style: text.bodySmall!.copyWith(color: c.fg2)),
                  ],
                ),
              ),
            ],
          ),
        ),
        if (expert.chatEnabled && current.allowsChat) ...[
          const SizedBox(height: AppSpacing.sm),
          _hinted(
            l10n.expertChatWith(expert.name),
            AppButton.secondary(
              label: l10n.expertChat,
              icon: Icons.chat_bubble_outline_rounded,
              expand: true,
              compact: true,
              onPressed: () => context.pushExpertChat(expert.id),
            ),
          ),
        ],
        _hinted(
          l10n.expertUnsubscribeFrom(expert.name),
          AppButton.ghost(
            label: l10n.expertUnsubscribe,
            expand: true,
            compact: true,
            onPressed: onUnsubscribe,
          ),
        ),
      ],
    );
  }
}

/// تلميح باسم الخبير على نفس عقدة الزر (3 بطاقات = 3 أزرار "Subscribe" بتنميّز)
Widget _hinted(String hint, Widget button) => MergeSemantics(child: Semantics(hint: hint, child: button));
