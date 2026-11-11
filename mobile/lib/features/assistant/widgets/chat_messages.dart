import 'dart:io';

import 'package:flutter/material.dart';

import '../../../app/router/app_navigator.dart';
import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/direction_badge.dart';
import '../../../core/widgets/not_advice_notice.dart';
import '../../../core/widgets/source_tag.dart';
import '../../../l10n/app_localizations.dart';
import '../models/assistant_models.dart';
import '../models/chart_analysis.dart';
import '../view_models/assistant_view_model.dart' show chartPatternLabel, pictureTrendLabel;

/// رسالة المستخدم: فقاعة بآخر السطر
class UserBubble extends StatelessWidget {
  const UserBubble({super.key, required this.message});

  final UserText message;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return _EndAligned(
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: c.selected,
          borderRadius: const BorderRadiusDirectional.only(
            topStart: Radius.circular(AppRadii.lg),
            topEnd: Radius.circular(AppRadii.lg),
            bottomStart: Radius.circular(AppRadii.lg),
            bottomEnd: Radius.circular(AppRadii.xs),
          ),
          border: Border.all(color: c.hairline),
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
          child: Text(
            message.text,
            style: context.textTheme.bodyLarge,
            semanticsLabel: '${AppLocalizations.of(context)!.commentAuthorYou}: ${message.text}',
          ),
        ),
      ),
    );
  }
}

/// صورة شارت بعتها المستخدم
class UserImageBubble extends StatelessWidget {
  const UserImageBubble({super.key, required this.message});

  final UserImage message;

  static const double height = 160;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final placeholder = Container(
      width: height * 1.4,
      height: height,
      color: c.inset,
      child: Icon(Icons.image_outlined, color: c.fg3, size: AppSizes.iconLg),
    );
    return _EndAligned(
      child: Semantics(
        image: true,
        label: l10n.asstChartImage,
        child: ClipRRect(
          borderRadius: AppRadii.heroCard,
          child: Image.file(
            File(message.path),
            height: height,
            // فكّ الصورة على حجم العرض بس (صورة كاميرا 12MP كانت تنفكّ كاملة بالذاكرة)
            cacheHeight: (height * MediaQuery.devicePixelRatioOf(context)).round(),
            fit: BoxFit.cover,
            errorBuilder: (_, __, ___) => placeholder,
          ),
        ),
      ),
    );
  }
}

class _EndAligned extends StatelessWidget {
  const _EndAligned({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: AlignmentDirectional.centerEnd,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: MediaQuery.sizeOf(context).width * 0.8),
        child: child,
      ),
    );
  }
}

/// صورة المساعد بالمحادثة: راس روبوت بدائرة بنفسجية خفيفة (ناتج نموذج).
/// زخرفة - اسم الجواب أو "عم يكتب" بيقرأه القارئ الصوتي.
class AssistantAvatar extends StatelessWidget {
  const AssistantAvatar({super.key});

  static const double size = 24;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return ExcludeSemantics(
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(color: c.forecastSoft, shape: BoxShape.circle),
        child: Icon(Icons.smart_toy_outlined, size: AppSizes.iconSm, color: c.forecast),
      ),
    );
  }
}

/// اسم نوع الجواب ("Explanation"...) - للبطاقة ولإعلان القارئ الصوتي
String replyKindLabel(AppLocalizations l10n, ReplyKind kind) => switch (kind) {
      ReplyKind.explain => l10n.asstKindExplain,
      ReplyKind.invalidate => l10n.asstKindInvalidate,
      ReplyKind.risk => l10n.asstKindRisk,
      ReplyKind.chart => l10n.asstKindChart,
      ReplyKind.unknown => l10n.asstKindUnknown,
    };

/// جواب المساعد كبطاقة بحث: صورة المساعد + نوع الجواب (بنفسجي = ناتج نموذج)، النص،
/// قراءة الشارت إذا في، وتحت شارة "Simulated" + الوقت
class ReplyCard extends StatelessWidget {
  const ReplyCard({super.key, required this.reply});

  final AssistantReply reply;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;
    final answer = reply.answer;
    final kind = replyKindLabel(l10n, answer.kind);
    final chart = answer.chart;
    final heading = [
      kind,
      if (reply.symbol != null) reply.symbol!,
      if (chart?.instrument != null && chart?.timeframe != null) chart!.timeframe!.label,
    ].join(' · ');

    return Semantics(
      container: true,
      label: l10n.asstAnswerLabel(heading),
      child: Material(
        color: c.card,
        shape: RoundedRectangleBorder(borderRadius: AppRadii.heroCard, side: BorderSide(color: c.hairline)),
        clipBehavior: Clip.antiAlias,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.sm, AppSpacing.md, AppSpacing.sm),
              child: Row(
                children: [
                  const AssistantAvatar(),
                  const SizedBox(width: AppSpacing.xs),
                  Expanded(child: Text(heading, style: text.labelLarge!.copyWith(color: c.fg2))),
                ],
              ),
            ),
            Divider(height: 1, thickness: 1, color: c.hairline),
            Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (chart != null) ...[
                    ChartResultRows(chart: chart),
                    const SizedBox(height: AppSpacing.md),
                  ],
                  Text(answer.text, style: text.bodyLarge!.copyWith(height: 1.5)),
                  if (chart?.instrument case final instrument?) ...[
                    const SizedBox(height: AppSpacing.md),
                    AppButton.secondary(
                      label: l10n.openMarket,
                      icon: Icons.candlestick_chart_outlined,
                      expand: true,
                      onPressed: () => context.pushMarket(instrument.symbol),
                    ),
                  ],
                ],
              ),
            ),
            ColoredBox(
              color: c.inset,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.xs),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Wrap(
                      spacing: AppSpacing.xs,
                      runSpacing: AppSpacing.xxs,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        if (answer.simulated) const SourceTag(SourceKind.demo),
                        Text(
                          [
                            Formatters.clock(reply.createdAt),
                            if (answer.simulated && chart == null) l10n.asstRuleBased,
                            if (chart?.fromCache ?? false) l10n.chartStored,
                          ].join(' · '),
                          style: text.bodySmall,
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.xxs),
                    const NotAdviceNotice(),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// أرقام تحليل الصورة: الاتجاه (من الاستراتيجية المحفوظة على نفس الأداة
/// والإطار، أو حركة الصورة بس لما ما انقرأت الأداة)، المستويات (نفس شاشة
/// تفاصيل الإشارة)، والشكل الفني. تسمية فوق قيمة حتى الخط الكبير ما يقصّ.
class ChartResultRows extends StatelessWidget {
  const ChartResultRows({super.key, required this.chart});

  final ChartAnalysisReply chart;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final text = context.textTheme;
    final instrument = chart.instrument;
    final signal = chart.signal;
    final plan = chart.plan;
    final numStyle = context.type.numSmall.copyWith(color: c.fg);

    final Widget trend;
    if (instrument == null || chart.timeframe == null) {
      trend = Text(l10n.chartPictureOnly(pictureTrendLabel(l10n, chart.analysis.trend)), style: text.bodyMedium);
    } else if (signal == null) {
      trend = Wrap(
        spacing: AppSpacing.xs,
        runSpacing: AppSpacing.xxs,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          const DirectionBadge(SignalDirection.neutral),
          Text(l10n.chartNoSetup(chart.timeframe!.label), style: text.bodyMedium),
        ],
      );
    } else {
      trend = Wrap(
        spacing: AppSpacing.xs,
        runSpacing: AppSpacing.xxs,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          DirectionBadge(signal.direction),
          Text(Formatters.percent(signal.probability), style: context.type.numSmall.copyWith(color: c.forecast)),
          if (chart.isHighProbability) Text(l10n.chartHighProbability, style: text.bodyMedium),
        ],
      );
    }

    final Widget levels;
    if (instrument != null && plan != null) {
      Widget level(String label, String value) => Wrap(
            spacing: AppSpacing.xs,
            children: [
              Text(label, style: text.bodyMedium!.copyWith(color: c.fg2)),
              Text(value, style: numStyle, textDirection: TextDirection.ltr),
            ],
          );
      levels = Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          level(l10n.zoneEntry, '${instrument.format(plan.entry.low)} – ${instrument.format(plan.entry.high)}'),
          level(l10n.zoneTarget, instrument.format(plan.target)),
          level(l10n.zoneStop, instrument.format(plan.stop)),
        ],
      );
    } else {
      levels = Text(l10n.chartNoLevels, style: text.bodyMedium);
    }

    Widget row(String label, Widget value) => Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: text.labelMedium!.copyWith(color: c.fg2)),
            const SizedBox(height: AppSpacing.xxs),
            value,
          ],
        );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        row(l10n.chartTrend, trend),
        const SizedBox(height: AppSpacing.sm),
        row(l10n.chartKeyLevels, levels),
        const SizedBox(height: AppSpacing.sm),
        row(l10n.chartPattern, Text(chartPatternLabel(l10n, chart.analysis.pattern), style: text.bodyMedium)),
      ],
    );
  }
}

/// "المساعد عم يكتب": 3 نقاط (الحلقة الوحيدة المسموحة بالتطبيق). مع تقليل
/// الحركة: نص ثابت.
class TypingIndicator extends StatefulWidget {
  const TypingIndicator({super.key});

  @override
  State<TypingIndicator> createState() => _TypingIndicatorState();
}

class _TypingIndicatorState extends State<TypingIndicator> with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: AppMotion.typingLoop,
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (context.reduceMotion) {
      _controller.stop();
    } else if (!_controller.isAnimating) {
      _controller.repeat();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final Widget dots = context.reduceMotion
        ? Text('…', style: context.textTheme.titleMedium!.copyWith(color: c.forecast))
        : AnimatedBuilder(
            animation: _controller,
            builder: (context, _) => Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                for (var i = 0; i < 3; i++) ...[
                  if (i > 0) const SizedBox(width: AppSpacing.xxs),
                  Opacity(
                    opacity: 0.3 + 0.7 * _pulse((_controller.value - i * 0.18) % 1),
                    child: Container(
                      width: AppSpacing.xs,
                      height: AppSpacing.xs,
                      decoration: BoxDecoration(color: c.forecast, shape: BoxShape.circle),
                    ),
                  ),
                ],
              ],
            ),
          );

    return Semantics(
      liveRegion: true,
      label: l10n.asstReplying,
      excludeSemantics: true,
      child: Align(
        alignment: AlignmentDirectional.centerStart,
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: c.card,
            borderRadius: AppRadii.heroCard,
            border: Border.all(color: c.hairline),
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const AssistantAvatar(),
                const SizedBox(width: AppSpacing.sm),
                dots,
                const SizedBox(width: AppSpacing.sm),
                Flexible(child: Text(l10n.asstReplying, style: context.textTheme.bodySmall)),
              ],
            ),
          ),
        ),
      ),
    );
  }

  /// نبضة ناعمة 0→1→0 بأول نص الدورة (بدون linear)
  static double _pulse(double t) {
    if (t > 0.5) return 0;
    return Curves.easeInOut.transform(t < 0.25 ? t * 4 : (0.5 - t) * 4);
  }
}
