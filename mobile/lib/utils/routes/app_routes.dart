import 'package:flutter/material.dart';

import '../../models/market_item_model.dart';
import '../../views/screens/about_screen.dart';
import '../../views/screens/ai_assistant_screen.dart';
import '../../views/screens/ai_chart_analyzer_screen.dart';
import '../../views/screens/ai_chat_screen.dart';
import '../../views/screens/ai_news_analyzer_screen.dart';
import '../../views/screens/discussion_screen.dart';
import '../../views/screens/edit_profile_screen.dart';
import '../../views/screens/help_support_screen.dart';
import '../../views/screens/home_screen.dart';
import '../../views/screens/login_screen.dart';
import '../../views/screens/market_news_screen.dart';
import '../../views/screens/news_detail_screen.dart';
import '../../views/screens/notification_preferences_screen.dart';
import '../../views/screens/notifications_screen.dart';
import '../../views/screens/otp_verification_screen.dart';
import '../../views/screens/profile_screen.dart';
import '../../views/screens/registration_screen.dart';
import '../../views/screens/security_screen.dart';
import '../../views/screens/splash_screen.dart';
import '../../views/screens/trade_screen.dart';
import 'route_args.dart';

// ═══════════════════════════════════════════════════════════
// App Routes - نظام التنقل المركزي للتطبيق
// ═══════════════════════════════════════════════════════════
//
// كل أسماء المسارات (Route Names) وكل منطق بناء الشاشات مركزي هون
// بدل ما يكون موزّع بكل شاشة على حدة (كل شاشة كانت قبل عم تبني
// MaterialPageRoute براسها وتستورد الشاشة الهدف مباشرة).
//
// الاستخدام الفعلي من داخل الشاشات ما بيصير مباشرة عبر هالملف، إنما
// عبر الـ helpers المحدَّدة النوع (Typed) بملف app_navigator.dart
// (مثلاً `context.pushTrade(item)`) - هاد الملف هو "المحرّك" يلي
// الـ helpers بتعتمد عليه، وهو المسجَّل بـ MaterialApp.onGenerateRoute
// بملف main.dart.
abstract final class AppRoutes {
  // ── Splash ────────────────────────────────────────────────
  static const String splash = '/splash';

  // ── Auth ──────────────────────────────────────────────────
  static const String registration = '/registration';
  static const String login = '/login';
  static const String otpVerification = '/otp-verification';

  // ── Main ──────────────────────────────────────────────────
  static const String home = '/home';
  static const String trade = '/trade';

  // ── News ──────────────────────────────────────────────────
  static const String newsDetail = '/news-detail';
  static const String discussion = '/discussion';
  static const String marketNews = '/market-news';

  // ── AI ────────────────────────────────────────────────────
  static const String aiAssistant = '/ai-assistant';
  static const String aiChat = '/ai-chat';
  static const String aiChartAnalyzer = '/ai-chart-analyzer';
  static const String aiNewsAnalyzer = '/ai-news-analyzer';

  // ── Notifications / Profile ──────────────────────────────
  static const String notifications = '/notifications';
  static const String profile = '/profile';
  static const String editProfile = '/edit-profile';
  static const String security = '/security';
  static const String notificationPreferences = '/notification-preferences';
  static const String helpSupport = '/help-support';
  static const String about = '/about';

  /// نقطة الدخول الوحيدة لبناء أي Route بالتطبيق - ممرَّرة لـ
  /// [MaterialApp.onGenerateRoute] بملف main.dart.
  ///
  /// الشاشات يلي مابتحتاج بيانات (زي [ProfileScreen]، [AboutScreen]..)
  /// بترجع MaterialPageRoute بسيط. الشاشات يلي محتاجة بيانات (زي
  /// [TradeScreen]، [NewsDetailScreen]..) بتاخد [RouteSettings.arguments]
  /// وتحوّلها (cast) للنوع المطلوب.
  ///
  /// ⚠️ ما في داعي تنادي هالدالة مباشرة من الشاشات - استخدم
  /// الـ helpers المحدَّدة النوع بملف app_navigator.dart بدلها
  /// (context.pushTrade(...) مثلًا)، حتى ما تضطر تبني الـ arguments
  /// يدويًا ولا تنسى نوعها.
  static Route<dynamic> onGenerateRoute(RouteSettings settings) {
    switch (settings.name) {
      case splash:
        return _page(const SplashScreen(), settings);

      case registration:
        return _page(const RegistrationScreen(), settings);

      case login:
        return _page(const LoginScreen(), settings);

      case otpVerification:
        final email = settings.arguments as String;
        return _page(OtpVerificationScreen(email: email), settings);

      case home:
        return _page(const HomeScreen(), settings);

      case trade:
        final market = settings.arguments as MarketItemModel;
        return _page(TradeScreen(market: market), settings);

      case newsDetail:
        final args = settings.arguments as NewsDetailScreenArgs;
        return _page(
          NewsDetailScreen(
            news: args.news,
            onAnalyzeWithAi: args.onAnalyzeWithAi,
            onCommentsCountChanged: args.onCommentsCountChanged,
          ),
          settings,
        );

      case discussion:
        final args = settings.arguments as DiscussionScreenArgs;
        return _page(
          DiscussionScreen(
            newsId: args.newsId,
            newsTitle: args.newsTitle,
            commentsCount: args.commentsCount,
            onCommentsCountChanged: args.onCommentsCountChanged,
          ),
          settings,
        );

      case marketNews:
        return _page(const MarketNewsScreen(), settings);

      case aiAssistant:
        return _page(const AiAssistantScreen(), settings);

      case aiChat:
        return _page(const AiChatScreen(), settings);

      case aiChartAnalyzer:
        return _page(const AiChartAnalyzerScreen(), settings);

      case aiNewsAnalyzer:
        final initialNewsId = settings.arguments as String?;
        return _page(
          AiNewsAnalyzerScreen(initialNewsId: initialNewsId),
          settings,
        );

      case notifications:
        return _page(const NotificationsScreen(), settings);

      case profile:
        return _page(const ProfileScreen(), settings);

      case editProfile:
        return _page(const EditProfileScreen(), settings);

      case security:
        return _page(const SecurityScreen(), settings);

      case notificationPreferences:
        return _page(const NotificationPreferencesScreen(), settings);

      case helpSupport:
        return _page(const HelpSupportScreen(), settings);

      case about:
        return _page(const AboutScreen(), settings);

      default:
        return _page(_UnknownRouteScreen(routeName: settings.name), settings);
    }
  }

  /// Helper موحّد لبناء MaterialPageRoute مع الحفاظ على [settings]
  /// (اسم الـ route + الـ arguments)، حتى تبقى متوفرة لأدوات مثل
  /// الـ Navigator Observer أو الاختبارات (Tests) لاحقًا.
  static MaterialPageRoute<dynamic> _page(
    Widget child,
    RouteSettings settings,
  ) {
    return MaterialPageRoute(builder: (_) => child, settings: settings);
  }
}

/// شاشة بديلة بسيطة تظهر بس لو صار طلب route اسمه مش معروف (خطأ
/// إملائي باسم الـ route مثلًا) - بدل ما التطبيق يطيح بصمت.
class _UnknownRouteScreen extends StatelessWidget {
  const _UnknownRouteScreen({this.routeName});

  final String? routeName;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Text('Route not found: ${routeName ?? '(unknown)'}'),
      ),
    );
  }
}
