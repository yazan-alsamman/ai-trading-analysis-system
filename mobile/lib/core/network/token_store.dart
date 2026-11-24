import 'dart:convert';

import 'package:flutter/foundation.dart';

import '../../services/secure_storage_service.dart';

// ═══════════════════════════════════════════════════════════
// Tokens - الـ access + refresh من الـ backend (`TokenPair`)
// ═══════════════════════════════════════════════════════════

/// `TokenPair` تبع `/auth/login` و`/auth/refresh`
@immutable
final class TokenPair {
  const TokenPair({required this.accessToken, required this.refreshToken, this.expiresIn});

  final String accessToken;
  final String refreshToken;

  /// عمر الـ access token (ثواني)
  final Duration? expiresIn;

  /// null إذا الجسم ناقص أو غلط
  static TokenPair? tryParse(Object? json) {
    if (json is! Map) return null;
    final access = json['access_token'];
    final refresh = json['refresh_token'];
    if (access is! String || access.isEmpty || refresh is! String || refresh.isEmpty) return null;
    final expires = json['expires_in'];
    return TokenPair(
      accessToken: access,
      refreshToken: refresh,
      expiresIn: expires is int ? Duration(seconds: expires) : null,
    );
  }
}

/// وقت انتهاء JWT من `exp` (بدون تحقق من التوقيع - السيرفر هو يلي بيقرّر).
/// null = مش JWT أو ما فيه `exp`.
DateTime? jwtExpiry(String token) {
  final parts = token.split('.');
  if (parts.length != 3) return null;
  try {
    final payload = jsonDecode(utf8.decode(base64Url.decode(base64Url.normalize(parts[1]))));
    final exp = payload is Map ? payload['exp'] : null;
    if (exp is! num) return null;
    return DateTime.fromMillisecondsSinceEpoch((exp * 1000).round(), isUtc: true);
  } catch (_) {
    return null;
  }
}

/// الـ tokens بالتخزين الآمن (فوق [SecureStorageService]): الـ access تحت نفس
/// مفتاح G3 (`auth_token`)، والـ refresh تحت `auth_refresh_token`
final class TokenStore {
  TokenStore(this._secure);

  final SecureStorageService _secure;

  Future<String?> accessToken() => _secure.readToken();

  Future<String?> refreshToken() => _secure.readRefreshToken();

  /// الـ refresh أول: إذا انقطع الحفظ بالنص، الـ refresh الجديد بيضل موجود
  Future<void> save(TokenPair tokens) async {
    await _secure.saveRefreshToken(tokens.refreshToken);
    await _secure.saveToken(tokens.accessToken);
  }

  Future<void> clear() async {
    await _secure.deleteToken();
    await _secure.deleteRefreshToken();
  }

  /// جلسة صالحة = refresh token موجود ومش منتهي (حسب `exp` إذا موجود)
  Future<bool> hasValidSession({DateTime? now}) async {
    final refresh = await refreshToken();
    if (refresh == null || refresh.isEmpty) return false;
    final expiry = jwtExpiry(refresh);
    return expiry == null || expiry.isAfter((now ?? DateTime.now()).toUtc());
  }
}
