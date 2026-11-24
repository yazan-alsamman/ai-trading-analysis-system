import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/network_status.dart';
import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../core/widgets/page_header.dart';
import '../../../core/widgets/source_tag.dart';
import '../../../l10n/app_localizations.dart';
import '../../profile/widgets/profile_identity_card.dart';
import '../data/experts_repository.dart';
import '../models/chat_message.dart';
import '../models/expert.dart';
import '../view_models/expert_chat_view_model.dart';
import '../widgets/chat_bubble.dart';
import '../widgets/subscribe_sheet.dart';

/// محادثة مع خبير (من زر "Chat" ببطاقته بس).
///
/// فوق: رجوع + الخبير + "Simulated"، وتحته سطر ثابت "Experts share opinions,
/// not financial advice. Not a broker.". بالنص الرسائل (الأحدث تحت)، وتحت حقل
/// الكتابة. بدون اشتراك (route مباشر): حالة "Subscribe to chat" بدل المحادثة.
/// بدون اتصال: ما في إرسال، السبب مكتوب، والمسودة بتضل.
class ExpertChatScreen extends ConsumerStatefulWidget {
  const ExpertChatScreen({super.key, required this.expertId});

  final String expertId;

  @override
  ConsumerState<ExpertChatScreen> createState() => _ExpertChatScreenState();
}

class _ExpertChatScreenState extends ConsumerState<ExpertChatScreen> {
  final _draft = TextEditingController();
  final _scroll = ScrollController();
  bool _showLatest = false;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      final show = _scroll.hasClients && _scroll.offset > 240;
      if (show != _showLatest) setState(() => _showLatest = show);
    });
  }

  @override
  void dispose() {
    _draft.dispose();
    _scroll.dispose();
    super.dispose();
  }

  ExpertChatViewModel get _vm => ref.read(expertChatViewModelProvider(widget.expertId).notifier);

  void _toLatest() {
    if (!_scroll.hasClients) return;
    if (context.reduceMotion) {
      _scroll.jumpTo(0);
    } else {
      _scroll.animateTo(0, duration: AppMotion.medium, curve: AppMotion.out);
    }
  }

  void _announce(String message) =>
      SemanticsService.sendAnnouncement(View.of(context), message, Directionality.of(context));

  void _send() {
    switch (_vm.send(_draft.text)) {
      case ChatSendResult.accepted:
        AppHaptics.selection();
        _draft.clear();
        setState(() {});
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) _toLatest();
        });
      case ChatSendResult.offline:
        // السطر تحت ظاهر أصلًا؛ المسودة بتضل
        _announce(AppLocalizations.of(context)!.chatOffline);
      case ChatSendResult.ignored || ChatSendResult.locked:
        break;
    }
  }

  void _retry(String clientId) {
    if (_vm.retry(clientId) == ChatSendResult.offline) _announce(AppLocalizations.of(context)!.chatOffline);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final expertAsync = ref.watch(expertByIdProvider(widget.expertId));
    final expert = expertAsync.valueOrNull;
    final provider = expertChatViewModelProvider(widget.expertId);
    final chat = ref.watch(provider);
    final open = chat.valueOrNull?.access == ChatAccess.open;

    // رد جديد من الخبير بينقرأ للقارئ الصوتي
    ref.listen(provider.select((s) => s.valueOrNull?.messages), (previous, next) {
      if (previous == null || next == null || next.length <= previous.length || expert == null) return;
      final last = next.last;
      if (last.fromMe) return;
      _announce(l10n.chatMessageTheirs(expert.name, Formatters.clock(last.createdAt.toLocal()), last.body));
    });

    final Widget body;
    if (expertAsync.hasError) {
      body = _centered(ErrorState(onRetry: () => ref.invalidate(expertsProvider)));
    } else if (expertAsync.hasValue && expert == null) {
      body = _centered(EmptyState(icon: Icons.person_off_outlined, title: l10n.chatNotFound));
    } else if (expert == null) {
      body = const _ChatSkeleton();
    } else {
      body = chat.when(
        skipLoadingOnRefresh: false,
        loading: () => const _ChatSkeleton(),
        error: (error, _) => _centered(error is ChatOfflineException
            ? EmptyState(
                icon: Icons.cloud_off_outlined,
                title: l10n.offlineBannerTitle,
                message: l10n.chatOfflineBody,
                actionLabel: l10n.tryAgain,
                onAction: () => ref.invalidate(provider),
              )
            : ErrorState(message: l10n.chatLoadError, onRetry: () => ref.invalidate(provider))),
        data: (state) => state.access == ChatAccess.locked
            ? _centered(EmptyState(
                icon: Icons.lock_outline_rounded,
                title: l10n.chatLockedTitle(expert.name),
                message: l10n.chatLockedBody(expert.name),
                actionLabel: expert.plan == null ? null : l10n.expertSubscribe,
                onAction: () => showSubscribeSheet(context, expert),
              ))
            : _messages(expert, state.messages),
      );
    }

    return Scaffold(
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _Header(expert: expert, loading: expertAsync.isLoading && expert == null),
            const _Disclaimer(),
            Expanded(child: body),
            if (open && expert != null) _composer(expert),
          ],
        ),
      ),
    );
  }

  Widget _centered(Widget child) => LayoutBuilder(
        builder: (context, constraints) => SingleChildScrollView(
          child: ConstrainedBox(
            constraints: BoxConstraints(minHeight: constraints.maxHeight),
            child: Center(child: child),
          ),
        ),
      );

  Widget _messages(Expert expert, List<ChatMessage> messages) {
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    if (messages.isEmpty) {
      return _centered(EmptyState(
        illustrated: true,
        icon: Icons.chat_bubble_outline_rounded,
        title: l10n.chatEmptyTitle,
        message: l10n.chatEmptyBody(expert.name),
      ));
    }
    return Stack(
      children: [
        ListView.separated(
          controller: _scroll,
          reverse: true,
          keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
          padding: EdgeInsets.fromLTRB(gutter, AppSpacing.md, gutter, AppSpacing.md),
          itemCount: messages.length,
          separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
          itemBuilder: (_, i) {
            final m = messages[messages.length - 1 - i];
            return ChatBubble(
              key: ValueKey(m.clientId ?? m.id),
              message: m,
              expertName: expert.name,
              onRetry: m.clientId == null ? null : () => _retry(m.clientId!),
            );
          },
        ),
        if (_showLatest)
          PositionedDirectional(
            end: gutter,
            bottom: AppSpacing.sm,
            child: IconButton.filledTonal(
              tooltip: l10n.chatLatest,
              constraints: const BoxConstraints(minWidth: AppSizes.minTap, minHeight: AppSizes.minTap),
              icon: const Icon(Icons.arrow_downward_rounded),
              onPressed: _toLatest,
            ),
          ),
      ],
    );
  }

  Widget _composer(Expert expert) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    final offline = ref.watch(networkStatusProvider) == NetworkStatus.offline;
    final canSend = !offline && _draft.text.trim().isNotEmpty;

    return DecoratedBox(
      decoration: BoxDecoration(color: c.canvas, border: Border(top: BorderSide(color: c.hairline))),
      child: Padding(
        padding: EdgeInsetsDirectional.fromSTEB(gutter, AppSpacing.xs, gutter - AppSpacing.sm, AppSpacing.xs),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (offline)
              Semantics(
                liveRegion: true,
                child: Padding(
                  padding: const EdgeInsetsDirectional.only(end: AppSpacing.sm, bottom: AppSpacing.xs),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.cloud_off_outlined, size: AppSizes.iconSm, color: c.warning),
                      const SizedBox(width: AppSpacing.xs),
                      Expanded(child: Text(l10n.chatOffline, style: context.textTheme.bodySmall!.copyWith(color: c.fg))),
                    ],
                  ),
                ),
              ),
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Expanded(
                  child: TextField(
                    controller: _draft,
                    minLines: 1,
                    maxLines: 5,
                    maxLength: kChatMessageMaxLength,
                    keyboardType: TextInputType.multiline,
                    textCapitalization: TextCapitalization.sentences,
                    decoration: InputDecoration(hintText: l10n.chatHint(expert.name), hintMaxLines: 4),
                    // العدّاد بيطلع بس قرب الحد
                    buildCounter: (context, {required currentLength, required isFocused, maxLength}) =>
                        maxLength != null && currentLength >= maxLength - 100
                            ? Text(l10n.chatCount('$currentLength', '$maxLength'), style: context.textTheme.bodySmall)
                            : null,
                    onChanged: (_) => setState(() {}),
                  ),
                ),
                const SizedBox(width: AppSpacing.xxs),
                IconButton.filled(
                  tooltip: l10n.chatSend,
                  constraints: const BoxConstraints(minWidth: AppSizes.minTap, minHeight: AppSizes.minTap),
                  style: IconButton.styleFrom(
                    backgroundColor: c.primaryAction,
                    foregroundColor: c.onPrimaryAction,
                    disabledBackgroundColor: c.pressed,
                    disabledForegroundColor: c.fgDisabled,
                  ),
                  // السهم بيأشّر للأمام (بينعكس بالعربي)
                  icon: const Icon(Icons.send_rounded),
                  onPressed: canSend ? _send : null,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// رجوع + صورة الخبير + اسمه + "Simulated"
class _Header extends StatelessWidget {
  const _Header({required this.expert, required this.loading});

  final Expert? expert;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    final gutter = AppSpacing.gutter(context);
    final expert = this.expert;
    return Padding(
      padding: EdgeInsetsDirectional.fromSTEB(gutter - AppSpacing.sm, AppSpacing.xs, gutter, AppSpacing.xs),
      child: Row(
        children: [
          const PageBackButton(),
          const SizedBox(width: AppSpacing.xxs),
          if (expert != null) ...[
            ExcludeSemantics(child: ProfileAvatar(name: expert.name, path: null, size: 40)),
            const SizedBox(width: AppSpacing.sm),
          ],
          Expanded(
            child: loading
                ? const Align(alignment: AlignmentDirectional.centerStart, child: Skeleton(width: 140, height: 20))
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (expert != null) Semantics(header: true, child: Text(expert.name, style: context.textTheme.titleMedium)),
                      const SizedBox(height: AppSpacing.xxs),
                      const SourceTag(SourceKind.demo),
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}

/// سطر ثابت تحت الرأس: آراء، مش نصيحة مالية، ومش وسيط
class _Disclaimer extends StatelessWidget {
  const _Disclaimer();

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final gutter = AppSpacing.gutter(context);
    return ColoredBox(
      color: c.inset,
      child: Padding(
        padding: EdgeInsets.symmetric(horizontal: gutter, vertical: AppSpacing.xs),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.info_outline_rounded, size: AppSizes.iconSm, color: c.fg3),
            const SizedBox(width: AppSpacing.xs),
            Expanded(child: Text(AppLocalizations.of(context)!.chatDisclaimer, style: context.textTheme.bodySmall)),
          ],
        ),
      ),
    );
  }
}

/// تحميل: فقاعات محجوزة (خبير / إنت بالتناوب)
class _ChatSkeleton extends StatelessWidget {
  const _ChatSkeleton();

  @override
  Widget build(BuildContext context) {
    final gutter = AppSpacing.gutter(context);
    final width = MediaQuery.sizeOf(context).width;
    return LoadingRegion(
      child: ListView(
        reverse: true,
        physics: const NeverScrollableScrollPhysics(),
        padding: EdgeInsets.fromLTRB(gutter, AppSpacing.md, gutter, AppSpacing.md),
        children: [
          for (final (i, factor) in [0.55, 0.7, 0.45].indexed) ...[
            if (i > 0) const SizedBox(height: AppSpacing.sm),
            Align(
              alignment: i.isEven ? AlignmentDirectional.centerEnd : AlignmentDirectional.centerStart,
              child: Skeleton(width: width * factor, height: AppSpacing.huge + AppSpacing.xs, radius: AppRadii.heroCard),
            ),
          ],
        ],
      ),
    );
  }
}
