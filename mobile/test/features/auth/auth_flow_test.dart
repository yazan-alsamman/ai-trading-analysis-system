// اختبارات الدخول (Stage C): Welcome، Create account (الحقول + المربّع
// الإلزامي + شروط كلمة المرور)، Log in، والتحقق من البريد - بالثيمين وبالعربي
// وبخط كبير، وقاعدة كلمة المرور نفس الـ backend.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/app/router/app_routes.dart';
import 'package:trading_app/app/shell/app_shell.dart';
import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/theme/theme_context.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/core/widgets/app_illustration.dart';
import 'package:trading_app/core/widgets/brand_mark.dart';
import 'package:trading_app/features/auth/views/login_screen.dart';
import 'package:trading_app/features/auth/views/otp_screen.dart';
import 'package:trading_app/features/auth/views/register_screen.dart';
import 'package:trading_app/features/auth/views/welcome_screen.dart';
import 'package:trading_app/features/auth/widgets/auth_scaffold.dart';
import 'package:trading_app/features/auth/view_models/auth_view_models.dart';
import 'package:trading_app/l10n/app_localizations.dart';
import 'package:trading_app/utils/validators.dart';

import '../../helpers/test_app.dart';

Future<void> pumpAuth(
  WidgetTester tester, {
  String route = AppRoutes.welcome,
  String locale = 'en',
  String theme = 'light',
  bool? signedIn = false,
}) async {
  usePhoneSize(tester);
  await tester.pumpWidget(await testScope(
    TestApp(initialRoute: route),
    locale: locale,
    prefs: {themeModeStorageKey: theme},
    signedIn: signedIn,
  ));
  await tester.pumpAndSettle();
}

Finder field(String label) => find.ancestor(of: find.text(label), matching: find.byType(Column)).first;

Future<void> type(WidgetTester tester, String label, String value) async {
  await tester.enterText(find.descendant(of: field(label), matching: find.byType(TextField)), value);
  await tester.pump();
}

void main() {
  final l10n = AppLocalizations(const Locale('en'));

  group('Validators follow the backend password rule', () {
    test('8 to 128 characters with a letter and a digit', () {
      expect(Validators.password('', l10n), l10n.passwordRequired);
      expect(Validators.password('abc123', l10n), l10n.passwordMinChars);
      expect(Validators.password('${'a1' * 64}x', l10n), l10n.passwordMaxChars);
      expect(Validators.password('12345678', l10n), l10n.passwordNeedsLetter);
      expect(Validators.password('abcdefgh', l10n), l10n.passwordNeedsNumber);
      // ما في شرط حرف كبير أو رمز (الـ backend ما بيطلبهن)
      expect(Validators.password('abcdefg1', l10n), isNull);
    });

    test('full name: 2 to 60 characters', () {
      expect(Validators.fullName(' a ', l10n), l10n.fullNameRequired);
      expect(Validators.fullName('a' * 61, l10n), l10n.fullNameTooLong);
      expect(Validators.fullName('Sara Haddad', l10n), isNull);
    });

    test('OTP accepts exactly 5 digits', () {
      expect(OtpViewModel.isComplete('12345'), isTrue);
      expect(OtpViewModel.isComplete('1234'), isFalse);
      expect(OtpViewModel.isComplete('12a45'), isFalse);
    });
  });

  group('Welcome', () {
    for (final theme in ['light', 'dark']) {
      testWidgets('brand, one sentence and two actions ($theme)', (tester) async {
        await pumpAuth(tester, theme: theme);
        expect(find.byType(WelcomeScreen), findsOneWidget);
        expect(find.textContaining('A clearer way', findRichText: true), findsOneWidget);
        expect(find.text('Create account'), findsOneWidget);
        expect(find.text('Log in'), findsOneWidget);
        // الشعار لحالو (بدون رسم / حلقة / قوس حواليه)، وسطر التنبيه القصير تحت
        expect(find.byType(BrandGlyph), findsOneWidget);
        expect(find.byType(AppIllustration), findsNothing);
        expect(find.text('Analysis and decision support only. Not financial advice, not a broker.'), findsOneWidget);
        expect(tester.takeException(), isNull);
      });
    }

    testWidgets('the language button switches to Arabic (RTL) before signing in', (tester) async {
      await pumpAuth(tester);
      await tester.tap(find.text('العربية'));
      await tester.pumpAndSettle();
      expect(find.text('إنشاء حساب'), findsOneWidget);
      expect(Directionality.of(tester.element(find.byType(WelcomeScreen))), TextDirection.rtl);
    });

    for (final locale in ['en', 'ar']) {
      testWidgets('largest font ($locale): scrolls, no overflow', (tester) async {
        useLargeText(tester);
        await pumpAuth(tester, locale: locale);
        await tester.drag(find.byType(SingleChildScrollView).first, const Offset(0, -2000));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
      });
    }

    testWidgets('Create account and Log in open their screens; back returns to Welcome', (tester) async {
      await pumpAuth(tester);
      await tester.tap(find.text('Create account'));
      await tester.pumpAndSettle();
      expect(find.byType(RegistrationScreen), findsOneWidget);
      // من Create account لـ Log in بيستبدل الشاشة: الرجوع بيوصل لـ Welcome
      await scrollTo(tester, find.widgetWithText(TextButton, 'Log in'));
      await tester.tap(find.widgetWithText(TextButton, 'Log in'));
      await tester.pumpAndSettle();
      expect(find.byType(LoginScreen), findsOneWidget);
      await tester.tap(find.byType(BackButton));
      await tester.pumpAndSettle();
      expect(find.byType(WelcomeScreen), findsOneWidget);
    });
  });

  group('Create account', () {
    testWidgets('empty submit shows every error, including the advice checkbox', (tester) async {
      await pumpAuth(tester, route: AppRoutes.registration);
      await scrollTo(tester, find.widgetWithText(FilledButton, 'Create account'));
      await tester.tap(find.widgetWithText(FilledButton, 'Create account'));
      await tester.pumpAndSettle();
      expect(find.text('Enter your full name.'), findsOneWidget);
      expect(find.text('Email is required'), findsOneWidget);
      expect(find.text('Password is required'), findsOneWidget);
      expect(find.text('Please confirm you understand the app does not give financial advice.'), findsOneWidget);
      expect(find.byType(OtpVerificationScreen), findsNothing);
    });

    testWidgets('password checks tick as you type', (tester) async {
      final semantics = tester.ensureSemantics();
      await pumpAuth(tester, route: AppRoutes.registration);
      expect(find.bySemanticsLabel('8+ characters, not met'), findsOneWidget);
      await type(tester, 'Password', 'abcdefg1');
      expect(find.bySemanticsLabel('8+ characters, met'), findsOneWidget);
      expect(find.bySemanticsLabel('A letter, met'), findsOneWidget);
      expect(find.bySemanticsLabel('A number, met'), findsOneWidget);
      semantics.dispose();
    });

    testWidgets('valid form → verify email → account ready → Home', (tester) async {
      // الجلسة الحقيقية: الحساب الجديد بيدخل، والـ guard بيخلّيه يكمّل لـ /otp ثم الرئيسية
      await pumpAuth(tester, route: AppRoutes.registration, signedIn: null);
      await type(tester, 'Full name', 'Sara Haddad');
      await type(tester, 'Email', 'sara@example.com');
      await type(tester, 'Password', 'research42');
      await type(tester, 'Confirm password', 'research42');
      await scrollTo(tester, find.text('I understand this is not financial advice.'));
      await tester.tap(find.text('I understand this is not financial advice.'));
      await tester.pump();
      await scrollTo(tester, find.widgetWithText(FilledButton, 'Create account'));
      await tester.tap(find.widgetWithText(FilledButton, 'Create account'));
      await tester.pump(const Duration(seconds: 3));
      await tester.pumpAndSettle();

      expect(find.byType(OtpVerificationScreen), findsOneWidget);
      expect(find.textContaining('sara@example.com', findRichText: true), findsOneWidget);

      // ناقص → رسالة؛ 5 أرقام → تحقق تلقائي
      await tester.tap(find.widgetWithText(FilledButton, 'Verify'));
      await tester.pumpAndSettle();
      expect(find.text('Enter all 5 digits.'), findsOneWidget);
      await tester.enterText(find.byType(TextField), '24680');
      await tester.pump(OtpViewModel.latency);
      await tester.pumpAndSettle();
      expect(find.text('You’re all set.'), findsOneWidget);

      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();
      expect(find.byType(AppShell), findsOneWidget);
    });

    testWidgets('Arabic + dark + largest font: no overflow after errors', (tester) async {
      useLargeText(tester);
      await pumpAuth(tester, route: AppRoutes.registration, locale: 'ar', theme: 'dark');
      await scrollTo(tester, find.widgetWithText(FilledButton, 'إنشاء حساب'));
      await tester.tap(find.widgetWithText(FilledButton, 'إنشاء حساب'));
      await tester.pumpAndSettle();
      await tester.drag(find.byType(SingleChildScrollView).first, const Offset(0, -3000));
      await tester.pumpAndSettle();
      expect(find.text('أدخل اسمك الكامل.'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });

  group('Log in', () {
    testWidgets('empty submit shows inline errors', (tester) async {
      await pumpAuth(tester, route: AppRoutes.login);
      await tester.tap(find.widgetWithText(FilledButton, 'Log in'));
      await tester.pumpAndSettle();
      expect(find.text('Email is required'), findsOneWidget);
      expect(find.text('Password is required'), findsOneWidget);
    });

    testWidgets('any password with letters only is fine on login (the rule is for new ones)', (tester) async {
      await pumpAuth(tester, route: AppRoutes.login, signedIn: null);
      await type(tester, 'Email', 'trader@example.com');
      await type(tester, 'Password', 'old');
      await tester.tap(find.widgetWithText(FilledButton, 'Log in'));
      await tester.pump(const Duration(seconds: 3));
      await tester.pumpAndSettle();
      expect(find.byType(AppShell), findsOneWidget);
    });

    testWidgets('offline: nothing is sent, the banner and an inline message explain why', (tester) async {
      await pumpAuth(tester, route: AppRoutes.login);
      final container = ProviderScope.containerOf(tester.element(find.byType(LoginScreen)));
      container.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      await tester.pumpAndSettle();
      await type(tester, 'Email', 'trader@example.com');
      await type(tester, 'Password', 'research42');
      await tester.tap(find.widgetWithText(FilledButton, 'Log in'));
      await tester.pumpAndSettle();
      expect(find.text('You are offline. Connect to the internet and try again.'), findsOneWidget);
      expect(find.textContaining('You’re offline', findRichText: true), findsOneWidget);
      expect(find.byType(LoginScreen), findsOneWidget);
    });

    for (final locale in ['en', 'ar']) {
      testWidgets('largest font ($locale): no overflow', (tester) async {
        useLargeText(tester);
        await pumpAuth(tester, route: AppRoutes.login, locale: locale, theme: 'dark');
        await tester.drag(find.byType(SingleChildScrollView).first, const Offset(0, -2000));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
      });
    }
  });

  group('Verify email', () {
    testWidgets('resend unlocks after the countdown and restarts it', (tester) async {
      usePhoneSize(tester);
      await tester.pumpWidget(await testScope(
        const TestApp(home: OtpVerificationScreen(email: 'trader@example.com')),
        signedIn: false,
      ));
      await tester.pump();
      expect(find.text('Resend code in 0:60'), findsOneWidget);
      await tester.pump(const Duration(seconds: 61));
      expect(find.text('Resend code'), findsOneWidget);
      await tester.tap(find.text('Resend code'));
      await tester.pump();
      expect(find.text('A new code is on its way.'), findsOneWidget);
      expect(find.text('Resend code in 0:60'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
    });

    testWidgets('Arabic: the code boxes stay left to right, no overflow at largest font', (tester) async {
      useLargeText(tester);
      usePhoneSize(tester);
      await tester.pumpWidget(await testScope(
        const TestApp(home: OtpVerificationScreen(email: 'trader@example.com')),
        locale: 'ar',
        signedIn: false,
      ));
      await tester.pump();
      await tester.enterText(find.byType(TextField), '12');
      await tester.pump();
      final one = tester.getRect(find.text('1'));
      final two = tester.getRect(find.text('2'));
      expect(one.left, lessThan(two.left));
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
    });
  });

  group('Revisions: solid titles, short disclaimer, polished fields', () {
    // العنوان Text واحد بلون fg الصافي (مش جملتين بلونين)
    void expectSolidTitle(WidgetTester tester, String title) {
      final text = tester.widget<Text>(find.text(title));
      expect(text.textSpan, isNull, reason: 'one span, one colour');
      expect(text.style?.color, tester.element(find.text(title)).colors.fg);
    }

    for (final theme in ['light', 'dark']) {
      testWidgets('every auth title is one solid colour ($theme)', (tester) async {
        await pumpAuth(tester, theme: theme);
        expectSolidTitle(tester, 'A clearer way to read the markets.');
        // شجرة جديدة لكل شاشة (غير هيك الـ Navigator القديم بيضل)
        await tester.pumpWidget(const SizedBox());
        await pumpAuth(tester, route: AppRoutes.login, theme: theme);
        expectSolidTitle(tester, 'Welcome back');
        await tester.pumpWidget(const SizedBox());
        await pumpAuth(tester, route: AppRoutes.registration, theme: theme);
        expectSolidTitle(tester, 'Create your account');
        await tester.pumpWidget(const SizedBox());
        await tester.pumpWidget(await testScope(
          const TestApp(home: OtpVerificationScreen(email: 'trader@example.com')),
          prefs: {themeModeStorageKey: theme},
          signedIn: false,
        ));
        await tester.pump();
        expectSolidTitle(tester, 'Check your email');
        await tester.pumpWidget(const SizedBox());
      });
    }

    testWidgets('Arabic dark: solid title, RTL, largest font fits', (tester) async {
      useLargeText(tester);
      await pumpAuth(tester, locale: 'ar', theme: 'dark', route: AppRoutes.login);
      expectSolidTitle(tester, 'أهلًا بعودتك');
      expect(find.text('للتحليل ودعم القرار فقط. ليس نصيحة مالية، وليس وسيطًا.'), findsOneWidget);
      expect(Directionality.of(tester.element(find.byType(LoginScreen))), TextDirection.rtl);
      expect(tester.takeException(), isNull);
    });

    testWidgets('Log in: one short disclaimer line; Create account keeps the checkbox instead', (tester) async {
      const line = 'Analysis and decision support only. Not financial advice, not a broker.';
      await pumpAuth(tester, route: AppRoutes.login);
      expect(find.text(line), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
      await pumpAuth(tester, route: AppRoutes.registration);
      expect(find.text(line), findsNothing);
      expect(find.byType(Checkbox), findsOneWidget);
    });

    testWidgets('fields: gold label on focus, field icons, no clear button, show password', (tester) async {
      await pumpAuth(tester, route: AppRoutes.login);
      final email = find.descendant(of: field('Email'), matching: find.byType(TextField));
      await tester.tap(email);
      await tester.pumpAndSettle();
      final context = tester.element(find.text('Email'));
      expect(DefaultTextStyle.of(context).style.color, context.colors.accent);
      expect(find.byIcon(Icons.mail_outline_rounded), findsOneWidget);

      await type(tester, 'Email', 'sara@example.com');
      expect(find.byIcon(Icons.cancel_outlined), findsNothing);
      expect(find.descendant(of: field('Email'), matching: find.byType(IconButton)), findsNothing);

      expect(find.byTooltip('Show password'), findsOneWidget);
      await tester.tap(find.byTooltip('Show password'));
      await tester.pump();
      expect(find.byTooltip('Hide password'), findsOneWidget);
    });

    // الهالة: تدرّج دائري لشفاف تمامًا، بدون حدود ولا ظل (مش حلقة ولا خط)
    void expectSoftGlow(WidgetTester tester, String reason) {
      final glow = find.byType(BrandGlow);
      expect(glow, findsOneWidget, reason: reason);
      final box = tester.widget<DecoratedBox>(find.descendant(of: glow, matching: find.byType(DecoratedBox)).first);
      final decoration = box.decoration as BoxDecoration;
      expect(decoration.border, isNull, reason: reason);
      expect(decoration.boxShadow, isNull, reason: reason);
      final gradient = decoration.gradient! as RadialGradient;
      expect(gradient.colors.last.a, 0, reason: reason);
      expect(gradient.colors.first.a, lessThanOrEqualTo(0.25), reason: reason);
    }

    testWidgets('the logo has a soft glow only on every auth screen: no ring, arc or outline', (tester) async {
      for (final route in [AppRoutes.splash, AppRoutes.welcome, AppRoutes.login, AppRoutes.registration]) {
        await tester.pumpWidget(const SizedBox());
        usePhoneSize(tester);
        await tester.pumpWidget(await testScope(TestApp(initialRoute: route), signedIn: false));
        await tester.pump(const Duration(milliseconds: 500));
        final glyph = find.byType(BrandGlyph);
        expect(glyph, findsOneWidget, reason: route);
        expect(find.byType(AppIllustration), findsNothing, reason: route);
        final glow = find.ancestor(
          of: glyph,
          matching: find.byWidgetPredicate(
            (w) => w is DecoratedBox && w.decoration is BoxDecoration && (w.decoration as BoxDecoration).boxShadow != null,
          ),
        );
        expect(glow, findsNothing, reason: route);
        expectSoftGlow(tester, route);
      }
      // Verify email: نفس الهالة ورا بلاطة الأيقونة
      await tester.pumpWidget(const SizedBox());
      await tester.pumpWidget(await testScope(
        const TestApp(home: OtpVerificationScreen(email: 'trader@example.com')),
        signedIn: false,
      ));
      await tester.pump();
      expectSoftGlow(tester, 'otp');
      expect(find.byType(BrandGlyph), findsNothing);
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(seconds: 2));
    });

    testWidgets('the brand glyph is shared between Welcome and Log in (Hero)', (tester) async {
      await pumpAuth(tester);
      Finder hero() => find.byWidgetPredicate((w) => w is Hero && w.tag == kAuthBrandHeroTag);
      expect(hero(), findsOneWidget);
      await scrollTo(tester, find.widgetWithText(OutlinedButton, 'Log in'));
      await tester.tap(find.widgetWithText(OutlinedButton, 'Log in'));
      await tester.pumpAndSettle();
      expect(find.byType(LoginScreen), findsOneWidget);
      expect(hero(), findsOneWidget);
    });

    testWidgets('reduced motion: Welcome is static from the first frame', (tester) async {
      tester.platformDispatcher.accessibilityFeaturesTestValue = const FakeAccessibilityFeatures(disableAnimations: true);
      addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
      usePhoneSize(tester);
      await tester.pumpWidget(await testScope(const TestApp(initialRoute: AppRoutes.welcome), signedIn: false));
      await tester.pump();
      expect(find.byType(TweenAnimationBuilder<double>), findsNothing);
      expect(tester.widgetList<BrandGlyph>(find.byType(BrandGlyph)).every((g) => g.progress == 1), isTrue);
    });

    testWidgets('Verify email: a clear success step with the verified address', (tester) async {
      usePhoneSize(tester);
      await tester.pumpWidget(await testScope(
        const TestApp(home: OtpVerificationScreen(email: 'trader@example.com')),
        signedIn: false,
      ));
      await tester.pump();
      await tester.enterText(find.byType(TextField), '13579');
      await tester.pump(OtpViewModel.latency);
      await tester.pumpAndSettle();
      expect(find.byType(SuccessIllustration), findsOneWidget);
      expect(find.text('Email verified'), findsOneWidget);
      expect(find.text('trader@example.com'), findsOneWidget);
      expect(find.widgetWithText(FilledButton, 'Continue'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
    });
  });
}
