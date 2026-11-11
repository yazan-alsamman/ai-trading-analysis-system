// T1: تسميات شريط Community (News · Posts · Experts) دايمًا سطر واحد - ما
// بتلتف ولا بتنقص - بالإنجليزي والعربي، فاتح وغامق، على خط 2.0، والجزء ≥ 48 dp.

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/features/community/views/community_screen.dart';

import '../../helpers/test_app.dart';

/// النص مرسوم كامل على سطر واحد وضمن زر الجزء تبعو
void expectOneLine(WidgetTester tester, Finder label) {
  expect(label, findsOneWidget);
  final paragraph = tester.renderObject<RenderParagraph>(label);
  expect(paragraph.didExceedMaxLines, isFalse);
  final length = paragraph.text.toPlainText().length;
  final lines = {
    for (final box in paragraph.getBoxesForSelection(TextSelection(baseOffset: 0, extentOffset: length)))
      box.top.round(),
  };
  expect(lines, hasLength(1), reason: 'wrapped onto ${lines.length} lines');

  // مكان النص الفعلي (بعد التصغير) جوّا الجزء
  final segment = find.ancestor(of: label, matching: find.byType(TextButton)).first;
  final bounds = tester.getRect(segment);
  final topLeft = paragraph.localToGlobal(Offset.zero);
  final bottomRight = paragraph.localToGlobal(paragraph.size.bottomRight(Offset.zero));
  expect(bounds.inflate(0.5).contains(topLeft), isTrue);
  expect(bounds.inflate(0.5).contains(bottomRight), isTrue);
  expect(bounds.height, greaterThanOrEqualTo(48));
}

void main() {
  for (final locale in ['en', 'ar']) {
    for (final theme in ['light', 'dark']) {
      testWidgets('Posts, News and Experts stay on one line at text scale 2.0 ($locale, $theme)', (tester) async {
        useLargeText(tester);
        usePhoneSize(tester);
        await tester.pumpWidget(await testScope(
          const TestApp(home: CommunityScreen()),
          locale: locale,
          prefs: {themeModeStorageKey: theme},
        ));
        await settleMocks(tester);

        final en = locale == 'en';
        if (!en) expect(Directionality.of(tester.element(find.byType(CommunityScreen))), TextDirection.rtl);
        for (final label in en ? ['Posts', 'News', 'Experts'] : ['المنشورات', 'الأخبار', 'الخبراء']) {
          final text = find.descendant(of: find.byType(SegmentedButton<CommunitySection>), matching: find.text(label));
          expectOneLine(tester, text);
          // الاسم نفسو، مش مقصوص ولا متبدّل
          final widget = tester.widget<Text>(text);
          expect(widget.data, label);
          expect(widget.overflow, isNot(TextOverflow.ellipsis));
        }

        // بعد ما تختار Posts بيضل سطر واحد (المحدّد إطارو أعرض)
        await tester.tap(find.text(en ? 'Posts' : 'المنشورات'));
        await settleMocks(tester);
        expectOneLine(
          tester,
          find.descendant(
            of: find.byType(SegmentedButton<CommunitySection>),
            matching: find.text(en ? 'Posts' : 'المنشورات'),
          ),
        );
        expect(tester.takeException(), isNull);
      });
    }
  }

  testWidgets('Posts stays on one line on a narrow phone (320 dp) at text scale 2.0', (tester) async {
    useLargeText(tester);
    tester.view.physicalSize = const Size(320, 700);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(await testScope(const TestApp(home: CommunityScreen()), locale: 'ar'));
    await settleMocks(tester);
    expectOneLine(
      tester,
      find.descendant(of: find.byType(SegmentedButton<CommunitySection>), matching: find.text('المنشورات')),
    );
    expect(tester.takeException(), isNull);
  });
}
