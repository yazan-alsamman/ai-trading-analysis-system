import 'package:flutter/foundation.dart';

/// حالة ربط Telegram (H4b): مش مربوط / مربوط (مع الاسم إذا الخادم بعتو)
@immutable
sealed class TelegramLinkStatus {
  const TelegramLinkStatus();

  bool get isLinked => this is TelegramLinked;
}

final class TelegramNotLinked extends TelegramLinkStatus {
  const TelegramNotLinked();

  @override
  bool operator ==(Object other) => other is TelegramNotLinked;

  @override
  int get hashCode => 0;
}

final class TelegramLinked extends TelegramLinkStatus {
  const TelegramLinked({this.handle, required this.linkedAt});

  /// اسم المستخدم بـ Telegram (`@name`) إذا معروف
  final String? handle;
  final DateTime linkedAt;

  @override
  bool operator ==(Object other) => other is TelegramLinked && other.handle == handle && other.linkedAt == linkedAt;

  @override
  int get hashCode => Object.hash(handle, linkedAt);
}

/// كود ربط لمرة وحدة: صالح 10 دقايق، والكود المنتهي ما بينعاد استعمالو أبدًا
@immutable
final class TelegramLinkCode {
  const TelegramLinkCode({required this.code, required this.expiresAt, required this.botUsername});

  static const validity = Duration(minutes: 10);

  final String code;
  final DateTime expiresAt;

  /// اسم البوت بدون `@` (من رد الخادم)
  final String botUsername;

  bool isExpiredAt(DateTime now) => !now.isBefore(expiresAt);

  Duration remaining(DateTime now) {
    final left = expiresAt.difference(now);
    return left.isNegative ? Duration.zero : left;
  }

  @override
  bool operator ==(Object other) =>
      other is TelegramLinkCode && other.code == code && other.expiresAt == expiresAt && other.botUsername == botUsername;

  @override
  int get hashCode => Object.hash(code, expiresAt, botUsername);
}

/// بدون اتصال: ما انبعت شي
final class TelegramOfflineException implements Exception {
  const TelegramOfflineException();
}

/// الكود انتهى (أو انستعمل أو انستبدل بكود أجدد): لازم كود جديد
final class TelegramCodeExpiredException implements Exception {
  const TelegramCodeExpiredException();
}
