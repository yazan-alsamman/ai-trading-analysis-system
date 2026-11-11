import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/headings.dart';
import '../../../l10n/app_localizations.dart';
import '../../markets/data/market_providers.dart';
import '../../markets/models/market_models.dart';
import '../models/price_alert.dart';
import '../view_models/alerts_view_model.dart';

/// تنبيهات هالأداة بشاشة السوق (بتطلع بس إذا في تنبيهات): قسم "Active" وبعده
/// "History"، سحب للحذف مع Undo، وزر حسب حالة التنبيه.
class AlertsSection extends ConsumerWidget {
  const AlertsSection({super.key, required this.instrument});

  final Instrument instrument;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final alerts = ref.watch(alertsForSymbolProvider(instrument.symbol)).valueOrNull ?? const [];
    if (alerts.isEmpty) return const SizedBox.shrink();
    final l10n = AppLocalizations.of(context)!;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsetsDirectional.only(start: AppSpacing.xxs, bottom: AppSpacing.xs),
          child: Semantics(header: true, child: Eyebrow(l10n.yourAlerts)),
        ),
        AlertSections(alerts: alerts, rowBuilder: (alert) => AlertRow(alert: alert, instrument: instrument)),
      ],
    );
  }
}

/// القسمين: "Active" (نشطة + موقوفة) وبعده "History" (اشتغلت + انتهت، الأحدث
/// أول). قسم فاضي ما بيطلع، إلا "Active" لما [showEmptyActive] (قائمة الإشعارات).
/// بيعلن للقارئ الصوتي لما تنبيه ظاهر بيشتغل أو بينتهي.
class AlertSections extends ConsumerWidget {
  const AlertSections({super.key, required this.alerts, required this.rowBuilder, this.showEmptyActive = false});

  final List<PriceAlert> alerts;
  final Widget Function(PriceAlert alert) rowBuilder;
  final bool showEmptyActive;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final text = context.textTheme;
    final ids = {for (final a in alerts) a.id};
    ref.listen<AsyncValue<List<PriceAlert>>>(alertsViewModelProvider, (previous, next) {
      final before = {for (final a in previous?.valueOrNull ?? const <PriceAlert>[]) a.id: a.status};
      for (final a in next.valueOrNull ?? const <PriceAlert>[]) {
        final was = before[a.id];
        if (!ids.contains(a.id) || was == null || was == a.status || !a.status.isHistory) continue;
        _announce(context, ref, a);
      }
    });

    final split = splitAlerts(alerts);
    Widget heading(String title) => Padding(
          padding: const EdgeInsetsDirectional.only(start: AppSpacing.xxs, bottom: AppSpacing.xs),
          child: Semantics(header: true, child: Text(title, style: text.titleSmall!.copyWith(color: context.colors.fg2))),
        );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (split.active.isNotEmpty || showEmptyActive) heading(l10n.alertsActiveHeading),
        if (split.active.isNotEmpty)
          AlertRowsCard(children: [for (final a in split.active) KeyedSubtree(key: ValueKey(a.id), child: rowBuilder(a))])
        else if (showEmptyActive)
          Padding(
            padding: const EdgeInsetsDirectional.only(start: AppSpacing.xxs),
            child: Text(l10n.alertsNoActive, style: text.bodyMedium),
          ),
        if (split.history.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.md),
          heading(l10n.alertsHistoryHeading),
          AlertRowsCard(children: [for (final a in split.history) KeyedSubtree(key: ValueKey(a.id), child: rowBuilder(a))]),
        ],
      ],
    );
  }

  void _announce(BuildContext context, WidgetRef ref, PriceAlert alert) {
    // الشاشة المغطّاة بشاشة تانية ما بتعلن (ما في إعلان مكرّر)
    if (!context.mounted || !(ModalRoute.of(context)?.isCurrent ?? true)) return;
    final l10n = AppLocalizations.of(context)!;
    final instrument = ref.read(instrumentProvider(alert.symbol));
    String format(double v) => instrument?.format(v) ?? v.toString();
    final rule = '${alert.symbol} · ${alertRuleText(l10n, alert, format)}';
    SemanticsService.sendAnnouncement(
      View.of(context),
      '$rule: ${alert.state.label(l10n, format)}',
      Directionality.of(context),
    );
  }
}

/// الصفوف ببطاقة وحدة مفصولة بخطوط رفيعة
class AlertRowsCard extends StatelessWidget {
  const AlertRowsCard({super.key, required this.children});

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

/// "Rises to 1.09000" / "Falls to 1.08000"
String alertRuleText(AppLocalizations l10n, PriceAlert alert, String Function(double) format) =>
    alert.condition.isRising ? l10n.alertRowRises(format(alert.value)) : l10n.alertRowFalls(format(alert.value));

/// وقت بالتنبيه: "Oct 21 14:05" (توقيت الجهاز)
String alertTime(BuildContext context, DateTime time) {
  final local = time.toLocal();
  return '${MaterialLocalizations.of(context).formatShortMonthDay(local)} ${Formatters.clock(local)}';
}

/// صف تنبيه واحد: القاعدة + الحالة (ووقتها)، سحب للحذف (مع Undo) من أي حالة،
/// إيقاف/استئناف للنشط، و"Set again" لـ يلي اشتغل.
/// [showSymbol] لما القائمة فيها أكتر من أداة (الإشعارات → Alerts).
class AlertRow extends ConsumerWidget {
  const AlertRow({
    super.key,
    required this.alert,
    required this.instrument,
    this.showSymbol = false,
    this.onTap,
  });

  final PriceAlert alert;
  final Instrument instrument;
  final bool showSymbol;
  final VoidCallback? onTap;

  void _failed(BuildContext context) {
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(AppLocalizations.of(context)!.alertActionFailed)),
    );
  }

  Future<void> _delete(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    final l10n = AppLocalizations.of(context)!;
    final vm = ref.read(alertsViewModelProvider.notifier);
    try {
      final removed = await vm.remove(alert.id);
      if (removed == null) return;
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(
          content: Text(l10n.alertDeleted),
          // بيرجع بحالته المحفوظة (اشتغل / انتهى / موقوف...)، مش Active جديد
          action: SnackBarAction(label: l10n.undo, onPressed: () => vm.undoRemove(removed)),
        ));
    } catch (_) {
      if (context.mounted) _failed(context);
    }
  }

  Future<void> _setAgain(BuildContext context, WidgetRef ref) async {
    AppHaptics.selection();
    final messenger = ScaffoldMessenger.of(context);
    final l10n = AppLocalizations.of(context)!;
    try {
      final created = await ref
          .read(alertsViewModelProvider.notifier)
          .setAgain(alert, current: ref.read(quoteProvider(alert.symbol)));
      if (created == null) return;
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(l10n.alertCreated(created.symbol, instrument.format(created.value)))));
    } catch (_) {
      if (context.mounted) _failed(context);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;
    final state = alert.state;
    final condition = alertRuleText(l10n, alert, instrument.format);
    final rule = showSymbol ? '${instrument.symbol} · $condition' : condition;
    final canPause = state.actions.contains(AlertAction.pause);
    final canResume = state.actions.contains(AlertAction.resume);
    final canSetAgain = state.actions.contains(AlertAction.setAgain);
    final time = state.time(alert);
    final details = [
      state.label(l10n, instrument.format),
      if (time != null) alert.status.isHistory ? alertTime(context, time) : l10n.alertUntil(alertTime(context, time)),
      if (alert.isActive && !alert.armed) l10n.alertWaitsForCross,
      if (alert.note case final note?) note,
    ];

    final background = ColoredBox(
      color: c.dangerSoft,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
        child: Row(
          children: [
            Icon(Icons.delete_outline_rounded, color: c.danger),
            const Spacer(),
            Icon(Icons.delete_outline_rounded, color: c.danger),
          ],
        ),
      ),
    );

    return Dismissible(
      key: ValueKey('dismiss-${alert.id}'),
      background: background,
      onDismissed: (_) => _delete(context, ref),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Semantics(
            // الحالة أول شي بعد القاعدة: "Active" / "Triggered at 1.09012" / "Expired"
            label: l10n.alertRowLabel(rule, details.join('. ')),
            customSemanticsActions: {
              CustomSemanticsAction(label: l10n.alertDelete): () => _delete(context, ref),
            },
            child: InkWell(
              onTap: onTap,
              child: ConstrainedBox(
                constraints: const BoxConstraints(minHeight: AppSizes.minTap + AppSpacing.md),
                child: Padding(
                  padding: const EdgeInsetsDirectional.only(start: AppSpacing.md, end: AppSpacing.xxs),
                  child: Row(
                    children: [
                      Expanded(
                        child: ExcludeSemantics(
                          child: Padding(
                            padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text(rule, style: text.titleSmall),
                                const SizedBox(height: 2),
                                Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Icon(state.icon, size: AppSizes.iconSm, color: state.color(c)),
                                    const SizedBox(width: AppSpacing.xxs),
                                    Flexible(child: Text(details.join(' · '), style: text.bodySmall)),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                      if (canPause || canResume)
                        IconButton(
                          tooltip: canPause ? l10n.alertPause : l10n.alertResume,
                          constraints: const BoxConstraints(minWidth: AppSizes.minTap, minHeight: AppSizes.minTap),
                          icon: Icon(
                            canPause ? Icons.pause_circle_outline_rounded : Icons.play_circle_outline_rounded,
                            color: c.fg2,
                          ),
                          onPressed: () async {
                            AppHaptics.selection();
                            try {
                              await ref.read(alertsViewModelProvider.notifier).setActive(alert.id, active: !canPause);
                            } catch (_) {
                              if (context.mounted) _failed(context);
                            }
                          },
                        ),
                    ],
                  ),
                ),
              ),
            ),
          ),
          // تحت النص (مش جنبه): بالخط الكبير ما بيعصر القاعدة
          if (canSetAgain)
            Padding(
              padding: const EdgeInsetsDirectional.only(start: AppSpacing.xs, bottom: AppSpacing.xs),
              child: Align(
                alignment: AlignmentDirectional.centerStart,
                child: TextButton.icon(
                  style: TextButton.styleFrom(minimumSize: const Size(AppSizes.minTap, AppSizes.minTap)),
                  icon: const Icon(Icons.replay_rounded, size: AppSizes.iconMd),
                  label: Text(l10n.alertSetAgain),
                  onPressed: () => _setAgain(context, ref),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
