import '../data/workspaces_repository.dart';
import '../models/workspace.dart';

/// تعديل على المساحات كـ Command: بيتنفّذ وبيتراجع عنه وبيرجع يتنفّذ (redo).
///
/// كل أمر بياخد الحالة الحالية وبيرجّع الجديدة، وبيكتب بالـ repository. القيم
/// يلي بيحتاجها التراجع (قبل التعديل، المكان، كانت فعّالة؟) بتنحفظ وقت الإنشاء.
sealed class WorkspaceCommand {
  const WorkspaceCommand();

  /// المساحة يلي بيخصّها الأمر
  Workspace get workspace;

  Future<WorkspacesState> execute(WorkspacesState state, WorkspacesRepository repo);

  Future<WorkspacesState> undo(WorkspacesState state, WorkspacesRepository repo);
}

/// إنشاء: المساحة الجديدة بتصير الفعّالة. التراجع بيرجّع الفعّالة القديمة.
final class CreateWorkspaceCommand extends WorkspaceCommand {
  const CreateWorkspaceCommand(this.workspace, {required this.previousActiveId});

  @override
  final Workspace workspace;
  final String previousActiveId;

  @override
  Future<WorkspacesState> execute(WorkspacesState state, WorkspacesRepository repo) async {
    await repo.create(workspace);
    await repo.saveActiveId(workspace.id);
    return state.copyWith(
      custom: [...state.custom.where((w) => w.id != workspace.id), workspace],
      activeId: workspace.id,
    );
  }

  @override
  Future<WorkspacesState> undo(WorkspacesState state, WorkspacesRepository repo) async {
    await repo.delete(workspace.id);
    final active = state.activeId == workspace.id ? previousActiveId : state.activeId;
    await repo.saveActiveId(active);
    return state.copyWith(custom: [...state.custom.where((w) => w.id != workspace.id)], activeId: active);
  }
}

/// تعديل الاسم و/أو الأدوات
final class UpdateWorkspaceCommand extends WorkspaceCommand {
  const UpdateWorkspaceCommand({required this.before, required this.after});

  final Workspace before;
  final Workspace after;

  @override
  Workspace get workspace => after;

  Future<WorkspacesState> _put(WorkspacesState state, WorkspacesRepository repo, Workspace value) async {
    await repo.update(value);
    return state.copyWith(custom: [for (final w in state.custom) w.id == value.id ? value : w]);
  }

  @override
  Future<WorkspacesState> execute(WorkspacesState state, WorkspacesRepository repo) => _put(state, repo, after);

  @override
  Future<WorkspacesState> undo(WorkspacesState state, WorkspacesRepository repo) => _put(state, repo, before);
}

/// حذف: إذا كانت الفعّالة، الـ Home بيرجع لـ "All instruments". التراجع
/// بيرجّعها لنفس مكانها ونفس حالتها (فعّالة أو لأ).
final class DeleteWorkspaceCommand extends WorkspaceCommand {
  const DeleteWorkspaceCommand(this.workspace, {required this.index, required this.wasActive});

  @override
  final Workspace workspace;
  final int index;
  final bool wasActive;

  @override
  Future<WorkspacesState> execute(WorkspacesState state, WorkspacesRepository repo) async {
    await repo.delete(workspace.id);
    final active = state.activeId == workspace.id ? Workspace.defaultId : state.activeId;
    if (active != state.activeId) await repo.saveActiveId(active);
    return state.copyWith(custom: [...state.custom.where((w) => w.id != workspace.id)], activeId: active);
  }

  @override
  Future<WorkspacesState> undo(WorkspacesState state, WorkspacesRepository repo) async {
    await repo.create(workspace, at: index);
    if (wasActive) await repo.saveActiveId(workspace.id);
    final list = [...state.custom.where((w) => w.id != workspace.id)];
    list.insert(index.clamp(0, list.length), workspace);
    return state.copyWith(custom: list, activeId: wasActive ? workspace.id : null);
  }
}

/// مكدّسين undo / redo. أمر جديد بيمسح الـ redo؛ أقدم الأوامر بينشالوا فوق [limit].
final class WorkspaceHistory {
  WorkspaceHistory({this.limit = 20});

  final int limit;
  final List<WorkspaceCommand> _undo = [];
  final List<WorkspaceCommand> _redo = [];

  bool get canUndo => _undo.isNotEmpty;
  bool get canRedo => _redo.isNotEmpty;
  WorkspaceCommand? get lastDone => _undo.isEmpty ? null : _undo.last;
  WorkspaceCommand? get lastUndone => _redo.isEmpty ? null : _redo.last;

  void push(WorkspaceCommand command) {
    _undo.add(command);
    if (_undo.length > limit) _undo.removeAt(0);
    _redo.clear();
  }

  /// بعد تراجع ناجح: من undo لـ redo
  void movedToRedo() => _redo.add(_undo.removeLast());

  /// بعد redo ناجح: من redo لـ undo
  void movedToUndo() => _undo.add(_redo.removeLast());

  void clear() {
    _undo.clear();
    _redo.clear();
  }
}
