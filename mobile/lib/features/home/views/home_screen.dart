import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/router/app_navigator.dart';
import '../../../core/data/clock.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/atmosphere.dart';
import '../../../core/widgets/brand_mark.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../core/widgets/motion.dart';
import '../../../core/widgets/not_advice_notice.dart';
import '../../../core/widgets/source_tag.dart';
import '../../../l10n/app_localizations.dart';
import '../../markets/data/market_providers.dart';
import '../../notifications/view_models/notifications_view_model.dart';
import '../../markets/models/fx_sessions.dart';
import '../../workspaces/models/workspace.dart';
import '../../workspaces/view_models/workspaces_view_model.dart';
import '../../workspaces/widgets/workspace_chip.dart';
import '../view_models/watchlist_view_model.dart';
import '../widgets/watchlist_row.dart';

/// تبويب Home: شريط علوي (الجرس + سطر حالة الجلسات)، قائمة المتابعة
/// (أدوات مساحة العمل الفعّالة بسعرها ورسم 24س ورأي النموذج، والـ chip فوقها
/// بيبدّل المساحة)، وسطر إخلاء مسؤولية.
/// كل صف بيفتح شاشة الأداة. السحب للتحديث بيعيد تحميل كل شي.
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  Future<void> _refresh(BuildContext context, WidgetRef ref) async {
    try {
      await ref.read(watchlistViewModelProvider.notifier).refresh();
    } catch (_) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(AppLocalizations.of(context)!.watchlistError)));
    }
  }

  /// ما في أدوات: إذا المساحة الفعّالة خاصة وأدواتها مش متوفرة → زر
  /// "Show all instruments"؛ وإلا القائمة نفسها فاضية (سحب للتحديث)
  Widget _emptyState(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final custom = !(ref.read(activeWorkspaceProvider).valueOrNull?.isDefault ?? true);
    if (!custom) {
      return EmptyState(icon: Icons.show_chart_rounded, title: l10n.watchlistEmpty, message: l10n.watchlistEmptyBody);
    }
    return EmptyState(
      icon: Icons.layers_outlined,
      title: l10n.workspaceEmptyTitle,
      message: l10n.workspaceEmptyBody,
      actionLabel: l10n.workspaceShowAll,
      onAction: () => ref.read(workspacesViewModelProvider.notifier).setActive(Workspace.defaultId),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    final watchlist = ref.watch(homeWatchlistProvider);
    final skeletonRows = ref.watch(activeWorkspaceProvider.select((w) => w.valueOrNull?.symbols.length)) ?? 8;
    final simulated = ref.watch(marketDataRepositoryProvider).isSimulated;

    return Scaffold(
      body: RefreshIndicator(
        onRefresh: () => _refresh(context, ref),
        color: context.colors.accent,
        child: CustomScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          slivers: [
            const SliverToBoxAdapter(child: _HomeHeader()),
            SliverPadding(
              padding: EdgeInsets.fromLTRB(gutter, AppSpacing.md, gutter, AppSpacing.xs),
              sliver: SliverToBoxAdapter(
                child: Row(
                  children: [
                    Expanded(
                      child: Semantics(
                        header: true,
                        child: Text(l10n.watchlist, style: context.textTheme.titleMedium),
                      ),
                    ),
                    if (simulated) const SourceTag(SourceKind.demo),
                  ],
                ),
              ),
            ),
            SliverPadding(
              padding: EdgeInsets.fromLTRB(gutter, 0, gutter, AppSpacing.xs),
              sliver: const SliverToBoxAdapter(
                child: Align(alignment: AlignmentDirectional.centerStart, child: WorkspaceChip()),
              ),
            ),
            SliverPadding(
              padding: EdgeInsets.symmetric(horizontal: gutter),
              sliver: SliverToBoxAdapter(
                child: watchlist.when(
                  skipLoadingOnRefresh: true,
                  loading: () => LoadingRegion(
                    child: _RowsCard(children: [for (var i = 0; i < skeletonRows; i++) const _SkeletonRow()]),
                  ),
                  error: (_, __) => ErrorState(
                    message: l10n.watchlistError,
                    onRetry: ref.read(watchlistViewModelProvider.notifier).retry,
                  ),
                  data: (instruments) => instruments.isEmpty
                      ? _emptyState(context, ref)
                      : _RowsCard(children: [
                          for (final (i, instrument) in instruments.indexed)
                            FadeRise(
                              key: ValueKey(instrument.symbol),
                              index: i,
                              child: WatchlistRow(
                                instrument: instrument,
                                onTap: () {
                                  AppHaptics.selection();
                                  context.pushMarket(instrument.symbol);
                                },
                              ),
                            ),
                        ]),
                ),
              ),
            ),
            SliverPadding(
              padding: EdgeInsets.fromLTRB(gutter, AppSpacing.md, gutter, AppSpacing.xxl),
              sliver: const SliverToBoxAdapter(child: NotAdviceNotice()),
            ),
          ],
        ),
      ),
    );
  }
}

/// الشريط العلوي فوق الـ Atmosphere: الشعار + "Home" + الجرس، وتحته سطر
/// التاريخ وحالة جلسات الفوركس
class _HomeHeader extends ConsumerWidget {
  const _HomeHeader();

  static const double _glyph = 28;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    final now = ref.watch(clockProvider).valueOrNull ?? DateTime.now();
    final unread = ref.watch(unreadNotificationsProvider);
    final date = MaterialLocalizations.of(context).formatMediumDate(now);

    return Atmosphere(
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: EdgeInsetsDirectional.fromSTEB(gutter, AppSpacing.xs, gutter - AppSpacing.xs, AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const ExcludeSemantics(child: BrandGlyph(size: _glyph)),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Semantics(
                      header: true,
                      child: Text(l10n.navHome, style: context.textTheme.displaySmall),
                    ),
                  ),
                  IconButton(
                    onPressed: context.pushNotifications,
                    tooltip: unread > 0 ? l10n.notificationsUnread('$unread') : l10n.notifications,
                    constraints: const BoxConstraints(minWidth: AppSizes.minTap, minHeight: AppSizes.minTap),
                    icon: ExcludeSemantics(
                      child: Badge(
                        isLabelVisible: unread > 0,
                        backgroundColor: c.accent,
                        textColor: c.onAccent,
                        label: Text(unread > 99 ? '99+' : '$unread'),
                        child: Icon(Icons.notifications_none_rounded, color: c.fg, size: AppSizes.iconLg),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.xxs),
              Text(
                '$date · ${fxSessionSummary(l10n, now)}',
                style: context.textTheme.bodySmall!.copyWith(color: c.fg2),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// الصفوف ببطاقة وحدة مفصولة بخطوط رفيعة
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

class _SkeletonRow extends StatelessWidget {
  const _SkeletonRow();

  @override
  Widget build(BuildContext context) {
    return const SizedBox(
      height: WatchlistRow.minHeight,
      child: Padding(
        padding: EdgeInsets.symmetric(horizontal: AppSpacing.md),
        child: Row(
          children: [
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Skeleton(width: AppSpacing.huge * 1.5),
                  SizedBox(height: AppSpacing.xs),
                  Skeleton(width: AppSpacing.huge * 2, height: AppSpacing.sm),
                ],
              ),
            ),
            Skeleton(width: AppSpacing.huge * 1.5),
          ],
        ),
      ),
    );
  }
}
