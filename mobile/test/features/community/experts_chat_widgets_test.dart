// T2: واجهة الخبراء - حالات بطاقة الخبير، sheet الاشتراك (محاكى، بدون بيانات
// بطاقة)، إلغاء الاشتراك مع Undo، وشاشة المحادثة (مقفولة بدون اشتراك، إرسال
// وحالاته، رد محاكى، بدون اتصال، إعادة محاولة، RTL، خط 2.0، فاتح/داكن، 48 dp).

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/app/router/app_navigator.dart';
import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/features/community/data/expert_chat_repository.dart';
import 'package:trading_app/features/community/data/expert_subscriptions_repository.dart';
import 'package:trading_app/features/community/models/chat_message.dart';
import 'package:trading_app/features/community/models/expert_plan.dart';
import 'package:trading_app/features/community/models/expert_subscription.dart';
import 'package:trading_app/features/community/views/community_screen.dart';
import 'package:trading_app/features/community/views/expert_chat_screen.dart';
import 'package:trading_app/features/community/widgets/chat_bubble.dart';
import 'package:trading_app/features/community/widgets/expert_card.dart';
import 'package:trading_app/features/community/widgets/subscribe_sheet.dart';

import '../../helpers/test_app.dart';

/// اشتراك محفوظ عند لينا (متل ما بيكون بعد إعادة تشغيل التطبيق)
Map<String, Object> subscribedToLina() => {
      LocalExpertSubscriptionsRepository.storageKey: jsonEncode([
        expertSubscriptionToJson(ExpertSubscription(
          id: 'sub-1',
          expertId: 'expert-1',
          expertName: 'Lina Haddad',
          planId: 'expert-1-plan',
          planName: 'Gold desk',
          status: SubscriptionStatus.active,
          price: 29,
          currency: 'USD',
          interval: PlanInterval.month,
          perks: const {'chat': true},
          currentPeriodEnd: DateTime.utc(2026, 11, 20),
          createdAt: DateTime.utc(2026, 10, 21),
        )),
      ]),
    };

/// محادثة بتفشل أول [failures] إرسالات
class FlakyChatRepository extends SimulatedExpertChatRepository {
  FlakyChatRepository({required super.hasChatAccess, this.failures = 1})
      : super(userId: () => 'test-user', languageCode: () => 'en', latency: const Duration(milliseconds: 100));

  int failures;

  @override
  Future<ChatMessage> send(ChatConversation conversation, {required String body, required String clientId}) async {
    if (failures > 0) {
      failures--;
      await Future<void>.delayed(const Duration(milliseconds: 100));
      throw const ChatSendException();
    }
    return super.send(conversation, body: body, clientId: clientId);
  }
}

Override flakyChat() => expertChatRepositoryProvider.overrideWith((ref) {
      final repo = FlakyChatRepository(
        hasChatAccess: (id) async =>
            (await ref.read(expertSubscriptionsRepositoryProvider).mine()).any((s) => s.expertId == id && s.allowsChat),
      );
      ref.onDispose(repo.dispose);
      return repo;
    });

Future<void> openExpertsTab(
  WidgetTester tester, {
  Map<String, Object> prefs = const {},
  String locale = 'en',
  String theme = 'light',
}) async {
  usePhoneSize(tester, height: 3000);
  await tester.pumpWidget(await testScope(
    const TestApp(home: CommunityScreen()),
    locale: locale,
    prefs: {themeModeStorageKey: theme, ...prefs},
  ));
  await settleMocks(tester);
  await tester.tap(find.text(locale == 'en' ? 'Experts' : 'الخبراء'));
  await tester.pumpAndSettle();
}

/// شاشة المحادثة مباشرة (متل route مباشر) + انتظار تحميل المحادثة المحاكاة
Future<void> openChat(
  WidgetTester tester, {
  Map<String, Object> prefs = const {},
  String locale = 'en',
  String theme = 'light',
  List<Override> overrides = const [],
  double height = 812,
}) async {
  usePhoneSize(tester, height: height);
  await tester.pumpWidget(await testScope(
    const TestApp(home: ExpertChatScreen(expertId: 'expert-1')),
    locale: locale,
    prefs: {themeModeStorageKey: theme, ...prefs},
    overrides: overrides,
  ));
  await waitFor(tester);
}

/// مهلات المحاكاة (فتح المحادثة، الإرسال، الاشتراك) بتخلص
Future<void> waitFor(WidgetTester tester, [Duration duration = const Duration(milliseconds: 1200)]) async {
  // أول إطار بيبني الشاشة الجديدة (مهلاتها بتبلّش هون)، بعدين الوقت بيمشي
  await tester.pump();
  await tester.pump(duration);
  await tester.pumpAndSettle();
}

Future<void> typeAndSend(WidgetTester tester, String text, {String send = 'Send'}) async {
  await tester.enterText(find.byType(TextField), text);
  await tester.pump();
  await tester.tap(find.byTooltip(send).hitTestable());
  await tester.pump();
}

void main() {
  group('Expert card', () {
    testWidgets('not subscribed: monthly price + Subscribe, no Chat', (tester) async {
      await openExpertsTab(tester);
      final lina = find.ancestor(of: find.text('Lina Haddad'), matching: find.byType(ExpertCard));
      expect(find.descendant(of: lina, matching: find.text('Plan: Gold desk · USD 29.00 / month')), findsOneWidget);
      expect(find.descendant(of: lina, matching: find.text('Subscribe')), findsOneWidget);
      expect(find.text('Chat'), findsNothing);
      expect(find.text('Subscribed'), findsNothing);
    });

    testWidgets('subscribed (read from storage): icon + "Subscribed", Chat and Unsubscribe', (tester) async {
      final semantics = tester.ensureSemantics();
      await openExpertsTab(tester, prefs: subscribedToLina());
      final lina = find.ancestor(of: find.text('Lina Haddad'), matching: find.byType(ExpertCard));
      expect(find.descendant(of: lina, matching: find.byIcon(Icons.check_circle_rounded)), findsOneWidget);
      expect(find.bySemanticsLabel(RegExp(r'^Subscribed to Lina Haddad\. Plan: Gold desk')), findsOneWidget);
      expect(find.descendant(of: lina, matching: find.text('Chat')), findsOneWidget);
      expect(find.descendant(of: lina, matching: find.text('Unsubscribe')), findsOneWidget);
      expect(find.descendant(of: lina, matching: find.text('Subscribe')), findsNothing);
      // باقي الخبراء مش مشتركين
      expect(find.text('Subscribe'), findsNWidgets(2));
      semantics.dispose();
    });

    testWidgets('Chat opens the conversation with its permanent disclaimer', (tester) async {
      await openExpertsTab(tester, prefs: subscribedToLina());
      await tester.tap(find.text('Chat'));
      await waitFor(tester);
      expect(find.byType(ExpertChatScreen), findsOneWidget);
      expect(find.text('Experts share opinions, not financial advice. Not a broker.'), findsOneWidget);
      expect(find.text('Start the conversation'), findsOneWidget);
    });

    testWidgets('Unsubscribe: light confirmation, then a snackbar whose Undo restores it', (tester) async {
      await openExpertsTab(tester, prefs: subscribedToLina());
      await tester.tap(find.text('Unsubscribe'));
      await tester.pumpAndSettle();
      expect(find.text('Unsubscribe from Lina Haddad?'), findsOneWidget);
      await tester.tap(find.descendant(of: find.byType(AlertDialog), matching: find.text('Unsubscribe')));
      await waitFor(tester);
      expect(find.text('Unsubscribed from Lina Haddad'), findsOneWidget);
      expect(find.text('Chat'), findsNothing);
      expect(find.text('Subscribe'), findsNWidgets(3));
      await tester.tap(find.text('Undo'));
      await waitFor(tester);
      expect(find.text('Chat'), findsOneWidget);
      expect(find.text('Subscribed'), findsOneWidget);
    });

    testWidgets('Unsubscribe → Cancel changes nothing', (tester) async {
      await openExpertsTab(tester, prefs: subscribedToLina());
      await tester.tap(find.text('Unsubscribe'));
      await tester.pumpAndSettle();
      await tester.tap(find.descendant(of: find.byType(AlertDialog), matching: find.text('Cancel')));
      await tester.pumpAndSettle();
      expect(find.text('Chat'), findsOneWidget);
    });
  });

  group('Subscribe sheet', () {
    Future<void> openSheet(WidgetTester tester) async {
      await tester.tap(find.text('Subscribe').first);
      await tester.pumpAndSettle();
    }

    testWidgets('shows the plan, what is included, the person-not-financial-advice note and "Simulated"; no card fields',
        (tester) async {
      await openExpertsTab(tester);
      await openSheet(tester);
      final sheet = find.byType(SubscribeSheet);
      expect(sheet, findsOneWidget);
      Finder inSheet(String text) => find.descendant(of: sheet, matching: find.text(text));
      expect(inSheet('Subscribe to Lina Haddad'), findsOneWidget);
      expect(inSheet('Gold desk'), findsOneWidget);
      expect(inSheet('USD 29.00 / month'), findsOneWidget);
      expect(inSheet('What’s included'), findsOneWidget);
      expect(inSheet('Private chat with Lina Haddad'), findsOneWidget);
      expect(find.descendant(of: sheet, matching: find.textContaining('not financial advice')), findsOneWidget);
      expect(inSheet('Simulated'), findsOneWidget);
      expect(inSheet('Simulated: no payment is taken and no card details are asked for.'), findsOneWidget);
      expect(find.descendant(of: sheet, matching: find.byType(TextField)), findsNothing, reason: 'no card data');
      expect(inSheet('Confirm subscription'), findsOneWidget);
      expect(inSheet('Cancel'), findsOneWidget);
    });

    testWidgets('Cancel closes the sheet and saves nothing', (tester) async {
      await openExpertsTab(tester);
      await openSheet(tester);
      await tester.tap(find.descendant(of: find.byType(SubscribeSheet), matching: find.text('Cancel')));
      await tester.pumpAndSettle();
      expect(find.byType(SubscribeSheet), findsNothing);
      expect(find.text('Chat'), findsNothing);
      final container = ProviderScope.containerOf(tester.element(find.byType(CommunityScreen)));
      expect(await container.read(expertSubscriptionsRepositoryProvider).mine(), isEmpty);
    });

    testWidgets('confirm: the card shows "Subscribed" + Chat, a snackbar confirms, and it is saved', (tester) async {
      await openExpertsTab(tester);
      await openSheet(tester);
      await tester.tap(find.text('Confirm subscription'));
      await tester.pump();
      // جارٍ الاشتراك: الزر بيحمّل
      expect(find.bySemanticsLabel(RegExp('Confirm subscription, Loading')), findsOneWidget);
      await waitFor(tester);
      expect(find.byType(SubscribeSheet), findsNothing);
      expect(find.text('Subscribed to Lina Haddad. You can chat now.'), findsOneWidget);
      expect(find.text('Subscribed'), findsOneWidget);
      expect(find.text('Chat'), findsOneWidget);
    });

    testWidgets('a double tap on Subscribe opens one sheet; a double tap on Confirm subscribes once', (tester) async {
      await openExpertsTab(tester);
      final subscribe = find.text('Subscribe').first;
      await tester.tap(subscribe);
      await tester.tap(subscribe, warnIfMissed: false);
      await tester.pumpAndSettle();
      expect(find.byType(SubscribeSheet), findsOneWidget);
      await tester.tap(find.text('Confirm subscription'));
      await tester.tap(find.text('Confirm subscription'), warnIfMissed: false);
      await waitFor(tester);
      expect(find.byType(SubscribeSheet), findsNothing);
      expect(find.text('Subscribed'), findsOneWidget);
    });

    testWidgets('offline: says why, sends nothing, keeps the sheet open', (tester) async {
      await openExpertsTab(tester);
      final container = ProviderScope.containerOf(tester.element(find.byType(CommunityScreen)));
      container.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      await openSheet(tester);
      await tester.tap(find.text('Confirm subscription'));
      await tester.pumpAndSettle();
      expect(find.text('You’re offline. Nothing was sent. Try again when you’re connected.'), findsOneWidget);
      expect(find.byType(SubscribeSheet), findsOneWidget);
      expect(await container.read(expertSubscriptionsRepositoryProvider).mine(), isEmpty);
    });

    testWidgets('reduced motion: the sheet opens with no animation', (tester) async {
      tester.platformDispatcher.accessibilityFeaturesTestValue = const FakeAccessibilityFeatures(disableAnimations: true);
      addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
      await openExpertsTab(tester);
      await tester.tap(find.text('Subscribe').first);
      await tester.pump();
      await tester.pump();
      expect(find.byType(SubscribeSheet).hitTestable(), findsOneWidget);
    });

    testWidgets('Arabic, dark, text scale 2.0: the sheet fits with 48 dp targets', (tester) async {
      useLargeText(tester);
      await openExpertsTab(tester, locale: 'ar', theme: 'dark');
      await tester.tap(find.text('اشترك').first);
      await tester.pumpAndSettle();
      expect(find.text('الاشتراك مع لينا حداد'), findsOneWidget);
      expect(find.text('محاكاة: لا يُدفع أي مبلغ ولا تُطلب بيانات بطاقة.'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
    });
  });

  group('Chat screen', () {
    testWidgets('direct route without a subscription: "Subscribe to chat", not the chat', (tester) async {
      usePhoneSize(tester);
      await tester.pumpWidget(await testScope(const TestApp(home: CommunityScreen())));
      await settleMocks(tester);
      testRouter(tester).push(AppRoutes.expertChat('expert-1'));
      await waitFor(tester);
      expect(find.text('Subscribe to chat with Lina Haddad'), findsOneWidget);
      expect(find.byType(TextField), findsNothing);
      expect(find.byTooltip('Send'), findsNothing);
      expect(find.text('Experts share opinions, not financial advice. Not a broker.'), findsOneWidget);
      // الاشتراك من هون بيفتح المحادثة
      await tester.tap(find.text('Subscribe'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Confirm subscription'));
      await waitFor(tester);
      await waitFor(tester);
      expect(find.text('Start the conversation'), findsOneWidget);
      expect(find.byType(TextField), findsOneWidget);
    });

    testWidgets('empty state hint, then send → Sending → Sent, and a reply labelled Simulated', (tester) async {
      final semantics = tester.ensureSemantics();
      await openChat(tester, prefs: subscribedToLina());
      expect(find.text('Start the conversation'), findsOneWidget);
      expect(find.textContaining('Replies here are simulated'), findsOneWidget);
      expect(find.text('Simulated'), findsOneWidget);

      await typeAndSend(tester, 'Hello there');
      expect(find.bySemanticsLabel(RegExp(r'^You, \d\d:\d\d: Hello there\. Sending$')), findsOneWidget);
      // الحقل فضي بعد الإرسال
      expect(tester.widget<TextField>(find.byType(TextField)).controller!.text, isEmpty);
      await waitFor(tester, const Duration(milliseconds: 600));
      expect(find.bySemanticsLabel(RegExp(r'^You, \d\d:\d\d: Hello there\. Sent$')), findsOneWidget);
      expect(find.byIcon(Icons.done_rounded), findsOneWidget);

      await waitFor(tester, const Duration(seconds: 2));
      expect(find.byType(ChatBubble), findsNWidgets(2));
      expect(find.bySemanticsLabel(RegExp(r'^Lina Haddad, \d\d:\d\d: Thanks.*Simulated reply$')), findsOneWidget);
      expect(find.textContaining('Simulated reply'), findsOneWidget);
      semantics.dispose();
    });

    testWidgets('offline: says why, Send is off, nothing is sent and the draft stays', (tester) async {
      await openChat(tester, prefs: subscribedToLina());
      final container = ProviderScope.containerOf(tester.element(find.byType(ExpertChatScreen)));
      container.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      await tester.pump();
      await tester.enterText(find.byType(TextField), 'My draft');
      await tester.pump();
      expect(find.text('You’re offline. Messages can’t be sent, and your draft stays here.'), findsOneWidget);
      final send = tester.widget<IconButton>(find.widgetWithIcon(IconButton, Icons.send_rounded));
      expect(send.onPressed, isNull);
      expect(find.byType(ChatBubble), findsNothing);
      expect(tester.widget<TextField>(find.byType(TextField)).controller!.text, 'My draft');
      container.read(networkStatusProvider.notifier).set(NetworkStatus.online);
      await tester.pump();
      expect(find.textContaining('You’re offline'), findsNothing);
      expect(tester.widget<IconButton>(find.widgetWithIcon(IconButton, Icons.send_rounded)).onPressed, isNotNull);
    });

    testWidgets('a failed message says "Not sent" (icon + word) and Try again sends it', (tester) async {
      await openChat(tester, prefs: subscribedToLina(), overrides: [flakyChat()]);
      await typeAndSend(tester, 'Will fail once');
      await waitFor(tester, const Duration(milliseconds: 300));
      expect(find.text('Not sent'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline_rounded), findsOneWidget);
      await tester.tap(find.text('Try again'));
      await waitFor(tester, const Duration(milliseconds: 300));
      expect(find.text('Not sent'), findsNothing);
      expect(find.text('Sent'), findsOneWidget);
      expect(find.text('Will fail once'), findsOneWidget);
      await waitFor(tester, const Duration(seconds: 2));
    });

    testWidgets('a double tap on Send sends one message', (tester) async {
      await openChat(tester, prefs: subscribedToLina());
      await tester.enterText(find.byType(TextField), 'Only once');
      await tester.pump();
      final send = find.byTooltip('Send');
      await tester.tap(send);
      await tester.tap(send, warnIfMissed: false);
      await waitFor(tester, const Duration(seconds: 3));
      expect(find.text('Only once'), findsOneWidget);
      expect(find.byType(ChatBubble), findsNWidgets(2), reason: 'one message + one reply');
    });

    testWidgets('RTL: your bubbles sit on the left, the expert on the right', (tester) async {
      await openChat(tester, prefs: subscribedToLina(), locale: 'ar');
      await typeAndSend(tester, 'مرحبا', send: 'إرسال');
      await waitFor(tester, const Duration(seconds: 3));
      final width = tester.view.physicalSize.width;
      final mine = tester.getRect(find.text('مرحبا'));
      final reply = tester.getRect(find.textContaining('شكرًا'));
      expect(mine.right, lessThan(width / 2), reason: 'mine at the end = left in RTL');
      expect(reply.right, greaterThan(width * 0.75), reason: 'expert at the start = right in RTL');
      expect(find.text('الخبراء يشاركون آراءهم، وليست نصيحة مالية. لسنا وسيطًا.'), findsOneWidget);
    });

    testWidgets('the composer limits the length and shows a counter near the limit', (tester) async {
      await openChat(tester, prefs: subscribedToLina());
      await tester.enterText(find.byType(TextField), 'a' * (kChatMessageMaxLength + 50));
      await tester.pump();
      final controller = tester.widget<TextField>(find.byType(TextField)).controller!;
      expect(controller.text.length, kChatMessageMaxLength);
      expect(find.text('1000 of 1000 characters'), findsOneWidget);
    });

    for (final locale in ['en', 'ar']) {
      for (final theme in ['light', 'dark']) {
        testWidgets('$locale, $theme, text scale 2.0: long messages wrap, nothing overflows, 48 dp targets',
            (tester) async {
          useLargeText(tester);
          await openChat(tester, prefs: subscribedToLina(), locale: locale, theme: theme);
          final long = List.filled(60, locale == 'en' ? 'gold' : 'ذهب').join(' ');
          await tester.enterText(find.byType(TextField), long);
          await tester.pump();
          await tester.tap(find.byTooltip(locale == 'en' ? 'Send' : 'إرسال').hitTestable());
          await waitFor(tester, const Duration(milliseconds: 600));
          expect(tester.takeException(), isNull);
          final bubble = tester.getRect(find.text(long));
          expect(bubble.width, lessThanOrEqualTo(tester.view.physicalSize.width * 0.82));
          // الرد (طويل كمان) بيوصل بدون overflow
          await waitFor(tester, const Duration(seconds: 2));
          expect(tester.takeException(), isNull);
          await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
          await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
        });
      }
    }

    testWidgets('unknown expert id: a clear "not listed" state', (tester) async {
      usePhoneSize(tester);
      await tester.pumpWidget(await testScope(const TestApp(home: ExpertChatScreen(expertId: 'nobody'))));
      await waitFor(tester);
      expect(find.text('This expert is no longer listed'), findsOneWidget);
      expect(find.byType(TextField), findsNothing);
    });
  });
}
