import 'dart:convert';

import '../../../core/database/user_cache_guard.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/data/json.dart';
import '../../../core/storage/preferences_provider.dart';
import '../models/workspace.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';

/// مصدر مساحات العمل - بيتبدّل بتنفيذ API (`/me/workspaces`) بعدين.
///
/// "All instruments" مش محفوظة هون (بالتطبيق بس). الـ backend بيخزّن الأدوات
/// كـ `state.watchlist` (UUIDs الأدوات، مش رموز) والفعّالة كـ `is_default`.
abstract interface class WorkspacesRepository {
  /// المساحات الخاصة بترتيبها. بيانات تالفة → قائمة فاضية (الافتراضية بس).
  /// API: `GET /me/workspaces` (ملخّص) + `GET /me/workspaces/{id}` لـ `state.watchlist`.
  /// TODO(API): تحويل UUIDs الأدوات لرموز عبر `GET /market/instruments`.
  Future<List<Workspace>> list();

  /// [at] = مكانها (Undo الحذف بيرجّعها لمحلّها).
  /// API: `POST /me/workspaces` (`name` + `state` فيه `watchlist`)، والمكان عبر `PUT /me/workspaces/order`.
  /// TODO(API): الـ backend بيطلب `state.panels` (لوحة وحدة عالأقل) و`active_panel`؛ ما في restore فالـ Undo بيعيد الإنشاء (id جديد).
  Future<void> create(Workspace workspace, {int? at});

  /// API: `PATCH /me/workspaces/{id}` (الاسم) + `PUT /me/workspaces/{id}` (`state.watchlist`، مع `version`).
  /// TODO(API): 409 لما الاسم مكرر أو النسخة قديمة.
  Future<void> update(Workspace workspace);

  /// API: `DELETE /me/workspaces/{id}` (204).
  /// TODO(API): ما في restore؛ الـ Undo = `POST` من جديد.
  Future<void> delete(String id);

  /// الفعّالة (null = ما في شي محفوظ).
  /// API: `GET /me/workspaces` → العنصر يلي `is_default: true`.
  /// TODO(API): "All instruments" مش موجودة بالـ backend؛ لازم نخزّنها محليًا أو نضيف حقل.
  Future<String?> readActiveId();

  /// API: `PATCH /me/workspaces/{id}` (`is_default: true`).
  /// TODO(API): الرجوع لـ "All instruments" ما إلو endpoint.
  Future<void> saveActiveId(String id);
}

/// محفوظ على الجهاز (SharedPreferences) لحد ما ينربط الحساب
final class LocalWorkspacesRepository implements WorkspacesRepository {
  const LocalWorkspacesRepository(this.prefs);

  static const storageKey = 'workspaces';
  static const activeKey = 'workspaces_active';

  final SharedPreferences prefs;

  /// بيقرأ بأمان: JSON مكسور أو مش قائمة → فاضي؛ عنصر غلط أو مكرر (id أو
  /// اسم) بينتشال؛ وفوق الحد الأقصى بينقص.
  List<Workspace> _read() {
    final raw = prefs.getString(storageKey);
    if (raw == null) return const [];
    Object? decoded;
    try {
      decoded = jsonDecode(raw);
    } on FormatException {
      return const [];
    }
    if (decoded is! List) return const [];
    final ids = <String>{};
    final names = <String>{};
    final out = <Workspace>[];
    for (final item in decoded) {
      final json = Json.from(item);
      final w = json == null ? null : Workspace.fromJson(json);
      if (w == null || !ids.add(w.id) || !names.add(w.name.toLowerCase())) continue;
      out.add(w);
      if (out.length >= WorkspacesState.maxCount - 1) break;
    }
    return out;
  }

  Future<void> _write(List<Workspace> list) =>
      prefs.setString(storageKey, jsonEncode([for (final w in list) w.toJson()]));

  @override
  Future<List<Workspace>> list() async => List.unmodifiable(_read());

  @override
  Future<void> create(Workspace workspace, {int? at}) {
    final list = [..._read()]..removeWhere((w) => w.id == workspace.id);
    list.insert((at ?? list.length).clamp(0, list.length), workspace);
    return _write(list);
  }

  @override
  Future<void> update(Workspace workspace) =>
      _write([for (final w in _read()) w.id == workspace.id ? workspace : w]);

  @override
  Future<void> delete(String id) => _write([for (final w in _read()) if (w.id != id) w]);

  @override
  Future<String?> readActiveId() async => prefs.getString(activeKey);

  @override
  Future<void> saveActiveId(String id) => prefs.setString(activeKey, id);
}

final workspacesRepositoryProvider = Provider<WorkspacesRepository>((ref) {
  // H5d: لكل حساب - نسخة جديدة لما يتغيّر الحساب (التخزين المحلي تبع الحساب
  // السابق بينمسح بالـ guard، والذاكرة بتروح مع النسخة القديمة)
  ref.watch(cacheOwnerProvider);
  return apiSource(
    ref,
    ApiFeature.workspaces,
    simulated: () => LocalWorkspacesRepository(ref.watch(sharedPreferencesProvider)),
  );
});
