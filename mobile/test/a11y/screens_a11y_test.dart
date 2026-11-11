// فحص الوصول الشامل (D5): الشاشات الرئيسية بالعربي والإنجليزي، فاتح وداكن،
// على أكبر خط (2.0): ولا overflow، ولا تسمية مقصوصة بـ "…"، أهداف اللمس
// ≥ 48dp وإلها اسم، تباين النص AA، وبدون أي حركة لما "تقليل الحركة" مفعّل.

import 'dart:ui' show Tristate;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/app/router/app_routes.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/features/assistant/views/assistant_screen.dart';
import 'package:trading_app/features/auth/views/otp_screen.dart';
import 'package:trading_app/features/backtest/views/backtest_screen.dart';
import 'package:trading_app/features/community/views/community_screen.dart';
import 'package:trading_app/features/home/views/home_screen.dart';
import 'package:trading_app/features/insights/views/insights_screen.dart';
import 'package:trading_app/features/markets/views/market_screen.dart';
import 'package:trading_app/features/markets/widgets/price_chart.dart';
import 'package:trading_app/features/membership/views/plans_screen.dart';
import 'package:trading_app/features/news/widgets/news_card.dart';
import 'package:trading_app/features/notifications/views/notifications_screen.dart';
import 'package:trading_app/features/profile/views/profile_screen.dart';
import 'package:trading_app/features/settings/views/settings_screen.dart';
import 'package:trading_app/features/signals/views/signals_screen.dart';

import '../helpers/test_app.dart';

/// شاشة للفحص: إما [home] جوّا التطبيق، أو [route] (شاشات الدخول، بدون جلسة)
class _Screen {
  const _Screen(this.name, {this.home, this.route});

  final String name;
  final Widget? home;
  final String? route;
}

const _screens = [
  _Screen('Home', home: HomeScreen()),
  _Screen('Market', home: MarketScreen(symbol: 'XAU/USD')),
  _Screen('Signals', home: SignalsScreen()),
  _Screen('Insights', home: InsightsScreen()),
  _Screen('Backtest', home: BacktestScreen()),
  _Screen('Assistant', home: AssistantScreen()),
  _Screen('Community', home: CommunityScreen()),
  _Screen('Notifications', home: NotificationsScreen()),
  _Screen('Profile', home: ProfileScreen()),
  _Screen('Settings', home: SettingsScreen()),
  _Screen('Plans', home: PlansScreen()),
  _Screen('Welcome', route: AppRoutes.welcome),
  _Screen('Log in', route: AppRoutes.login),
  _Screen('Create account', route: AppRoutes.registration),
];

Future<void> _pump(
  WidgetTester tester,
  _Screen screen, {
  String locale = 'en',
  String theme = 'light',
  double height = 1600,
}) async {
  usePhoneSize(tester, height: height);
  await tester.pumpWidget(await testScope(
    TestApp(home: screen.home, initialRoute: screen.route),
    locale: locale,
    prefs: {themeModeStorageKey: theme},
    signedIn: screen.route == null,
  ));
  await tester.pumpAndSettle();
}

/// كل نص مرسوم على الشاشة كامل (ما في سطر انقص بـ "…")
///
/// الاستثناء الوحيد: ملخّص الخبر ببطاقته (معاينة، النص الكامل بصفحة الخبر).
void _expectNothingCutOff(WidgetTester tester, String context) {
  final previews = find.descendant(of: find.byType(NewsCard), matching: find.byType(RichText)).evaluate().toSet();
  for (final element in find.byType(RichText).evaluate()) {
    if (previews.contains(element)) continue;
    final paragraph = element.renderObject;
    if (paragraph is! RenderParagraph || !paragraph.attached || !paragraph.hasSize) continue;
    expect(
      paragraph.didExceedMaxLines,
      isFalse,
      reason: '$context: "${paragraph.text.toPlainText()}" is cut off',
    );
  }
}

/// الخطوط الحقيقية (Inter وIBM Plex Sans Arabic...) بدل خط الاختبار المربّع،
/// حتى فحص "ولا نص مقصوص" يقيس نفس العرض يلي على الجهاز
Future<void> _loadAppFonts() async {
  const families = {
    'Inter': ['inter/Inter-Regular.ttf', 'inter/Inter-Medium.ttf', 'inter/Inter-SemiBold.ttf', 'inter/Inter-Bold.ttf'],
    'JetBrainsMono': [
      'jetbrains_mono/JetBrainsMono-Regular.ttf',
      'jetbrains_mono/JetBrainsMono-Medium.ttf',
      'jetbrains_mono/JetBrainsMono-SemiBold.ttf',
    ],
    'InstrumentSerif': ['instrument_serif/InstrumentSerif-Regular.ttf', 'instrument_serif/InstrumentSerif-Italic.ttf'],
    'IBMPlexSansArabic': [
      'ibm_plex_sans_arabic/IBMPlexSansArabic-Regular.ttf',
      'ibm_plex_sans_arabic/IBMPlexSansArabic-Medium.ttf',
      'ibm_plex_sans_arabic/IBMPlexSansArabic-SemiBold.ttf',
    ],
    'NotoNaskhArabic': ['noto_naskh_arabic/NotoNaskhArabic.ttf'],
  };
  for (final entry in families.entries) {
    final loader = FontLoader(entry.key);
    for (final file in entry.value) {
      loader.addFont(rootBundle.load('assets/fonts/$file'));
    }
    await loader.load();
  }
}

/// كل عقدة بتنقرأ "زر" (ومفعّلة) لازم يكون إلها إجراء ضغط، وإلا TalkBack /
/// Switch Access ما بيقدروا يفعّلوها
void _expectButtonsActivatable(WidgetTester tester, String context) {
  final root = tester.binding.renderViews.first.owner!.semanticsOwner!.rootSemanticsNode!;
  final dead = <String>[];
  void visit(SemanticsNode node) {
    final data = node.getSemanticsData();
    final flags = data.flagsCollection;
    if (flags.isButton && flags.isEnabled != Tristate.isFalse && !data.hasAction(SemanticsAction.tap)) {
      dead.add('"${data.label}"');
    }
    node.visitChildren((child) {
      visit(child);
      return true;
    });
  }

  visit(root);
  expect(dead, isEmpty, reason: '$context: buttons without a tap action: ${dead.join(', ')}');
}

void main() {
  setUpAll(_loadAppFonts);

  for (final screen in _screens) {
    for (final locale in ['en', 'ar']) {
      for (final theme in ['light', 'dark']) {
        testWidgets('${screen.name} ($locale, $theme, text 2.0): fits, labelled, 48 dp, AA contrast',
            (tester) async {
          final semantics = tester.ensureSemantics();
          useLargeText(tester);
          await _pump(tester, screen, locale: locale, theme: theme);

          expect(tester.takeException(), isNull, reason: 'no overflow / build error');
          _expectNothingCutOff(tester, screen.name);
          _expectButtonsActivatable(tester, screen.name);
          await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
          await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
          await expectLater(tester, meetsGuideline(textContrastGuideline));
          semantics.dispose();
        });
      }
    }

    testWidgets('${screen.name}: reduced motion shows the final state with no animation', (tester) async {
      tester.platformDispatcher.accessibilityFeaturesTestValue =
          const FakeAccessibilityFeatures(disableAnimations: true);
      addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
      await _pump(tester, screen);

      expect(find.byType(Animate), findsNothing, reason: 'flutter_animate effects must be skipped');
      for (final hero in tester.widgetList<HeroMode>(find.byType(HeroMode))) {
        expect(hero.enabled, isFalse, reason: 'Hero flights are off');
      }
      expect(tester.takeException(), isNull);
    });
  }

  group('screen-reader names', () {
    testWidgets('the price chart has a text summary: last price, change with its direction word, high and low',
        (tester) async {
      final semantics = tester.ensureSemantics();
      await _pump(tester, const _Screen('Market', home: MarketScreen(symbol: 'EUR/USD')));
      final label = tester.getSemantics(find.byType(PriceChart)).label;
      expect(label, contains('EUR/USD'));
      expect(label, matches(RegExp(r'(Up|Down|Unchanged|Flat)')));
      expect(label, contains('High'));
      expect(label, contains('low'));
      expect(label, isNot(contains('Touch and hold')), reason: 'the readout is not reachable by a screen reader');
      semantics.dispose();
    });

    testWidgets('form fields are named by their visible label', (tester) async {
      final semantics = tester.ensureSemantics();
      await _pump(tester, const _Screen('Log in', route: AppRoutes.login));
      final labels = [
        for (final e in find.byType(EditableText).evaluate()) tester.getSemantics(find.byWidget(e.widget)).label,
      ];
      expect(labels, containsAll(['Email', 'Password']));
      semantics.dispose();
    });

    testWidgets('the hidden verification-code field is still reachable by a screen reader', (tester) async {
      final semantics = tester.ensureSemantics();
      await _pump(tester, const _Screen('Verify email', home: OtpVerificationScreen(email: 'trader@example.com')));
      expect(find.bySemanticsLabel(RegExp('Verification code')), findsOneWidget);
      semantics.dispose();
    });
  });
}
