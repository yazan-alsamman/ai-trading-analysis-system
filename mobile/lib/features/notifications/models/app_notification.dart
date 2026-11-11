import 'package:flutter/material.dart';

import '../../../l10n/app_localizations.dart';

/// نوع الإشعار بالمركز (3 فلاتر). الـ backend عندو أنواع أكتر - كل شي غير
/// `price_alert` و `signal` بينعرض كـ "System".
enum NotificationKind {
  priceAlert,
  opportunity,
  system;

  static NotificationKind? fromApi(String? type) => switch (type) {
        null || '' => null,
        'price_alert' => priceAlert,
        'signal' => opportunity,
        _ => system,
      };

  String label(AppLocalizations l10n) => switch (this) {
        priceAlert => l10n.kindPriceAlert,
        opportunity => l10n.kindOpportunity,
        system => l10n.kindSystem,
      };

  IconData get icon => switch (this) {
        priceAlert => Icons.notifications_active_outlined,
        opportunity => Icons.auto_awesome_outlined,
        system => Icons.info_outline_rounded,
      };
}

/// إشعار واحد (immutable) - حقول `NotificationRead` بالـ backend
@immutable
final class AppNotification {
  const AppNotification({
    required this.id,
    required this.kind,
    required this.title,
    required this.body,
    required this.createdAt,
    this.symbol,
    this.readAt,
  });

  final String id;
  final NotificationKind kind;
  final String title;
  final String body;
  final DateTime createdAt;

  /// الأداة المرتبطة (من `data.symbol`) - الضغط على الإشعار بيفتح شاشتها
  final String? symbol;
  final DateTime? readAt;

  bool get isRead => readAt != null;

  AppNotification withRead(bool read, {DateTime? at}) => AppNotification(
        id: id,
        kind: kind,
        title: title,
        body: body,
        createdAt: createdAt,
        symbol: symbol,
        readAt: read ? (readAt ?? at ?? DateTime.now().toUtc()) : null,
      );
}

/// بيانات إشعار "تنبيه سعر اشتغل" (H4a). المستوى والسعر منسّقين بدقة الأداة
/// (أرقام لاتينية باللغتين)، والنص بينبني بلغة الطلب وقت القراءة.
@immutable
final class PriceAlertNotice {
  const PriceAlertNotice({
    required this.alertId,
    required this.symbol,
    required this.level,
    required this.price,
    required this.at,
  });

  final String alertId;
  final String symbol;
  final String level;
  final String price;
  final DateTime at;

  /// إشعار واحد لكل تنبيه اشتغل (نفس الـ id = ما بيتكرّر)
  String get notificationId => 'alert-$alertId';
}
