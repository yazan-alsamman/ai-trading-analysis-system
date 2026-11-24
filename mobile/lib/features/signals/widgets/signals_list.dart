import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/router/app_navigator.dart';
import '../../../core/data/clock.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../core/widgets/motion.dart';
import '../../../l10n/app_localizations.dart';
import '../models/opportunity.dart';
import '../view_models/signals_feed_view_model.dart';
import 'signal_row.dart';
import 'strategy_bar.dart';

/// قائمة الفرص (sliver) بحالاتها: تحميل (هياكل) / فاضية (تعديل الاستراتيجية) /
/// خطأ (حاول مجددًا) / بدون اتصال / الصفوف بدخول متدرّج.
/// الضغط على صف بيفتح تفاصيلها (`context.pushSignalDetail`، Hero على الرمز).
class SignalsList extends ConsumerWidget {
  const SignalsList({super.key});

  /// كم صف هيكل أثناء التحميل
  static const int _skeletonRows = 4;

  /// "حاول مجددًا": الفشل بيرجع يطلع كحالة خطأ، فما في شي نعمله هون
  static Future<void> _retry(WidgetRef ref) async {
    try {
      await ref.read(signalsFeedViewModelProvider.notifier).retry();
    } on Object {
      // الحالة نفسها بتعرض الخطأ
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    final now = ref.watch(clockProvider).valueOrNull ?? DateTime.now();

    Widget fill(Widget child) => SliverFillRemaining(
          hasScrollBody: false,
          child: Padding(padding: EdgeInsets.symmetric(horizontal: gutter), child: child),
        );

    return ref.watch(visibleSignalsProvider).when(
          skipLoadingOnRefresh: true,
          loading: () => SliverPadding(
            padding: EdgeInsets.symmetric(horizontal: gutter),
            sliver: SliverToBoxAdapter(
              child: Semantics(
                label: l10n.loading,
                child: _RowsCard(children: [
                  for (var i = 0; i < _skeletonRows; i++) const SignalRowSkeleton(),
                ]),
              ),
            ),
          ),
          error: (error, _) => fill(
            error is SignalsOfflineException
                ? EmptyState(
                    illustrated: true,
                    icon: Icons.cloud_off_outlined,
                    title: l10n.offlineBannerTitle,
                    message: l10n.signalsOfflineBody,
                    actionLabel: l10n.tryAgain,
                    onAction: () => _retry(ref),
                  )
                : ErrorState(message: l10n.signalsError, onRetry: () => _retry(ref)),
          ),
          data: (signals) => signals.isEmpty
              ? fill(EmptyState(
                  illustrated: true,
                  icon: Icons.insights_outlined,
                  title: l10n.signalsEmptyTitle,
                  message: l10n.signalsEmptyBody,
                  actionLabel: l10n.strategyTitle,
                  onAction: () => StrategyBar.open(context),
                ))
              : SliverPadding(
                  padding: EdgeInsets.symmetric(horizontal: gutter),
                  sliver: SliverToBoxAdapter(child: _rows(context, signals, now)),
                ),
        );
  }

  Widget _rows(BuildContext context, List<Opportunity> signals, DateTime now) => _RowsCard(children: [
        for (final (i, signal) in signals.indexed)
          FadeRise(
            key: ValueKey(signal.id),
            index: i,
            child: SignalRow(
              signal: signal,
              now: now,
              onTap: () => context.pushSignalDetail(signal.id, symbol: signal.symbol),
            ),
          ),
      ]);
}

/// الصفوف ببطاقة وحدة مفصولة بخطوط رفيعة (نفس قائمة المتابعة بالـ Home)
class _RowsCard extends StatelessWidget {
  const _RowsCard({required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Material(
      color: c.card,
      shape: RoundedRectangleBorder(borderRadius: AppRadii.card, side: BorderSide(color: c.hairline)),
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          for (var i = 0; i < children.length; i++) ...[
            if (i > 0) Divider(height: 1, thickness: 1, color: c.hairline, indent: AppSpacing.md),
            children[i],
          ],
        ],
      ),
    );
  }
}
