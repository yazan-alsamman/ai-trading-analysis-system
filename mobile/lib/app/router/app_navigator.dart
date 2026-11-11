import 'package:flutter/scheduler.dart';
import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

import '../../features/help/views/legal_screen.dart';
import '../shell/shell_tab.dart';
import 'app_routes.dart';

export 'app_routes.dart';
export 'navigator_key.dart';
export '../shell/shell_tab.dart';

// ═══════════════════════════════════════════════════════════
// App Navigator - دوال تنقّل نظيفة ومحدَّدة النوع (فوق go_router)
// ═══════════════════════════════════════════════════════════
//
// امتداد (Extension) على [BuildContext] بيوفر دالة تنقّل واحدة لكل شاشة،
// فالشاشات ما بتعرف شو المسار ولا شلون بينبنى - بس "بدي روح عالـ Market".
// - Type-safe: `context.pushOtpVerification(email: ...)` ما بيسمح تنسى
//   تمرر `email` أو تمرره بنوع غلط.
// - كل المسارات مركزية (app_routes.dart + جدولها بـ app_router.dart).
// - push = فوق الشاشة الحالية (جوّا فرع التبويب أو على الجذر حسب جدول
//   الـ routes)، go = يبدّل الشجرة كلها (دخول، تبويب).
extension AppNavigator on BuildContext {
  GoRouter get _router => GoRouter.of(this);

  /// التبويب يلي المستخدم فيه هلق (من المسار الأساسي، بدون الـ push فوقه)
  ShellTab get _currentTab => AppRoutes.tabOf(_router.routerDelegate.currentConfiguration.uri.path) ?? ShellTab.home;

  /// هالـ context على الشاشة يلي فوق؟ (مش تحت شاشة أو sheet تانية، بأي
  /// navigator: فرع التبويب أو الجذر). أساس حماية الضغطة المزدوجة.
  bool get isTopmostRoute {
    BuildContext? current = this;
    while (current != null) {
      final route = ModalRoute.of(current);
      if (route == null) return true;
      if (!route.isCurrent) return false;
      // الـ route يلي فيها هالـ navigator (فرع جوّا الـ shell → صفحة الـ shell بالجذر)
      current = route.navigator?.context;
    }
    return true;
  }

  /// حماية الضغطة المزدوجة: ضغطة تانية قبل ما الشاشة الجديدة تطلع (أو وهي
  /// مش فوق) بتنتجاهل. go_router بيبني الصفحة بالإطار الجاي، فمنقفل لحد آخره.
  bool _claimPush() {
    if (_pushPending || !isTopmostRoute) return false;
    _pushPending = true;
    SchedulerBinding.instance
      ..addPostFrameCallback((_) => _pushPending = false)
      ..ensureVisualUpdate();
    return true;
  }

  // ── Shell tabs ────────────────────────────────────────────

  /// يختار [tab] (نفس زر الرجوع بالنظام من جذر تبويب): جوّا الـ shell التبويب
  /// بيرجع بحالته وشاشاته؛ من شاشة فوق الـ shell (الجذر) بيسكّرها ويفتح جذر التبويب.
  void goToTab(ShellTab tab) {
    final shell = StatefulNavigationShell.maybeOf(this);
    if (shell != null) {
      shell.goBranch(tab.index);
    } else {
      _router.go(AppRoutes.tab(tab));
    }
  }

  // ── Auth ──────────────────────────────────────────────────

  /// Log in - [replace] من شاشة Create account (حتى الرجوع يوصل لـ Welcome)
  Future<void> pushLogin({bool replace = false}) =>
      replace ? _router.pushReplacement<void>(AppRoutes.login) : _router.push<void>(AppRoutes.login);

  /// Create account - [replace] من شاشة Log in
  Future<void> pushRegistration({bool replace = false}) =>
      replace ? _router.pushReplacement<void>(AppRoutes.registration) : _router.push<void>(AppRoutes.registration);

  /// من Create account للتحقق من البريد
  Future<void> pushOtpVerification({required String email}) => _router.push<void>(AppRoutes.otp(email));

  /// دخول ناجح (Login أو OTP) - بيبدّل الشجرة كلها بالهوم، حتى زر الرجوع ما
  /// يرجّع المستخدم لشاشات الدخول بعد ما دخل
  Future<void> pushHomeAndClearStack() async => _router.go(AppRoutes.home);

  // ── Markets ───────────────────────────────────────────────

  /// شاشة الأداة، جوّا التبويب الحالي. ضغطة مزدوجة ما بتفتح شاشتين.
  Future<void> pushMarket(String symbol) async {
    if (!_claimPush()) return;
    await _router.push<void>(AppRoutes.market(symbol, tab: _currentTab));
  }

  // ── Signals ───────────────────────────────────────────────

  /// تفاصيل إشارة (قائمة Signals، أو نتيجة "Request analysis") - جوّا التبويب
  /// الحالي، نفس حماية الضغطة المزدوجة تبع [pushMarket].
  /// [symbol] معروف من الصف، فالعنوان (Hero) بيطلع من أول إطار حتى أثناء التحميل.
  Future<void> pushSignalDetail(String signalId, {required String symbol}) async {
    if (!_claimPush()) return;
    final tab = AppRoutes.tabOf(_router.routerDelegate.currentConfiguration.uri.path) ?? ShellTab.signals;
    await _router.push<void>(AppRoutes.signalDetail(signalId, symbol: symbol, tab: tab));
  }

  /// Insights من سطر الدقة - نفس حماية الضغطة المزدوجة تبع [pushMarket]
  Future<void> pushInsights() async {
    if (!_claimPush()) return;
    await _router.push<void>(AppRoutes.insights);
  }

  /// Backtest من "Test on past data" بـ Strategy (بيقرأ الاستراتيجية المحفوظة)
  /// - على الجذر فوق الـ sheet، والرجوع بيرجّع لها. نفس حماية الضغطة المزدوجة.
  Future<void> pushBacktest() async {
    if (!_claimPush()) return;
    await _router.push<void>(AppRoutes.backtest);
  }

  // ── Membership ────────────────────────────────────────────

  Future<void> pushPlans() => _router.push<void>(AppRoutes.plans);

  // ── Community ─────────────────────────────────────────────

  /// محادثة خبير (زر Chat ببطاقته) - نفس حماية الضغطة المزدوجة تبع [pushMarket]
  Future<void> pushExpertChat(String expertId) async {
    if (!_claimPush()) return;
    await _router.push<void>(AppRoutes.expertChat(expertId));
  }

  // ── News ──────────────────────────────────────────────────

  Future<void> pushNewsDetail(String articleId) => _router.push<void>(AppRoutes.newsDetail(articleId));

  // ── Notifications / Profile ──────────────────────────────

  Future<void> pushNotifications() => _router.push<void>(AppRoutes.notifications);

  Future<void> pushEditProfile() => _router.push<void>(AppRoutes.editProfile);

  Future<void> pushSecurity() => _router.push<void>(AppRoutes.security);

  Future<void> pushNotificationPreferences() => _router.push<void>(AppRoutes.notificationPreferences);

  Future<void> pushSettings() => _router.push<void>(AppRoutes.appSettings);

  Future<void> pushHelpAbout() => _router.push<void>(AppRoutes.helpAbout);

  Future<void> pushLegal(LegalDocument document) => _router.push<void>(AppRoutes.legal(document));
}

/// push جاري لسّا ما انبنى (راجع `_claimPush`)
bool _pushPending = false;
