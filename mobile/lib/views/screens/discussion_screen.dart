import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../controllers/comments_controller.dart';
import '../../l10n/app_localizations.dart';
import '../../models/comment_model.dart';
import '../../providers/app_providers.dart';
import '../../providers/screen_providers.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_navigation.dart';
import '../widgets/app_bottom_nav.dart';
import '../widgets/auth_background.dart';

// ═══════════════════════════════════════════════════════════
// Discussion Screen - شاشة تعليقات خبر واحد (شاشة كاملة)
// ═══════════════════════════════════════════════════════════

/// شاشة كاملة تعرض نقاش (تعليقات) خبر واحد.
///
/// الدور المعماري: **View (واجهة)**
///
/// نقاط الوصول لهذه الشاشة (كلها بنفس السلوك، بتفتح نفس الشاشة):
/// - من [HomeScreen]: الضغط على عدّاد التعليقات بمعاينة الأخبار المصغّرة
/// - من [MarketNewsScreen]: الضغط على عدّاد التعليقات بالقائمة الكاملة
/// - من [NewsDetailScreen]: الضغط على زر "Comments" بعد فتح الخبر
///
/// بتحل مكان الـ Bottom Sheet القديم (يلي كان جزئي وما بيغطي الشاشة)
/// بشاشة كاملة مستقلة، بنفس منطق [CommentsController] (تحميل/إضافة/حذف
/// تعليقات) بس بتصميم مختلف بالكامل: خلفية [AuthBackground]، عنوان
/// "Discussion" بخط Serif، وشريط تنقّل سفلي بتكبر فيه أيقونة الـ AI
/// (الدماغ) لتمييزها.
class DiscussionScreen extends ConsumerWidget {
  const DiscussionScreen({
    super.key,
    required this.newsId,
    required this.newsTitle,
    required this.commentsCount,
    this.onCommentsCountChanged,
  });

  /// معرّف الخبر الثابت ([NewsItemModel.id]) - المفتاح يلي بتتحفظ عليه
  /// تعليقات المستخدم بـ [NewsRepository]، حتى تضل موجودة لو المستخدم
  /// طلع من هاي الشاشة ورجع فاتها من جديد
  final String newsId;

  /// عنوان الخبر - بيُعرض كعنوان فرعي تحت "Discussion"
  final String newsTitle;

  /// عدد التعليقات الحالي (نفس المعروض على [NewsItemCard]) - الشاشة
  /// بتولّد بالضبط هالعدد من التعليقات (مو أقل ولا أكتر) عند فتحها.
  final int commentsCount;

  /// بينادى كل مرة يتغيّر فيها عدد التعليقات (إضافة/حذف)، حتى الشاشة
  /// الأصلية (Home / Market News / News Detail) تحدّث العدّاد المعروض
  /// عندها لنفس الخبر.
  final ValueChanged<int>? onCommentsCountChanged;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final repository = ref.read(newsRepositoryProvider);
    final l10n = AppLocalizations.of(context)!;

    return ProviderScope(
      overrides: [
        commentsControllerProvider.overrideWith(
          (ref) => CommentsController(
            newsId: newsId,
            initialCommentsCount: commentsCount,
            repository: repository,
            l10n: l10n,
            onCountChanged: onCommentsCountChanged,
          ),
        ),
      ],
      child: _DiscussionView(newsTitle: newsTitle),
    );
  }
}

// ═══════════════════════════════════════════════════════════
// Screen View - جسم الشاشة الفعلي
// ═══════════════════════════════════════════════════════════

class _DiscussionView extends ConsumerStatefulWidget {
  const _DiscussionView({required this.newsTitle});

  final String newsTitle;

  @override
  ConsumerState<_DiscussionView> createState() => _DiscussionViewState();
}

class _DiscussionViewState extends ConsumerState<_DiscussionView> {
  /// فهرس أيقونة الـ AI (الدماغ) بشريط التنقل السفلي
  static const int _aiIndex = 2;

  /// عناصر شريط التنقل السفلي بهاي الشاشة تحديدًا: نفس عناصر
  /// [AppBottomNav.defaultItems]، بس أيقونة الـ AI (الدماغ) مكبّرة
  /// لتمييزها - بالضبط متل التصميم المرجعي لشاشة الـ Discussion.
  static final List<NavBarItemData> _navItems = [
    for (var i = 0; i < AppBottomNav.defaultItems.length; i++)
      if (i == _aiIndex)
        const NavBarItemData(
          imagePath: 'assets/images/strategy_assistant.png',
          useNativeColor: true,
          size: 40, // مكبّرة عن الحجم الافتراضي (26) لتمييزها بهاي الشاشة
        )
      else
        AppBottomNav.defaultItems[i],
  ];

  // ═══════════════════════════════════════════════════════════
  // Event Handlers - معالجات الأحداث
  // ═══════════════════════════════════════════════════════════

  /// معالج ضغطات شريط التنقل السفلي - مفوّض بالكامل للمعالج المشترك
  /// [handleGlobalBottomNavTap] حتى يشتغل زر "Markets" (كان مو مفعّل
  /// أساسًا هون) بنفس سلوك باقي شاشات التطبيق.
  Future<void> _handleBottomNavTap(int index) => handleGlobalBottomNavTap(index);

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final controller = ref.watch(commentsControllerProvider);

    return Scaffold(
      body: AuthBackground(
        child: SafeArea(
          bottom: false,
          child: Column(
            children: [
              _buildTopBar(),
              _buildHeader(l10n),
              Expanded(child: _buildBody(controller, l10n)),
              _CommentInputBar(
                l10n: l10n,
                onSubmit: (text) =>
                    ref.read(commentsControllerProvider).addComment(text),
              ),
            ],
          ),
        ),
      ),
      bottomNavigationBar: AppBottomNav(
        selectedIndex: -1, // ما في تبويب "محدد" بهاي الشاشة، الدماغ مميّز بالحجم بس
        onTap: _handleBottomNavTap,
        items: _navItems,
      ),
    );
  }

  /// شريط علوي: سهم رجوع بس، ملاصق لبداية الشاشة (مو بنص الـ app bar)
  Widget _buildTopBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 12, 16, 4),
      child: Align(
        alignment: AlignmentDirectional.centerStart,
        child: InkWell(
          onTap: () => Navigator.of(context).maybePop(),
          borderRadius: BorderRadius.circular(14),
          child: const Padding(
            padding: EdgeInsets.all(12),
            child: Icon(
              Icons.arrow_back_rounded,
              color: AppColors.textPrimary,
              size: 26,
            ),
          ),
        ),
      ),
    );
  }

  /// عنوان "Discussion" الكبير + عنوان الخبر تحته
  Widget _buildHeader(AppLocalizations l10n) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l10n.discussion, style: _serif(38, FontWeight.w700)),
          const SizedBox(height: 12),
          Text(
            widget.newsTitle,
            style: GoogleFonts.quicksand(
              fontSize: 17,
              fontWeight: FontWeight.w500,
              color: AppColors.accentCyan,
              height: 1.3,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBody(CommentsController controller, AppLocalizations l10n) {
    if (controller.isLoading) {
      return const Center(
        child: CircularProgressIndicator(color: AppColors.accentGreen),
      );
    }

    final comments = controller.comments;
    if (comments.isEmpty) {
      return Center(
        child: Text(
          l10n.noCommentsYet,
          style: GoogleFonts.quicksand(
            fontSize: 16,
            color: AppColors.textSecondary,
          ),
        ),
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
      itemCount: comments.length,
      separatorBuilder: (_, __) => const SizedBox(height: 16),
      itemBuilder: (context, index) => _CommentCard(comment: comments[index]),
    );
  }

  /// خط Serif مشترك لكل عناوين هاي الشاشة (متل التصميم المرجعي)
  TextStyle _serif(double size, FontWeight weight) {
    return GoogleFonts.playfairDisplay(
      fontSize: size,
      fontWeight: weight,
      color: AppColors.textPrimary,
      height: 1.15,
    );
  }
}

// ═══════════════════════════════════════════════════════════
// Comment Card - كرت تعليق واحد
// ═══════════════════════════════════════════════════════════

/// عرض تعليق واحد بشكل كرت (متل التصميم المرجعي):
/// أفاتار بحرف الاسم الأول + الاسم (Serif) + الوقت + نص التعليق
class _CommentCard extends ConsumerWidget {
  const _CommentCard({required this.comment});

  final CommentModel comment;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.bgSurface.withOpacity(0.75),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: AppColors.fieldBorder.withOpacity(0.25)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildAvatar(),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        comment.authorName,
                        style: GoogleFonts.playfairDisplay(
                          fontSize: 19,
                          fontWeight: FontWeight.w600,
                          color: AppColors.textPrimary,
                        ),
                      ),
                    ),
                    if (comment.isOwn) _buildDeleteButton(ref),
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  comment.timeAgo,
                  style: GoogleFonts.quicksand(
                    fontSize: 13,
                    color: AppColors.textHint,
                  ),
                ),
                const SizedBox(height: 10),
                Text(
                  comment.text,
                  style: GoogleFonts.quicksand(
                    fontSize: 16,
                    fontWeight: FontWeight.w500,
                    color: AppColors.textPrimary,
                    height: 1.45,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAvatar() {
    return CircleAvatar(
      radius: 22,
      backgroundColor: AppColors.accentGreen.withOpacity(0.85),
      child: Text(
        comment.authorName.isNotEmpty ? comment.authorName[0].toUpperCase() : '?',
        style: GoogleFonts.playfairDisplay(
          fontSize: 17,
          color: AppColors.buttonText,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }

  /// زر حذف التعليق - بيظهر بس على تعليقات المستخدم الحالي ([CommentModel.isOwn])
  Widget _buildDeleteButton(WidgetRef ref) {
    return InkWell(
      onTap: () =>
          ref.read(commentsControllerProvider).deleteComment(comment.id),
      borderRadius: BorderRadius.circular(16),
      child: const Padding(
        padding: EdgeInsets.all(4),
        child: Icon(
          Icons.delete_outline_rounded,
          size: 18,
          color: AppColors.textHint,
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════
// Comment Input Bar - شريط كتابة تعليق جديد
// ═══════════════════════════════════════════════════════════

/// شريط إدخال تعليق جديد أسفل الشاشة + زر الإرسال (متل التصميم المرجعي)
///
/// الدور المعماري: **View (واجهة) بحتة**
/// لا تحتفظ بأي منطق أعمال، فقط تستدعي [onSubmit] بالنص المُدخل
class _CommentInputBar extends StatefulWidget {
  const _CommentInputBar({required this.onSubmit, required this.l10n});

  final ValueChanged<String> onSubmit;
  final AppLocalizations l10n;

  @override
  State<_CommentInputBar> createState() => _CommentInputBarState();
}

class _CommentInputBarState extends State<_CommentInputBar> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _handleSend() {
    final text = _controller.text;
    if (text.trim().isEmpty) return;
    widget.onSubmit(text);
    _controller.clear();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 10, 20, 14),
      child: SafeArea(
        top: false,
        child: Row(
          children: [
            Expanded(
              child: Container(
                height: 52,
                padding: const EdgeInsets.symmetric(horizontal: 20),
                decoration: BoxDecoration(
                  color: AppColors.bgSurface.withOpacity(0.6),
                  borderRadius: BorderRadius.circular(26),
                  border: Border.all(
                    color: AppColors.fieldBorder.withOpacity(0.5),
                  ),
                ),
                child: Center(
                  child: TextField(
                    controller: _controller,
                    minLines: 1,
                    maxLines: 1,
                    textInputAction: TextInputAction.send,
                    onSubmitted: (_) => _handleSend(),
                    style: GoogleFonts.quicksand(
                      fontSize: 16,
                      color: AppColors.textPrimary,
                    ),
                    decoration: InputDecoration(
                      hintText: widget.l10n.addYourComment,
                      hintStyle: GoogleFonts.quicksand(
                        fontSize: 16,
                        color: AppColors.textHint,
                      ),
                      border: InputBorder.none,
                      enabledBorder: InputBorder.none,
                      focusedBorder: InputBorder.none,
                      disabledBorder: InputBorder.none,
                      errorBorder: InputBorder.none,
                      focusedErrorBorder: InputBorder.none,
                      isCollapsed: true,
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 10),
            _SendButton(onTap: _handleSend),
          ],
        ),
      ),
    );
  }
}

/// زر الإرسال الدائري
class _SendButton extends StatelessWidget {
  const _SendButton({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(26),
      child: Container(
        width: 52,
        height: 52,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: AppColors.accentGreen,
          borderRadius: BorderRadius.circular(18),
        ),
        child: const Icon(
          Icons.send_rounded,
          color: AppColors.buttonText,
          size: 22,
        ),
      ),
    );
  }
}
