import '../l10n/app_localizations.dart';
import '../models/notification_model.dart';

/// بناء قائمة الإشعارات التجريبية (Mock) بلغة [l10n] المُعطاة - نفس
/// أسلوب `_buildMockNews` بملف `news_repository.dart`.
///
/// كل إشعار مكتوب بلغة التطبيق التداولية (توصية شراء/بيع أو تنبيه
/// سعر)، مش رسائل نظام عامة، حتى ينسجم مع باقي تجربة التطبيق. الـ
/// [NotificationModel.id] و[NotificationModel.symbol] ثابتين بكل
/// اللغات (معرّفات ورموز أسواق، مش نص للعرض)، بس [NotificationModel.title]
/// و[NotificationModel.message] و[NotificationModel.timeAgo] بتتغيّر
/// حسب [l10n].
List<NotificationModel> buildMockNotifications(AppLocalizations l10n) {
  return [
    NotificationModel(
      id: 'notif-gold-buy',
      type: NotificationType.buySignal,
      symbol: 'XAU/USD',
      title: l10n.notifGoldBuyTitle,
      message: l10n.notifGoldBuyMessage,
      timeAgo: l10n.minutesAgo(10),
      isRead: false,
    ),
    NotificationModel(
      id: 'notif-eurusd-sell',
      type: NotificationType.sellSignal,
      symbol: 'EUR/USD',
      title: l10n.notifEurSellTitle,
      message: l10n.notifEurSellMessage,
      timeAgo: l10n.minutesAgo(48),
      isRead: false,
    ),
    NotificationModel(
      id: 'notif-btc-alert',
      type: NotificationType.priceAlert,
      symbol: 'BTC/USD',
      title: l10n.notifBtcAlertTitle,
      message: l10n.notifBtcAlertMessage,
      timeAgo: l10n.hoursAgo(2),
      isRead: true,
    ),
    NotificationModel(
      id: 'notif-oil-buy',
      type: NotificationType.buySignal,
      symbol: 'WTI Crude',
      title: l10n.notifOilBuyTitle,
      message: l10n.notifOilBuyMessage,
      timeAgo: l10n.hoursAgo(5),
      isRead: true,
    ),
    NotificationModel(
      id: 'notif-account-general',
      type: NotificationType.general,
      title: l10n.notifWelcomeTitle,
      message: l10n.notifWelcomeMessage,
      timeAgo: l10n.daysAgo(1),
      isRead: true,
    ),
  ];
}
