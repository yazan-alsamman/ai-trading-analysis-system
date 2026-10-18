import 'package:flutter/foundation.dart';

import '../l10n/app_localizations.dart';
import '../models/comment_model.dart';
import 'news_repository.dart';

// ═══════════════════════════════════════════════════════════
// Comments Controller - متحكم تعليقات خبر واحد
// ═══════════════════════════════════════════════════════════

/// متحكم قائمة تعليقات خبر واحد (تُفتح بـ Bottom Sheet من [NewsItemCard])
///
/// الدور المعماري: **Controller (متحكم)**
///
/// مسؤولياته:
/// - تحميل تعليقات الخبر (حاليًا Mock بنفس عدد [initialCommentsCount]
///   المعروض على الكارد، ريثما تُربط بخدمة حقيقية) + تعليقات المستخدم
///   المحفوظة مسبقًا لهاد الخبر بالذات (راجع [repository])
/// - إدارة حالة التحميل (Loading)
/// - إضافة تعليق جديد من المستخدم **وحفظه بـ [repository]** حتى يضل
///   موجود لو المستخدم طلع من الشاشة ورجع فاتها من جديد (بدل ما يضيع
///   متل ما كان عم يصير قبل)
/// - حذف تعليق المستخدم من [repository] لما يتحذف من هون
///
/// ⚠️ لا يوجد أي منطق عرض هون - الـ View بتقرأ [comments] و[isLoading]
/// فقط عبر Provider.
final class CommentsController extends ChangeNotifier {
  CommentsController({
    required this.newsId,
    required this.initialCommentsCount,
    required this.repository,
    required AppLocalizations l10n,
    this.onCountChanged,
  }) : _l10n = l10n {
    _loadComments();
  }

  /// معرّف الخبر الثابت ([NewsItemModel.id]) - المفتاح يلي بتتخزن/تترجع
  /// عليه تعليقات المستخدم من [repository]
  final String newsId;

  /// عدد التعليقات الكلي المعروض حاليًا على [NewsItemCard] وقت فتح
  /// الشاشة (ممكن يكون شامل تعليقات محفوظة من جلسة سابقة) - بيتحدد
  /// منه كم تعليق Mock لازم يتولّد (بعد طرح عدد التعليقات المحفوظة
  /// منه)، حتى المجموع النهائي يطابقه بالضبط (راجع [_loadComments])
  final int initialCommentsCount;

  /// المصدر المشترك (Single Source of Truth) يلي بتتخزّن فيه تعليقات
  /// المستخدم فعليًا، طول عمر التطبيق - راجع توثيق
  /// [NewsRepository.userCommentsFor] لتفاصيل أكتر
  final NewsRepository repository;

  /// بينادى كل مرة يتغيّر فيها عدد التعليقات (إضافة أو حذف)، حتى تقدر
  /// الشاشة يلي فاتحة الـ Bottom Sheet تحدّث العدد المعروض على
  /// [NewsItemCard] بالقائمة الأصلية.
  final ValueChanged<int>? onCountChanged;

  /// نصوص التطبيق المترجمة الحالية - تُستخدم لتوليد اسم/وقت/نص
  /// التعليقات التجريبية (Mock) بلغة التطبيق الحالية
  final AppLocalizations _l10n;

  // ═══════════════════════════════════════════════════════════
  // Private State - الحالة الخاصة
  // ═══════════════════════════════════════════════════════════

  List<CommentModel> _comments = [];
  bool _isLoading = false;

  // ═══════════════════════════════════════════════════════════
  // Public Getters - القراءة العامة
  // ═══════════════════════════════════════════════════════════

  /// كل تعليقات الخبر المُحمّلة حاليًا (للقراءة فقط)
  List<CommentModel> get comments => List.unmodifiable(_comments);

  /// هل عم يتم تحميل التعليقات حاليًا؟
  bool get isLoading => _isLoading;

  // ═══════════════════════════════════════════════════════════
  // Public Methods - العمليات العامة
  // ═══════════════════════════════════════════════════════════

  /// إضافة تعليق جديد من المستخدم الحالي بأعلى القائمة، وحفظه بـ
  /// [repository] فورًا حتى يضل موجود لو المستخدم طلع من الشاشة ورجع
  /// فاتها من جديد
  void addComment(String rawText) {
    final text = rawText.trim();
    if (text.isEmpty) return;

    final comment = CommentModel(
      id: DateTime.now().microsecondsSinceEpoch.toString(),
      authorName: _l10n.commentAuthorYou,
      text: text,
      timeAgo: _l10n.justNow,
      isOwn: true,
    );

    repository.addUserComment(newsId, comment);
    _comments = [comment, ..._comments];
    _notifyCountChanged();
  }

  /// حذف تعليق أضافه المستخدم الحالي (بالاعتماد على [CommentModel.id])
  /// - وحذفه من [repository] كمان لو كان تعليق محفوظ تبع المستخدم،
  ///   حتى ما يرجع يظهر لما تُفتح الشاشة من جديد
  void deleteComment(String commentId) {
    final lengthBefore = _comments.length;
    final deleted = _comments.where((c) => c.id == commentId).firstOrNull;
    _comments = _comments.where((c) => c.id != commentId).toList();
    if (_comments.length == lengthBefore) return; // ما لقى شي يحذفه

    if (deleted != null && deleted.isOwn) {
      repository.removeUserComment(newsId, commentId);
    }

    _notifyCountChanged();
  }

  /// بينادي المستمعين وبيبلّغ [onCountChanged] بالعدد الجديد
  void _notifyCountChanged() {
    notifyListeners();
    onCountChanged?.call(_comments.length);
  }

  // ═══════════════════════════════════════════════════════════
  // Private Helpers - دوال مساعدة خاصة
  // ═══════════════════════════════════════════════════════════

  /// تحميل التعليقات - Mock مؤقت ريثما يُربط بـ NewsService حقيقي، مع
  /// دمج تعليقات المستخدم المحفوظة مسبقًا لهاد الخبر (لو في) بأعلى
  /// القائمة.
  ///
  /// ⚠️ [initialCommentsCount] هو العدد الكلي المعروض على الكارد وقت
  /// فتح الشاشة، وهو ممكن يكون أصلًا شامل تعليقات المستخدم المحفوظة من
  /// جلسة سابقة (لأنو بيتحدّث بـ [NewsRepository] فورًا عند أي إضافة).
  /// فلازم نطرح عدد التعليقات المحفوظة منه قبل ما نولّد الـ Mock، وإلا
  /// بينضاعف عدّها (مرة جوا الـ Mock ومرة كتعليقات محفوظة فوقهم) وبيصير
  /// عدد التعليقات المعروض أكبر من الحقيقي بكل مرة ترجع تفتح الشاشة -
  /// وهيك أي حذف بعدين بيبين وكأنه "مش عم ينقص العدد" (فعليًا عم ينقص،
  /// بس من رقم منفوخ أصلًا).
  Future<void> _loadComments() async {
    _isLoading = true;
    notifyListeners();

    // TODO: استبدال هالسطر بنداء حقيقي:
    // _comments = await NewsService.instance.fetchComments(newsId);
    await Future.delayed(const Duration(milliseconds: 350));

    final userComments = repository.userCommentsFor(newsId);
    final mockCount =
        (initialCommentsCount - userComments.length).clamp(0, initialCommentsCount);

    _comments = [
      ...userComments,
      ..._generateMockComments(mockCount),
    ];

    _isLoading = false;
    notifyListeners();
  }

  /// يولّد [count] تعليق بالضبط، بالدوران على نفس الحوض من الأسماء
  /// والنصوص الجاهزة (Placeholder) ريثما تصير التعليقات حقيقية عبر API.
  List<CommentModel> _generateMockComments(int count) {
    if (count <= 0) return const [];

    final pool = _commentPool(_l10n);
    return List.generate(count, (index) {
      final template = pool[index % pool.length];
      return CommentModel(
        authorName: template.authorName,
        text: template.text,
        timeAgo: _timeAgoFor(index),
      );
    });
  }

  /// وقت تقريبي متزايد لكل تعليق حسب ترتيبه (الأحدث فوق)
  String _timeAgoFor(int index) {
    final minutes = (index + 1) * 7;
    if (minutes < 60) return _l10n.minutesAgo(minutes);
    final hours = minutes ~/ 60;
    return _l10n.hoursAgo(hours);
  }

  /// حوض التعليقات التجريبية (Mock) - أسماء المستخدمين ثابتة (Usernames)،
  /// بس نص التعليق نفسه بيتغيّر حسب لغة التطبيق الحالية
  List<CommentModel> _commentPool(AppLocalizations l10n) => [
        CommentModel(
          authorName: 'Ahmad_Trader',
          text: l10n.commentText1,
          timeAgo: '',
        ),
        CommentModel(
          authorName: 'Sara.Fx',
          text: l10n.commentText2,
          timeAgo: '',
        ),
        CommentModel(
          authorName: 'GoldBull22',
          text: l10n.commentText3,
          timeAgo: '',
        ),
        CommentModel(
          authorName: 'Khaled_M',
          text: l10n.commentText4,
          timeAgo: '',
        ),
        CommentModel(
          authorName: 'Nour_Invest',
          text: l10n.commentText5,
          timeAgo: '',
        ),
        CommentModel(
          authorName: 'Omar.Pips',
          text: l10n.commentText6,
          timeAgo: '',
        ),
        CommentModel(
          authorName: 'LinaTrades',
          text: l10n.commentText7,
          timeAgo: '',
        ),
        CommentModel(
          authorName: 'Yousef_FX',
          text: l10n.commentText8,
          timeAgo: '',
        ),
      ];
}
