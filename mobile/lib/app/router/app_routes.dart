import '../../features/help/views/legal_screen.dart' show LegalDocument;
import '../shell/shell_tab.dart';

// ═══════════════════════════════════════════════════════════
// App Routes - مسارات التطبيق (go_router)
// ═══════════════════════════════════════════════════════════
//
// كل المسارات هون: ثابتة ومقروءة، وكل شاشة إلها مسار (جاهزة لفتحها من
// إشعار لاحقًا بـ `context.go(path)`). البارامترات قيم بسيطة بس (رمز، معرّف،
// بريد) - ما في objects بتنمرق بالتنقّل.
//
// الشاشات ما بتبني المسارات بإيدها: بتستخدم الـ helpers بـ app_navigator.dart
// (`context.pushMarket(...)` مثلًا). جدول الـ routes نفسه بـ app_router.dart.
abstract final class AppRoutes {
  // ── بدون جلسة (الـ navigator الجذر) ─────────────────────────
  static const String splash = '/splash';

  /// أول شاشة بدون جلسة (وين بيرجع الـ guard وتسجيل الخروج)
  static const String welcome = '/welcome';
  static const String registration = '/register';
  static const String login = '/login';

  /// التحقق من البريد - `?email=`
  static const String otpVerification = '/otp';

  /// معرض الـ design system - للتطوير بس (debug):
  /// `flutter run --dart-define=DESIGN_GALLERY=true`
  static const String designSystem = '/dev/design-system';

  /// الشاشات المفتوحة بدون جلسة - أي مسار تاني محمي بالـ auth guard
  static const Set<String> publicRoutes = {splash, welcome, registration, login, otpVerification, designSystem};

  /// شاشات ما إلها معنى مع جلسة: المسجّل دخوله بيتحوّل منها للرئيسية
  static const Set<String> signedOutOnly = {welcome, login, registration};

  // ── التبويبات (كل واحد فرع بالـ shell) ─────────────────────
  static const String home = '/home';
  static const String signals = '/signals';
  static const String assistant = '/assistant';
  static const String community = '/community';
  static const String profile = '/profile';

  /// جذر تبويب
  static String tab(ShellTab tab) => switch (tab) {
        ShellTab.home => home,
        ShellTab.signals => signals,
        ShellTab.assistant => assistant,
        ShellTab.community => community,
        ShellTab.profile => profile,
      };

  /// التبويب يلي بيبلّش فيه [path] (أول جزء)، أو null إذا برّا الـ shell
  static ShellTab? tabOf(String path) {
    final segments = Uri.parse(path).pathSegments;
    if (segments.isEmpty) return null;
    for (final tab in ShellTab.values) {
      if (AppRoutes.tab(tab) == '/${segments.first}') return tab;
    }
    return null;
  }

  // ── مسارات الشاشات (location builders) ─────────────────────

  static String otp(String email) => '$otpVerification?email=${Uri.encodeQueryComponent(email)}';

  /// شاشة الأداة - جوّا التبويب يلي انفتحت منه (حتى الـ Hero والشريط السفلي يضلّوا)
  static String market(String symbol, {ShellTab tab = ShellTab.home}) =>
      '${AppRoutes.tab(tab)}/market/${_segment(symbol)}';

  /// تفاصيل إشارة - [symbol] حتى العنوان (Hero) يطلع من أول إطار.
  /// بتبويب Signals: `/signals/:id`؛ بباقي التبويبات يلي فيها شاشة السوق
  /// (نتيجة "Request analysis" من شاشة الأداة): `/<tab>/signal/:id`، حتى
  /// تنفتح بنفس التبويب والرجوع يرجّع لشاشة الأداة. Profile ما فيه سوق → Signals.
  static String signalDetail(String id, {required String symbol, ShellTab tab = ShellTab.signals}) {
    final query = '?symbol=${Uri.encodeQueryComponent(symbol)}';
    return switch (tab) {
      ShellTab.signals || ShellTab.profile => '$signals/${_segment(id)}$query',
      _ => '${AppRoutes.tab(tab)}/signal/${_segment(id)}$query',
    };
  }

  static const String insights = '$signals/insights';
  static const String backtest = '$signals/backtest';

  static const String notifications = '$home/notifications';

  static String newsDetail(String articleId) => '$community/news/${_segment(articleId)}';
  static String expertChat(String expertId) => '$community/experts/${_segment(expertId)}/chat';

  static const String editProfile = '$profile/edit';
  static const String security = '$profile/security';
  static const String plans = '$profile/plans';
  static const String appSettings = '$profile/settings';
  static const String notificationPreferences = '$appSettings/notifications';
  static const String helpAbout = '$profile/help';
  static String legal(LegalDocument document) => '$helpAbout/legal/${document.name}';

  /// الرموز والمعرّفات فيها '/' (EUR/USD) - بتنشفّر كجزء واحد، وgo_router بيفكّها
  static String _segment(String value) => Uri.encodeComponent(value);
}
