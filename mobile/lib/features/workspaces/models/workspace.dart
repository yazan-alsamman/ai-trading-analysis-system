import 'package:flutter/foundation.dart';

import '../../../core/data/json.dart';
import '../../markets/models/market_models.dart';

/// مساحة عمل: قائمة أدوات باسم، بتقرر شو بتعرض قائمة المتابعة بالـ Home.
///
/// "All instruments" ([Workspace.all]) دايمًا موجودة وما بتنحذف ولا بتتعدّل؛
/// اسمها مترجم بالشاشة، فـ [name] تبعها فاضي.
@immutable
final class Workspace {
  const Workspace({required this.id, required this.name, required this.symbols});

  final String id;
  final String name;

  /// دايمًا بترتيب [kProductSymbols] وبدون تكرار ([orderSymbols])
  final List<String> symbols;

  static const String defaultId = 'all';

  /// أطول اسم (الـ backend بيقبل 60؛ 24 حتى يضل الـ chip مقروء)
  static const int maxNameLength = 24;

  static final Workspace all = Workspace(
    id: defaultId,
    name: '',
    symbols: List.unmodifiable(kProductSymbols),
  );

  bool get isDefault => id == defaultId;

  /// الأدوات المعروفة بس، بترتيب المنتج
  static List<String> orderSymbols(Iterable<String> symbols) {
    final set = symbols.toSet();
    return List.unmodifiable([for (final s in kProductSymbols) if (set.contains(s)) s]);
  }

  /// بيشيل المسافات من الطرفين وبيجمع المسافات بالنص لمسافة وحدة
  static String normalizeName(String name) => name.trim().replaceAll(RegExp(r'\s+'), ' ');

  Workspace copyWith({String? name, Iterable<String>? symbols}) => Workspace(
        id: id,
        name: name ?? this.name,
        symbols: symbols == null ? this.symbols : orderSymbols(symbols),
      );

  Map<String, Object?> toJson() => {'id': id, 'name': name, 'symbols': symbols};

  /// null لما العنصر مش صالح (بدون id، اسم فاضي أو طويل، ولا أداة معروفة)
  static Workspace? fromJson(Json json) {
    final id = json.string('id');
    final name = normalizeName(json.string('name') ?? '');
    final raw = json.raw['symbols'];
    if (id == null || id.isEmpty || id == defaultId || raw is! List) return null;
    if (name.isEmpty || name.length > maxNameLength) return null;
    final symbols = orderSymbols(raw.whereType<String>());
    if (symbols.isEmpty) return null;
    return Workspace(id: id, name: name, symbols: symbols);
  }

  @override
  bool operator ==(Object other) =>
      other is Workspace && other.id == id && other.name == name && listEquals(other.symbols, symbols);

  @override
  int get hashCode => Object.hash(id, name, Object.hashAll(symbols));

  @override
  String toString() => 'Workspace($id, $name, $symbols)';
}

/// كل المساحات + الفعّالة. [custom] بترتيب الإنشاء (الافتراضية مش منها).
@immutable
final class WorkspacesState {
  const WorkspacesState({this.custom = const [], this.activeId = Workspace.defaultId});

  /// أكتر عدد مساحات (مع "All instruments")
  static const int maxCount = 10;

  final List<Workspace> custom;
  final String activeId;

  List<Workspace> get all => [Workspace.all, ...custom];

  /// الفعّالة؛ إذا انحذفت أو ما انعرفت → الافتراضية
  Workspace get active => byId(activeId) ?? Workspace.all;

  bool get atLimit => custom.length + 1 >= maxCount;

  Workspace? byId(String id) {
    if (id == Workspace.defaultId) return Workspace.all;
    for (final w in custom) {
      if (w.id == id) return w;
    }
    return null;
  }

  int indexOf(String id) => custom.indexWhere((w) => w.id == id);

  WorkspacesState copyWith({List<Workspace>? custom, String? activeId}) => WorkspacesState(
        custom: custom == null ? this.custom : List.unmodifiable(custom),
        activeId: activeId ?? this.activeId,
      );

  @override
  bool operator ==(Object other) =>
      other is WorkspacesState && other.activeId == activeId && listEquals(other.custom, custom);

  @override
  int get hashCode => Object.hash(activeId, Object.hashAll(custom));
}

/// ليش ما بينحفظ (الشاشة بتعرض الرسالة المناسبة)
enum WorkspaceIssue { nameRequired, nameTooLong, nameTaken, noInstruments, limitReached, defaultLocked, notFound }

/// قواعد الحفظ بمكان واحد (الـ ViewModel والـ sheet).
///
/// - الاسم لازم ومحدود الطول، وما بيتكرر (بدون فرق أحرف كبيرة/صغيرة، ومع
///   اسم "All instruments" بكل اللغات [reservedNames]).
/// - أداة وحدة عالأقل، وما بيصير أكتر من [WorkspacesState.maxCount] مساحة.
/// - [editingId] = تعديل مساحة موجودة (اسمها ما بيتعدّ مكرر).
Set<WorkspaceIssue> workspaceIssues(
  WorkspacesState state, {
  required String name,
  required Iterable<String> symbols,
  String? editingId,
  Set<String> reservedNames = const {},
}) {
  final issues = <WorkspaceIssue>{};
  if (editingId == Workspace.defaultId) return {WorkspaceIssue.defaultLocked};
  if (editingId != null && state.byId(editingId) == null) return {WorkspaceIssue.notFound};
  final normalized = Workspace.normalizeName(name);
  final key = normalized.toLowerCase();
  if (normalized.isEmpty) {
    issues.add(WorkspaceIssue.nameRequired);
  } else if (normalized.length > Workspace.maxNameLength) {
    issues.add(WorkspaceIssue.nameTooLong);
  } else if (reservedNames.any((r) => r.toLowerCase() == key) ||
      state.custom.any((w) => w.id != editingId && w.name.toLowerCase() == key)) {
    issues.add(WorkspaceIssue.nameTaken);
  }
  if (Workspace.orderSymbols(symbols).isEmpty) issues.add(WorkspaceIssue.noInstruments);
  if (editingId == null && state.atLimit) issues.add(WorkspaceIssue.limitReached);
  return issues;
}
