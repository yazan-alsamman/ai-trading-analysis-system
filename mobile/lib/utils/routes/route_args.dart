import 'package:flutter/foundation.dart';

import '../../models/news_item_model.dart';

// ═══════════════════════════════════════════════════════════
// Route Arguments - كائنات بيانات المسارات
// ═══════════════════════════════════════════════════════════
//
// كل شاشة بتحتاج أكثر من قيمة وحدة (زي [NewsDetailScreen] أو
// [DiscussionScreen]) إلها كلاس Arguments هون، بيتم تمريره عبر
// RouteSettings.arguments وقراءته من AppRoutes.onGenerateRoute.
//
// الشاشات يلي بتحتاج قيمة وحدة بس (مثلاً TradeScreen <- MarketItemModel،
// أو OtpVerificationScreen <- String email) بتمرر القيمة مباشرة بدون
// حاجة لكلاس Arguments خاص فيها.

/// بيانات فتح [NewsDetailScreen] عبر [AppRoutes.newsDetail]
@immutable
class NewsDetailScreenArgs {
  const NewsDetailScreenArgs({
    required this.news,
    this.onAnalyzeWithAi,
    this.onCommentsCountChanged,
  });

  /// بيانات الخبر الكاملة
  final NewsItemModel news;

  /// يُستدعى عند الضغط على زر "AI Analyze"
  final VoidCallback? onAnalyzeWithAi;

  /// يُستدعى كل مرة يتغيّر فيها عدد التعليقات (إضافة/حذف)، حتى الشاشة
  /// يلي فتحت منها [NewsDetailScreen] تحدّث العدّاد المعروض عندها
  final ValueChanged<int>? onCommentsCountChanged;
}

/// بيانات فتح [DiscussionScreen] عبر [AppRoutes.discussion]
@immutable
class DiscussionScreenArgs {
  const DiscussionScreenArgs({
    required this.newsId,
    required this.newsTitle,
    required this.commentsCount,
    this.onCommentsCountChanged,
  });

  /// معرّف الخبر الثابت ([NewsItemModel.id])
  final String newsId;

  /// عنوان الخبر - يُعرض بأعلى شاشة النقاش
  final String newsTitle;

  /// عدد التعليقات الحالي وقت فتح الشاشة
  final int commentsCount;

  /// يُستدعى كل مرة يتغيّر فيها عدد التعليقات (إضافة/حذف)
  final ValueChanged<int>? onCommentsCountChanged;
}
