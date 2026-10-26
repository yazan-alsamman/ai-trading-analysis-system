import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../controllers/ai_chart_analyzer_controller.dart';
import '../controllers/ai_chat_controller.dart';
import '../controllers/ai_news_analyzer_controller.dart';
import '../controllers/comments_controller.dart';
import 'app_providers.dart';

// ═══════════════════════════════════════════════════════════
// Screen-scoped Providers - متحكمات محلية لكل شاشة
// ═══════════════════════════════════════════════════════════
//
// بعكس app_providers.dart (متحكمات حية طول عمر التطبيق)، المتحكمات
// هون كانت بمرحلة Provider مُغلَّفة محليًا بكل شاشة عبر
// `ChangeNotifierProvider(create: ...)` مباشرة داخل build() الشاشة،
// حتى تبلش كل مرة تُفتح فيها الشاشة بحالة نظيفة وتتخلّص من حالتها
// تلقائيًا عند الخروج منها.
//
// معادلها بـ Riverpod: كل Provider هون بيتم تجاوزه (override) فعليًا
// من داخل الشاشة (Screen) نفسها عبر [ProviderScope] محلي يلف الشاشة -
// بالضبط نفس مكان الإنشاء القديم `ChangeNotifierProvider(create: ...)`
// جوا build() الشاشة. الفائدة: نفس ضمان "instance جديدة بكل فتحة
// للشاشة، وتتخلّص تلقائيًا عند الخروج منها" (تخلّص الـ ProviderScope
// المحلي بيصير تلقائيًا لما الشاشة تُزال من شجرة الـ widgets).
//
// الـ "create" الافتراضي المكتوب هون (قبل الـ override) بيبقى بس
// fallback بسيط - عمليًا ما بينادى إلا لو نُسي الـ override بالشاشة.

/// شاشة AI Chart Analyzer - تبلش دايمًا بدون صورة سابقة
///
/// ⚠️ بنفس مبدأ [aiChatControllerProvider] تحت - [AiChartAnalyzerScreen]
/// هي يلي بتعمل الـ override الفعلي بـ [AppLocalizations] الحقيقية.
final aiChartAnalyzerControllerProvider =
    ChangeNotifierProvider<AiChartAnalyzerController>(
  (ref) => throw UnimplementedError(
    'aiChartAnalyzerControllerProvider لازم يُستخدم عبر override محلي من '
    'AiChartAnalyzerScreen (AppLocalizations) - راجع ai_chart_analyzer_screen.dart',
  ),
);

/// شاشة AI Chat - تبلش دايمًا بمحادثة جديدة (بس رسالة الترحيب)
///
/// ⚠️ بنفس مبدأ [commentsControllerProvider] تحت - [AiChatScreen] هي
/// يلي بتعمل الـ override الفعلي بـ [AppLocalizations] الحقيقية (من
/// الـ context تبعها) عبر [ProviderScope] محلي، حتى رسالة الترحيب
/// والأسئلة السريعة والردود التجريبية تطلع بلغة التطبيق الحالية.
final aiChatControllerProvider = ChangeNotifierProvider<AiChatController>(
  (ref) => throw UnimplementedError(
    'aiChatControllerProvider لازم يُستخدم عبر override محلي من '
    'AiChatScreen (AppLocalizations) - راجع ai_chat_screen.dart',
  ),
);

/// شاشة AI News Analyzer.
///
/// ⚠️ بنفس مبدأ [aiChatControllerProvider] فوق - [AiNewsAnalyzerScreen]
/// هي يلي بتعمل الـ override الفعلي (newsItems / initialNewsId /
/// AppLocalizations الحقيقية) عبر [ProviderScope] محلي، فهاد الـ
/// "create" عمليًا ما بينادى إلا لو نُسي الـ override.
final aiNewsAnalyzerControllerProvider =
    ChangeNotifierProvider<AiNewsAnalyzerController>(
  (ref) => throw UnimplementedError(
    'aiNewsAnalyzerControllerProvider لازم يُستخدم عبر override محلي من '
    'AiNewsAnalyzerScreen (newsItems / initialNewsId / AppLocalizations) - '
    'راجع ai_news_analyzer_screen.dart',
  ),
);

/// شاشة Discussion (تعليقات خبر واحد).
///
/// ⚠️ بنفس مبدأ [aiNewsAnalyzerControllerProvider] فوق - [DiscussionScreen]
/// هي يلي بتعمل الـ override الفعلي بـ newsId / initialCommentsCount /
/// onCountChanged الحقيقيين عبر [ProviderScope] محلي. الـ "create"
/// الافتراضي هون بيرمي خطأ واضح لو صار استخدامه بالغلط بدون override.
final commentsControllerProvider = ChangeNotifierProvider<CommentsController>(
  (ref) => throw UnimplementedError(
    'commentsControllerProvider لازم يُستخدم عبر override محلي من '
    'DiscussionScreen (newsId / initialCommentsCount / onCountChanged) - '
    'راجع discussion_screen.dart',
  ),
);
