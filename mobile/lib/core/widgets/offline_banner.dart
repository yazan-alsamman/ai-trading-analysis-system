import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../l10n/app_localizations.dart';
import '../data/network_status.dart';
import '../theme/theme_context.dart';

/// شريط رفيع فوق شريط التنقل: "غير متصل · نعرض آخر بيانات وصلت"
///
/// بيضل ظاهر لحد ما يرجع الاتصال (مش قابل للإغلاق)، وبيختفي بدون أثر
/// لما الجهاز متصل.
class OfflineBanner extends ConsumerWidget {
  const OfflineBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final offline = ref.watch(networkStatusProvider) == NetworkStatus.offline;

    return AnimatedSize(
      duration: context.motion(AppMotion.base),
      curve: AppMotion.out,
      alignment: Alignment.bottomCenter,
      child: AnimatedSwitcher(
        duration: context.motion(AppMotion.base),
        switchInCurve: AppMotion.out,
        switchOutCurve: AppMotion.exit,
        child: offline
            ? const _OfflineRow(key: ValueKey('offline'))
            : const SizedBox(key: ValueKey('online'), width: double.infinity),
      ),
    );
  }
}

class _OfflineRow extends StatelessWidget {
  const _OfflineRow({super.key});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);

    return Semantics(
      liveRegion: true,
      container: true,
      child: Material(
        // اللون الـ soft شفاف - منركّبه فوق سطح شريط التنقل
        color: Color.alphaBlend(c.warningSoft, c.raised),
        child: Padding(
          padding: EdgeInsets.symmetric(horizontal: gutter),
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: AppSizes.minTap),
            child: Row(
              children: [
                Icon(Icons.cloud_off_rounded, size: AppSizes.iconMd, color: c.warning),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
                    child: Text.rich(
                      TextSpan(children: [
                        TextSpan(
                          text: '${l10n.offlineBannerTitle}  ',
                          style: text.labelLarge!.copyWith(color: c.warning),
                        ),
                        TextSpan(
                          text: l10n.offlineBannerBody,
                          style: text.bodySmall!.copyWith(color: c.fg2),
                        ),
                      ]),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
