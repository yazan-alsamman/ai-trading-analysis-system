import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/router/app_navigator.dart';
import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../core/widgets/source_tag.dart';
import '../../../l10n/app_localizations.dart';
import '../../markets/data/market_providers.dart';

/// سطر الدقة أعلى Signals: كم إشارة سابقة وصلت للهدف قبل الوقف (بصراحة،
/// مع عدد الإشارات والفترة)، حتى المستخدم يعرف قديش يعتمد على النموذج.
///
/// الضغط بيفتح Insights (التفاصيل: الفترات، حسب الأداة والإطار، عبر الزمن).
/// أثناء التحميل أو الخطأ السطر مش زر.
class AccuracyLine extends ConsumerWidget {
  const AccuracyLine({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final text = context.textTheme;
    final c = context.colors;

    return ref.watch(modelAccuracyProvider).when(
          loading: () => Semantics(
            label: l10n.loading,
            child: const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Skeleton(width: 240),
                SizedBox(height: AppSpacing.xs),
                Skeleton(width: 180, height: AppSpacing.sm),
              ],
            ),
          ),
          error: (_, __) => Row(
            children: [
              Icon(Icons.error_outline_rounded, size: AppSizes.iconMd, color: c.danger),
              const SizedBox(width: AppSpacing.xs),
              Expanded(child: Text(l10n.accuracyError, style: text.bodyMedium!.copyWith(color: c.fg))),
              TextButton(
                onPressed: () => ref.invalidate(modelAccuracyProvider),
                child: Text(l10n.tryAgain),
              ),
            ],
          ),
          data: (accuracy) {
            final rate = accuracy.hitRate;
            final line = rate == null
                ? l10n.accuracyNoResults(accuracy.windowDays.toString())
                : l10n.accuracyLine(
                    Formatters.percent(rate),
                    accuracy.resolved.toString(),
                    accuracy.windowDays.toString(),
                  );
            return Semantics(
              container: true,
              button: true,
              hint: l10n.accuracyOpenHint,
              child: InkWell(
                onTap: context.pushInsights,
                borderRadius: AppRadii.card,
                child: ConstrainedBox(
                  constraints: const BoxConstraints(minHeight: AppSizes.minTap),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: AppSpacing.xxs),
                    child: Row(
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              Wrap(
                                spacing: AppSpacing.xs,
                                runSpacing: AppSpacing.xxs,
                                crossAxisAlignment: WrapCrossAlignment.center,
                                children: [
                                  Icon(Icons.verified_outlined, size: AppSizes.iconMd, color: c.fg2),
                                  Text(line, style: text.titleSmall),
                                  const SourceTag(SourceKind.demo),
                                ],
                              ),
                              const SizedBox(height: AppSpacing.xxs),
                              Text(l10n.accuracyCaption, style: text.bodySmall),
                            ],
                          ),
                        ),
                        const SizedBox(width: AppSpacing.xs),
                        Icon(Icons.chevron_right_rounded, color: c.fg3, size: AppSizes.iconLg),
                      ],
                    ),
                  ),
                ),
              ),
            );
          },
        );
  }
}
