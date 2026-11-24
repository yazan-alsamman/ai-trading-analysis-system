import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:trading_app/app/router/app_router.dart';
import 'package:trading_app/app/router/app_routes.dart';
import 'package:trading_app/app/router/navigator_key.dart';
import 'package:trading_app/core/storage/preferences_provider.dart';
import 'package:trading_app/core/theme/app_theme.dart';
import 'package:trading_app/core/data/clock.dart';
import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/database/app_database_holder.dart';
import 'package:trading_app/core/database/database_providers.dart';
import 'package:trading_app/core/database/user_cache_guard.dart';
import 'package:trading_app/core/network/connectivity_source.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/features/alerts/data/alerts_repository.dart';
import 'package:trading_app/features/auth/auth_state.dart';
import 'package:trading_app/features/auth/data/session_store.dart';
import 'package:trading_app/features/community/data/posts_repository.dart';
import 'package:trading_app/features/markets/data/market_data_repository.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/markets/data/simulated_market_source.dart';
import 'package:trading_app/features/membership/data/membership_repository.dart';
import 'package:trading_app/features/membership/models/membership_models.dart';
import 'package:trading_app/features/news/data/news_repository.dart';
import 'package:trading_app/features/signals/data/signals_repository.dart';
import 'package:trading_app/features/notifications/data/notification_permission_service.dart';
import 'package:trading_app/features/notifications/data/notifications_repository.dart';
import 'package:trading_app/features/notifications/data/push_device_repository.dart';
import 'package:trading_app/features/notifications/data/telegram_link_repository.dart';
import 'package:trading_app/l10n/app_localizations.dart';
import 'package:trading_app/models/user_model.dart';
import 'package:trading_app/providers/locale_provider.dart';

/// أربعاء 21 تشرين الأول 2026، 14:05 UTC - وقت ثابت لكل الاختبارات (أسعار حتمية)
final kTestNow = DateTime.utc(2026, 10, 21, 14, 5);

/// السوق المحاكى على وقت ثابت وبدون تأخير
List<Override> simulatedMarketOverrides({DateTime Function()? clock}) {
  final source = SimulatedMarketSource(clock: clock ?? () => kTestNow);
  return [
    simulatedMarketSourceProvider.overrideWithValue(source),
    marketDataRepositoryProvider.overrideWithValue(SimulatedMarketDataRepository(source: source)),
    // H5b: الإشارات كمان بدون طبقة الكاش (متل السوق هون)؛ اختبارات الكاش
    // بتستعمل [cachedFeatureOverrides]
    signalsRepositoryProvider.overrideWith((ref) => ref.watch(signalsSourceRepositoryProvider)),
  ];
}

/// H5a: كاش السوق الحقيقي (Drift **بالذاكرة**) فوق السوق المحاكى بدون تأخير،
/// وساعة كاش وهمية ([clock]: وقت الكتابة + حدّ كتابة النبضات). [db] مشترك =
/// "نسكّر ونفتح" التطبيق بنفس الكاش. [source] = مصدر بديل (فاشل مثلًا).
/// [enabled] false = المفتاح مطفي (التطبيق متل قبل H5a).
List<Override> cachedMarketOverrides({
  AppDatabaseHolder? db,
  DateTime Function()? clock,
  DateTime Function()? marketClock,
  MarketDataRepository? source,
  bool enabled = true,
}) {
  final simulated = SimulatedMarketSource(clock: marketClock ?? () => kTestNow);
  final holder = db ?? AppDatabaseHolder.memory();
  return [
    simulatedMarketSourceProvider.overrideWithValue(simulated),
    appDatabaseProvider.overrideWithValue(holder),
    marketCacheEnabledProvider.overrideWithValue(enabled),
    marketCacheClockProvider.overrideWithValue(clock ?? () => kTestNow),
    marketSourceRepositoryProvider.overrideWithValue(source ?? SimulatedMarketDataRepository(source: simulated)),
    // يرجّع المنطق الحقيقي (testScope بيعمل override للمحاكاة مباشرة)
    marketDataRepositoryProvider.overrideWith(createMarketDataRepository),
  ];
}

/// H5b: طبقة الكاش الحقيقية للإشارات والأخبار والإشعارات فوق مصادر محاكاة
/// (أو [signals] / [news] / [notifications] بديلة، فاشلة مثلًا). بتنضاف مع
/// [cachedMarketOverrides] (نفس القاعدة بالذاكرة ونفس الساعة والمفتاح).
List<Override> cachedFeatureOverrides({
  SignalsRepository? signals,
  NewsRepository? news,
  NotificationsRepository? notifications,
}) =>
    [
      if (signals != null) signalsSourceRepositoryProvider.overrideWithValue(signals),
      signalsRepositoryProvider.overrideWith(createSignalsRepository),
      newsSourceRepositoryProvider.overrideWithValue(news ?? SimulatedNewsRepository(clock: () => kTestNow)),
      newsRepositoryProvider.overrideWith(createNewsRepository),
      // H5c: متل الحقيقي، المحاكاة (المقروء / المحذوف بالذاكرة) نسخة لكل حساب
      notifications != null
          ? notificationsSourceRepositoryProvider.overrideWithValue(notifications)
          : notificationsSourceRepositoryProvider.overrideWith((ref) {
              ref.watch(cacheOwnerProvider);
              return SimulatedNotificationsRepository(clock: () => kTestNow);
            }),
      notificationsRepositoryProvider.overrideWith(createNotificationsRepository),
    ];

/// يجهّز التخزين الوهمي (ومعه اللغة [locale]) ويرجع ProviderScope جاهز فيه [child]
///
/// افتراضيًا: مستخدم داخل (الـ auth guard ما بيحوّل)، الجلسة المحفوظة انقرأت
/// (الـ router بيفتح المسار مباشرة بدون splash، إلا [TestApp] على الـ splash
/// نفسه)، سوق محاكى على [kTestNow]، وساعة ثابتة. أي override بـ [overrides]
/// بيغلب الافتراضي. [secure] = قيم التخزين الآمن (الـ token مثلًا، راجع
/// [SavedSession]). [signedIn] null = الجلسة الحقيقية (الـ AuthController
/// الوهمي، بتبلّش بدون جلسة وبتتغيّر لما المستخدم يدخل أو يطلع).
Future<ProviderScope> testScope(
  Widget child, {
  Map<String, Object> prefs = const {},
  Map<String, String> secure = const {},
  String locale = 'en',
  List<Override> overrides = const [],
  bool? signedIn = true,
  bool? sessionRestored,
}) async {
  final restored = sessionRestored ?? !(child is TestApp && child.initialRoute == AppRoutes.splash);
  SharedPreferences.setMockInitialValues(prefs);
  // LocaleNotifier بيقرأ اللغة المحفوظة من secure storage
  FlutterSecureStorage.setMockInitialValues({'app_locale': locale, ...secure});
  final shared = await SharedPreferences.getInstance();
  return ProviderScope(
    overrides: [
      sharedPreferencesProvider.overrideWithValue(shared),
      if (signedIn != null)
        authStateProvider.overrideWithValue(
          signedIn ? const SignedIn(UserModel(id: 'test-user', email: 'trader@example.com')) : const SignedOut(),
        ),
      if (restored) sessionRestoredProvider.overrideWith(_RestoredSession.new),
      clockProvider.overrideWith((ref) => Stream.value(kTestNow)),
      // ساعة التنبيهات (الإنشاء والانتهاء) على نفس الوقت الثابت
      alertsClockProvider.overrideWithValue(() => kTestNow),
      // اتصال وهمي (online) بدل connectivity_plus (ما في plugin بالاختبارات)
      connectivityOverride(),
      // H5a: ولا اختبار بيفتح ملف SQLite حقيقي (path_provider مش موجود)
      appDatabaseProvider.overrideWith((ref) {
        final holder = AppDatabaseHolder.memory();
        ref.onDispose(holder.close);
        return holder;
      }),
      ...simulatedMarketOverrides(),
      // إشعارات وأخبار ومنشورات محاكاة على نفس الوقت الثابت (الأوقات النسبية حتمية)
      notificationsRepositoryProvider.overrideWith((ref) => SimulatedNotificationsRepository(clock: () => kTestNow)),
      newsRepositoryProvider.overrideWith((ref) => SimulatedNewsRepository(clock: () => kTestNow)),
      postsRepositoryProvider.overrideWith(
        (ref) => SimulatedPostsRepository(clock: () => kTestNow, author: () => ref.read(postAuthorProvider)),
      ),
      // H4b: ربط Telegram بدون تأخير وبكود حتمي لكل طلب، ساعة ثابتة؛ إذن الإشعارات
      // مسموح (متل هاتف وافق قبل) وتسجيل الجهاز بالذاكرة
      telegramClockProvider.overrideWithValue(() => kTestNow),
      telegramLinkRepositoryProvider.overrideWith(
        (ref) => SimulatedTelegramLinkRepository(
          prefs: ref.watch(sharedPreferencesProvider),
          clock: ref.watch(telegramClockProvider),
          codeFor: testTelegramCode,
        ),
      ),
      notificationPermissionServiceProvider.overrideWith(
        (ref) => SimulatedNotificationPermissionService(
          ref.watch(sharedPreferencesProvider),
          initial: prefs.containsKey(SimulatedNotificationPermissionService.storageKey) ? null : PushPermission.granted,
        ),
      ),
      pushDeviceRepositoryProvider.overrideWith((ref) => SimulatedPushDeviceRepository()),
      ...overrides,
    ],
    child: child,
  );
}

/// كود Telegram الحتمي للطلب رقم [request] (1، 2، ...)
String testTelegramCode(int request) => 'TGK${request.toString().padLeft(3, '0')}';

/// ساعة وهمية بتتقدّم بس لما الاختبار يقدّمها (العدّ التنازلي والصلاحية)
final class FakeClock {
  FakeClock([DateTime? start]) : now = start ?? kTestNow;

  DateTime now;

  DateTime call() => now;

  void advance(Duration by) => now = now.add(by);
}

/// مصدر اتصال وهمي: [emit] بيبدّل الحالة متل ما الجهاز بيبعت تغيير،
/// و[emitMobileData] نوع الاتصال (H5b: اقتراح الـ Low data mode)
final class FakeConnectivitySource implements ConnectivitySource, ConnectionTypeSource {
  FakeConnectivitySource([this.status = NetworkStatus.online, this.mobileData = false]);

  NetworkStatus status;
  bool mobileData;
  final _changes = StreamController<NetworkStatus>.broadcast();
  final _mobileChanges = StreamController<bool>.broadcast();

  void emit(NetworkStatus next) {
    status = next;
    _changes.add(next);
  }

  void emitMobileData(bool next) {
    mobileData = next;
    _mobileChanges.add(next);
  }

  @override
  Future<NetworkStatus> current() async => status;

  @override
  Stream<NetworkStatus> changes() => _changes.stream;

  @override
  Future<bool> isMobileData() async => mobileData;

  @override
  Stream<bool> mobileDataChanges() => _mobileChanges.stream;
}

/// override الاتصال الوهمي (لـ ProviderContainer مباشر كمان)
Override connectivityOverride([FakeConnectivitySource? source]) =>
    connectivitySourceProvider.overrideWithValue(source ?? FakeConnectivitySource());

/// جلسة محفوظة على الجهاز (متل ما بتضل بعد ما المستخدم سكّر التطبيق وهو داخل):
/// [prefs] (بيانات المستخدم) و[secure] (الـ token)، لـ testScope
final class SavedSession {
  SavedSession({this.user = const UserModel(id: 'uid_saved', email: 'saved@example.com', displayName: 'Sara Saved')});

  final UserModel user;

  Map<String, Object> get prefs => {
        SessionStore.userKey: jsonEncode({'id': user.id, 'email': user.email, 'displayName': user.displayName, 'role': 'trader'}),
      };

  Map<String, String> get secure => {'auth_token': 'mock_token_${user.id}'};

  /// الجلسة المحفوظة هلق بالتخزين الوهمي (حتى "نسكّر ونفتح" التطبيق بنفس القيم)
  static Future<({String? user, String? token})> current() async => (
        user: (await SharedPreferences.getInstance()).getString(SessionStore.userKey),
        token: await const FlutterSecureStorage().read(key: 'auth_token'),
      );
}

/// الجلسة المحفوظة انقرأت من أول إطار (بدل انتظار الـ splash)
class _RestoredSession extends SessionRestoreNotifier {
  @override
  bool build() => true;
}

/// مسار الشاشة يلي بيمرّرها الاختبار بـ [TestApp.home] (بالـ navigator الجذر)
const kTestHomePath = '/test-home';

/// نفس إعداد MaterialApp الحقيقي (ثيم + لغة + go_router) بس بشاشة بداية
/// نحددها نحن:
/// - [home]: الشاشة على مسار لحالها ([kTestHomePath]) مع جدول المسارات
///   الحقيقي بدون الـ shell (فروعه مسارات عادية عالجذر)، فكل `context.pushX()`
///   منها بيفتح الشاشة الحقيقية فوقها والرجوع بيرجّع لها. (push لمسار جوّا
///   الـ shell من برّاه بيبني الـ shell كله فوق، وهالشي ما بيصير بالتطبيق.)
///   الـ shell نفسه (الشريط، الفروع، الرجوع) مختبر بالـ router الحقيقي.
/// - [initialRoute] (أو بدونهم = /home): الـ router الحقيقي
///   ([appRouterProvider]: نفس الـ guard ونهاية الجلسة) على هالمسار.
/// الجلسة المحفوظة "انقرأت" من الأول (testScope)، فما في splash - إلا إذا
/// [initialRoute] هو الـ splash نفسه.
class TestApp extends ConsumerStatefulWidget {
  const TestApp({super.key, this.home, this.initialRoute});

  final Widget? home;
  final String? initialRoute;

  @override
  ConsumerState<TestApp> createState() => _TestAppState();
}

class _TestAppState extends ConsumerState<TestApp> {
  late final GoRouter _router;

  /// router الاختبار تبع [TestApp.home] (منسكّره نحن؛ الحقيقي بيسكّره الـ provider)
  GoRouter? _ownRouter;
  final _refresh = ValueNotifier<int>(0);

  @override
  void initState() {
    super.initState();
    final route = widget.home == null ? (widget.initialRoute ?? AppRoutes.home) : kTestHomePath;
    final app = ref.read(appRouterProvider);
    final home = widget.home;
    if (home == null) {
      _router = app..go(route);
      return;
    }
    final startedSignedIn = ref.read(authStateProvider).isSignedIn;
    // نهاية الجلسة → إعادة الـ redirect (نفس الحقيقي)
    ref.listenManual<AuthState>(authStateProvider, (previous, next) {
      if ((previous?.isSignedIn ?? false) && !next.isSignedIn) _refresh.value++;
    });
    _router = _ownRouter = GoRouter(
      navigatorKey: appNavigatorKey,
      initialLocation: kTestHomePath,
      refreshListenable: _refresh,
      redirect: (context, state) {
        final signedIn = ref.read(authStateProvider).isSignedIn;
        // [TestApp.home] بدون جلسة (Verify email مثلًا) بيضل مفتوح؛ إذا الجلسة
        // انتهت بيرجع لـ Welcome متل أي شاشة محمية
        if (state.uri.path == kTestHomePath) return signedIn || !startedSignedIn ? null : AppRoutes.welcome;
        return authRedirect(path: state.uri.path, signedIn: signedIn, sessionRestored: true);
      },
      errorBuilder: (context, state) => UnknownRouteScreen(routeName: state.uri.toString()),
      routes: [
        GoRoute(path: kTestHomePath, builder: (context, state) => home),
        ..._withoutShell(app.configuration.routes),
      ],
    );
  }

  @override
  void dispose() {
    _ownRouter?.dispose();
    _refresh.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final locale = ref.watch(localeProvider);
    final arabic = locale.languageCode == 'ar';
    return MaterialApp.router(
      routerConfig: _router,
      locale: locale,
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      theme: AppTheme.light(arabic: arabic),
      darkTheme: AppTheme.dark(arabic: arabic),
      themeMode: ref.watch(themeModeProvider),
      themeAnimationDuration: Duration.zero,
    );
  }
}

/// جدول المسارات بدون الـ shell: فروعه مسارات عادية عالـ navigator الجذر
List<RouteBase> _withoutShell(List<RouteBase> routes) => [
      for (final route in routes)
        if (route is StatefulShellRoute) ...[for (final branch in route.branches) ...branch.routes] else route,
    ];

/// الـ GoRouter المركّب بالشجرة (حتى الاختبار يفتح مسار مباشرة: `testRouter(tester).push(...)`)
GoRouter testRouter(WidgetTester tester) => GoRouter.of(appNavigatorKey.currentContext!);

/// شاشة هاتف عادية (375×812) - [height] أطول لما بدنا كل المحتوى ينبني
void usePhoneSize(WidgetTester tester, {double height = 812}) {
  tester.view.physicalSize = Size(375, height);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
}

/// يسكرول لحد ما [finder] ينبني ويصير كامل ضمن الشاشة (قبل الضغط عليه)
Future<void> scrollTo(WidgetTester tester, Finder finder) async {
  await tester.scrollUntilVisible(
    finder,
    200,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pumpAndSettle();
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
}

/// أكبر حجم خط بإعدادات الجهاز (للتأكد إنو ما في overflow)
void useLargeText(WidgetTester tester, {double scale = 2}) {
  tester.platformDispatcher.textScaleFactorTestValue = scale;
  addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
}

/// يخلّص الحركات + المؤقتات التجريبية بالشاشات القديمة (تحميل الأخبار
/// التجريبي 400ms بالـ Home مثلًا)
Future<void> settleMocks(WidgetTester tester) async {
  await tester.pumpAndSettle();
  await tester.pump(const Duration(seconds: 1));
  await tester.pumpAndSettle();
}

/// سهم الرجوع والعنوان بنفس الصف: نفس المركز العمودي تقريبًا، والسهم
/// بأول الصف (يسار بالإنجليزي، يمين بالعربي)
void expectArrowBesideTitle(
  WidgetTester tester, {
  required Finder arrow,
  required Finder title,
  required bool rtl,
}) {
  final a = tester.getRect(arrow);
  final t = tester.getRect(title);
  expect((a.center.dy - t.center.dy).abs(), lessThan(8),
      reason: 'arrow and title must share one row');
  if (rtl) {
    expect(a.left, greaterThanOrEqualTo(t.right - 1), reason: 'RTL: arrow on the right');
  } else {
    expect(a.right, lessThanOrEqualTo(t.left + 1), reason: 'LTR: arrow on the left');
  }
  expect(a.width, greaterThanOrEqualTo(48));
  expect(a.height, greaterThanOrEqualTo(48));
}

/// مستودع عضوية وهمي بخطة حالية محددة (متل ما رح يرجّع الـ backend)
final class FakeMembershipRepository implements MembershipRepository {
  const FakeMembershipRepository(this.plan);

  final PlanId? plan;

  @override
  Future<MembershipCatalog> fetchCatalog() async => kMembershipCatalog;

  @override
  Future<PlanId?> fetchCurrentPlan() async => plan;
}

Override currentPlanIs(PlanId? plan) =>
    membershipRepositoryProvider.overrideWithValue(FakeMembershipRepository(plan));
