import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/router/app_navigator.dart';
import '../../../core/data/clock.dart';
import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/direction_badge.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../core/widgets/headings.dart';
import '../../../core/widgets/motion.dart';
import '../../../core/widgets/not_advice_notice.dart';
import '../../../core/widgets/page_header.dart';
import '../../../core/widgets/source_tag.dart';
import '../../../l10n/app_localizations.dart';
import '../../alerts/widgets/set_alert_sheet.dart';
import '../../../core/data/low_data_mode.dart';
import '../../markets/data/caching_market_data_repository.dart';
import '../../markets/data/market_providers.dart';
import '../../markets/widgets/saved_data_status.dart';
import '../data/caching_signals_repository.dart';
import '../../markets/view_models/market_view_model.dart';
import '../../markets/widgets/market_hero.dart';
import '../../markets/widgets/price_chart.dart';
import '../../risk/widgets/size_trade_sheet.dart';
import '../models/opportunity.dart';
import '../models/signal_detail.dart';
import '../models/signal_rationale.dart';
import '../view_models/signal_detail_view_model.dart';
import '../view_models/signals_feed_view_model.dart';
import '../widgets/method_picker.dart';
import '../widgets/request_analysis_sheet.dart' show noSetupReasonText;
import '../widgets/signal_row.dart';

/// تفاصيل إشارة (من قائمة Signals): الاتجاه + الاحتمال + الصلاحية، الخطة
/// (دخول / هدف / وقف + البعد بالنقاط + العائد : المخاطرة)، رسم صغير بمناطق
/// الخطة، ليش النموذج شايف هيك، والإجراءات (احسب الحجم، تنبيه، افتح السوق).
///
/// إشارة بتخلص والشاشة مفتوحة بتضل ظاهرة ومعلّمة "منتهية" (مؤقّت الـ ViewModel)،
/// وما عاد في "احسب حجم الصفقة" على مستويات قديمة.
class SignalDetailScreen extends ConsumerWidget {
  const SignalDetailScreen({super.key, required this.signalId, required this.symbol});

  final String signalId;

  /// من الصف يلي فتحها: العنوان (Hero) بيطلع من أول إطار
  final String symbol;

  /// "حاول مجددًا": الفشل بيرجع يطلع كحالة، فما في شي نعمله هون
  Future<void> _retry(WidgetRef ref) async {
    try {
      await ref.read(signalDetailViewModelProvider(signalId).notifier).retry();
    } on Object {
      // الحالة نفسها بتعرض الخطأ
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final state = ref.watch(signalDetailViewModelProvider(signalId));

    Widget centered(Widget child) => Center(child: SingleChildScrollView(child: child));

    final body = state.when(
      skipLoadingOnRefresh: false,
      loading: () => const _LoadingBody(),
      error: (error, _) => centered(
        error is SignalsOfflineException
            ? EmptyState(
                illustrated: true,
                icon: Icons.cloud_off_outlined,
                title: l10n.offlineBannerTitle,
                message: l10n.signalsOfflineBody,
                actionLabel: l10n.tryAgain,
                onAction: () => _retry(ref),
              )
            : ErrorState(message: l10n.signalDetailError, onRetry: () => _retry(ref)),
      ),
      data: (detail) => detail == null
          ? centered(EmptyState(
              illustrated: true,
              icon: Icons.search_off_rounded,
              title: l10n.signalNotFoundTitle,
              message: l10n.signalNotFoundBody,
              actionLabel: l10n.backToSignals,
              onAction: () => Navigator.of(context).maybePop(),
            ))
          : _DetailBody(detail: detail),
    );

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _Header(signalId: signalId, symbol: symbol),
            // H5b: إشارة محفوظة (بدون اتصال / المصدر فشل) → الشارة + "Last updated"
            if (state.valueOrNull != null)
              Padding(
                padding: EdgeInsets.symmetric(horizontal: AppSpacing.gutter(context)),
                child: SavedDataStatus(
                  updatedAt: ref.watch(signalsSavedAtProvider(CachingSignalsRepository.itemKey(signalId))),
                ),
              ),
            Expanded(child: body),
          ],
        ),
      ),
    );
  }
}

/// سهم الرجوع + الرمز (Hero من صف القائمة) + الاسم الكامل
class _Header extends StatelessWidget {
  const _Header({required this.signalId, required this.symbol});

  final String signalId;
  final String symbol;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    return Padding(
      padding: EdgeInsetsDirectional.fromSTEB(gutter - AppSpacing.sm, AppSpacing.xs, gutter, AppSpacing.xs),
      child: Row(
        children: [
          const PageBackButton(),
          const SizedBox(width: AppSpacing.xxs),
          Expanded(
            child: Semantics(
              header: true,
              label: '$symbol, ${l10n.instrumentName(symbol)}',
              excludeSemantics: true,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  // مع تقليل الحركة MarketSymbolHero ما بيطير (HeroMode جوّاته)
                  MarketSymbolHero(
                    symbol: symbol,
                    style: context.textTheme.titleLarge!,
                    heroTag: SignalRow.heroTag(signalId),
                  ),
                  Text(l10n.instrumentName(symbol), style: context.textTheme.bodySmall),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _LoadingBody extends StatelessWidget {
  const _LoadingBody();

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    return Semantics(
      label: l10n.loading,
      child: ListView(
        padding: EdgeInsets.fromLTRB(gutter, AppSpacing.xs, gutter, AppSpacing.xxl),
        children: const [
          Skeleton(width: AppSpacing.huge * 3, height: AppSpacing.xl),
          SizedBox(height: AppSpacing.xs),
          Skeleton(width: AppSpacing.huge * 4),
          SizedBox(height: AppSpacing.lg),
          Skeleton(height: AppSpacing.huge * 3, radius: AppRadii.card),
          SizedBox(height: AppSpacing.md),
          Skeleton(height: PriceChart.compactHeight, radius: AppRadii.card),
        ],
      ),
    );
  }
}

class _DetailBody extends ConsumerWidget {
  const _DetailBody({required this.detail});

  final SignalDetail detail;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final gutter = AppSpacing.gutter(context);
    final sections = [
      _Summary(detail: detail),
      if (detail.expired) _ExpiredNotice(detail: detail),
      _PlanCard(detail: detail),
      _PlanChart(detail: detail),
      _WhyCard(detail: detail),
      _Actions(detail: detail),
      const NotAdviceNotice(),
    ];
    return ListView(
      padding: EdgeInsets.fromLTRB(gutter, AppSpacing.xs, gutter, AppSpacing.xxl),
      children: [
        for (final (i, section) in sections.indexed) ...[
          if (i > 0) const SizedBox(height: AppSpacing.md),
          // مفتاح بالنوع: لما "Expired" ينضاف فوق، الأقسام تحت (والرسم) بيحافظوا على حالتهم
          FadeRise(key: ValueKey(section.runtimeType), index: i, child: section),
        ],
      ],
    );
  }
}

/// الاتجاه (سهم + كلمة) + الاحتمال (بنفسجي = النموذج) + الإطار + المصدر،
/// وتحتهن عمرها وصلاحيتها (أو "منتهية")
class _Summary extends ConsumerWidget {
  const _Summary({required this.detail});

  final SignalDetail detail;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final signal = detail.signal;
    final simulated = ref.watch(signalsRepositoryProvider).isSimulated;
    final now = ref.watch(clockProvider).valueOrNull ?? DateTime.now();
    final probability = Formatters.percent(signal.probability);
    final generated = l10n.signalGenerated(relativeTime(l10n, signal.generatedAt, now));
    final validity = l10n.validUntil(Formatters.clock(detail.validUntil.toLocal()));
    final methodName = watchMethodName(ref, context, detail.methodId);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Semantics(
          container: true,
          label: l10n.signalSummaryLabel(signal.direction.label(l10n), probability, signal.timeframe.label),
          excludeSemantics: true,
          child: Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.xs,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              DirectionBadge(signal.direction),
              Text(
                probability,
                style: context.type.numLarge.copyWith(color: c.forecast),
                textDirection: TextDirection.ltr,
              ),
              Text(signal.timeframe.label, style: context.type.numSmall),
            ],
          ),
        ),
        Text(l10n.probabilityCaption, style: context.textTheme.bodySmall),
        const SizedBox(height: AppSpacing.sm),
        Wrap(
          spacing: AppSpacing.xs,
          runSpacing: AppSpacing.xs,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            if (detail.expired) const _ExpiredBadge(),
            Text(
              detail.expired ? generated : '$generated · $validity',
              style: context.textTheme.labelMedium!.copyWith(color: c.fg3),
            ),
            SourceTag(simulated ? SourceKind.demo : SourceKind.model),
            if (signal.requestedByYou) const RequestedTag(),
          ],
        ),
        if (methodName != null) ...[
          const SizedBox(height: AppSpacing.xs),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ExcludeSemantics(child: Icon(Icons.tune_rounded, size: AppSizes.iconSm, color: c.accent)),
              const SizedBox(width: AppSpacing.xs),
              Expanded(
                child: Text(l10n.strategyUsed(methodName), style: context.textTheme.labelMedium!.copyWith(color: c.fg)),
              ),
            ],
          ),
        ],
      ],
    );
  }
}

/// شارة "منتهية": أيقونة + كلمة (مش اللون لحالو)
class _ExpiredBadge extends StatelessWidget {
  const _ExpiredBadge();

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return DecoratedBox(
      decoration: BoxDecoration(color: c.warningSoft, borderRadius: AppRadii.badge),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xs, vertical: AppSpacing.xxs / 2),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.history_toggle_off_rounded, size: AppSizes.iconSm - 2, color: c.warning),
            const SizedBox(width: AppSpacing.xxs),
            Text(
              AppLocalizations.of(context)!.signalExpiredBadge,
              style: context.textTheme.labelSmall!.copyWith(color: c.warning),
            ),
          ],
        ),
      ),
    );
  }
}

/// ملاحظة الانتهاء: المستويات قديمة، الرأي الحالي بشاشة السوق. بتنعلن للقارئ
/// الصوتي لما المؤقّت يقلبها والشاشة مفتوحة.
class _ExpiredNotice extends StatelessWidget {
  const _ExpiredNotice({required this.detail});

  final SignalDetail detail;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    return Semantics(
      liveRegion: true,
      container: true,
      child: AppCard(
        color: c.warningSoft,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ExcludeSemantics(child: Icon(Icons.history_toggle_off_rounded, color: c.warning)),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(l10n.signalExpiredTitle, style: context.textTheme.titleSmall),
                  const SizedBox(height: AppSpacing.xxs),
                  Text(
                    l10n.signalExpiredBody(Formatters.clock(detail.validUntil.toLocal())),
                    style: context.textTheme.bodyMedium,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// الدخول (منطقة) / الهدف / الوقف (منتصف منطقتهن + البعد بالنقاط) + العائد : المخاطرة.
/// علامة + كلمة + رقم، أبدًا اللون لحالو.
class _PlanCard extends StatelessWidget {
  const _PlanCard({required this.detail});

  final SignalDetail detail;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final plan = detail.plan;
    final instrument = detail.instrument;
    String pips(double value) => l10n.signalPipsAway(Formatters.trimZeros(value.toStringAsFixed(1)));

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Semantics(header: true, child: Eyebrow(l10n.signalPlanTitle)),
          const SizedBox(height: AppSpacing.xs),
          _PlanLine(
            marker: c.accent,
            label: l10n.zoneEntry,
            value: '${instrument.format(plan.entry.low)} – ${instrument.format(plan.entry.high)}',
          ),
          _PlanLine(
            marker: c.up,
            label: l10n.zoneTarget,
            value: instrument.format(plan.target),
            detail: pips(plan.targetPips),
          ),
          _PlanLine(
            marker: c.down,
            label: l10n.zoneStop,
            value: instrument.format(plan.stop),
            detail: pips(plan.stopPips),
          ),
          _PlanLine(label: l10n.riskRewardLabel, value: '1 : ${plan.riskReward.toStringAsFixed(1)}'),
        ],
      ),
    );
  }
}

class _PlanLine extends StatelessWidget {
  const _PlanLine({required this.label, required this.value, this.marker, this.detail});

  final Color? marker;
  final String label;
  final String value;

  /// البعد عن الدخول (للهدف والوقف)
  final String? detail;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Semantics(
      container: true,
      label: [label, value, if (detail != null) detail!].join(', '),
      excludeSemantics: true,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: AppSpacing.xxs,
              height: AppSpacing.md,
              margin: const EdgeInsets.only(top: 2),
              decoration: BoxDecoration(color: marker, borderRadius: AppRadii.badge),
            ),
            const SizedBox(width: AppSpacing.xs),
            // بالخط الكبير القيمة بتنزل تحت التسمية بدل ما تطلع برا الكرت
            Expanded(
              child: Wrap(
                alignment: WrapAlignment.spaceBetween,
                spacing: AppSpacing.sm,
                children: [
                  Text(label, style: context.textTheme.bodyMedium),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        value,
                        style: context.type.numSmall.copyWith(color: c.fg),
                        textDirection: TextDirection.ltr,
                      ),
                      if (detail != null) Text(detail!, style: context.textTheme.labelSmall),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// رسم صغير على إطار الإشارة مع مناطق الخطة (نفس رسم شاشة السوق، بدون أدوات:
/// الأدوات والمؤشرات بشاشة السوق)
class _PlanChart extends ConsumerWidget {
  const _PlanChart({required this.detail});

  final SignalDetail detail;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final key = (detail.symbol, detail.signal.timeframe);
    final candles = ref.watch(liveCandlesProvider(key));

    Widget box(String id, Widget child) => SizedBox(
          key: ValueKey(id),
          height: PriceChart.compactHeight,
          child: Center(child: SingleChildScrollView(child: child)),
        );

    return AppCard(
      padding: const EdgeInsets.fromLTRB(AppSpacing.sm, AppSpacing.sm, AppSpacing.xs, AppSpacing.sm),
      child: AnimatedSwitcher(
        duration: context.motion(AppMotion.base),
        child: candles.when(
          skipLoadingOnRefresh: true,
          loading: () => const Skeleton(
            key: ValueKey('loading'),
            height: PriceChart.compactHeight,
            radius: AppRadii.card,
          ),
          // H5b: بدون اتصال وهالرسم مش محفوظ → نفس شرح شاشة السوق (بيتحمّل لحالو)
          error: (error, __) => box(
            'error',
            error is MarketOfflineException
                ? EmptyState(icon: Icons.cloud_off_outlined, title: l10n.offlineBannerTitle, message: l10n.chartOfflineNoCache)
                : ErrorState(message: l10n.chartError, onRetry: () => ref.invalidate(liveCandlesProvider(key))),
          ),
          data: (list) => list.isEmpty
              ? box('empty', EmptyState(icon: Icons.candlestick_chart_outlined, title: l10n.chartEmpty))
              : PriceChart(
                  key: const ValueKey('chart'),
                  candles: list,
                  instrument: detail.instrument,
                  timeframe: detail.signal.timeframe,
                  chartType: ChartType.candles,
                  indicators: const {},
                  read: detail.signal,
                  height: PriceChart.compactHeight,
                  animated: !ref.watch(lowDataModeProvider),
                ),
        ),
      ),
    );
  }
}

/// "ليش النموذج شايف هيك": جمل قصيرة بكلام احتمالات
/// "ليش النموذج شايف هيك": أقوى [kTopReasons] أسباب أول (القائمة جاية مرتّبة)،
/// والباقي ورا زر "أسباب أخرى (N)" / "أسباب أقل".
class _WhyCard extends StatefulWidget {
  const _WhyCard({required this.detail});

  final SignalDetail detail;

  @override
  State<_WhyCard> createState() => _WhyCardState();
}

class _WhyCardState extends State<_WhyCard> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final detail = widget.detail;
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;

    (IconData, Color, String) item(SignalReason reason) => switch (reason) {
          AgreementReason(:final agreeing, :final analysed) => (
              Icons.layers_outlined,
              c.fg2,
              l10n.reasonAgreement('$agreeing', '$analysed')
            ),
          final ChanceReason r => (Icons.pie_chart_outline_rounded, c.forecast, l10n.reasonChance('${r.outOfTen}')),
          RewardRiskReason(:final ratio) => (
              Icons.straighten_rounded,
              c.fg2,
              l10n.reasonRewardRisk(Formatters.trimZeros(ratio.toStringAsFixed(1))),
            ),
          VolatilityReason(:final level) => level == RiskLevel.high
              ? (Icons.waves_rounded, c.fg2, l10n.reasonVolatilityHigh)
              : (Icons.water_rounded, c.fg2, l10n.reasonVolatilityLow),
          MaCrossReason(:final direction, :final timeframe) => direction == SignalDirection.short
              ? (Icons.trending_down_rounded, c.down, l10n.reasonMaCrossDown(timeframe.label))
              : (Icons.trending_up_rounded, c.up, l10n.reasonMaCrossUp(timeframe.label)),
          RsiReason(:final direction, :final timeframe, :final value) => direction == SignalDirection.short
              ? (Icons.south_east_rounded, c.down, l10n.reasonRsiOverbought(value.toStringAsFixed(0), timeframe.label))
              : (Icons.north_east_rounded, c.up, l10n.reasonRsiOversold(value.toStringAsFixed(0), timeframe.label)),
          final NoSetupReason r => (Icons.remove_rounded, c.fg2, noSetupReasonText(l10n, r)),
        };

    final all = detail.rationale;
    final hidden = all.length - kTopReasons;
    final shown = _expanded || hidden <= 0 ? all : all.take(kTopReasons);

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Semantics(header: true, child: Eyebrow(l10n.signalWhyTitle)),
          const SizedBox(height: AppSpacing.xs),
          for (final reason in shown)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: AppSpacing.xxs),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  ExcludeSemantics(child: Icon(item(reason).$1, size: AppSizes.iconMd, color: item(reason).$2)),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(item(reason).$3, style: context.textTheme.bodyMedium),
                        // درجة التأثير (من ترتيب القوة نفسه): كلمة، مش لون
                        Text(
                          l10n.reasonInfluenceLabel(influenceText(l10n, reason.influence)),
                          style: context.textTheme.labelSmall!.copyWith(color: c.fg3),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          if (hidden > 0)
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: AppButton.ghost(
                label: _expanded ? l10n.reasonsShowLess : l10n.reasonsShowMore('$hidden'),
                trailingIcon: _expanded ? Icons.expand_less_rounded : Icons.expand_more_rounded,
                compact: true,
                onPressed: () => setState(() => _expanded = !_expanded),
              ),
            ),
        ],
      ),
    );
  }
}

/// الإجراءات: "احسب حجم الصفقة" (الرئيسي، بس للإشارة الصالحة)، "ضبط تنبيه"،
/// "افتح السوق" (بيصير الرئيسي لما تنتهي)، كل واحد بعرض الشاشة. التطبيق ما بينفّذ ولا أمر.
class _Actions extends StatelessWidget {
  const _Actions({required this.detail});

  final SignalDetail detail;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final instrument = detail.instrument;
    void openMarket() => context.pushMarket(detail.symbol);
    final alert = AppButton.secondary(
      label: l10n.setAlert,
      icon: Icons.add_alert_outlined,
      expand: true,
      onPressed: () => setAlertAndConfirm(context, instrument: instrument),
    );

    final Widget primary;
    final List<Widget> secondary;
    if (detail.expired) {
      primary = AppButton(
        label: l10n.openMarket,
        icon: Icons.candlestick_chart_outlined,
        expand: true,
        onPressed: openMarket,
      );
      secondary = [alert];
    } else {
      primary = AppButton(
        label: l10n.sizeTrade,
        icon: Icons.calculate_outlined,
        expand: true,
        onPressed: () => showSizeTradeSheet(context, instrument: instrument, read: detail.signal),
      );
      secondary = [
        alert,
        AppButton.secondary(
          label: l10n.openMarket,
          icon: Icons.candlestick_chart_outlined,
          expand: true,
          onPressed: openMarket,
        ),
      ];
    }

    // كل زر بعرض الشاشة (تحت بعض): التسمية كاملة دايمًا، حتى بالعربي وبالخط الكبير
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final (i, button) in [primary, ...secondary].indexed) ...[
          if (i > 0) const SizedBox(height: AppSpacing.xs),
          button,
        ],
      ],
    );
  }
}

/// "High" / "Medium" / "Low"
String influenceText(AppLocalizations l10n, ReasonInfluence influence) => switch (influence) {
      ReasonInfluence.high => l10n.reasonInfluenceHigh,
      ReasonInfluence.medium => l10n.reasonInfluenceMedium,
      ReasonInfluence.low => l10n.reasonInfluenceLow,
    };
