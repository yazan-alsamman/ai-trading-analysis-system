import 'package:flutter/material.dart';

import '../../../l10n/app_localizations.dart';

/// تقييم النموذج لنبرة الخبر - نفس `SentimentLabel` بالـ backend.
/// ناتج نموذج، فلونه بنفسجي دايمًا (مش أخضر/أحمر: هدول للاتجاه بس).
enum Sentiment {
  positive,
  neutral,
  negative;

  static Sentiment? fromApi(String? value) => switch (value) {
        'positive' => positive,
        'neutral' => neutral,
        'negative' => negative,
        _ => null,
      };

  String label(AppLocalizations l10n) => switch (this) {
        positive => l10n.sentimentPositive,
        neutral => l10n.sentimentNeutral,
        negative => l10n.sentimentNegative,
      };

  IconData get icon => switch (this) {
        positive => Icons.sentiment_satisfied_alt_outlined,
        neutral => Icons.sentiment_neutral_outlined,
        negative => Icons.sentiment_dissatisfied_outlined,
      };
}

/// خبر واحد (immutable) - حقول `ArticleRead` بالـ backend
@immutable
final class NewsArticle {
  const NewsArticle({
    required this.id,
    required this.source,
    required this.title,
    required this.summary,
    required this.body,
    required this.publishedAt,
    required this.symbols,
    required this.commentsCount,
    this.sentiment,
  });

  final String id;

  /// اسم المصدر للعرض (`source.name`)
  final String source;
  final String title;
  final String summary;

  /// النص الكامل (فقرات مفصولة بسطر فاضي)
  final String body;
  final DateTime publishedAt;

  /// الأدوات المرتبطة (`instruments[].symbol`) - من أدوات المنتج بس
  final List<String> symbols;
  final int commentsCount;

  /// null = لسّا ما انحلّل
  final Sentiment? sentiment;

  NewsArticle withCommentsCount(int count) => NewsArticle(
        id: id,
        source: source,
        title: title,
        summary: summary,
        body: body,
        publishedAt: publishedAt,
        symbols: symbols,
        commentsCount: count,
        sentiment: sentiment,
      );
}

/// مزاج السوق خلال 24 ساعة - `SentimentAggregate.overall` بالـ backend
@immutable
final class MarketMood {
  const MarketMood({
    required this.positive,
    required this.neutral,
    required this.negative,
    required this.meanScore,
  });

  final int positive;
  final int neutral;
  final int negative;

  /// -1 (سلبي جدًا) .. 1 (إيجابي جدًا) - null لما ما في أخبار مقيّمة
  final double? meanScore;

  int get scored => positive + neutral + negative;

  /// الميل العام: أبعد من ±0.15 بيعتبر ميل، غير هيك "مختلط"
  Sentiment? get leaning {
    final score = meanScore;
    if (score == null || scored == 0) return null;
    if (score > 0.15) return Sentiment.positive;
    if (score < -0.15) return Sentiment.negative;
    return Sentiment.neutral;
  }
}

/// كل يلي بيحتاجه قسم News
@immutable
final class NewsFeed {
  const NewsFeed({required this.articles, required this.mood});

  final List<NewsArticle> articles;
  final MarketMood mood;
}
