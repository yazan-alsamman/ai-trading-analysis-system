import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/router/app_navigator.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../core/widgets/source_tag.dart';
import '../../../l10n/app_localizations.dart';
import '../data/telegram_link_repository.dart';
import '../view_models/telegram_link_view_model.dart';

/// "Connect Telegram" (H4b): sheet عالـ navigator الجذر. كود لمرة وحدة (10
/// دقايق مع عدّ تنازلي و Copy)، اسم البوت مع Copy (ما في url_launcher)، و
/// "Check connection". التسكير بيلغي أي فحص معلّق. بيرجّع true لما ينربط.
Future<bool> showTelegramConnectSheet(BuildContext context) async {
  if (!context.isTopmostRoute) return false;
  final l10n = AppLocalizations.of(context)!;
  final messenger = ScaffoldMessenger.of(context);
  AppHaptics.light();
  final linked = await showModalBottomSheet<bool>(
    useRootNavigator: true,
    context: context,
    sheetAnimationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
    isScrollControlled: true,
    useSafeArea: true,
    showDragHandle: true,
    builder: (_) => const TelegramConnectSheet(),
  );
  if (linked != true) return false;
  messenger
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(l10n.telegramConnectedSnack)));
  return true;
}

class TelegramConnectSheet extends ConsumerStatefulWidget {
  const TelegramConnectSheet({super.key});

  @override
  ConsumerState<TelegramConnectSheet> createState() => _TelegramConnectSheetState();
}

class _TelegramConnectSheetState extends ConsumerState<TelegramConnectSheet> {
  Timer? _ticker;
  Timer? _copiedReset;
  String? _copied;
  var _closing = false;

  /// آخر دقيقة انعلنت (حتى العدّ ما ينقرا كل ثانية)
  int? _announcedMinute;

  @override
  void initState() {
    super.initState();
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) => _tick());
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) ref.read(telegramCodeProvider.notifier).requestCode();
    });
  }

  @override
  void dispose() {
    _ticker?.cancel();
    _copiedReset?.cancel();
    super.dispose();
  }

  DateTime _now() => ref.read(telegramClockProvider)().toUtc();

  void _tick() {
    if (!mounted) return;
    final code = ref.read(telegramCodeProvider).code;
    if (code != null) {
      final left = code.remaining(_now());
      // إعلان مهذّب: دقيقة وحدة باقية، وانتهى (مش كل ثانية)
      final l10n = AppLocalizations.of(context)!;
      if (left == Duration.zero && _announcedMinute != 0) {
        _announcedMinute = 0;
        _announce(l10n.telegramCodeExpired);
      } else if (left > Duration.zero && left <= const Duration(minutes: 1) && _announcedMinute == null) {
        _announcedMinute = 1;
        _announce(l10n.telegramOneMinuteLeft);
      }
    }
    setState(() {});
  }

  void _announce(String message) {
    SemanticsService.sendAnnouncement(View.of(context), message, Directionality.of(context));
  }

  Future<void> _copy(String value, String done) async {
    await Clipboard.setData(ClipboardData(text: value));
    if (!mounted) return;
    AppHaptics.selection();
    _announce(done);
    setState(() => _copied = value);
    _copiedReset?.cancel();
    _copiedReset = Timer(const Duration(seconds: 2), () {
      if (mounted) setState(() => _copied = null);
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final text = context.textTheme;
    final gutter = AppSpacing.gutter(context);
    final state = ref.watch(telegramCodeProvider);
    final vm = ref.read(telegramCodeProvider.notifier);

    // انربط: الشيت بيتسكّر مرة وحدة
    ref.listen<TelegramCodeState>(telegramCodeProvider, (previous, next) {
      if (next.linked != null && previous?.linked == null && !_closing) {
        _closing = true;
        AppHaptics.confirm();
        Navigator.of(context).pop(true);
      }
      if (next.code != previous?.code) _announcedMinute = null;
    });

    final code = state.code;
    final expired = code != null && (state.issue == TelegramCodeIssue.expired || code.isExpiredAt(_now()));

    return SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(gutter, 0, gutter, AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(top: AppSpacing.xs),
                  child: Semantics(header: true, child: Text(l10n.telegramConnect, style: text.titleLarge)),
                ),
              ),
              IconButton(
                tooltip: MaterialLocalizations.of(context).closeButtonTooltip,
                constraints: const BoxConstraints(minWidth: AppSizes.minTap, minHeight: AppSizes.minTap),
                icon: Icon(Icons.close_rounded, color: c.fg2),
                onPressed: () => Navigator.of(context).pop(false),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(l10n.telegramSheetIntro, style: text.bodyMedium!.copyWith(color: c.fg2)),
          const SizedBox(height: AppSpacing.xs),
          const Align(alignment: AlignmentDirectional.centerStart, child: SourceTag(SourceKind.demo)),
          const SizedBox(height: AppSpacing.lg),
          if (state.requesting)
            LoadingRegion(
              child: Semantics(
                label: l10n.telegramGettingCode,
                child: const Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Skeleton(width: 180),
                    SizedBox(height: AppSpacing.md),
                    Skeleton(height: 72),
                    SizedBox(height: AppSpacing.md),
                    Skeleton(width: 140),
                  ],
                ),
              ),
            )
          else if (code == null)
            _Issue(
              message: state.issue == TelegramCodeIssue.offline ? l10n.telegramOffline : l10n.telegramFailed,
              icon: state.issue == TelegramCodeIssue.offline ? Icons.cloud_off_rounded : Icons.error_outline_rounded,
              action: AppButton.secondary(label: l10n.tryAgain, onPressed: vm.requestCode, expand: true),
            )
          else if (expired)
            _Issue(
              title: l10n.telegramCodeExpired,
              message: l10n.telegramCodeExpiredBody,
              icon: Icons.timer_off_outlined,
              action: AppButton(label: l10n.telegramNewCode, onPressed: vm.requestCode, expand: true),
            )
          else ...[
            _StepLabel(l10n.telegramStepBot),
            const SizedBox(height: AppSpacing.xs),
            _CopyRow(
              value: '@${code.botUsername}',
              semanticsLabel: l10n.telegramBotLabel('@${code.botUsername}'),
              style: text.titleMedium!,
              copyLabel: _copied == '@${code.botUsername}' ? l10n.telegramCopied : l10n.telegramCopy,
              copyTooltip: l10n.telegramCopyBot,
              onCopy: () => _copy('@${code.botUsername}', l10n.telegramBotCopied),
            ),
            const SizedBox(height: AppSpacing.md),
            _StepLabel(l10n.telegramStepCode),
            const SizedBox(height: AppSpacing.xs),
            _CopyRow(
              value: code.code,
              // الحروف وحدة وحدة للقارئ الصوتي
              semanticsLabel: l10n.telegramCodeLabel(code.code.split('').join(' ')),
              style: context.type.numHero.copyWith(letterSpacing: 4),
              copyLabel: _copied == code.code ? l10n.telegramCopied : l10n.telegramCopy,
              copyTooltip: l10n.telegramCopyCode,
              onCopy: () => _copy(code.code, l10n.telegramCodeCopied),
            ),
            const SizedBox(height: AppSpacing.xs),
            _Countdown(left: code.remaining(_now())),
            const SizedBox(height: AppSpacing.md),
            _StepLabel(l10n.telegramStepCheck),
            const SizedBox(height: AppSpacing.sm),
            if (state.issue case final issue? when issue != TelegramCodeIssue.expired) ...[
              Semantics(
                liveRegion: true,
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      issue == TelegramCodeIssue.offline ? Icons.cloud_off_rounded : Icons.info_outline_rounded,
                      size: AppSizes.iconMd,
                      color: c.warning,
                    ),
                    const SizedBox(width: AppSpacing.xs),
                    Expanded(
                      child: Text(
                        switch (issue) {
                          TelegramCodeIssue.offline => l10n.telegramOffline,
                          TelegramCodeIssue.notYet => l10n.telegramNotYet,
                          _ => l10n.telegramFailed,
                        },
                        style: text.bodyMedium!.copyWith(color: c.fg),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
            ],
            AppButton(
              label: l10n.telegramCheck,
              icon: Icons.link_rounded,
              loading: state.checking,
              expand: true,
              onPressed: vm.check,
            ),
          ],
          const SizedBox(height: AppSpacing.md),
          Text(l10n.telegramSheetNote, style: text.bodySmall),
        ],
      ),
    );
  }
}

class _StepLabel extends StatelessWidget {
  const _StepLabel(this.label);

  final String label;

  @override
  Widget build(BuildContext context) => Text(label, style: context.textTheme.titleSmall);
}

/// قيمة بتنقرا من اليسار لليمين (حتى بالعربي) + زر Copy (48dp)
class _CopyRow extends StatelessWidget {
  const _CopyRow({
    required this.value,
    required this.semanticsLabel,
    required this.style,
    required this.copyLabel,
    required this.copyTooltip,
    required this.onCopy,
  });

  final String value;
  final String semanticsLabel;
  final TextStyle style;
  final String copyLabel;
  final String copyTooltip;
  final VoidCallback onCopy;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: c.inset,
        borderRadius: AppRadii.card,
        border: Border.all(color: c.hairline),
      ),
      child: Padding(
        padding: const EdgeInsetsDirectional.fromSTEB(AppSpacing.md, AppSpacing.xs, AppSpacing.xs, AppSpacing.xs),
        child: Wrap(
          alignment: WrapAlignment.spaceBetween,
          crossAxisAlignment: WrapCrossAlignment.center,
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.xs,
          children: [
            Semantics(
              label: semanticsLabel,
              child: ExcludeSemantics(
                child: Directionality(
                  textDirection: TextDirection.ltr,
                  child: SelectableText(value, style: style),
                ),
              ),
            ),
            // القارئ الصوتي بيسمع "Copy code" / "Copy bot name" (مش "Copy" مرتين)
            Semantics(
              label: copyTooltip,
              button: true,
              onTap: onCopy,
              excludeSemantics: true,
              child: AppButton.ghost(label: copyLabel, icon: Icons.copy_rounded, compact: true, onPressed: onCopy),
            ),
          ],
        ),
      ),
    );
  }
}

/// "Valid for 9:41" بيتحدّث كل ثانية عالشاشة، بس القارئ الصوتي بيسمع الدقايق
/// بس (ما بيتغيّر كل ثانية، ومش live region)
class _Countdown extends StatelessWidget {
  const _Countdown({required this.left});

  final Duration left;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final minutes = left.inMinutes;
    final seconds = left.inSeconds % 60;
    final clock = '$minutes:${seconds.toString().padLeft(2, '0')}';
    final spoken = left < const Duration(minutes: 1)
        ? l10n.telegramValidUnderMinute
        : l10n.telegramValidMinutes('${left.inSeconds % 60 == 0 ? minutes : minutes + 1}');
    return Semantics(
      label: spoken,
      child: ExcludeSemantics(
        child: Row(
          children: [
            Icon(Icons.timer_outlined, size: AppSizes.iconSm, color: c.fg2),
            const SizedBox(width: AppSpacing.xxs),
            Flexible(
              child: Text(
                l10n.telegramValidFor(clock),
                style: context.textTheme.bodySmall!.copyWith(color: c.fg2),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Issue extends StatelessWidget {
  const _Issue({this.title, required this.message, required this.icon, required this.action});

  final String? title;
  final String message;
  final IconData icon;
  final Widget action;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Semantics(
          liveRegion: true,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, size: AppSizes.iconLg, color: c.warning),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (title != null) ...[
                      Text(title!, style: text.titleMedium),
                      const SizedBox(height: AppSpacing.xxs),
                    ],
                    Text(message, style: text.bodyMedium!.copyWith(color: c.fg)),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        action,
      ],
    );
  }
}
