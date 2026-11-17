import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/shell/widgets/back_to_home_button.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/not_advice_notice.dart';
import '../../../core/widgets/source_tag.dart';
import '../../../l10n/app_localizations.dart';
import '../../markets/data/market_providers.dart';
import '../../markets/widgets/saved_data_status.dart';
import '../data/caching_signals_repository.dart';
import '../view_models/signals_feed_view_model.dart';
import '../widgets/accuracy_line.dart';
import '../widgets/request_analysis_sheet.dart';
import '../widgets/signals_list.dart';
import '../widgets/strategy_bar.dart';

/// تبويب "Signals": زر "Request analysis" بالرأس، سطر دقة النموذج + "Strategy"
/// (الطريقة + الفلاتر)، وتحتهم قائمة الفرص يلي بتطابق الاستراتيجية. السحب
/// للتحديث بيعيد تحميل القائمة.
class SignalsScreen extends ConsumerWidget {
  const SignalsScreen({super.key});

  /// تحديث فاشل بيخلّي القائمة الحالية وبيطلع snackbar
  Future<void> _refresh(BuildContext context, WidgetRef ref) async {
    try {
      await ref.read(signalsFeedViewModelProvider.notifier).refresh();
    } on Object catch (error) {
      if (!context.mounted) return;
      final l10n = AppLocalizations.of(context)!;
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(
          // H5b: فوق الكاش القائمة المحفوظة بتضل، وبتتحدّث لحالها لما يرجع الاتصال
          content: Text(switch (error) {
            SignalsOfflineException() when ref.read(signalsRepositoryProvider) is CachingSignalsRepository =>
              l10n.signalsRefreshOffline,
            SignalsOfflineException() => l10n.signalsOfflineAction,
            _ => l10n.signalsError,
          }),
        ));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    final simulated = ref.watch(signalsRepositoryProvider).isSimulated;

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: RefreshIndicator(
          onRefresh: () => _refresh(context, ref),
          color: context.colors.accent,
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: [
              SliverToBoxAdapter(
                child: TabHeader(
                  title: l10n.navSignals,
                  // مدخل "Request analysis" الوحيد بالتبويب (الأداة بتنختار بالـ sheet)
                  actions: [
                    ConstrainedBox(
                      constraints: BoxConstraints(maxWidth: MediaQuery.sizeOf(context).width * 0.5),
                      child: AppButton.secondary(
                        label: l10n.requestAnalysisTitle,
                        icon: Icons.manage_search_rounded,
                        compact: true,
                        onPressed: () => showRequestAnalysisSheet(context),
                      ),
                    ),
                  ],
                ),
              ),
              SliverPadding(
                padding: EdgeInsets.fromLTRB(gutter, AppSpacing.xs, gutter, 0),
                sliver: const SliverToBoxAdapter(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      AccuracyLine(),
                      SizedBox(height: AppSpacing.md),
                      StrategyBar(),
                    ],
                  ),
                ),
              ),
              SliverPadding(
                padding: EdgeInsets.fromLTRB(gutter, AppSpacing.lg, gutter, AppSpacing.xs),
                sliver: SliverToBoxAdapter(
                  child: Row(
                    children: [
                      Expanded(
                        child: Semantics(
                          header: true,
                          child: Text(l10n.signalsListTitle, style: context.textTheme.titleMedium),
                        ),
                      ),
                      if (simulated) const SourceTag(SourceKind.demo),
                    ],
                  ),
                ),
              ),
              SliverPadding(
                padding: EdgeInsets.fromLTRB(gutter, 0, gutter, AppSpacing.sm),
                sliver: const SliverToBoxAdapter(child: NotAdviceNotice()),
              ),
              // H5b: قائمة محفوظة (بدون اتصال / المصدر فشل) → الشارة + "Last updated"
              SliverPadding(
                padding: EdgeInsets.symmetric(horizontal: gutter),
                sliver: SliverToBoxAdapter(
                  child: SavedDataStatus(
                    updatedAt: ref.watch(signalsFeedViewModelProvider).hasValue
                        ? ref.watch(signalsSavedAtProvider(CachingSignalsRepository.feedKey))
                        : null,
                  ),
                ),
              ),
              const SignalsList(),
              const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.xxl)),
            ],
          ),
        ),
      ),
    );
  }
}
