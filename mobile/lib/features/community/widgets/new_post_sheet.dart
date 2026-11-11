import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../l10n/app_localizations.dart';
import '../../markets/models/market_models.dart';
import '../data/posts_repository.dart';
import '../models/post.dart';
import '../view_models/posts_view_model.dart';

/// "New post" بـ bottom sheet: النص (لحد [kPostMaxLength] حرف، العدّاد ظاهر)،
/// أداة اختيارية من الـ 8، وزر "Post" معطّل وهو فاضي. الفشل بيطلع تحت النص
/// والنص بيضل. بيرجّع true لما ينشر.
Future<bool?> showNewPostSheet(BuildContext context) {
  AppHaptics.light();
  return showModalBottomSheet<bool>(
    useRootNavigator: true,
    context: context,
    sheetAnimationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
    isScrollControlled: true,
    useSafeArea: true,
    showDragHandle: true,
    builder: (context) => Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: const _NewPostSheet(),
    ),
  );
}

class _NewPostSheet extends ConsumerStatefulWidget {
  const _NewPostSheet();

  @override
  ConsumerState<_NewPostSheet> createState() => _NewPostSheetState();
}

class _NewPostSheetState extends ConsumerState<_NewPostSheet> {
  final _body = TextEditingController();
  String? _symbol;
  bool _posting = false;
  String? _error;

  @override
  void dispose() {
    _body.dispose();
    super.dispose();
  }

  bool get _canPost => !_posting && _body.text.trim().isNotEmpty && _body.text.trim().length <= kPostMaxLength;

  Future<void> _submit() async {
    if (!_canPost) return;
    final l10n = AppLocalizations.of(context)!;
    setState(() {
      _posting = true;
      _error = null;
    });
    try {
      final ok = await ref.read(postsViewModelProvider.notifier).create(_body.text, symbol: _symbol);
      if (!mounted) return;
      if (ok) {
        AppHaptics.confirm();
        Navigator.of(context).pop(true);
        return;
      }
    } on PostsOfflineException {
      if (mounted) setState(() => _error = l10n.postOffline);
    } catch (_) {
      if (mounted) setState(() => _error = l10n.postFailed);
    }
    if (mounted) setState(() => _posting = false);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final text = context.textTheme;
    final gutter = AppSpacing.gutter(context);
    final me = ref.watch(postAuthorProvider);

    return SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(gutter, 0, gutter, AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Semantics(header: true, child: Text(l10n.newPostTitle, style: text.titleLarge)),
          const SizedBox(height: AppSpacing.xxs),
          Text(l10n.newPostAs(me), style: text.bodyMedium),
          const SizedBox(height: AppSpacing.md),
          TextField(
            controller: _body,
            enabled: !_posting,
            autofocus: true,
            minLines: 4,
            maxLines: 8,
            maxLength: kPostMaxLength,
            textCapitalization: TextCapitalization.sentences,
            keyboardType: TextInputType.multiline,
            decoration: InputDecoration(
              labelText: l10n.newPostLabel,
              hintText: l10n.newPostHint,
              hintMaxLines: 3,
              alignLabelWithHint: true,
              floatingLabelBehavior: FloatingLabelBehavior.never,
            ),
            onChanged: (_) => setState(() => _error = null),
          ),
          if (_error case final error?) ...[
            const SizedBox(height: AppSpacing.xs),
            Semantics(
              liveRegion: true,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.error_outline_rounded, size: AppSizes.iconMd, color: c.danger),
                  const SizedBox(width: AppSpacing.xs),
                  Expanded(child: Text(error, style: text.bodyMedium!.copyWith(color: c.fg))),
                ],
              ),
            ),
          ],
          const SizedBox(height: AppSpacing.md),
          Text(l10n.newPostInstrument, style: text.labelLarge),
          const SizedBox(height: AppSpacing.xs),
          Wrap(
            spacing: AppSpacing.xs,
            runSpacing: AppSpacing.xs,
            children: [
              for (final symbol in kProductSymbols)
                ChoiceChip(
                  label: Text(symbol, textDirection: TextDirection.ltr),
                  selected: _symbol == symbol,
                  showCheckmark: false,
                  materialTapTargetSize: MaterialTapTargetSize.padded,
                  onSelected: _posting
                      ? null
                      : (selected) {
                          AppHaptics.selection();
                          // ضغطة تانية عالمختار بتشيله (الأداة اختيارية)
                          setState(() => _symbol = selected ? symbol : null);
                        },
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.only(top: 1),
                child: Icon(Icons.public_rounded, size: AppSizes.iconSm, color: c.fg3),
              ),
              const SizedBox(width: AppSpacing.xs),
              Expanded(child: Text(l10n.newPostNote, style: text.bodySmall)),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.only(top: 1),
                child: Icon(Icons.info_outline_rounded, size: AppSizes.iconSm, color: c.fg3),
              ),
              const SizedBox(width: AppSpacing.xs),
              Expanded(child: Text(l10n.newPostNotAdvice, style: text.bodySmall)),
            ],
          ),
          const SizedBox(height: AppSpacing.lg),
          AppButton(
            label: l10n.postAction,
            icon: Icons.send_rounded,
            expand: true,
            loading: _posting,
            onPressed: _canPost ? _submit : null,
          ),
        ],
      ),
    );
  }
}
