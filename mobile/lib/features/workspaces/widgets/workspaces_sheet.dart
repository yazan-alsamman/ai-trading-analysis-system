import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/router/app_navigator.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_text_field.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../l10n/app_localizations.dart';
import '../../markets/models/market_models.dart';
import '../models/workspace.dart';
import '../view_models/workspace_commands.dart';
import '../view_models/workspaces_view_model.dart';

/// "Workspaces": bottom sheet التبديل والإنشاء والتعديل والحذف.
///
/// - القائمة: الضغط على مساحة = التبديل (الـ Home وراها بيتحدّث فورًا)؛ زر
///   القلم بيفتح المحرّر (مش للـ "All instruments").
/// - المحرّر (بنفس الـ sheet): اسم + اختيار الأدوات. Save بيحفظ وبيضل هون
///   ("Saved" + إعلان للقارئ الصوتي)؛ تعديل أو حذف = snackbar مع Undo جوّا الـ sheet.
/// - الـ sheet بتتسكّر بس لما المستخدم يسكّرها (زر الإغلاق، سحب لتحت)؛ الرجوع
///   من المحرّر بيرجّع للقائمة. التعديلات غير المحفوظة بتنرمى بدون dialog.
Future<void> showWorkspacesSheet(BuildContext context) async {
  // ضغطتين ورا بعض = sheet وحدة
  if (!context.isTopmostRoute) return;
  AppHaptics.light();
  await showModalBottomSheet<void>(
    useRootNavigator: true,
    context: context,
    sheetAnimationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
    isScrollControlled: true,
    useSafeArea: true,
    showDragHandle: true,
    builder: (_) => const WorkspacesSheet(),
  );
}

class WorkspacesSheet extends ConsumerStatefulWidget {
  const WorkspacesSheet({super.key});

  @override
  ConsumerState<WorkspacesSheet> createState() => _WorkspacesSheetState();
}

class _WorkspacesSheetState extends ConsumerState<WorkspacesSheet> {
  final _messenger = GlobalKey<ScaffoldMessengerState>();
  final _name = TextEditingController();

  bool _editorOpen = false;

  /// null = مساحة جديدة لسّا ما انحفظت
  String? _editingId;
  Set<String> _symbols = {};
  bool _saving = false;
  bool _justSaved = false;

  /// Save انضغط وفي غلط → كل الرسائل بتبيّن
  bool _attempted = false;
  bool _nameEdited = false;
  bool _symbolsEdited = false;
  String? _failure;

  WorkspacesViewModel get _vm => ref.read(workspacesViewModelProvider.notifier);

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  void _announce(String message) =>
      SemanticsService.sendAnnouncement(View.of(context), message, Directionality.of(context));

  void _snack(String message, {VoidCallback? onUndo}) {
    final l10n = AppLocalizations.of(context)!;
    _messenger.currentState
      ?..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(
        content: Text(message),
        action: onUndo == null ? null : SnackBarAction(label: l10n.undo, onPressed: onUndo),
      ));
  }

  void _loadDraft(Workspace? workspace) {
    _editingId = workspace?.id;
    _name.text = workspace?.name ?? '';
    _symbols = {...?workspace?.symbols};
    _attempted = _nameEdited = _symbolsEdited = _justSaved = false;
    _failure = null;
  }

  void _openEditor(Workspace? workspace) {
    AppHaptics.selection();
    _messenger.currentState?.hideCurrentSnackBar();
    setState(() {
      _loadDraft(workspace);
      _editorOpen = true;
    });
  }

  void _closeEditor() {
    if (_saving) return;
    setState(() {
      _editorOpen = false;
      _loadDraft(null);
    });
  }

  Future<void> _switch(Workspace workspace) async {
    AppHaptics.selection();
    final l10n = AppLocalizations.of(context)!;
    await _vm.setActive(workspace.id);
    if (mounted) _announce(l10n.workspaceSwitched(workspaceDisplayName(l10n, workspace)));
  }

  /// المحفوظة يلي عم تتعدّل (null للجديدة)
  Workspace? _saved(WorkspacesState? state) => _editingId == null ? null : state?.byId(_editingId!);

  bool _dirty(Workspace? saved) =>
      saved == null ||
      Workspace.normalizeName(_name.text) != saved.name ||
      !setEquals(_symbols, saved.symbols.toSet());

  /// بيحفظ وبيضل بالمحرّر. ضغطة مزدوجة = حفظة وحدة.
  Future<void> _save() async {
    if (_saving) return;
    final l10n = AppLocalizations.of(context)!;
    final issues = _vm.validate(name: _name.text, symbols: _symbols, editingId: _editingId);
    if (issues.isNotEmpty) {
      setState(() => _attempted = true);
      return;
    }
    _messenger.currentState?.hideCurrentSnackBar();
    setState(() {
      _saving = true;
      _failure = null;
    });
    try {
      final id = _editingId;
      if (id == null) {
        final command = await _vm.create(name: _name.text, symbols: _symbols);
        if (!mounted) return;
        setState(() {
          _loadDraft(command.workspace);
          _justSaved = true;
        });
        _announce(l10n.workspaceSaved);
      } else {
        final command = await _vm.edit(id, name: _name.text, symbols: _symbols);
        if (!mounted) return;
        setState(() {
          if (command != null) _loadDraft(command.after);
          _justSaved = true;
        });
        // الـ snackbar بينقرأ لحالو (ما في إعلان تاني)
        if (command != null) _snack(l10n.workspaceUpdated, onUndo: () => _undoUpdate(command));
      }
    } on WorkspaceRuleException {
      if (mounted) setState(() => _attempted = true);
    } catch (_) {
      if (mounted) setState(() => _failure = l10n.workspaceSaveError);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _undoUpdate(UpdateWorkspaceCommand command) async {
    final undone = await _vm.undo(only: command);
    if (!undone || !mounted || _editingId != command.after.id) return;
    setState(() => _loadDraft(command.before));
  }

  Future<void> _delete() async {
    final id = _editingId;
    if (id == null || _saving) return;
    final l10n = AppLocalizations.of(context)!;
    setState(() => _saving = true);
    try {
      final command = await _vm.delete(id);
      if (!mounted) return;
      _saving = false;
      _closeEditor();
      final name = command.workspace.name;
      _snack(
        command.wasActive ? l10n.workspaceDeletedActive(name) : l10n.workspaceDeleted(name),
        onUndo: () => _vm.undo(only: command),
      );
    } catch (_) {
      if (mounted) setState(() => _failure = l10n.workspaceSaveError);
    } finally {
      if (mounted && _saving) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return FractionallySizedBox(
      heightFactor: 0.9,
      child: ScaffoldMessenger(
        key: _messenger,
        child: Scaffold(
          backgroundColor: Colors.transparent,
          body: PopScope(
            // الرجوع من المحرّر = للقائمة؛ من القائمة = بيسكّر الـ sheet
            canPop: !_editorOpen,
            onPopInvokedWithResult: (didPop, _) {
              if (!didPop) _closeEditor();
            },
            child: AnimatedSwitcher(
              duration: context.motion(AppMotion.fast),
              child: _editorOpen
                  ? KeyedSubtree(key: const ValueKey('editor'), child: _editor(context))
                  : KeyedSubtree(key: const ValueKey('list'), child: _list(context)),
            ),
          ),
        ),
      ),
    );
  }

  Widget _closeButton(BuildContext context) => IconButton(
        tooltip: MaterialLocalizations.of(context).closeButtonTooltip,
        constraints: const BoxConstraints(minWidth: AppSizes.minTap, minHeight: AppSizes.minTap),
        icon: Icon(Icons.close_rounded, color: context.colors.fg2),
        // pop مباشرة (مش maybePop): بيسكّر حتى لو المحرّر مفتوح
        onPressed: () => Navigator.of(context).pop(),
      );

  /// زر Undo / Redo بالرأس (تاريخ الأوامر نفسه يلي ورا Undo تبع الـ snackbar)
  Widget _historyButton(BuildContext context, {required bool redo, required bool enabled}) {
    final l10n = AppLocalizations.of(context)!;
    Future<void> run() async {
      AppHaptics.selection();
      // Undo تبع الـ snackbar بيصير قديم (أمره ما عاد الأخير)
      _messenger.currentState?.hideCurrentSnackBar();
      final done = redo ? await _vm.redo() : await _vm.undo();
      if (done && mounted) _announce(redo ? l10n.workspaceRedone : l10n.workspaceUndone);
    }

    return Semantics(
      button: true,
      enabled: enabled,
      label: redo ? l10n.workspaceRedoLabel : l10n.workspaceUndoLabel,
      onTap: enabled ? run : null,
      excludeSemantics: true,
      child: IconButton(
        tooltip: redo ? l10n.workspaceRedo : l10n.workspaceUndo,
        constraints: const BoxConstraints(minWidth: AppSizes.minTap, minHeight: AppSizes.minTap),
        icon: Icon(redo ? Icons.redo_rounded : Icons.undo_rounded, textDirection: Directionality.of(context)),
        color: context.colors.fg,
        disabledColor: context.colors.fg3,
        onPressed: enabled ? run : null,
      ),
    );
  }

  Widget _list(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;
    final state = ref.watch(workspacesViewModelProvider).valueOrNull;
    // كل أمر (وكل undo / redo) بيطلّع حالة جديدة، فالقيم هون دايمًا محدّثة
    final canUndo = state != null && _vm.canUndo;
    final canRedo = state != null && _vm.canRedo;
    final title = Semantics(header: true, child: Text(l10n.workspaces, style: text.titleLarge));
    final actions = [
      _historyButton(context, redo: false, enabled: canUndo),
      _historyButton(context, redo: true, enabled: canRedo),
    ];
    // بالخط الكبير العنوان بسطر لحالو (جنب 3 أزرار كان بينكسر بنص الكلمة)
    final largeText = MediaQuery.textScalerOf(context).scale(1) > 1.3;

    return ListView(
      padding: const EdgeInsets.fromLTRB(AppSpacing.lg, 0, AppSpacing.lg, AppSpacing.lg),
      children: [
        if (largeText) ...[
          Row(children: [...actions, const Spacer(), _closeButton(context)]),
          title,
        ] else
          Row(
            children: [
              Expanded(child: title),
              ...actions,
              _closeButton(context),
            ],
          ),
        const SizedBox(height: AppSpacing.xxs),
        Text(l10n.workspacesIntro, style: text.bodyMedium),
        const SizedBox(height: AppSpacing.md),
        _Rows(children: [
          if (state == null)
            for (var i = 0; i < 2; i++) const _SkeletonTile()
          else
            for (final w in state.all)
              _WorkspaceTile(
                key: ValueKey(w.id),
                workspace: w,
                active: w.id == state.active.id,
                onTap: () => _switch(w),
                onEdit: w.isDefault ? null : () => _openEditor(w),
              ),
        ]),
        if (state != null && state.custom.isEmpty) ...[
          const SizedBox(height: AppSpacing.sm),
          Text(l10n.workspacesHint, style: text.bodySmall),
        ],
        const SizedBox(height: AppSpacing.lg),
        AppButton.secondary(
          label: l10n.workspaceNew,
          icon: Icons.add_rounded,
          expand: true,
          onPressed: state == null || state.atLimit ? null : () => _openEditor(null),
        ),
        if (state != null && state.atLimit) ...[
          const SizedBox(height: AppSpacing.xs),
          Text(
            l10n.workspaceLimit('${WorkspacesState.maxCount}'),
            style: text.bodySmall!.copyWith(color: c.fg2),
            textAlign: TextAlign.center,
          ),
        ],
      ],
    );
  }

  Widget _editor(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;
    final state = ref.watch(workspacesViewModelProvider).valueOrNull;
    final saved = _saved(state);
    final dirty = _dirty(saved);
    final showSaved = _justSaved && !dirty;
    final issues = _vm.validate(name: _name.text, symbols: _symbols, editingId: _editingId);

    final nameError = !(_attempted || _nameEdited)
        ? null
        : issues.contains(WorkspaceIssue.nameRequired)
            ? l10n.workspaceNameRequired
            : issues.contains(WorkspaceIssue.nameTooLong)
                ? l10n.workspaceNameTooLong('${Workspace.maxNameLength}')
                : issues.contains(WorkspaceIssue.nameTaken)
                    ? l10n.workspaceNameTaken
                    : null;
    final symbolsError =
        (_attempted || _symbolsEdited) && issues.contains(WorkspaceIssue.noInstruments)
            ? l10n.workspacePickInstrument
            : null;
    final limitError = _attempted && issues.contains(WorkspaceIssue.limitReached)
        ? l10n.workspaceLimit('${WorkspacesState.maxCount}')
        : null;

    Widget message(String value) => Padding(
          padding: const EdgeInsets.only(top: AppSpacing.xs),
          child: Semantics(
            liveRegion: true,
            child: Text(value, style: text.bodyMedium!.copyWith(color: c.danger)),
          ),
        );

    return ListView(
      padding: const EdgeInsetsDirectional.fromSTEB(AppSpacing.xs, 0, AppSpacing.lg, AppSpacing.lg),
      children: [
        Row(
          children: [
            IconButton(
              tooltip: l10n.workspaceBack,
              constraints: const BoxConstraints(minWidth: AppSizes.minTap, minHeight: AppSizes.minTap),
              icon: const BackButtonIcon(),
              onPressed: _saving ? null : _closeEditor,
            ),
            Expanded(
              child: Semantics(
                header: true,
                child: Text(saved == null ? l10n.workspaceNew : l10n.workspaceEditTitle, style: text.titleLarge),
              ),
            ),
            _closeButton(context),
          ],
        ),
        Padding(
          padding: const EdgeInsetsDirectional.only(start: AppSpacing.sm),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: AppSpacing.sm),
              AppTextField(
                label: l10n.workspaceName,
                controller: _name,
                maxLength: Workspace.maxNameLength,
                errorText: nameError,
                enabled: !_saving,
                textInputAction: TextInputAction.done,
                textCapitalization: TextCapitalization.sentences,
                onChanged: (_) => setState(() {
                  _nameEdited = true;
                  _justSaved = false;
                }),
              ),
              // المثال بسطر لحالو (جنب العدّاد ما في مكان بالخط الكبير)
              Text(l10n.workspaceNameHint, style: text.bodySmall),
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.md, bottom: AppSpacing.xs),
                child: Semantics(header: true, child: Text(l10n.workspaceInstruments, style: text.titleSmall)),
              ),
              _Rows(children: [
                for (final symbol in kProductSymbols)
                  CheckboxListTile(
                    key: ValueKey('ws-symbol-$symbol'),
                    value: _symbols.contains(symbol),
                    onChanged: _saving
                        ? null
                        : (on) {
                            AppHaptics.selection();
                            setState(() {
                              _symbols = on ?? false ? {..._symbols, symbol} : ({..._symbols}..remove(symbol));
                              _symbolsEdited = true;
                              _justSaved = false;
                            });
                          },
                    title: Text(symbol, style: context.type.numSmall.copyWith(color: c.fg)),
                    subtitle: Text(l10n.instrumentName(symbol), style: text.bodySmall),
                  ),
              ]),
              if (symbolsError != null) message(symbolsError),
              if (limitError != null) message(limitError),
              if (_failure != null) message(_failure!),
              const SizedBox(height: AppSpacing.lg),
              // في تعديل → "Save" شغّال؛ بعد الحفظ "Saved" (أيقونة + كلمة) ومطفي
              AppButton(
                label: showSaved ? l10n.workspaceSavedState : l10n.save,
                icon: showSaved ? Icons.check_rounded : null,
                expand: true,
                loading: _saving,
                onPressed: dirty ? _save : null,
              ),
              if (saved != null) ...[
                const SizedBox(height: AppSpacing.xs),
                AppButton.ghost(
                  label: l10n.workspaceDelete,
                  icon: Icons.delete_outline_rounded,
                  expand: true,
                  onPressed: _saving ? null : _delete,
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

/// صفوف ببطاقة وحدة مفصولة بخطوط رفيعة
class _Rows extends StatelessWidget {
  const _Rows({required this.children});

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

/// صف مساحة: الضغط = التبديل (radio)، والقلم = التعديل
class _WorkspaceTile extends StatelessWidget {
  const _WorkspaceTile({
    super.key,
    required this.workspace,
    required this.active,
    required this.onTap,
    required this.onEdit,
  });

  static const double minHeight = 64;

  final Workspace workspace;
  final bool active;
  final VoidCallback onTap;
  final VoidCallback? onEdit;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;
    final name = workspaceDisplayName(l10n, workspace);
    final count = l10n.workspaceInstrumentCount(workspace.symbols.length);

    return ConstrainedBox(
      constraints: const BoxConstraints(minHeight: minHeight),
      child: Row(
        children: [
          Expanded(
            child: Semantics(
              button: true,
              selected: active,
              inMutuallyExclusiveGroup: true,
              label: '$name, $count',
              onTap: onTap,
              excludeSemantics: true,
              child: InkWell(
                onTap: onTap,
                child: ConstrainedBox(
                  constraints: const BoxConstraints(minHeight: minHeight),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
                    child: Row(
                      children: [
                        Icon(
                          active ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded,
                          size: AppSizes.iconLg,
                          color: active ? c.accent : c.fg3,
                        ),
                        const SizedBox(width: AppSpacing.sm),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(name, style: text.titleSmall),
                              const SizedBox(height: AppSpacing.xxs),
                              Text(count, style: text.bodySmall),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
          if (onEdit != null)
            Padding(
              padding: const EdgeInsetsDirectional.only(end: AppSpacing.xxs),
              child: IconButton(
                tooltip: l10n.workspaceEditNamed(name),
                constraints: const BoxConstraints(minWidth: AppSizes.minTap, minHeight: AppSizes.minTap),
                icon: Icon(Icons.edit_outlined, color: c.fg2),
                onPressed: onEdit,
              ),
            ),
        ],
      ),
    );
  }
}

class _SkeletonTile extends StatelessWidget {
  const _SkeletonTile();

  @override
  Widget build(BuildContext context) {
    return const SizedBox(
      height: _WorkspaceTile.minHeight,
      child: Padding(
        padding: EdgeInsets.symmetric(horizontal: AppSpacing.md),
        child: Row(
          children: [
            Skeleton(width: AppSizes.iconLg, height: AppSizes.iconLg, radius: AppRadii.pillAll),
            SizedBox(width: AppSpacing.sm),
            Skeleton(width: AppSpacing.huge * 2),
          ],
        ),
      ),
    );
  }
}
