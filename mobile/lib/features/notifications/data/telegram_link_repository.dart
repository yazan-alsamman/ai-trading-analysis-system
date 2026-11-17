import 'dart:convert';
import '../../../core/database/user_cache_guard.dart';
import 'dart:math';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/data/json.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';
import '../../../core/storage/preferences_provider.dart';
import '../models/telegram_link.dart';

/// ربط حساب Telegram (H4b). عام عن قصد: طريقة الربط الحقيقية (بوت + كود
/// لمرة وحدة، أو غيرها) سؤال مفتوح لصاحب الـ backend؛ التطبيق بيعرف بس:
/// كود بمدة صلاحية + اسم البوت، فحص الحالة، فك الربط.
abstract interface class TelegramLinkRepository {
  /// حالة الربط الحالية.
  /// API (مقترح): `GET /me/telegram` → `{linked, handle, linked_at}`.
  /// TODO(API): المسار والشكل عند صاحب الـ backend.
  Future<TelegramLinkStatus> status();

  /// كود ربط جديد لمرة وحدة (الكود القديم بيبطل).
  /// API (مقترح): `POST /me/telegram/link-codes` → `{code, expires_at, bot_username}`.
  /// TODO(API): مدة الصلاحية من `expires_at` (التطبيق ما بيفرض 10 دقايق).
  Future<TelegramLinkCode> requestCode();

  /// فحص الكود بعد ما المستخدم بعتو للبوت: [TelegramLinked] = انربط،
  /// [TelegramNotLinked] = لسّا ما وصل. كود منتهي / مستعمل → [TelegramCodeExpiredException].
  /// API (مقترح): `GET /me/telegram/link-codes/{code}` → `{status: pending|linked|expired, handle}`.
  /// TODO(API): polling ولا push؟ (سؤال مفتوح).
  Future<TelegramLinkStatus> checkCode(String code);

  /// فك الربط.
  /// API (مقترح): `DELETE /me/telegram`.
  /// TODO(API).
  Future<void> unlink();

  /// Undo لفك الربط: نفس الربط يرجع بدون كود جديد.
  /// API (مقترح): `POST /me/telegram/restore` (خلال مهلة الـ Undo) - أو التطبيق
  /// بيأجّل `DELETE` لحد ما تخلص المهلة. TODO(API): القرار عند صاحب الـ backend.
  Future<void> restore(TelegramLinked link);
}

/// ساعة الربط (صلاحية الكود والعدّ التنازلي) - الاختبارات بتثبّتها
final telegramClockProvider = Provider<DateTime Function()>((ref) => DateTime.now);

/// محاكاة: الربط محفوظ على الجهاز (بيضل بعد إعادة التشغيل)، الكود بالذاكرة.
/// "Check connection" = المستخدم بعت الكود للبوت، فالكود الصالح بيربط.
/// كود منتهي أو مستعمل أو انستبدل ما بيرجع يشتغل أبدًا.
class SimulatedTelegramLinkRepository implements TelegramLinkRepository {
  SimulatedTelegramLinkRepository({
    required this.prefs,
    DateTime Function()? clock,
    this.latency = Duration.zero,
    String Function(int request)? codeFor,
    this.handle = '@trader_demo',
  })  : _clock = clock ?? DateTime.now,
        _codeFor = codeFor ?? _randomCode;

  static const storageKey = 'telegram_link';
  static const botUsername = 'TradingAssistantDemoBot';

  final SharedPreferences prefs;
  final DateTime Function() _clock;
  final String Function(int request) _codeFor;
  final Duration latency;
  final String? handle;

  /// الكود الصالح الوحيد (طلب جديد بيلغي القديم)
  ({String code, DateTime expiresAt})? _issued;
  var _requests = 0;

  /// كل الأكواد يلي انطلبت (للاختبارات: ما في كود بيتكرّر)
  final issuedCodes = <String>[];

  static final _random = Random.secure();
  static const _alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';

  static String _randomCode(int _) =>
      String.fromCharCodes([for (var i = 0; i < 6; i++) _alphabet.codeUnitAt(_random.nextInt(_alphabet.length))]);

  Future<void> _wait() async {
    if (latency > Duration.zero) await Future<void>.delayed(latency);
  }

  @override
  Future<TelegramLinkStatus> status() async {
    await _wait();
    return _read();
  }

  TelegramLinkStatus _read() {
    try {
      final json = Json.from(jsonDecode(prefs.getString(storageKey) ?? 'null'));
      final at = json?.dateTime('linked_at');
      if (json == null || json.boolean('linked') != true || at == null) return const TelegramNotLinked();
      final name = json.string('handle')?.trim();
      return TelegramLinked(handle: name == null || name.isEmpty ? null : name, linkedAt: at);
    } on FormatException {
      return const TelegramNotLinked();
    }
  }

  Future<void> _save(TelegramLinked link) => prefs.setString(
        storageKey,
        jsonEncode({'linked': true, 'handle': link.handle, 'linked_at': link.linkedAt.toUtc().toIso8601String()}),
      );

  @override
  Future<TelegramLinkCode> requestCode() async {
    await _wait();
    _requests++;
    var code = _codeFor(_requests);
    // كود ما بيتكرّر أبدًا (حتى لو المولّد رجّع نفسو)
    while (issuedCodes.contains(code)) {
      code = '$code${_requests % 10}';
    }
    issuedCodes.add(code);
    final expiresAt = _clock().toUtc().add(TelegramLinkCode.validity);
    _issued = (code: code, expiresAt: expiresAt);
    return TelegramLinkCode(code: code, expiresAt: expiresAt, botUsername: botUsername);
  }

  @override
  Future<TelegramLinkStatus> checkCode(String code) async {
    await _wait();
    final issued = _issued;
    if (issued == null || issued.code != code || !_clock().toUtc().isBefore(issued.expiresAt)) {
      if (issued?.code == code) _issued = null;
      throw const TelegramCodeExpiredException();
    }
    // مستعمل = ما بيشتغل مرة تانية
    _issued = null;
    final link = TelegramLinked(handle: handle, linkedAt: _clock().toUtc());
    await _save(link);
    return link;
  }

  @override
  Future<void> unlink() async {
    await _wait();
    _issued = null;
    await prefs.remove(storageKey);
  }

  @override
  Future<void> restore(TelegramLinked link) async {
    await _wait();
    await _save(link);
  }
}

final telegramLinkRepositoryProvider = Provider<TelegramLinkRepository>((ref) {
  // H5d: لكل حساب - نسخة جديدة لما يتغيّر الحساب (التخزين المحلي تبع الحساب
  // السابق بينمسح بالـ guard، والذاكرة بتروح مع النسخة القديمة)
  ref.watch(cacheOwnerProvider);
  return apiSource(
    ref,
    ApiFeature.telegramLink,
    simulated: () => SimulatedTelegramLinkRepository(
      prefs: ref.watch(sharedPreferencesProvider),
      clock: ref.watch(telegramClockProvider),
      latency: const Duration(milliseconds: 400),
    ),
  );
});
