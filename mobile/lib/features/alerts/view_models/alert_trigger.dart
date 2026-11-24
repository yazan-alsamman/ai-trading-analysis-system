import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/app_lifecycle.dart';
import '../../markets/data/market_providers.dart';
import '../../markets/models/market_models.dart';
import '../../notifications/data/notification_preferences_repository.dart';
import '../../notifications/data/notifications_repository.dart';
import '../../notifications/models/app_notification.dart';
import '../../notifications/models/notification_preferences.dart' as prefs;
import '../../notifications/view_models/notifications_view_model.dart';
import '../models/price_alert.dart';
import 'alerts_view_model.dart';

/// فاحص التنبيهات (H4a, محاكاة): بيشتغل من مصدر الأسعار الموجود (بدون أي
/// مؤقّت زيادة)، ولما التطبيق يرجع للواجهة بيقارن آخر سعر بالمستوى، فتنبيه
/// انعبر والتطبيق بالخلفية بيشتغل مرة وحدة عند الرجوع.
///
/// كل تنبيه بيشتغل = إشعار واحد داخل التطبيق (نوع "price alert")، والضغط عليه
/// بيفتح الأداة (نفس تنقّل الإشعارات). بيتفعّل من الـ shell (المستخدم داخل).
/// TODO(API): مع الـ API الخادم هو يلي بيفحص وبينشئ الإشعار؛ هون بس قراءة.
final alertTriggerProvider = Provider<void>((ref) {
  var disposed = false;
  ref.onDispose(() => disposed = true);

  Future<void> check(Map<String, Quote> quotes) async {
    try {
      final triggered = await ref.read(alertsViewModelProvider.notifier).checkQuotes(quotes);
      if (disposed || triggered.isEmpty) return;
      // H4b: الإشعار داخل التطبيق بيتبع التفضيلات (قناة "داخل التطبيق" + نوع
      // "تنبيه سعر")؛ التنبيه نفسو بيصير Triggered بكل الأحوال
      if (!ref.read(notificationPreferencesProvider).deliversInApp(prefs.NotificationKind.priceAlert)) return;
      final notifications = ref.read(notificationsRepositoryProvider);
      var added = false;
      for (final alert in triggered) {
        added = await notifications.addPriceAlert(_notice(ref, alert)) || added;
      }
      // القائمة (والجرس) بتتحدّث إذا محمّلة؛ إذا لأ بتنحمّل لاحقًا ومعها الجديد
      if (added && !disposed && ref.exists(notificationsViewModelProvider)) {
        await ref.read(notificationsViewModelProvider.notifier).refresh();
      }
    } catch (_) {
      // الفحص الجاي (النبضة التالية) بيعيد المحاولة على النسخة المحفوظة
    }
  }

  ref.listen<AsyncValue<Map<String, Quote>>>(
    liveQuotesProvider,
    (_, next) {
      if (next.valueOrNull case final quotes?) check(quotes);
    },
    fireImmediately: true,
  );

  // رجوع من الخلفية: آخر سعر من المصدر (مش اللقطة القديمة) مقابل المستوى
  ref.listen<bool>(appActiveProvider, (previous, active) async {
    if (previous != false || !active) return;
    try {
      final fresh = await ref.read(marketDataRepositoryProvider).quotes();
      if (!disposed) await check({for (final q in fresh) q.symbol: q});
    } catch (_) {
      // بدون اتصال: النبضات لما ترجع بتفحص
    }
  });
});

PriceAlertNotice _notice(Ref ref, PriceAlert alert) {
  final instrument = ref.read(instrumentProvider(alert.symbol));
  String format(double v) => instrument?.format(v) ?? v.toString();
  return PriceAlertNotice(
    alertId: alert.id,
    symbol: alert.symbol,
    level: format(alert.value),
    price: format(alert.triggeredPrice ?? alert.value),
    at: alert.lastTriggeredAt ?? DateTime.now().toUtc(),
  );
}
