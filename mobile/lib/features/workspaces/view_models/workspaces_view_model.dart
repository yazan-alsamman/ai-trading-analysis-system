import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../l10n/app_localizations.dart';
import '../data/workspaces_repository.dart';
import '../models/workspace.dart';
import 'workspace_commands.dart';

/// الحفظ انرفض بسبب قاعدة ([issues])
final class WorkspaceRuleException implements Exception {
  const WorkspaceRuleException(this.issues);

  final Set<WorkspaceIssue> issues;

  @override
  String toString() => 'WorkspaceRuleException($issues)';
}

/// ViewModel مساحات العمل: الإنشاء والتعديل والحذف كـ Commands مع undo / redo،
/// والتبديل بين المساحات.
///
/// - مش autoDispose: الفعّالة بتضل لحد ما المستخدم يغيّرها (ولا شي بيرجّعها
///   لحالو)، ومحفوظة بالـ repository فبتضل بعد إعادة التشغيل.
/// - تخزين تالف أو فشل بالقراءة → "All instruments" بس.
/// - كل العمليات بالدور (طابور): ضغطات سريعة ورا بعض كل وحدة بتتحقق من
///   الحالة يلي تركتها يلي قبلها، فما في اسمين مكررين ولا حالة قديمة.
/// - بعد أي `await`: إذا انعمل dispose ما في كتابة عالحالة.
class WorkspacesViewModel extends AsyncNotifier<WorkspacesState> {
  final WorkspaceHistory _history = WorkspaceHistory();
  Future<void> _queue = Future.value();
  bool _disposed = false;
  int _seq = 0;

  /// اسم "All instruments" بكل اللغات - ما بينفع اسم لمساحة خاصة
  static final Set<String> reservedNames = {
    for (final locale in AppLocalizations.supportedLocales) AppLocalizations(locale).workspaceAll,
  };

  bool get canUndo => _history.canUndo;
  bool get canRedo => _history.canRedo;

  @override
  Future<WorkspacesState> build() async {
    _disposed = false;
    ref.onDispose(() => _disposed = true);
    final repo = ref.watch(workspacesRepositoryProvider);
    try {
      final (custom, activeId) = await (repo.list(), repo.readActiveId()).wait;
      final loaded = WorkspacesState(custom: List.unmodifiable(custom));
      final known = activeId != null && loaded.byId(activeId) != null;
      return loaded.copyWith(activeId: known ? activeId : Workspace.defaultId);
    } catch (_) {
      return const WorkspacesState();
    }
  }

  WorkspacesRepository get _repo => ref.read(workspacesRepositoryProvider);

  /// قواعد الحفظ على الحالة الحالية (الـ sheet بتعرض الرسائل منها)
  Set<WorkspaceIssue> validate({required String name, required Iterable<String> symbols, String? editingId}) =>
      workspaceIssues(
        state.valueOrNull ?? const WorkspacesState(),
        name: name,
        symbols: symbols,
        editingId: editingId,
        reservedNames: reservedNames,
      );

  /// بيشغّل [op] بعد يلي قبلها، على آخر حالة
  Future<T> _serial<T>(Future<T> Function(WorkspacesState current) op) {
    final run = _queue.then((_) async => op(await future));
    _queue = run.then<void>((_) {}, onError: (Object _) {});
    return run;
  }

  void _emit(WorkspacesState next) {
    if (!_disposed) state = AsyncData(next);
  }

  Future<void> _execute(WorkspaceCommand command, WorkspacesState current) async {
    final next = await command.execute(current, _repo);
    if (_disposed) return;
    _history.push(command);
    _emit(next);
  }

  void _check(WorkspacesState current, {required String name, required Iterable<String> symbols, String? editingId}) {
    final issues = workspaceIssues(
      current,
      name: name,
      symbols: symbols,
      editingId: editingId,
      reservedNames: reservedNames,
    );
    if (issues.isNotEmpty) throw WorkspaceRuleException(issues);
  }

  String _newId() => 'ws_${DateTime.now().microsecondsSinceEpoch.toRadixString(36)}_${_seq++}';

  /// مساحة جديدة، وبتصير الفعّالة
  Future<CreateWorkspaceCommand> create({required String name, required Iterable<String> symbols}) =>
      _serial((current) async {
        _check(current, name: name, symbols: symbols);
        final command = CreateWorkspaceCommand(
          Workspace(id: _newId(), name: Workspace.normalizeName(name), symbols: Workspace.orderSymbols(symbols)),
          previousActiveId: current.activeId,
        );
        await _execute(command, current);
        return command;
      });

  /// null = ما تغيّر شي (ما في أمر ولا Undo)
  Future<UpdateWorkspaceCommand?> edit(String id, {required String name, required Iterable<String> symbols}) =>
      _serial((current) async {
        _check(current, name: name, symbols: symbols, editingId: id);
        final before = current.byId(id)!;
        final after = before.copyWith(name: Workspace.normalizeName(name), symbols: symbols);
        if (after == before) return null;
        final command = UpdateWorkspaceCommand(before: before, after: after);
        await _execute(command, current);
        return command;
      });

  /// "All instruments" ما بتنحذف
  Future<DeleteWorkspaceCommand> delete(String id) => _serial((current) async {
        if (id == Workspace.defaultId) throw const WorkspaceRuleException({WorkspaceIssue.defaultLocked});
        final index = current.indexOf(id);
        if (index < 0) throw const WorkspaceRuleException({WorkspaceIssue.notFound});
        final command = DeleteWorkspaceCommand(
          current.custom[index],
          index: index,
          wasActive: current.activeId == id,
        );
        await _execute(command, current);
        return command;
      });

  /// التبديل (مش Command: ما في Undo للتبديل). مساحة مش معروفة → ما في شي.
  Future<void> setActive(String id) => _serial((current) async {
        if (current.activeId == id || current.byId(id) == null) return;
        await _repo.saveActiveId(id);
        _emit(current.copyWith(activeId: id));
      });

  /// تراجع عن آخر أمر. [only] = زر Undo تبع snackbar معيّن: بيتراجع بس إذا
  /// هالأمر لسّا الأخير (ما في شي صار بعده)، وإلا false.
  Future<bool> undo({WorkspaceCommand? only}) => _serial((current) async {
        final command = _history.lastDone;
        if (command == null || (only != null && !identical(command, only))) return false;
        final next = await command.undo(current, _repo);
        if (_disposed) return false;
        _history.movedToRedo();
        _emit(next);
        return true;
      });

  Future<bool> redo() => _serial((current) async {
        final command = _history.lastUndone;
        if (command == null) return false;
        final next = await command.execute(current, _repo);
        if (_disposed) return false;
        _history.movedToUndo();
        _emit(next);
        return true;
      });
}

final workspacesViewModelProvider =
    AsyncNotifierProvider<WorkspacesViewModel, WorkspacesState>(WorkspacesViewModel.new);

/// المساحة الفعّالة (الـ Home والـ chip)
final activeWorkspaceProvider = Provider<AsyncValue<Workspace>>(
  (ref) => ref.watch(workspacesViewModelProvider).whenData((s) => s.active),
);

/// اسم المساحة كما بينعرض ("All instruments" مترجمة)
String workspaceDisplayName(AppLocalizations l10n, Workspace workspace) =>
    workspace.isDefault ? l10n.workspaceAll : workspace.name;

