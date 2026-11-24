// اختبارات AppIllustration (مبني بـ Flutter، بدون ملفات حركة): زخرفة مخفية عن
// القارئ الصوتي، دخول مرة وحدة وبعدين ثابت، وبدون حركة مع "تقليل الحركة".

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/core/widgets/app_illustration.dart';
import 'package:trading_app/core/widgets/feedback_states.dart';

import '../helpers/test_app.dart';

void main() {
  testWidgets('an illustrated empty state: the drawing is decoration, the copy is read', (tester) async {
    final semantics = tester.ensureSemantics();
    await tester.pumpWidget(await testScope(const TestApp(
      home: Scaffold(
        body: EmptyState(illustrated: true, icon: Icons.notifications_off_outlined, title: 'Nothing here'),
      ),
    )));
    await tester.pumpAndSettle();
    expect(find.byType(AppIllustration), findsOneWidget);
    expect(find.bySemanticsLabel('Nothing here'), findsOneWidget);
    expect(find.descendant(of: find.byType(AppIllustration), matching: find.byType(ExcludeSemantics)), findsWidgets);
    semantics.dispose();
  });

  testWidgets('plain empty states keep the small icon (no illustration)', (tester) async {
    await tester.pumpWidget(await testScope(const TestApp(
      home: Scaffold(body: EmptyState(icon: Icons.forum_outlined, title: 'No comments')),
    )));
    expect(find.byType(AppIllustration), findsNothing);
    expect(find.byIcon(Icons.forum_outlined), findsOneWidget);
  });

  testWidgets('the entrance plays once (≤ 400 ms) and then stays still', (tester) async {
    await tester.pumpWidget(await testScope(const TestApp(
      home: Scaffold(body: Center(child: SuccessIllustration())),
    )));
    // كل pump = 50ms: الحركة بتخلص بـ 400ms (+ فريم)
    final pumps = await tester.pumpAndSettle(const Duration(milliseconds: 50));
    expect(pumps * 50, lessThanOrEqualTo(450));
    expect(tester.hasRunningAnimations, isFalse);
    expect(find.byIcon(Icons.check_rounded), findsNothing, reason: 'the check is drawn, not an icon');
  });

  testWidgets('reduced motion: final state from the first frame', (tester) async {
    await tester.pumpWidget(await testScope(const TestApp(
      home: MediaQuery(
        data: MediaQueryData(disableAnimations: true),
        child: Scaffold(body: Center(child: SuccessIllustration())),
      ),
    )));
    expect(find.byType(TweenAnimationBuilder<double>), findsNothing);
    expect(tester.hasRunningAnimations, isFalse);
  });

  for (final theme in ['light', 'dark']) {
    testWidgets('paints in both themes and in RTL without errors ($theme)', (tester) async {
      await tester.pumpWidget(await testScope(
        const TestApp(home: Scaffold(body: Center(child: AppIllustration(icon: Icons.inbox_outlined)))),
        locale: 'ar',
        prefs: {themeModeStorageKey: theme},
      ));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });
  }
}
