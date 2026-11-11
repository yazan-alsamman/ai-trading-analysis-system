import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme/theme_context.dart';
import '../../dev/design_system_screen.dart';
import '../../features/alerts/widgets/alert_trigger_scope.dart';
import '../../features/assistant/views/assistant_screen.dart';
import '../../features/auth/auth_state.dart';
import '../../features/auth/views/login_screen.dart';
import '../../features/auth/views/otp_screen.dart';
import '../../features/auth/views/register_screen.dart';
import '../../features/auth/views/splash_screen.dart';
import '../../features/auth/views/welcome_screen.dart';
import '../../features/backtest/views/backtest_screen.dart';
import '../../features/community/views/community_screen.dart';
import '../../features/community/views/expert_chat_screen.dart';
import '../../features/help/views/help_about_screen.dart';
import '../../features/help/views/legal_screen.dart';
import '../../features/home/views/home_screen.dart';
import '../../features/insights/views/insights_screen.dart';
import '../../features/markets/views/market_screen.dart';
import '../../features/membership/views/plans_screen.dart';
import '../../features/news/views/news_detail_screen.dart';
import '../../features/notifications/views/notification_preferences_screen.dart';
import '../../features/notifications/views/notifications_screen.dart';
import '../../features/notifications/widgets/push_registration_scope.dart';
import '../../features/profile/views/edit_profile_screen.dart';
import '../../features/profile/views/profile_screen.dart';
import '../../features/profile/views/security_screen.dart';
import '../../features/settings/views/settings_screen.dart';
import '../../features/signals/views/signal_detail_screen.dart';
import '../../features/signals/views/signals_screen.dart';
import '../shell/app_shell.dart';
import 'app_routes.dart';
import 'navigator_key.dart';

/// معرض الـ design system (debug بس): `--dart-define=DESIGN_GALLERY=true`
const _openDesignGallery = bool.fromEnvironment('DESIGN_GALLERY');

// ═══════════════════════════════════════════════════════════
// App Router - go_router
// ═══════════════════════════════════════════════════════════
//
// - الـ GoRouter بينبنى مرة وحدة (ما بينعاد بناؤه): الـ redirect بيقرأ الجلسة
//   بـ ref.read، و[_RouterRefresh] بيخبّره يعيد التقييم لما الجلسة تخلص أو لما
//   الـ splash يخلص قراءة الجلسة المحفوظة.
// - الـ shell = StatefulShellRoute.indexedStack: 5 فروع، كل فرع إلو navigator
//   (حالته وسكروله محفوظين، بينبنى أول ما ينفتح). الشاشات الفرعية جوّا فرعها
//   (الشريط السفلي ظاهر والـ Hero بنفس الـ navigator)، إلا يلي لازم تغطي الشاشة
//   كلها: الدخول، محادثة الخبير، وBacktest (لازم يطلع فوق sheet الـ Strategy
//   يلي على الـ navigator الجذر، والرجوع يرجّع للـ sheet).
final appRouterProvider = Provider<GoRouter>((ref) {
  final refresh = _RouterRefresh();
  ref.listen<AuthState>(authStateProvider, (previous, next) {
    // نهاية الجلسة بس (مش الدخول): حساب جديد لازم يكمّل لـ /otp، والدخول
    // بيروح عالرئيسية من شاشته (pushHomeAndClearStack)
    if ((previous?.isSignedIn ?? false) && !next.isSignedIn) refresh.notify();
  });
  ref.listen<bool>(sessionRestoredProvider, (_, __) => refresh.notify());

  final router = GoRouter(
    navigatorKey: appNavigatorKey,
    initialLocation: kDebugMode && _openDesignGallery ? AppRoutes.designSystem : AppRoutes.splash,
    refreshListenable: refresh,
    redirect: (context, state) => authRedirect(
      path: state.uri.path,
      signedIn: ref.read(authStateProvider).isSignedIn,
      sessionRestored: ref.read(sessionRestoredProvider),
    ),
    errorBuilder: (context, state) => UnknownRouteScreen(routeName: state.uri.toString()),
    routes: _routes(),
  );
  ref.onDispose(() {
    router.dispose();
    refresh.dispose();
  });
  return router;
});

/// الـ auth guard (دالة صافية حتى تنختبر لحالها):
/// - الـ splash بيضل لحد ما تنقرأ الجلسة المحفوظة، بعدها: جلسة → /home، بدونها
///   → /welcome (المسجّل ما بيشوف Welcome أبدًا عند الإقلاع).
/// - قبل قراءة الجلسة أي مسار تاني بيرجع للـ splash (إلا معرض الـ design system).
/// - بدون جلسة: أي مسار محمي → /welcome. مع جلسة: Welcome / Log in / Create
///   account → /home.
String? authRedirect({required String path, required bool signedIn, required bool sessionRestored}) {
  if (path == AppRoutes.splash) {
    if (!sessionRestored) return null;
    return signedIn ? AppRoutes.home : AppRoutes.welcome;
  }
  if (path == AppRoutes.designSystem) return null;
  if (!sessionRestored) return AppRoutes.splash;
  if (!signedIn && !AppRoutes.publicRoutes.contains(path)) return AppRoutes.welcome;
  if (signedIn && AppRoutes.signedOutOnly.contains(path)) return AppRoutes.home;
  return null;
}

/// الـ refreshListenable: بيخبّر الـ router يعيد الـ redirect بدون ما ينعاد بناؤه
class _RouterRefresh extends ChangeNotifier {
  void notify() => notifyListeners();
}

List<RouteBase> _routes() => [
      // ── بدون جلسة: الـ navigator الجذر، بدون شريط سفلي ─────────
      GoRoute(path: AppRoutes.splash, builder: (context, state) => const SplashScreen()),
      GoRoute(path: AppRoutes.welcome, pageBuilder: (context, state) => _authPage(state, const WelcomeScreen())),
      GoRoute(
        path: AppRoutes.registration,
        pageBuilder: (context, state) => _authPage(state, const RegistrationScreen()),
      ),
      GoRoute(path: AppRoutes.login, pageBuilder: (context, state) => _authPage(state, const LoginScreen())),
      GoRoute(
        path: AppRoutes.otpVerification,
        pageBuilder: (context, state) {
          final email = state.uri.queryParameters['email'];
          if (email == null || email.isEmpty) return _unknownPage(state);
          return _authPage(state, OtpVerificationScreen(email: email));
        },
      ),
      GoRoute(path: AppRoutes.designSystem, builder: (context, state) => const DesignSystemScreen()),

      // ── الـ shell: 5 فروع (نفس ترتيب ShellTab) ────────────────
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) =>
            AlertTriggerScope(child: PushRegistrationScope(child: AppShell(navigationShell: navigationShell))),
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppRoutes.home,
                builder: (context, state) => const HomeScreen(),
                routes: [
                  _marketRoute(),
                  _signalDetailRoute('signal/:id'),
                  GoRoute(path: 'notifications', builder: (context, state) => const NotificationsScreen()),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppRoutes.signals,
                builder: (context, state) => const SignalsScreen(),
                routes: [
                  GoRoute(path: 'insights', builder: (context, state) => const InsightsScreen()),
                  // فوق sheet الـ Strategy (الجذر)، فالرجوع بيرجّع للـ sheet المفتوحة
                  GoRoute(
                    path: 'backtest',
                    parentNavigatorKey: appNavigatorKey,
                    builder: (context, state) => const BacktestScreen(),
                  ),
                  _marketRoute(),
                  // آخر شي: ':id' ما لازم يبلع 'insights' / 'backtest'
                  _signalDetailRoute(':id'),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppRoutes.assistant,
                builder: (context, state) => const AssistantScreen(),
                routes: [_marketRoute(), _signalDetailRoute('signal/:id')],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppRoutes.community,
                builder: (context, state) => const CommunityScreen(),
                routes: [
                  GoRoute(
                    path: 'news/:id',
                    builder: (context, state) => NewsDetailScreen(articleId: state.pathParameters['id']!),
                  ),
                  _marketRoute(),
                  _signalDetailRoute('signal/:id'),
                  // محادثة = شاشة كاملة بدون شريط سفلي (الجذر)
                  GoRoute(
                    path: 'experts/:id/chat',
                    parentNavigatorKey: appNavigatorKey,
                    builder: (context, state) => ExpertChatScreen(expertId: state.pathParameters['id']!),
                  ),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppRoutes.profile,
                builder: (context, state) => const ProfileScreen(),
                routes: [
                  GoRoute(path: 'edit', builder: (context, state) => const EditProfileScreen()),
                  GoRoute(path: 'security', builder: (context, state) => const SecurityScreen()),
                  GoRoute(path: 'plans', builder: (context, state) => const PlansScreen()),
                  GoRoute(
                    path: 'settings',
                    builder: (context, state) => const SettingsScreen(),
                    routes: [
                      GoRoute(
                        path: 'notifications',
                        builder: (context, state) => const NotificationPreferencesScreen(),
                      ),
                    ],
                  ),
                  GoRoute(
                    path: 'help',
                    builder: (context, state) => const HelpAboutScreen(),
                    routes: [
                      GoRoute(
                        path: 'legal/:document',
                        builder: (context, state) {
                          final document = LegalDocument.values.asNameMap()[state.pathParameters['document']];
                          if (document == null) return UnknownRouteScreen(routeName: state.uri.toString());
                          return LegalScreen(document: document);
                        },
                      ),
                    ],
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
    ];

/// شاشة الأداة - بكل فرع (instance جديد لكل واحد)، حتى تنفتح جوّا التبويب يلي
/// انضغط منه وما تنقل المستخدم لتبويب تاني
GoRoute _marketRoute() => GoRoute(
      path: 'market/:symbol',
      builder: (context, state) => MarketScreen(symbol: state.pathParameters['symbol']!),
    );

/// تفاصيل إشارة - `:id` بفرع Signals، و`signal/:id` بالفروع يلي فيها شاشة
/// السوق (نتيجة "Request analysis" بتنفتح بنفس التبويب). `?symbol=` لازم.
GoRoute _signalDetailRoute(String path) => GoRoute(
      path: path,
      builder: (context, state) {
        final symbol = state.uri.queryParameters['symbol'];
        if (symbol == null || symbol.isEmpty) return UnknownRouteScreen(routeName: state.uri.toString());
        return SignalDetailScreen(signalId: state.pathParameters['id']!, symbol: symbol);
      },
    );

/// انتقال شاشات الدخول (Welcome / Log in / Create account / Verify email):
/// fade + طلوع خفيف 3% بدل الانزلاق الجانبي، حتى الخلفية تضل "وحدة" والشعار
/// (Hero) يطير بينها. مع "تقليل الحركة" الشاشة بتطلع فورًا.
CustomTransitionPage<void> _authPage(GoRouterState state, Widget child) => CustomTransitionPage<void>(
      key: state.pageKey,
      child: child,
      transitionDuration: AppMotion.page,
      reverseTransitionDuration: AppMotion.medium,
      transitionsBuilder: (context, animation, _, page) {
        if (context.reduceMotion) return page;
        final curved = CurvedAnimation(parent: animation, curve: AppMotion.out, reverseCurve: AppMotion.exit);
        return FadeTransition(
          opacity: curved,
          child: SlideTransition(
            position: Tween(begin: const Offset(0, 0.03), end: Offset.zero).animate(curved),
            child: page,
          ),
        );
      },
    );

Page<void> _unknownPage(GoRouterState state) =>
    MaterialPage<void>(key: state.pageKey, child: UnknownRouteScreen(routeName: state.uri.toString()));

/// شاشة بديلة بسيطة لمسار مش معروف (أو بارامتر ناقص/غلط) - بدل ما التطبيق
/// يطيح بصمت. هي الـ errorBuilder تبع الـ router.
class UnknownRouteScreen extends StatelessWidget {
  const UnknownRouteScreen({super.key, this.routeName});

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
