import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/router/app_navigator.dart';
import '../../../core/data/network_status.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../core/widgets/motion.dart';
import '../../../core/widgets/not_advice_notice.dart';
import '../../../core/widgets/page_header.dart';
import '../../../core/widgets/segment_label.dart';
import '../../../l10n/app_localizations.dart';
import '../../alerts/models/price_alert.dart';
import '../../alerts/view_models/alerts_view_model.dart';
import '../../alerts/widgets/alerts_section.dart';
import '../../markets/data/market_providers.dart';
import '../models/app_notification.dart';
import '../view_models/notifications_view_model.dart';
import '../../../core/database/cache_support.dart';
import '../../markets/widgets/saved_data_status.dart';
import '../data/caching_notifications_repository.dart';
import '../data/notifications_repository.dart';
import '../widgets/notification_row.dart';

enum NotificationsSection { inbox, alerts }

/// مركز الإشعارات (من الجرس بالـ Home): قسمين
/// - Inbox: فلاتر (الكل / تنبيهات سعر / فرص / نظام)، سحب لمقروء أو حذف
///   (مع Undo)، الضغط بيفتح شاشة الأداة.
/// - Alerts: كل تنبيهات السعر لكل الأدوات: "Active" وبعده "History" (اشتغلت /
///   انتهت)، إيقاف / استئناف / "Set again" / حذف + Undo.
class NotificationsScreen extends ConsumerStatefulWidget {
  const NotificationsScreen({super.key});

  @override
  ConsumerState<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends ConsumerState<NotificationsScreen> {
  NotificationsSection _section = NotificationsSection.inbox;

  /// null = الكل
  NotificationKind? _filter;

  Future<void> _markAllRead() async {
    AppHaptics.selection();
    try {
      await ref.read(notificationsViewModelProvider.notifier).markAllRead();
    } catch (_) {
      if (mounted) _showFailed();
    }
  }

  void _showFailed() {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(AppLocalizations.of(context)!.notifActionFailed)));
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    final unread = ref.watch(unreadNotificationsProvider);
    // قسم "Active" بس (السجل ما بينعد)
    final alertCount = ref.watch(activeAlertCountProvider);

    return Scaffold(
      // H5c: شريط "غير متصل" واحد بس = تبع الـ shell (هالشاشة جوّا فرع)
      body: SafeArea(
        bottom: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            PageHeader(
              title: l10n.notifications,
              back: const PageBackButton(),
              actions: [
                if (_section == NotificationsSection.inbox && unread > 0)
                  IconButton(
                    tooltip: l10n.notifMarkAllRead,
                    constraints: const BoxConstraints(minWidth: AppSizes.minTap, minHeight: AppSizes.minTap),
                    icon: Icon(Icons.done_all_rounded, color: context.colors.fg),
                    onPressed: _markAllRead,
                  ),
              ],
            ),
            Padding(
              padding: EdgeInsets.fromLTRB(gutter, 0, gutter, AppSpacing.sm),
              child: SegmentedButton<NotificationsSection>(
                showSelectedIcon: false,
                segments: [
                  ButtonSegment(
                    value: NotificationsSection.inbox,
                    icon: const Icon(Icons.inbox_outlined),
                    label: SegmentLabel(unread > 0 ? l10n.notifInboxCount('$unread') : l10n.notifInbox),
                  ),
                  ButtonSegment(
                    value: NotificationsSection.alerts,
                    icon: const Icon(Icons.notifications_active_outlined),
                    label: SegmentLabel(alertCount > 0 ? l10n.notifAlertsCount('$alertCount') : l10n.notifAlerts),
                  ),
                ],
                selected: {_section},
                onSelectionChanged: (selection) {
                  AppHaptics.selection();
                  setState(() => _section = selection.first);
                },
              ),
            ),
            Expanded(
              child: IndexedStack(
                index: _section.index,
                children: [
                  _Inbox(
                    filter: _filter,
                    onFilter: (kind) => setState(() => _filter = kind),
                    onFailed: _showFailed,
                  ),
                  const _AlertsList(),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Inbox extends ConsumerWidget {
  const _Inbox({required this.filter, required this.onFilter, required this.onFailed});

  final NotificationKind? filter;
  final ValueChanged<NotificationKind?> onFilter;
  final VoidCallback onFailed;

  Future<void> _remove(BuildContext context, WidgetRef ref, AppNotification notification) async {
    final messenger = ScaffoldMessenger.of(context);
    final l10n = AppLocalizations.of(context)!;
    final vm = ref.read(notificationsViewModelProvider.notifier);
    try {
      final removed = await vm.remove(notification.id);
      if (removed == null) return;
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(
          content: Text(l10n.notifDeleted),
          action: SnackBarAction(label: l10n.undo, onPressed: () => vm.undoRemove(removed)),
        ));
    } catch (_) {
      onFailed();
    }
  }

  Future<void> _toggleRead(WidgetRef ref, AppNotification notification) async {
    AppHaptics.selection();
    try {
      await ref.read(notificationsViewModelProvider.notifier).setRead(notification.id, read: !notification.isRead);
    } catch (_) {
      onFailed();
    }
  }

  void _open(BuildContext context, WidgetRef ref, AppNotification notification) {
    ref.read(notificationsViewModelProvider.notifier).setRead(notification.id, read: true).ignore();
    if (notification.symbol case final symbol?) context.pushMarket(symbol);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    final notifications = ref.watch(notificationsViewModelProvider);

    Widget scroll(List<Widget> children) => RefreshIndicator(
          color: context.colors.accent,
          onRefresh: () async {
            try {
              await ref.read(notificationsViewModelProvider.notifier).refresh();
            } on NoSavedDataException {
              // H5b: بدون اتصال القائمة المحفوظة بتضل، وبتتحدّث لحالها لما يرجع الاتصال
              if (!context.mounted) return;
              ScaffoldMessenger.of(context)
                ..hideCurrentSnackBar()
                ..showSnackBar(SnackBar(content: Text(l10n.notificationsRefreshOffline)));
            } catch (_) {
              onFailed();
            }
          },
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: EdgeInsets.fromLTRB(gutter, 0, gutter, AppSpacing.xxl),
            children: children,
          ),
        );

    final chips = _FilterChips(selected: filter, onSelected: onFilter);
    final language = Localizations.localeOf(context).languageCode;
    final status = SavedDataStatus(
      updatedAt: ref.watch(notificationsSavedAtProvider(CachingNotificationsRepository.inboxKey(language))),
    );

    return notifications.when(
      skipLoadingOnRefresh: true,
      loading: () => scroll([
        chips,
        const SizedBox(height: AppSpacing.sm),
        LoadingRegion(child: _RowsCard(children: [for (var i = 0; i < 5; i++) const _SkeletonRow()])),
      ]),
      // H5b: بدون اتصال وما في إشعارات محفوظة → السبب (بتتحمّل لحالها لما يرجع الاتصال)
      error: (error, __) => scroll([
        if (error is NoSavedDataException)
          EmptyState(
            illustrated: true,
            icon: Icons.cloud_off_outlined,
            title: l10n.offlineBannerTitle,
            message: l10n.notificationsOfflineNoCache,
          )
        else
          ErrorState(
            message: l10n.notifLoadError,
            onRetry: () => ref.invalidate(notificationsViewModelProvider),
          ),
      ]),
      data: (all) {
        if (all.isEmpty) {
          return scroll([
            status,
            EmptyState(
              illustrated: true,
              icon: Icons.notifications_none_rounded,
              title: l10n.notifEmptyTitle,
              message: l10n.notifEmptyBody,
            ),
          ]);
        }
        final shown = filter == null
            ? all
            : [
                for (final n in all)
                  if (n.kind == filter) n
              ];
        return scroll([
          // H5b: صندوق محفوظ (بدون اتصال / المصدر فشل) → الشارة + "Last updated"
          status,
          chips,
          const SizedBox(height: AppSpacing.sm),
          if (shown.isEmpty)
            EmptyState(
              icon: filter!.icon,
              title: l10n.notifFilterEmpty(filter!.label(l10n)),
            )
          else
            _RowsCard(children: [
              for (final (i, n) in shown.indexed)
                FadeRise(
                  key: ValueKey(n.id),
                  index: i,
                  child: NotificationRow(
                    notification: n,
                    onTap: () => _open(context, ref, n),
                    onToggleRead: () => _toggleRead(ref, n),
                    onDelete: () => _remove(context, ref, n),
                  ),
                ),
            ]),
          // فرصة (قراءة نموذج) ظاهرة = سطر "مش نصيحة استثمارية" تحت القائمة
          if (shown.any((n) => n.kind == NotificationKind.opportunity)) ...[
            const SizedBox(height: AppSpacing.sm),
            const NotAdviceNotice(),
          ],
        ]);
      },
    );
  }
}

/// فلاتر النوع - سكرول أفقي حتى بالخط الكبير ما بتنكسر لسطرين
class _FilterChips extends StatelessWidget {
  const _FilterChips({required this.selected, required this.onSelected});

  final NotificationKind? selected;
  final ValueChanged<NotificationKind?> onSelected;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final options = <(NotificationKind?, String)>[
      (null, l10n.filterAll),
      for (final kind in NotificationKind.values) (kind, kind.label(l10n)),
    ];
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      clipBehavior: Clip.none,
      child: Row(
        children: [
          for (final (i, (kind, label)) in options.indexed) ...[
            if (i > 0) const SizedBox(width: AppSpacing.xs),
            ChoiceChip(
              label: Text(label),
              selected: selected == kind,
              showCheckmark: false,
              materialTapTargetSize: MaterialTapTargetSize.padded,
              onSelected: (_) {
                if (selected == kind) return;
                AppHaptics.selection();
                onSelected(kind);
              },
            ),
          ],
        ],
      ),
    );
  }
}

/// كل تنبيهات السعر (كل الأدوات)
class _AlertsList extends ConsumerWidget {
  const _AlertsList();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    final alerts = ref.watch(alertsViewModelProvider);
    final offline = ref.watch(networkStatusProvider) == NetworkStatus.offline;

    // بدون اتصال الأسعار واقفة، فالتنبيهات ما بتنفحص لحد ما ترجع
    Widget scroll(List<Widget> children) => ListView(
          padding: EdgeInsets.fromLTRB(gutter, 0, gutter, AppSpacing.xxl),
          children: [
            if (offline)
              Padding(
                padding: const EdgeInsetsDirectional.only(start: AppSpacing.xxs, bottom: AppSpacing.sm),
                child: Semantics(
                  liveRegion: true,
                  child: Text(l10n.alertsOffline, style: context.textTheme.bodyMedium),
                ),
              ),
            ...children,
          ],
        );

    return alerts.when(
      loading: () => scroll([
        LoadingRegion(child: _RowsCard(children: [for (var i = 0; i < 3; i++) const _SkeletonRow()])),
      ]),
      error: (_, __) => scroll([ErrorState(onRetry: () => ref.invalidate(alertsViewModelProvider))]),
      data: (list) => list.isEmpty
          ? scroll([
              EmptyState(
                illustrated: true,
                icon: Icons.notifications_off_outlined,
                title: l10n.alertsEmptyTitle,
                message: l10n.alertsEmptyBody,
              ),
            ])
          : scroll([
              Padding(
                padding: const EdgeInsetsDirectional.only(start: AppSpacing.xxs, bottom: AppSpacing.sm),
                child: Text(l10n.alertsHint, style: context.textTheme.bodySmall),
              ),
              AlertSections(
                alerts: list,
                showEmptyActive: true,
                rowBuilder: (alert) => FadeRise(index: list.indexOf(alert), child: _AlertListRow(alert: alert)),
              ),
            ]),
    );
  }
}

class _AlertListRow extends ConsumerWidget {
  const _AlertListRow({required this.alert});

  final PriceAlert alert;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final instrument = ref.watch(instrumentProvider(alert.symbol));
    if (instrument == null) return const _SkeletonRow();
    return AlertRow(
      alert: alert,
      instrument: instrument,
      showSymbol: true,
      onTap: () => context.pushMarket(alert.symbol),
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
            if (i > 0) Divider(height: 1, thickness: 1, color: c.hairline),
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
    return const Padding(
      padding: EdgeInsets.all(AppSpacing.md),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Skeleton(width: AppSpacing.xxl, height: AppSpacing.xxl, radius: AppRadii.field),
          SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Skeleton(width: AppSpacing.huge * 3),
                SizedBox(height: AppSpacing.xs),
                Skeleton(height: AppSpacing.sm),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
