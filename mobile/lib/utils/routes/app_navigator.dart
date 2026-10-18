import 'package:flutter/material.dart';

import '../../models/market_item_model.dart';
import '../../models/news_item_model.dart';
import 'app_routes.dart';
import 'route_args.dart';

export 'app_routes.dart';
export 'route_args.dart';

// ═══════════════════════════════════════════════════════════
// App Navigator - دوال تنقّل نظيفة ومحدَّدة النوع
// ═══════════════════════════════════════════════════════════
//
// امتداد (Extension) على [BuildContext] بيوفر دالة تنقّل واحدة لكل
// شاشة بالتطبيق، بدل ما كل شاشة تبني MaterialPageRoute وتستورد
// ملف الشاشة الهدف مباشرة (زي ما كان الوضع قبل).
//
// ليش هيك بدل Navigator.pushNamed مباشرة بكل مكان؟
// - Type-safe: `context.pushTrade(item)` ما بيسمح تنسى تمرر
//   `market` أو تمرره بنوع غلط - الخطأ بيطلع وقت الـ compile.
// - كل أسماء المسارات والـ arguments مركزية بمكان واحد (هون +
//   app_routes.dart) - أي تعديل مستقبلي بمكان واحد بس.
// - الشاشات (Views) رجعت ما بتعرف شو اسم الشاشة الهدف ولا شلون
//   بتتبنى (Push عادي / Push مع مسح الشجرة..) - بس بتعرف "بدي روح
//   عالـ Trade Screen" وخلص.
extension AppNavigator on BuildContext {
  NavigatorState get _navigator => Navigator.of(this);

  // ── Auth ──────────────────────────────────────────────────

  /// من شاشة التسجيل لشاشة تسجيل الدخول
  Future<void> pushLogin() => _navigator.pushNamed(AppRoutes.login);

  /// من شاشة التسجيل لشاشة التحقق من OTP
  Future<void> pushOtpVerification({required String email}) =>
      _navigator.pushNamed(AppRoutes.otpVerification, arguments: email);

  /// دخول ناجح (Login أو OTP) - بيمسح شجرة التنقل بالكامل ويفتح الهوم،
  /// حتى زر الرجوع ما يرجّع المستخدم لشاشات الدخول بعد ما دخل
  Future<void> pushHomeAndClearStack() =>
      _navigator.pushNamedAndRemoveUntil(AppRoutes.home, (route) => false);

  /// تسجيل خروج - بيمسح شجرة التنقل بالكامل ويرجع لشاشة التسجيل
  Future<void> pushRegistrationAndClearStack() =>
      _navigator.pushNamedAndRemoveUntil(
        AppRoutes.registration,
        (route) => false,
      );

  // ── Trading ───────────────────────────────────────────────

  Future<void> pushTrade(MarketItemModel market) =>
      _navigator.pushNamed(AppRoutes.trade, arguments: market);

  // ── News ──────────────────────────────────────────────────

  Future<void> pushNewsDetail({
    required NewsItemModel news,
    VoidCallback? onAnalyzeWithAi,
    ValueChanged<int>? onCommentsCountChanged,
  }) => _navigator.pushNamed(
    AppRoutes.newsDetail,
    arguments: NewsDetailScreenArgs(
      news: news,
      onAnalyzeWithAi: onAnalyzeWithAi,
      onCommentsCountChanged: onCommentsCountChanged,
    ),
  );

  Future<void> pushDiscussion({
    required String newsId,
    required String newsTitle,
    required int commentsCount,
    ValueChanged<int>? onCommentsCountChanged,
  }) => _navigator.pushNamed(
    AppRoutes.discussion,
    arguments: DiscussionScreenArgs(
      newsId: newsId,
      newsTitle: newsTitle,
      commentsCount: commentsCount,
      onCommentsCountChanged: onCommentsCountChanged,
    ),
  );

  Future<void> pushMarketNews() => _navigator.pushNamed(AppRoutes.marketNews);

  // ── AI ────────────────────────────────────────────────────

  Future<void> pushAiAssistant() =>
      _navigator.pushNamed(AppRoutes.aiAssistant);

  Future<void> pushAiChat() => _navigator.pushNamed(AppRoutes.aiChat);

  Future<void> pushAiChartAnalyzer() =>
      _navigator.pushNamed(AppRoutes.aiChartAnalyzer);

  /// [initialNewsId] لو تم تمريره، الخبر المطابق إله بيصير محدَّد
  /// تلقائيًا (Preselect) فور فتح الشاشة
  Future<void> pushAiNewsAnalyzer({String? initialNewsId}) =>
      _navigator.pushNamed(
        AppRoutes.aiNewsAnalyzer,
        arguments: initialNewsId,
      );

  // ── Notifications / Profile ──────────────────────────────

  Future<void> pushNotifications() =>
      _navigator.pushNamed(AppRoutes.notifications);

  Future<void> pushProfile() => _navigator.pushNamed(AppRoutes.profile);

  Future<void> pushEditProfile() =>
      _navigator.pushNamed(AppRoutes.editProfile);

  Future<void> pushSecurity() => _navigator.pushNamed(AppRoutes.security);

  Future<void> pushNotificationPreferences() =>
      _navigator.pushNamed(AppRoutes.notificationPreferences);

  Future<void> pushHelpSupport() =>
      _navigator.pushNamed(AppRoutes.helpSupport);

  Future<void> pushAbout() => _navigator.pushNamed(AppRoutes.about);
}
