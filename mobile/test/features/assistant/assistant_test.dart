// اختبارات تبويب Assistant (Stage C): الاقتراحات، بطاقة الجواب بنوعها، Stop،
// New chat + Undo، شريحة السياق، إرفاق صورة شارت (B09)، بدون اتصال، التصنيف،
// العربي والخط الكبير.

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/storage/preferences_provider.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/features/assistant/data/assistant_repository.dart';
import 'package:trading_app/features/assistant/data/chart_analysis_repository.dart';
import 'package:trading_app/features/assistant/data/chart_image_picker.dart';
import 'package:trading_app/features/assistant/models/assistant_models.dart';
import 'package:trading_app/features/assistant/views/assistant_screen.dart';
import 'package:trading_app/features/assistant/view_models/assistant_view_model.dart';
import 'package:trading_app/features/assistant/widgets/chat_messages.dart';

import 'package:trading_app/l10n/app_localizations.dart';

import '../../helpers/test_app.dart';

const _latency = Duration(milliseconds: 500);

/// PNG 1×1 حقيقي
final _png = base64Decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=');

/// بدّل اختيار الصورة: بيرجّع النتيجة يلي منحددها بدل ما يفتح الكاميرا
class _FakePicker extends ChartImagePicker {
  _FakePicker(this.result);

  final ChartPick result;

  @override
  Future<ChartPick> pick(ChartImageSource source) async => result;
}

final class _FailingAssistant implements AssistantRepository {
  @override
  Future<AssistantAnswer> ask(String question, {ReplyKind? kind, required AssistantContext context, required String languageCode}) =>
      Future.error(StateError('down'));
}

Future<ProviderContainer> pumpAssistant(
  WidgetTester tester, {
  String locale = 'en',
  String theme = 'light',
  ChartPick? pick,
  List<Override> overrides = const [],
}) async {
  usePhoneSize(tester);
  await tester.pumpWidget(await testScope(
    const TestApp(home: AssistantScreen()),
    locale: locale,
    prefs: {themeModeStorageKey: theme},
    overrides: [
      assistantRepositoryProvider.overrideWithValue(RuleBasedAssistantRepository(latency: _latency)),
      chartImagePickerProvider.overrideWithValue(_FakePicker(pick ?? ChartPicked('/tmp/chart.png', _png))),
      chartAnalysisRepositoryProvider.overrideWith(
        (ref) => SimulatedChartAnalysisRepository(ref.watch(sharedPreferencesProvider),
            userId: 'test-user', clock: () => kTestNow, latency: _latency),
      ),
      ...overrides,
    ],
  ));
  await tester.pumpAndSettle();
  return ProviderScope.containerOf(tester.element(find.byType(AssistantScreen)));
}

/// الاقتراحات تحت الزر الرئيسي: سكرول لحدها وبعدين ضغط
Future<void> tapSuggestion(WidgetTester tester, Finder finder) async {
  await scrollTo(tester, finder);
  await tester.tap(finder);
}

/// الجواب: النقاط بتلف (الحلقة الوحيدة) فما منستعمل pumpAndSettle وهي ظاهرة
Future<void> waitForReply(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(_latency);
  await tester.pump(const Duration(milliseconds: 100));
  await tester.pumpAndSettle();
}

void main() {
  test('questions are classified by keyword (EN and AR)', () {
    expect(RuleBasedAssistantRepository.classify('Explain this signal'), ReplyKind.explain);
    expect(RuleBasedAssistantRepository.classify('what would make it wrong?'), ReplyKind.invalidate);
    expect(RuleBasedAssistantRepository.classify('position size for my capital'), ReplyKind.risk);
    expect(RuleBasedAssistantRepository.classify('اشرح التحليل'), ReplyKind.explain);
    expect(RuleBasedAssistantRepository.classify('كم المخاطرة؟'), ReplyKind.risk);
    expect(RuleBasedAssistantRepository.classify('will gold go up tomorrow'), ReplyKind.unknown);
  });

  for (final theme in ['light', 'dark']) {
    testWidgets('empty chat: context chip and three suggestions ($theme)', (tester) async {
      await pumpAssistant(tester, theme: theme);
      expect(find.text('Ask about EUR/USD'), findsOneWidget);
      // الاقتراحات تحت الزر الرئيسي (ثانوية)
      await scrollTo(tester, find.text('Size the risk for my capital'));
      expect(find.text('Explain the current analysis'), findsOneWidget);
      expect(find.text('What would invalidate it?'), findsOneWidget);
      expect(find.text('Size the risk for my capital'), findsOneWidget);
      expect(find.byTooltip('New chat'), findsNothing);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('a suggestion sends, shows the typing dots, then a labelled reply card', (tester) async {
    await pumpAssistant(tester);
    await tapSuggestion(tester, find.text('Explain the current analysis'));
    await tester.pump();
    expect(find.byType(UserBubble), findsOneWidget);
    expect(find.byType(TypingIndicator), findsOneWidget);
    expect(find.byTooltip('Stop'), findsOneWidget);
    await waitForReply(tester);
    expect(find.byType(TypingIndicator), findsNothing);
    expect(find.byType(ReplyCard), findsOneWidget);
    expect(find.text('Analysis summary · EUR/USD'), findsOneWidget);
    expect(find.text('Simulated'), findsOneWidget);
    // الجواب من بيانات التطبيق: إما رأي النموذج أو "ما في إعداد"
    expect(
      find.textContaining(RegExp(r'EUR/USD (on|has no)|no current setup on EUR/USD')),
      findsOneWidget,
    );
  });

  testWidgets('Stop drops the pending reply', (tester) async {
    await pumpAssistant(tester);
    await tester.enterText(find.byType(TextField), 'Explain the signal');
    await tester.pump();
    await tester.tap(find.byTooltip('Send'));
    await tester.pump();
    await tester.tap(find.byTooltip('Stop'));
    await tester.pump(_latency * 2);
    await tester.pumpAndSettle();
    expect(find.byType(ReplyCard), findsNothing);
    expect(find.byType(UserBubble), findsOneWidget);
  });

  testWidgets('New chat clears with Undo', (tester) async {
    await pumpAssistant(tester);
    await tapSuggestion(tester, find.text('What would invalidate it?'));
    await waitForReply(tester);
    await tester.tap(find.byTooltip('New chat'));
    await tester.pumpAndSettle();
    expect(find.byType(ReplyCard), findsNothing);
    expect(find.text('Conversation cleared'), findsOneWidget);
    await tester.tap(find.text('Undo'));
    await tester.pumpAndSettle();
    expect(find.byType(ReplyCard), findsOneWidget);
  });

  testWidgets('risk without capital explains how to set it', (tester) async {
    await pumpAssistant(tester);
    await tapSuggestion(tester, find.text('Size the risk for my capital'));
    await waitForReply(tester);
    expect(find.text('Risk sizing · EUR/USD'), findsOneWidget);
    expect(
      find.textContaining(RegExp(r'Set your capital|no active setup on EUR/USD')),
      findsOneWidget,
    );
  });

  testWidgets('context chip: choosing No instrument changes the answers', (tester) async {
    await pumpAssistant(tester);
    await tester.tap(find.bySemanticsLabel('Context: EUR/USD'));
    await tester.pumpAndSettle();
    expect(find.text('What the assistant can see'), findsOneWidget);
    await tester.tap(find.text('No instrument'));
    await tester.pumpAndSettle();
    expect(find.text('Ask about gold and FX'), findsOneWidget);
    await tapSuggestion(tester, find.text('Explain the current analysis'));
    await waitForReply(tester);
    expect(find.textContaining('Choose an instrument in Context'), findsOneWidget);
  });

  testWidgets('attach a chart image → preview → Analyze → image bubble + chart analysis card', (tester) async {
    await pumpAssistant(tester);
    await tester.tap(find.byTooltip('Attach a chart image'));
    await tester.pumpAndSettle();
    expect(find.text('Read a chart image'), findsOneWidget);
    expect(find.text('0 of 5 analyses today'), findsWidgets);
    await tester.tap(find.text('Choose from gallery'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Analyze'));
    await tester.pump();
    await waitForReply(tester);
    final messages = ProviderScope.containerOf(tester.element(find.byType(AssistantScreen)))
        .read(assistantViewModelProvider)
        .messages;
    expect(messages.first, isA<UserImage>());
    expect(find.textContaining('Chart analysis'), findsOneWidget);
    expect(find.text('Trend'), findsOneWidget);
    expect(find.text('Pattern'), findsOneWidget);
    // الصورة فوق الجواب (القائمة معكوسة): منسكرول لفوق لنشوفها
    await tester.drag(find.byType(ListView).first, const Offset(0, 600));
    await tester.pumpAndSettle();
    expect(find.byType(UserImageBubble), findsOneWidget);
  });

  testWidgets('a rejected image explains why in a snackbar', (tester) async {
    await pumpAssistant(tester, pick: const ChartPickRejected(ChartImageProblem.size));
    await tester.tap(find.byTooltip('Attach a chart image'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Take a photo'));
    await tester.pumpAndSettle();
    expect(find.text('The image is over 10 MB.'), findsOneWidget);
    expect(find.byType(UserImageBubble), findsNothing);
  });

  testWidgets('a failed answer keeps the question and offers Try again', (tester) async {
    await pumpAssistant(tester, overrides: [assistantRepositoryProvider.overrideWithValue(_FailingAssistant())]);
    await tapSuggestion(tester, find.text('Explain the current analysis'));
    await tester.pump();
    await tester.pumpAndSettle();
    expect(find.text('The assistant could not answer.'), findsOneWidget);
    expect(find.byType(UserBubble), findsOneWidget);
    expect(find.text('Try again'), findsOneWidget);
  });

  testWidgets('offline: composer and suggestions are disabled with a note', (tester) async {
    final container = await pumpAssistant(tester);
    container.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
    await tester.pumpAndSettle();
    expect(find.text('You are offline. The assistant needs a connection.'), findsOneWidget);
    expect(tester.widget<TextField>(find.byType(TextField)).enabled, isFalse);
    final suggestion = tester.widget<OutlinedButton>(find.widgetWithText(OutlinedButton, 'Explain the current analysis'));
    expect(suggestion.onPressed, isNull);
  });

  testWidgets('Arabic: RTL, translated suggestions and reply', (tester) async {
    await pumpAssistant(tester, locale: 'ar', theme: 'dark');
    expect(find.text('اسأل عن EUR/USD'), findsOneWidget);
    expect(Directionality.of(tester.element(find.byType(AssistantScreen))), TextDirection.rtl);
    await tapSuggestion(tester, find.text('اشرح التحليل الحالي'));
    await waitForReply(tester);
    expect(find.text('ملخّص التحليل · EUR/USD'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  for (final locale in ['en', 'ar']) {
    testWidgets('largest font ($locale): empty state and a reply without overflow', (tester) async {
      useLargeText(tester);
      await pumpAssistant(tester, locale: locale);
      await tester.drag(find.byType(ListView).first, const Offset(0, -2000));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      await tester.drag(find.byType(ListView).first, const Offset(0, 2000));
      await tester.pumpAndSettle();
      final suggestion = find.text(locale == 'en' ? 'What would invalidate it?' : 'ما الذي قد يُلغيه؟');
      await scrollTo(tester, suggestion);
      await tester.tap(suggestion);
      await waitForReply(tester);
      await tester.drag(find.byType(ListView).first, const Offset(0, 2000));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });
  }

  for (final (locale, theme) in [('en', 'light'), ('ar', 'dark')]) {
    testWidgets('robot head in the header, the empty state and on replies ($locale, $theme)', (tester) async {
      await pumpAssistant(tester, locale: locale, theme: theme);
      // الراس + حالة الفراغ
      expect(find.byIcon(Icons.smart_toy_outlined), findsNWidgets(2));
      expect(find.byIcon(Icons.auto_awesome_rounded), findsNothing);
      await tapSuggestion(tester, find.text(AppLocalizations(Locale(locale)).asstSuggestExplain));
      await tester.pump();
      expect(find.descendant(of: find.byType(TypingIndicator), matching: find.byType(AssistantAvatar)), findsOneWidget);
      await waitForReply(tester);
      expect(find.descendant(of: find.byType(ReplyCard), matching: find.byType(AssistantAvatar)), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }
}
