// اختبارات Community → News (Stage C): الـ mappers، مزاج السوق، بطاقات الأخبار
// بنبرتها، صفحة الخبر، sheet التعليقات (إضافة / حذف + Undo والعدد بيتحدّث)،
// العربي والخط الكبير.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/core/data/json.dart';
import 'package:trading_app/features/comments/models/comment.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/features/community/views/community_screen.dart';
import 'package:trading_app/features/news/data/news_repository.dart';
import 'package:trading_app/features/news/models/news_models.dart';
import 'package:trading_app/features/news/views/news_detail_screen.dart';
import 'package:trading_app/features/news/widgets/news_card.dart';
import 'package:trading_app/features/news/widgets/news_section.dart';

import '../../helpers/test_app.dart';

Future<void> pumpNews(WidgetTester tester, {String locale = 'en', String theme = 'light', double height = 1400}) async {
  usePhoneSize(tester, height: height);
  await tester.pumpWidget(await testScope(
    const TestApp(home: CommunityScreen()),
    locale: locale,
    prefs: {themeModeStorageKey: theme},
  ));
  await tester.pumpAndSettle();
}

Future<void> openFirstArticle(WidgetTester tester) async {
  // بالخط الكبير أول بطاقة ممكن تكون لسّا ما انبنت (تحت الشاشة)
  for (var i = 0; i < 10 && find.byType(NewsCard).evaluate().isEmpty; i++) {
    await tester.drag(find.byType(Scrollable).first, const Offset(0, -200));
    await tester.pumpAndSettle();
  }
  await tester.ensureVisible(find.byType(NewsCard).first);
  await tester.pumpAndSettle();
  await tester.tap(find.byType(NewsCard).first);
  await tester.pumpAndSettle();
}

void main() {
  group('mappers', () {
    test('article: product instruments only, sentiment label, safe defaults', () {
      final article = newsArticleFromJson(const Json({
        'id': 'a',
        'source': {'key': 'fx', 'name': 'ForexLive'},
        'title': ' Title ',
        'summary': 'Short',
        'published_at': '2026-10-21T12:00:00Z',
        'sentiment': {'label': 'negative', 'score': -0.4},
        'instruments': [
          {'symbol': 'eur/usd'},
          {'symbol': 'BTC/USDT'},
        ],
      }))!;
      expect(article.title, 'Title');
      expect(article.symbols, ['EUR/USD']);
      expect(article.sentiment, Sentiment.negative);
      expect(article.body, 'Short'); // بدون body: الملخص
      expect(article.commentsCount, 0);
      expect(newsArticleFromJson(const Json({'id': 'a', 'title': '', 'published_at': '2026-10-21T12:00:00Z'})), isNull);
    });

    test('mood: leaning from the mean score, invalid payloads rejected', () {
      MarketMood? mood(Object? mean, {int pos = 2, int neu = 1, int neg = 1}) => marketMoodFromJson(Json({
            'overall': {'positive': pos, 'neutral': neu, 'negative': neg, 'mean_score': mean},
          }));
      expect(mood(0.4)!.leaning, Sentiment.positive);
      expect(mood(-0.3)!.leaning, Sentiment.negative);
      expect(mood(0.05)!.leaning, Sentiment.neutral);
      expect(mood(null)!.leaning, isNull);
      expect(mood(0.1, pos: -1), isNull);
      expect(marketMoodFromJson(const Json({})), isNull);
    });

    test('comment: deleted or hidden comments are dropped', () {
      expect(commentFromJson(const Json({'id': 'c', 'body': null, 'created_at': '2026-10-21T12:00:00Z', 'author': null})), isNull);
      final c = commentFromJson(const Json({
        'id': 'c',
        'body': 'Hi',
        'created_at': '2026-10-21T12:00:00Z',
        'author': {'name': 'Sara'},
        'can_edit': true,
      }))!;
      expect(c.isOwn, isTrue);
    });
  });

  for (final theme in ['light', 'dark']) {
    testWidgets('mood line and four stories with tone, instruments and counts ($theme)', (tester) async {
      await pumpNews(tester, theme: theme);
      expect(find.byType(MoodLine), findsOneWidget);
      expect(find.textContaining('Mixed', findRichText: true), findsOneWidget);
      expect(find.textContaining('2 positive, 1 neutral, 1 negative', findRichText: true), findsOneWidget);
      expect(find.byType(NewsCard), findsNWidgets(4));
      expect(find.byType(SentimentTag), findsNWidgets(4));
      expect(find.text('ForexLive · 2h ago'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('a story opens as a native article with comments at the bottom', (tester) async {
    await pumpNews(tester);
    await openFirstArticle(tester);
    expect(find.byType(NewsDetailScreen), findsOneWidget);
    expect(find.text('Federal Reserve Announces Interest Rate Decision'), findsOneWidget);
    expect(find.text('Comments · 5'), findsOneWidget);
    expect(find.text('The tone tag is a model’s reading of the text, not a price forecast.'), findsOneWidget);
  });

  testWidgets('comments sheet: post, delete with Undo, counts follow everywhere', (tester) async {
    await pumpNews(tester);
    await openFirstArticle(tester);
    await tester.tap(find.text('Comments · 5'));
    await tester.pumpAndSettle();
    expect(find.text('Comments · 5'), findsNWidgets(2)); // عنوان الـ sheet + الزر وراه

    await tester.enterText(find.widgetWithText(TextField, 'Add a comment'), 'Watching the payrolls first.');
    await tester.pump();
    await tester.tap(find.byTooltip('Post comment'));
    await tester.pumpAndSettle();
    expect(find.text('Watching the payrolls first.'), findsOneWidget);
    expect(find.text('You'), findsOneWidget);
    expect(find.text('Comments · 6'), findsNWidgets(2));

    await tester.tap(find.byTooltip('Delete comment'));
    await tester.pumpAndSettle();
    expect(find.text('Watching the payrolls first.'), findsNothing);
    expect(find.text('Comment deleted'), findsOneWidget);
    await tester.tap(find.text('Undo'));
    await tester.pumpAndSettle();
    expect(find.text('Watching the payrolls first.'), findsOneWidget);

    // رجوع للقائمة: العدد محدّث بالبطاقة
    Navigator.of(tester.element(find.text('Watching the payrolls first.'))).pop();
    await tester.pumpAndSettle();
    await tester.tap(find.byType(BackButton));
    await tester.pumpAndSettle();
    final card = tester.widget<NewsCard>(find.byType(NewsCard).first);
    expect(card.article.commentsCount, 6);
  });

  testWidgets('send is disabled while the comment is empty', (tester) async {
    await pumpNews(tester);
    await openFirstArticle(tester);
    await tester.tap(find.text('Comments · 5'));
    await tester.pumpAndSettle();
    final send = tester.widget<IconButton>(find.widgetWithIcon(IconButton, Icons.send_rounded));
    expect(send.onPressed, isNull);
  });

  testWidgets('Arabic: translated stories, RTL, no overflow', (tester) async {
    await pumpNews(tester, locale: 'ar', theme: 'dark');
    expect(find.textContaining('متباين', findRichText: true), findsOneWidget);
    expect(find.text('إيجابي'), findsWidgets);
    expect(Directionality.of(tester.element(find.byType(NewsSection))), TextDirection.rtl);
    await openFirstArticle(tester);
    expect(find.text('التعليقات · 5'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  for (final locale in ['en', 'ar']) {
    testWidgets('largest font ($locale): list, article and comments without overflow', (tester) async {
      useLargeText(tester);
      await pumpNews(tester, locale: locale, height: 812);
      await openFirstArticle(tester);
      await tester.drag(find.byType(ListView).first, const Offset(0, -4000));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      await tester.tap(find.byIcon(Icons.mode_comment_outlined).last);
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      Navigator.of(tester.element(find.byIcon(Icons.send_rounded))).pop();
      await tester.pumpAndSettle();
      await tester.tap(find.byType(BackButton));
      await tester.pumpAndSettle();
      for (var i = 0; i < 6; i++) {
        await tester.drag(find.byType(ListView).first, const Offset(0, -900));
        await tester.pumpAndSettle();
      }
      expect(tester.takeException(), isNull);
    });
  }
}
