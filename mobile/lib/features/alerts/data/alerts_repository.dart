import 'dart:convert';

import '../../../core/database/user_cache_guard.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/data/json.dart';
import '../../../core/storage/preferences_provider.dart';
import '../models/price_alert.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';

/// `PriceAlertRead` (backend/app/schemas/price_alerts.py) → domain.
///
/// H4a بيقترح حقول جديدة: `status` (active | paused | triggered | expired)،
/// `expires_at`، `triggered_price`، `armed`. بدون `status` (الشكل الحالي
/// بالـ backend) الحالة بتنحسب من `is_active` و `last_triggered_at`.
final class PriceAlertDto {
  const PriceAlertDto(this.json);

  final Json json;

  PriceAlert? toDomain() {
    final id = json.string('id');
    final symbol = json.object('instrument')?.string('symbol')?.trim().toUpperCase();
    final condition = AlertCondition.fromApi(json.string('condition'));
    final value = json.number('value');
    final createdAt = json.dateTime('created_at');
    if (id == null || symbol == null || condition == null || value == null || value <= 0 || createdAt == null) {
      return null;
    }
    final triggeredAt = json.dateTime('last_triggered_at');
    final rawStatus = json.string('status');
    final status = rawStatus == null
        ? (json.boolean('is_active') ?? true)
            ? AlertStatus.active
            : triggeredAt != null
                ? AlertStatus.triggered
                : AlertStatus.paused
        : AlertStatus.fromApi(rawStatus);
    // حالة مش معروفة → التنبيه بينرمى (ما منخمّن)
    if (status == null) return null;
    final price = json.number('triggered_price');
    return PriceAlert(
      id: id,
      symbol: symbol,
      condition: condition,
      value: value,
      status: status,
      note: json.string('note'),
      createdAt: createdAt,
      expiresAt: json.dateTime('expires_at'),
      lastTriggeredAt: triggeredAt,
      triggeredPrice: price != null && price > 0 ? price : null,
      armed: json.boolean('armed') ?? true,
    );
  }

  /// نفس شكل `PriceAlertRead` (+ حقول H4a) - للتخزين المحلي وللـ restore
  static Map<String, Object?> toJson(PriceAlert a) => {
        'id': a.id,
        'instrument': {'id': null, 'symbol': a.symbol},
        'condition': a.condition.apiValue,
        'value': a.value,
        'repeat': 'once',
        'note': a.note,
        'is_active': a.isActive,
        'status': a.status.apiValue,
        'expires_at': a.expiresAt?.toUtc().toIso8601String(),
        'last_triggered_at': a.lastTriggeredAt?.toUtc().toIso8601String(),
        'triggered_price': a.triggeredPrice,
        'armed': a.armed,
        'created_at': a.createdAt.toUtc().toIso8601String(),
      };

  /// جسم `PriceAlertCreate` (+ `expires_at` المقترح). دايمًا `repeat: once`:
  /// بعد ما يشتغل بيروح عالسجل، و"Set again" بينشئ واحد جديد.
  static Map<String, Object?> createBody(AlertDraft draft, {String? instrumentId}) => {
        'instrument_id': instrumentId,
        'condition': draft.condition.apiValue,
        'value': draft.value,
        'repeat': 'once',
        if (draft.note case final note? when note.trim().isNotEmpty) 'note': note.trim(),
        if (draft.expiresAt case final at?) 'expires_at': at.toUtc().toIso8601String(),
      };
}

/// مصدر التنبيهات - بيتبدّل بتنفيذ API (`/me/price-alerts`)
abstract interface class AlertsRepository {
  /// `GET /me/price-alerts` (+ `/history` للي اشتغلت/انتهت)
  Future<List<PriceAlert>> list();

  /// `POST /me/price-alerts` (`PriceAlertCreate` + `expires_at`)
  Future<PriceAlert> create(AlertDraft draft);

  /// `PATCH /me/price-alerts/{id}` (`is_active`). إيقاف/استئناف بس بين
  /// Active و Paused؛ بأي حالة تانية بيرجّع النسخة المحفوظة بدون تغيير.
  Future<PriceAlert> setActive(String id, {required bool active});

  /// `DELETE /me/price-alerts/{id}` (204). بيرجّع النسخة يلي انحذفت (حتى
  /// Undo يرجّع حالتها الحقيقية حتى لو اشتغلت بآخر لحظة)، null = مش موجود.
  /// TODO(API): الـ backend ما بيرجّع جسم؛ التنفيذ الحقيقي بيرجّع آخر نسخة قرأها.
  Future<PriceAlert?> delete(String id);

  /// يرجّع تنبيه انحذف (Undo) بنفس بياناته وحالته.
  /// TODO(API): ما في restore بالـ backend؛ لازم `POST` بنفس الحالة أو route جديد.
  Future<PriceAlert> restore(PriceAlert alert);

  /// H4a: سعر جديد لتنبيه واحد، على النسخة المحفوظة (ذرّي): Active + عبر
  /// المستوى → Triggered (مرة وحدة بس)؛ انتهت مدته → Expired (ما بيشتغل)؛
  /// بيستنّى عبور جديد ورجع السعر لجهة البداية → جاهز. null = ما تغيّر شي.
  /// TODO(API): الخادم هو يلي بيفحص الأسعار (`price_alert` worker) وبيغيّر
  /// الحالة؛ التطبيق بيقرأها من `GET /me/price-alerts`، فهالطريقة بتختفي.
  Future<PriceAlert?> applyPrice(String id, {required double price, required DateTime at});

  /// H4a: كل تنبيه Active / Paused مرّ وقت انتهائه → Expired. بيرجّع يلي تغيّروا.
  /// TODO(API): الخادم بينهيها عند `expires_at`؛ التطبيق بيقرأ الحالة بس.
  Future<List<PriceAlert>> expireDue(DateTime now);
}

/// بالذاكرة: نفس شكل الـ JSON حتى طبقة الـ DTO تنفحص. [persist] بينادى بعد
/// كل تغيير (التنفيذ المحلي بيحفظ فيه).
class InMemoryAlertsRepository implements AlertsRepository {
  InMemoryAlertsRepository({DateTime Function()? clock, List<Map<String, Object?>>? rows})
      : _clock = clock ?? DateTime.now,
        _rows = rows ?? [];

  final DateTime Function() _clock;
  final List<Map<String, Object?>> _rows;
  var _nextId = 1;

  @protected
  List<Map<String, Object?>> get rows => _rows;

  /// بعد كل تغيير (المحلي بيكتب بالتخزين)
  @protected
  Future<void> persist() async {}

  int _index(String id) => _rows.indexWhere((r) => r['id'] == id);

  PriceAlert? _at(int i) => i < 0 ? null : PriceAlertDto(Json(_rows[i])).toDomain();

  Future<PriceAlert> _put(int i, PriceAlert alert) async {
    _rows[i] = PriceAlertDto.toJson(alert);
    await persist();
    return alert;
  }

  String _newId() {
    String id;
    do {
      id = 'alert-${_clock().microsecondsSinceEpoch.toRadixString(36)}-${_nextId++}';
    } while (_index(id) >= 0);
    return id;
  }

  @override
  Future<List<PriceAlert>> list() async => mapValid(_rows, (r) => PriceAlertDto(Json(r)).toDomain());

  @override
  Future<PriceAlert> create(AlertDraft draft) async {
    if (draft.note != null && draft.note!.length > 200) {
      throw ArgumentError.value(draft.note, 'note', 'max 200 characters');
    }
    final body = PriceAlertDto.createBody(draft);
    final alert = PriceAlert(
      id: _newId(),
      symbol: draft.symbol,
      condition: draft.condition,
      value: (body['value']! as num).toDouble(),
      status: AlertStatus.active,
      note: body['note'] as String?,
      createdAt: _clock().toUtc(),
      expiresAt: draft.expiresAt?.toUtc(),
      armed: draft.armed,
    );
    _rows.insert(0, PriceAlertDto.toJson(alert));
    await persist();
    return alert;
  }

  @override
  Future<PriceAlert> setActive(String id, {required bool active}) async {
    final i = _index(id);
    final saved = _at(i);
    if (saved == null) throw StateError('alert $id not found');
    final next = saved.moveTo(active ? AlertStatus.active : AlertStatus.paused);
    if (next == null) return saved;
    return _put(i, next);
  }

  @override
  Future<PriceAlert?> delete(String id) async {
    final i = _index(id);
    if (i < 0) return null;
    final saved = _at(i);
    _rows.removeAt(i);
    await persist();
    return saved;
  }

  @override
  Future<PriceAlert> restore(PriceAlert alert) async {
    if (_index(alert.id) >= 0) return alert;
    _rows.add(PriceAlertDto.toJson(alert));
    _rows.sort((a, b) => '${b['created_at']}'.compareTo('${a['created_at']}'));
    await persist();
    return alert;
  }

  @override
  Future<PriceAlert?> applyPrice(String id, {required double price, required DateTime at}) async {
    final i = _index(id);
    final saved = _at(i);
    if (saved == null || saved.status != AlertStatus.active) return null;
    // انتهت مدته قبل هالسعر → Expired، وما بيشتغل أبدًا
    if (saved.isDue(at)) return _put(i, saved.moveTo(AlertStatus.expired)!);
    if (!saved.armed) {
      return saved.crossedBy(price) ? null : _put(i, saved.copyWith(armed: true));
    }
    if (!saved.crossedBy(price)) return null;
    return _put(i, saved.moveTo(AlertStatus.triggered, at: at.toUtc(), price: price)!);
  }

  @override
  Future<List<PriceAlert>> expireDue(DateTime now) async {
    final changed = <PriceAlert>[];
    for (var i = 0; i < _rows.length; i++) {
      final saved = _at(i);
      if (saved == null || !saved.isDue(now)) continue;
      final next = saved.moveTo(AlertStatus.expired)!;
      _rows[i] = PriceAlertDto.toJson(next);
      changed.add(next);
    }
    if (changed.isNotEmpty) await persist();
    return changed;
  }
}

/// محلي (لحد ما ينربط الـ API): نفس الذاكرة + SharedPreferences (مفتاح
/// [storageKey]، قائمة `PriceAlertRead` JSON)، فالحالات بتضل بعد إعادة التشغيل.
/// تخزين تالف → ما في تنبيهات؛ عنصر غلط بينرمى.
class LocalAlertsRepository extends InMemoryAlertsRepository {
  LocalAlertsRepository(this._prefs, {super.clock}) : super(rows: _read(_prefs));

  static const storageKey = 'price_alerts';

  final SharedPreferences _prefs;

  static List<Map<String, Object?>> _read(SharedPreferences prefs) {
    try {
      final raw = jsonDecode(prefs.getString(storageKey) ?? '[]');
      if (raw is! List) return [];
      return [
        for (final item in raw)
          if (item is Map<String, Object?> && PriceAlertDto(Json(item)).toDomain() != null) item,
      ];
    } catch (_) {
      return [];
    }
  }

  @override
  Future<void> persist() => _prefs.setString(storageKey, jsonEncode(rows));
}

/// ساعة التنبيهات (الانتهاء والإنشاء). الاختبارات بتثبّتها.
final alertsClockProvider = Provider<DateTime Function()>((ref) => DateTime.now);

final alertsRepositoryProvider = Provider<AlertsRepository>((ref) {
  // H5d: لكل حساب - نسخة جديدة لما يتغيّر الحساب (التخزين المحلي تبع الحساب
  // السابق بينمسح بالـ guard، والذاكرة بتروح مع النسخة القديمة)
  ref.watch(cacheOwnerProvider);
  return apiSource(
    ref,
    ApiFeature.alerts,
    simulated: () => LocalAlertsRepository(ref.watch(sharedPreferencesProvider), clock: ref.watch(alertsClockProvider)),
  );
});
