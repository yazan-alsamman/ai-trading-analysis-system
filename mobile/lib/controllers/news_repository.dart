import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../l10n/app_localizations.dart';
import '../models/comment_model.dart';
import '../models/news_item_model.dart';

// ═══════════════════════════════════════════════════════════
// News Repository - المصدر الوحيد لأخبار السوق بالتطبيق
// ═══════════════════════════════════════════════════════════

/// المصدر الوحيد (Single Source of Truth) لكل أخبار السوق بالتطبيق
///
/// الدور المعماري: **Controller/Repository (متحكم مشترك)**
///
/// ⚠️ لازم تُزوَّد **مرة وحدة** بجذر التطبيق ([TradingApp] بملف main.dart)
/// وليس داخل كل شاشة على حدة، حتى نفس قائمة الأخبار (بنفس عدد
/// التعليقات) تكون مشتركة فعليًا بين [HomeScreen]، [MarketNewsScreen]،
/// و[DiscussionScreen]:
/// - لما يزيد عدد التعليقات بشاشة الـ Discussion (إضافة تعليق)، الرقم
///   بيزيد بنفس اللحظة بمعاينة الهوم وبقائمة Market News الكاملة.
/// - لما ينقص (حذف تعليق)، بينقص بكل الأماكن الثلاثة سوا.
///
/// مسؤولياته:
/// - تحميل قائمة الأخبار الكاملة (حاليًا Mock ريثما تُربط بخدمة حقيقية)
/// - إدارة حالة التحميل (Loading) تحضيرًا لربط API لاحقًا
/// - تحديث عدد تعليقات خبر معيّن بالاعتماد على [NewsItemModel.id]
///   الثابت (مو Object reference)، حتى التحديث يشتغل مهما كانت الشاشة
///   يلي بدأت منها
/// - **حفظ تعليقات المستخدم** (يلي هو نفسه ضافها) لكل خبر، بالاعتماد
///   على [NewsItemModel.id] الثابت، حتى تضل موجودة طول ما التطبيق شغّال
///   حتى لو المستخدم طلع من شاشة [DiscussionScreen] ورجع فاتها من
///   جديد (بدل ما تنولّد Mock من الصفر وتضيع تعليقاته - راجع
///   [CommentsController] لتفاصيل الاستخدام)
///
/// ⚠️ لا يوجد أي منطق عرض هون - الـ View بتقرأ [newsItems] و[isLoading]
/// فقط عبر Provider.
///
/// ⚠️ ملاحظة على الترجمة (AR/EN): بعكس متحكمات الـ AI (يلي بتتولّد من
/// جديد بكل فتحة لشاشتها، فبتاخد [AppLocalizations] الحالية دايمًا)،
/// هاي الـ Repository جذرية وحيّة طول عمر التطبيق، فما بتاخد
/// [AppLocalizations] من BuildContext مباشرة. بدل هيك:
/// 1. عند أول تحميل ([_loadNews])، بتقرأ لغة التطبيق المحفوظة مباشرة
///    من نفس مخزن [LocaleNotifier] (راجع lib/providers/locale_provider.dart)
///    وتبني المحتوى فيها من البداية - فحتى لو المستخدم فتح التطبيق
///    ولغته المحفوظة عربي، الأخبار بتطلع عربي من أول تحميل.
/// 2. لو المستخدم بدّل اللغة وهو داخل التطبيق (من شاشة Profile)، لازم
///    ينادى [relocalize] يدويًا بعد التبديل مباشرة (مو تلقائيًا) حتى
///    ما يصير أي تعارض إعادة-بناء أثناء بناء واجهة تانية - [ProfileScreen]
///    هي يلي بتعمل هالنداء بعد ما تحفظ اللغة الجديدة.
final class NewsRepository extends ChangeNotifier {
  NewsRepository() {
    _loadNews();
  }

  // ═══════════════════════════════════════════════════════════
  // Private State - الحالة الخاصة
  // ═══════════════════════════════════════════════════════════

  static const _localeStorageKey = 'app_locale';
  static const _supportedLanguageCodes = ['en', 'ar'];

  List<NewsItemModel> _newsItems = [];
  bool _isLoading = false;

  /// آخر لغة تم بناء محتوى الأخبار فيها - تُستخدم لمنع إعادة بناء
  /// المحتوى بدون داعي لو [relocalize] انادت بنفس اللغة الحالية أصلًا
  String? _lastLocalizedLanguageCode;

  /// تعليقات المستخدم المحفوظة لكل خبر (المفتاح = [NewsItemModel.id]) -
  /// بتضل بالذاكرة طول ما الـ Repository حيّة (يعني طول عمر التطبيق،
  /// لأنها مزوَّدة مرة وحدة بجذر التطبيق)، عكس [CommentsController]
  /// يلي بينعمل وينعاد إنشاؤه بكل مرة تُفتح فيها شاشة [DiscussionScreen]
  final Map<String, List<CommentModel>> _userComments = {};

  // ═══════════════════════════════════════════════════════════
  // Public Getters - القراءة العامة
  // ═══════════════════════════════════════════════════════════

  /// كل أخبار السوق المُحمّلة حاليًا (للقراءة فقط)
  List<NewsItemModel> get newsItems => List.unmodifiable(_newsItems);

  /// هل عم يتم تحميل الأخبار حاليًا؟
  bool get isLoading => _isLoading;

  /// الأخبار يلي [ids] بيحددها، بنفس ترتيبها بالقائمة الأصلية -
  /// تُستخدم بمعاينة الأخبار المصغّرة بـ [HomeScreen] حتى تعرض بس
  /// خبرين محددين (بس برضو بنفس عدد التعليقات الحيّ من هالـ Repository)
  List<NewsItemModel> byIds(List<String> ids) =>
      _newsItems.where((n) => ids.contains(n.id)).toList(growable: false);

  // ═══════════════════════════════════════════════════════════
  // Public Methods - العمليات العامة
  // ═══════════════════════════════════════════════════════════

  /// إعادة تحميل قائمة الأخبار (Pull-to-refresh مثلًا)
  Future<void> refresh() => _loadNews();

  /// إعادة بناء عناوين/نصوص الأخبار التجريبية بلغة [l10n] الحالية،
  /// مع الحفاظ على عدد التعليقات الحيّ لكل خبر (ما منعيد تصفيره).
  /// تُنادى من [ProfileScreen] مباشرة بعد ما المستخدم يبدّل لغة
  /// التطبيق وهو داخل جلسة شغّالة - راجع ملاحظة الترجمة أعلاه.
  void relocalize(AppLocalizations l10n) {
    if (_lastLocalizedLanguageCode == l10n.locale.languageCode) return;
    _lastLocalizedLanguageCode = l10n.locale.languageCode;

    final preservedCounts = {
      for (final n in _newsItems) n.id: n.commentsCount,
    };

    _newsItems = _buildMockNews(l10n)
        .map(
          (n) => preservedCounts.containsKey(n.id)
              ? n.copyWith(commentsCount: preservedCounts[n.id])
              : n,
        )
        .toList(growable: false);
    notifyListeners();
  }

  /// تحديث عدد تعليقات خبر معيّن (بعد إضافة/حذف تعليق من شاشة
  /// [DiscussionScreen])، بالاعتماد على [NewsItemModel.id] الثابت -
  /// بينعكس فورًا بكل شاشة عم تراقب هالـ Repository
  void updateCommentsCount(String newsId, int newCount) {
    final index = _newsItems.indexWhere((n) => n.id == newsId);
    if (index == -1) return;

    _newsItems = List.of(_newsItems)
      ..[index] = _newsItems[index].copyWith(commentsCount: newCount);
    notifyListeners();
  }

  /// تعليقات المستخدم المحفوظة لخبر معيّن (الأحدث أولًا) - فاضية لو ما
  /// ضاف المستخدم أي تعليق على هالخبر لسا
  List<CommentModel> userCommentsFor(String newsId) =>
      List.unmodifiable(_userComments[newsId] ?? const []);

  /// حفظ تعليق جديد ضافه المستخدم على خبر معيّن، حتى يضل موجود لو
  /// المستخدم طلع من شاشة [DiscussionScreen] ورجع فاتها من جديد
  void addUserComment(String newsId, CommentModel comment) {
    final existing = _userComments[newsId] ?? const [];
    _userComments[newsId] = [comment, ...existing];
  }

  /// حذف تعليق محفوظ ضافه المستخدم (بعد ما يحذفه من شاشة
  /// [DiscussionScreen])، بالاعتماد على [CommentModel.id]
  void removeUserComment(String newsId, String commentId) {
    final existing = _userComments[newsId];
    if (existing == null) return;

    _userComments[newsId] =
        existing.where((c) => c.id != commentId).toList();
  }

  // ═══════════════════════════════════════════════════════════
  // Private Helpers - دوال مساعدة خاصة
  // ═══════════════════════════════════════════════════════════

  /// تحميل الأخبار - Mock مؤقت ريثما يُربط بـ NewsService حقيقي
  Future<void> _loadNews() async {
    _isLoading = true;
    notifyListeners();

    // TODO: استبدال هالسطر بنداء حقيقي:
    // _newsItems = await NewsService.instance.fetchMarketNews();
    await Future.delayed(const Duration(milliseconds: 400));

    final l10n = AppLocalizations(await _readSavedLocale());
    _lastLocalizedLanguageCode = l10n.locale.languageCode;
    _newsItems = _buildMockNews(l10n);

    _isLoading = false;
    notifyListeners();
  }

  /// قراءة لغة التطبيق المحفوظة مباشرة من نفس المخزن يلي [LocaleNotifier]
  /// (lib/providers/locale_provider.dart) بيقرأ منه، حتى أول تحميل
  /// للأخبار يطلع بلغة التطبيق الصح من البداية بدون انتظار أي widget
  Future<Locale> _readSavedLocale() async {
    try {
      const storage = FlutterSecureStorage();
      final saved = await storage.read(key: _localeStorageKey);
      if (saved != null && _supportedLanguageCodes.contains(saved)) {
        return Locale(saved);
      }
    } catch (_) {
      // تجاهل أي خطأ قراءة (مثلًا أول تشغيل بدون تخزين بعد) - نكمل
      // بالإنجليزية الافتراضية
    }
    return const Locale('en');
  }

  /// بناء قائمة الأخبار التجريبية (Mock) بلغة [l10n] المُعطاة
  List<NewsItemModel> _buildMockNews(AppLocalizations l10n) {
    return [
      NewsItemModel(
        id: 'fed-rate-decision',
        title: l10n.newsFedTitle,
        source: 'ForexLive',
        timeAgo: l10n.hoursAgo(2),
        impact: NewsImpactLevel.high,
        description: l10n.newsFedDescription,
        commentsCount: 24,
        content: l10n.newsFedContent,
      ),
      NewsItemModel(
        id: 'ecb-rate-cuts',
        title: l10n.newsEcbTitle,
        source: 'ForexLive',
        timeAgo: l10n.hoursAgo(3),
        impact: NewsImpactLevel.medium,
        description: l10n.newsEcbDescription,
        commentsCount: 11,
        content: l10n.newsEcbContent,
      ),
      NewsItemModel(
        id: 'gold-prices-steady',
        title: l10n.newsGoldTitle,
        source: 'Kitco News',
        timeAgo: l10n.hoursAgo(5),
        impact: NewsImpactLevel.low,
        description: l10n.newsGoldDescription,
        commentsCount: 6,
        content: l10n.newsGoldContent,
      ),
      NewsItemModel(
        id: 'uk-retail-sales',
        title: l10n.newsUkTitle,
        source: 'ForexLive',
        timeAgo: l10n.hoursAgo(7),
        impact: NewsImpactLevel.low,
        description: l10n.newsUkDescription,
        commentsCount: 3,
        content: l10n.newsUkContent,
      ),
    ];
  }
}
