import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';
import '../../../core/network/token_store.dart';
import '../../../core/storage/preferences_provider.dart';
import '../../../models/user_model.dart';
import '../../../providers/app_providers.dart';
import '../../../services/secure_storage_service.dart';

// ═══════════════════════════════════════════════════════════
// Session Store - الجلسة المحفوظة على الجهاز (G3)
// ═══════════════════════════════════════════════════════════
//
// الجلسة المحفوظة = جزئين، ولازم الاتنين يكونوا موجودين:
// - الـ token (mock هلق) بالتخزين الآمن (Keystore / Keychain) - هو الشي "السرّي".
// - أقل بيانات للمستخدم بتحتاجها الواجهة (id، البريد، الاسم، الدور، تاريخ
//   الإنشاء) بـ SharedPreferences: مش سرّية، وبتنمسح مع حذف التطبيق (الـ
//   Keychain بـ iOS ما بينمسح، فـ token لحاله من تثبيت قديم ما بيرجّع جلسة).
// ما في كلمة مرور ولا أي سر تاني محفوظ.
//
// الحفظ: الـ token أول، بعدين المستخدم (آخر خطوة = الجلسة صارت محفوظة).
// المسح: المستخدم أول، بعدين الـ token. جزء ناقص أو تالف = ما في جلسة (وبينمسح).
//
// وضعين (E1)، نفس الواجهة ونفس authStateProvider:
// - محاكاة (الافتراضي): متل G3 بالزبط، token وهمي `mock_token_<id>`.
// - API حقيقي (USE_REAL_API فيها auth): "داخل" = tokens صالحة بالتخزين الآمن
//   (refresh موجود ومش منتهي حسب `exp`) + نسخة المستخدم للواجهة. الـ tokens
//   بتجي من استجابة `/auth/login` ([save] مع `tokens`) وبيبدّلها الـ refresh.
//   بدون tokens ما في حفظ (الدخول بيضل بالذاكرة).
//
// TODO(B02): لما ينربط /auth/login، المستخدم بينجاب من `GET /users/me` بدل
// النسخة المحفوظة.
final class SessionStore {
  SessionStore({required SecureStorageService secureStorage, required SharedPreferences preferences, this.realApi = false})
      : _secure = secureStorage,
        _tokens = TokenStore(secureStorage),
        _prefs = preferences;

  final SecureStorageService _secure;
  final TokenStore _tokens;
  final SharedPreferences _prefs;

  /// true = الجلسة هي الـ tokens الحقيقية (مش الـ token الوهمي)
  final bool realApi;

  /// مفتاح بيانات المستخدم بـ SharedPreferences
  static const String userKey = 'auth_session_user';

  /// يحفظ الجلسة (بعد Log in، أو بعد التحقق من البريد لحساب جديد).
  /// API حقيقي: [tokens] من الاستجابة، أو بدونها إذا في tokens صالحة أصلًا
  /// (تعديل البروفايل)، غير هيك [StateError] وما بينحفظ شي.
  Future<void> save(UserModel user, {TokenPair? tokens}) async {
    if (!realApi) {
      await _secure.saveToken('mock_token_${user.id}');
    } else if (tokens != null) {
      await _tokens.save(tokens);
    } else if (!await _tokens.hasValidSession()) {
      throw StateError('No API tokens to save the session with');
    }
    await _prefs.setString(userKey, jsonEncode(_minimal(user)));
  }

  /// الجلسة المحفوظة، أو null (ولا جزء، أو جزء ناقص / تالف → بتنمسح)
  Future<UserModel?> read() async {
    final raw = _prefs.getString(userKey);
    final token = await _secure.readToken();
    final refresh = realApi ? await _secure.readRefreshToken() : null;
    final hasTokens = realApi ? await _tokens.hasValidSession() : token != null && token.isNotEmpty;
    if (raw == null || !hasTokens) {
      if (raw != null || token != null || refresh != null) await clear();
      return null;
    }
    try {
      final json = jsonDecode(raw);
      if (json is! Map<String, dynamic>) throw const FormatException('not an object');
      final user = UserModel.fromJson(json);
      if (user.id.isEmpty || user.email.isEmpty) throw const FormatException('empty user');
      return user;
    } catch (_) {
      await clear();
      return null;
    }
  }

  /// يمسح الجلسة المحفوظة (تسجيل خروج / نهاية الجلسة)
  Future<void> clear() async {
    await _prefs.remove(userKey);
    await _tokens.clear();
  }

  /// بس يلي الواجهة بتستخدمه - بدون مسار الصورة (ملف مؤقت من الـ picker)
  static Map<String, dynamic> _minimal(UserModel user) => {
        'id': user.id,
        'email': user.email,
        if (user.displayName != null) 'displayName': user.displayName,
        if (user.createdAt != null) 'createdAt': user.createdAt!.toIso8601String(),
        'role': user.role.name,
      };
}

final sessionStoreProvider = Provider<SessionStore>(
  (ref) => SessionStore(
    secureStorage: ref.read(secureStorageServiceProvider),
    preferences: ref.read(sharedPreferencesProvider),
    realApi: ref.watch(useRealApiProvider(ApiFeature.auth)),
  ),
);
