import 'package:flutter_secure_storage/flutter_secure_storage.dart';

// ═══════════════════════════════════════════════════════════
// Secure Storage Service - خدمة التخزين الآمن
// ═══════════════════════════════════════════════════════════

/// خدمة رفيعة (thin wrapper) فوق [FlutterSecureStorage]، مسؤوليتها
/// الوحيدة: تخزين/قراءة/حذف auth token بشكل مشفّر على الجهاز
/// (Keystore بأندرويد / Keychain بـ iOS)، بدل ما ينحفظ كنص عادي.
///
/// ⚠️ IMPORTANT: هاي الخدمة لتخزين بيانات حساسة بس (token، إلخ).
/// لتخزين إعدادات/تفضيلات عادية (مش حساسة) استخدم shared_preferences
/// بدلها - أخف وأسرع، ومافي داعي للتشفير فيها.
final class SecureStorageService {
  SecureStorageService({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  /// المفتاح الثابت يلي بينحفظ تحته الـ auth token
  static const _authTokenKey = 'auth_token';

  /// حفظ الـ auth token - بينادى عليها بعد نجاح تسجيل الدخول/التسجيل
  Future<void> saveToken(String token) => _storage.write(
        key: _authTokenKey,
        value: token,
      );

  /// قراءة الـ token المحفوظ (بترجع null إذا ما في جلسة محفوظة أصلاً)
  Future<String?> readToken() => _storage.read(key: _authTokenKey);

  /// حذف الـ token - بينادى عليها عند تسجيل الخروج
  Future<void> deleteToken() => _storage.delete(key: _authTokenKey);
}
