import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../l10n/app_localizations.dart';
import '../data/low_data_mode.dart';
import '../theme/theme_context.dart';

/// H5b: اقتراح الـ Low data mode (بيانات جوال أو اتصال بطيء). بينسكّر
/// ("Not now" بينحفظ)، وما بيشغّل الوضع أبدًا لحالو: "Turn on" بس.
class LowDataSuggestionBanner extends ConsumerWidget {
  const LowDataSuggestionBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final reason = ref.watch(lowDataSuggestionProvider);
    final child = reason == null ? const SizedBox(width: double.infinity) : _Banner(reason: reason);
    // تقليل الحركة: بدون AnimatedSize (بمدة صفر بيعيد تعليم حالو أثناء الـ layout)
    if (context.reduceMotion) return child;
    return AnimatedSize(
      duration: AppMotion.base,
      curve: AppMotion.out,
      alignment: AlignmentDirectional.topStart,
      child: child,
    );
  }
}

class _Banner extends ConsumerWidget {
  const _Banner({required this.reason});

  final LowDataReason reason;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;
    final body = switch (reason) {
      LowDataReason.mobileData => l10n.lowDataSuggestMobile,
      LowDataReason.slowConnection => l10n.lowDataSuggestSlow,
    };

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Semantics(
        container: true,
        liveRegion: true,
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: c.raised,
            borderRadius: AppRadii.card,
            border: Border.all(color: c.hairline),
          ),
          child: Padding(
            padding: const EdgeInsetsDirectional.fromSTEB(AppSpacing.md, AppSpacing.sm, AppSpacing.xs, AppSpacing.xs),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Padding(
                      padding: const EdgeInsets.only(top: 2),
                      child: Icon(Icons.data_saver_on_rounded, size: AppSizes.iconMd, color: c.fg2),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Semantics(header: true, child: Text(l10n.lowDataSuggestTitle, style: text.titleSmall)),
                          const SizedBox(height: AppSpacing.xxs),
                          Text(body, style: text.bodySmall!.copyWith(color: c.fg2)),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.xxs),
                Wrap(
                  alignment: WrapAlignment.end,
                  spacing: AppSpacing.xxs,
                  children: [
                    TextButton(
                      style: TextButton.styleFrom(minimumSize: const Size(AppSizes.minTap, AppSizes.minTap)),
                      onPressed: () => ref.read(lowDataSuggestionDismissedProvider.notifier).dismiss(),
                      child: Text(l10n.lowDataNotNow),
                    ),
                    TextButton(
                      style: TextButton.styleFrom(minimumSize: const Size(AppSizes.minTap, AppSizes.minTap)),
                      onPressed: () {
                        ref.read(lowDataModeProvider.notifier).set(true);
                        ScaffoldMessenger.maybeOf(context)
                          ?..hideCurrentSnackBar()
                          ..showSnackBar(SnackBar(content: Text(l10n.lowDataTurnedOn)));
                      },
                      child: Text(l10n.lowDataTurnOn),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
