import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../l10n/app_localizations.dart';
import '../models/notification_model.dart';
import '../utils/mock_notifications.dart';

// ═══════════════════════════════════════════════════════════
// Notifications Repository - المصدر الوحيد لإشعارات التطبيق
// ═══════════════════════════════════════════════════════════

/// المصدر الوحيد (Single Source of Truth) لكل إشعارات التطبيق
///
/// الدور المعماري: **Controller/Repository (متحكم مشترك)**
///
/// ⚠️ لازم تُزوَّد **مرة وحدة** بجذر التطبيق ([TradingApp] بملف main.dart)
/// وليس داخل [NotificationsScreen] لحالها، حتى:
/// - عدد الإشعارات غير المقروءة (اللي بتعرضه نقطة حمرا فوق أيقونة
///   الجرس بـ [HomeScreen]) يبقى محدَّث حتى لو الشاشة نفسها مسكّرة.
/// - لما المستخدم يضغط إشعار ويعلّمه كمقروء ثم يطلع من الشاشة ويرجع،
///   حالة "مقروء" تضل محفوظة (مش تترجع للحالة الأصلية من جديد).
///
/// ⚠️ لا يوجد أي منطق عرض هون - الـ View بتقرأ [notifications] و
/// [unreadCount] فقط عبر Provider.
///
/// ⚠️ ملاحظة على الترجمة (AR/EN): بنفس أسلوب [NewsRepository] بالضبط -
/// هاي الـ Repository جذرية وحيّة طول عمر التطبيق، فما بتاخد
/// [AppLocalizations] من BuildContext مباشرة. بدل هيك:
/// 1. عند أول تحميل ([_loadNotifications])، بتقرأ لغة التطبيق المحفوظة
///    مباشرة من نفس مخزن [LocaleNotifier] (راجع
///    lib/providers/locale_provider.dart) وتبني المحتوى فيها من
///    البداية - فحتى لو المستخدم فتح التطبيق ولغته المحفوظة عربي،
///    الإشعارات بتطلع عربي من أول تحميل.
/// 2. لو المستخدم بدّل اللغة وهو داخل التطبيق (من شاشة Profile)، لازم
///    ينادى [relocalize] يدويًا بعد التبديل مباشرة (مو تلقائيًا) حتى
///    ما يصير أي تعارض إعادة-بناء أثناء بناء واجهة تانية - [ProfileScreen]
///    هي يلي بتعمل هالنداء بعد ما تحفظ اللغة الجديدة.
final class NotificationsRepository extends ChangeNotifier {
  NotificationsRepository() {
    _loadNotifications();
  }

  // ═══════════════════════════════════════════════════════════
  // Private State - الحالة الخاصة
  // ═══════════════════════════════════════════════════════════

  static const _localeStorageKey = 'app_locale';
  static const _supportedLanguageCodes = ['en', 'ar'];

  List<NotificationModel> _notifications = [];

  /// آخر لغة تم بناء محتوى الإشعارات فيها - تُستخدم لمنع إعادة بناء
  /// المحتوى بدون داعي لو [relocalize] انادت بنفس اللغة الحالية أصلًا
  String? _lastLocalizedLanguageCode;

  // ═══════════════════════════════════════════════════════════
  // Public Getters - القراءة العامة
  // ═══════════════════════════════════════════════════════════

  /// كل الإشعارات الحالية (للقراءة فقط)
  List<NotificationModel> get notifications =>
      List.unmodifiable(_notifications);

  /// عدد الإشعارات غير المقروءة - يُعرض كنقطة حمرا فوق أيقونة الجرس
  int get unreadCount => _notifications.where((n) => !n.isRead).length;

  // ═══════════════════════════════════════════════════════════
  // Public Methods - العمليات العامة
  // ═══════════════════════════════════════════════════════════

  /// تعليم إشعار معيّن كمقروء، بالاعتماد على [NotificationModel.id]
  /// الثابت - بينعكس فورًا (تنقيص عدّاد النقطة الحمرا) بكل شاشة عم
  /// تراقب هالـ Repository
  void markAsRead(String notificationId) {
    final index = _notifications.indexWhere((n) => n.id == notificationId);
    if (index == -1 || _notifications[index].isRead) return;

    _notifications = List.of(_notifications)
      ..[index] = _notifications[index].copyWith(isRead: true);
    notifyListeners();
  }

  /// حذف إشعار معيّن نهائيًا، بالاعتماد على [NotificationModel.id]
  /// الثابت - إذا كان الإشعار المحذوف غير مقروء، عدّاد النقطة الحمرا
  /// بينقص معه تلقائيًا (لأنه مبني على [unreadCount] الحيّة)
  void removeNotification(String notificationId) {
    final existingLength = _notifications.length;
    _notifications =
        _notifications.where((n) => n.id != notificationId).toList();

    if (_notifications.length != existingLength) {
      notifyListeners();
    }
  }

  /// إعادة بناء عناوين/نصوص الإشعارات التجريبية بلغة [l10n] الحالية،
  /// مع الحفاظ على حالة "مقروء" الحيّة لكل إشعار (ما منعيد تصفيرها).
  /// تُنادى من [ProfileScreen] مباشرة بعد ما المستخدم يبدّل لغة
  /// التطبيق وهو داخل جلسة شغّالة - راجع ملاحظة الترجمة أعلاه.
  void relocalize(AppLocalizations l10n) {
    if (_lastLocalizedLanguageCode == l10n.locale.languageCode) return;
    _lastLocalizedLanguageCode = l10n.locale.languageCode;

    final preservedReadState = {
      for (final n in _notifications) n.id: n.isRead,
    };

    _notifications = buildMockNotifications(l10n)
        .map(
          (n) => preservedReadState.containsKey(n.id)
              ? n.copyWith(isRead: preservedReadState[n.id])
              : n,
        )
        .toList();
    notifyListeners();
  }

  // ═══════════════════════════════════════════════════════════
  // Private Helpers - دوال مساعدة خاصة
  // ═══════════════════════════════════════════════════════════

  /// تحميل الإشعارات - Mock مؤقت ريثما تُربط بخدمة إشعارات حقيقية
  Future<void> _loadNotifications() async {
    final l10n = AppLocalizations(await _readSavedLocale());
    _lastLocalizedLanguageCode = l10n.locale.languageCode;
    _notifications = buildMockNotifications(l10n);
    notifyListeners();
  }

  /// قراءة لغة التطبيق المحفوظة مباشرة من نفس المخزن يلي [LocaleNotifier]
  /// (lib/providers/locale_provider.dart) بيقرأ منه، حتى أول تحميل
  /// للإشعارات يطلع بلغة التطبيق الصح من البداية بدون انتظار أي widget
  Future<Locale> _readSavedLocale() async {
    try {
      const storage = FlutterSecureStorage();
      final saved = await storage.read(key: _localeStorageKey);
      if (saved != null && _supportedLanguageCodes.contains(saved)) {
        return Locale(saved);
      }
    } catch (_) {
      // تجاهل أي خطأ قراءة (مثلًا أول تشغيل بدون تخزين بعد) - نكمل
      // بالإنجليزية الافتراضية
    }
    return const Locale('en');
  }
}
