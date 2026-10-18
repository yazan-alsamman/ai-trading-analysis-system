import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../controllers/ai_chat_controller.dart';
import '../../l10n/app_localizations.dart';
import '../../models/chat_message_model.dart';
import '../../providers/screen_providers.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_navigation.dart';
import '../../utils/app_text_styles.dart';
import '../widgets/app_bottom_nav.dart';
import '../widgets/auth_background.dart';

/// شاشة الشات مع AI Strategy Assistant
///
/// الدور المعماري: **View (واجهة)**
/// - تعرض سجل المحادثة (رسائل المستخدم + رسائل AI)
/// - تعرض أسئلة سريعة مقترحة عند بداية المحادثة
/// - تأخذ إدخال المستخدم وترسله عبر [AiChatController]
///
/// نقاط الوصول لهذه الشاشة:
/// - من [HomeScreen]: زر "AI Quick Access" بقسم Quantitative Intelligence
/// - من [AiAssistantScreen] ("AI Hub"): بطاقة "AI Strategy Assistant"
/// - و[AiAssistantScreen] نفسها توصلها من أيقونة المخ بالـ navbar
///
/// تُغلّف [_AiChatView] بـ [ProviderScope] محلي (override لـ
/// [aiChatControllerProvider])، بحيث تبدأ محادثة جديدة (نظيفة) في كل
/// مرة تُفتح فيها الشاشة، وتُتخلّص من حالتها تلقائيًا عند الخروج منها.
class AiChatScreen extends StatelessWidget {
  const AiChatScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return ProviderScope(
      overrides: [
        aiChatControllerProvider.overrideWith(
          (ref) => AiChatController(l10n: l10n),
        ),
      ],
      child: const _AiChatView(),
    );
  }
}

// ═══════════════════════════════════════════════════════════
// Chat View - جسم الشاشة الفعلي
// ═══════════════════════════════════════════════════════════

class _AiChatView extends ConsumerStatefulWidget {
  const _AiChatView();

  @override
  ConsumerState<_AiChatView> createState() => _AiChatViewState();
}

class _AiChatViewState extends ConsumerState<_AiChatView> {
  /// فهرس تبويب AI بشريط التنقل السفلي (نفس فهرس [AiAssistantScreen])
  static const int _ownIndex = 2;

  final TextEditingController _inputController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  int _selectedBottomIndex = _ownIndex;

  @override
  void dispose() {
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  // ═══════════════════════════════════════════════════════════
  // Event Handlers - معالجات الأحداث
  // ═══════════════════════════════════════════════════════════

  void _handleSend(AiChatController controller) {
    final text = _inputController.text;
    if (text.trim().isEmpty) return;
    controller.sendMessage(text);
    _inputController.clear();
  }

  /// معالج ضغطات شريط التنقل السفلي - مفوّض بالكامل للمعالج المشترك
  /// [handleGlobalBottomNavTap] حتى يشتغل زر "Markets" (كان مو مفعّل
  /// أساسًا هون) بنفس سلوك باقي شاشات التطبيق.
  void _handleBottomNavTap(int index) => handleGlobalBottomNavTap(index);

  /// ينزل بالمحادثة لآخر رسالة (يُستدعى بعد كل تحديث بالرسائل)
  void _scrollToBottom() {
    if (!_scrollController.hasClients) return;
    _scrollController.animateTo(
      _scrollController.position.maxScrollExtent,
      duration: const Duration(milliseconds: 280),
      curve: Curves.easeOut,
    );
  }

  // ═══════════════════════════════════════════════════════════
  // Build Methods - دوال البناء
  // ═══════════════════════════════════════════════════════════

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final controller = ref.watch(aiChatControllerProvider);
    final messages = controller.messages;

    // الأسئلة السريعة تبين بس بأول المحادثة (رسالة الترحيب لسا لحالها)
    // منتفي لما يبلش المستخدم يحكي فعليًا، حتى ما تزاحم المحادثة.
    final showQuickQuestions = messages.length <= 1 && !controller.isAiTyping;

    // بعد كل build (يعني بعد أي رسالة جديدة) منزل للآخر تلقائيًا
    WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());

    return Scaffold(
      body: AuthBackground(
        child: SafeArea(
          bottom: false,
          child: Column(
            children: [
              _buildTopBar(),
              Expanded(
                child: ListView(
                  controller: _scrollController,
                  padding: const EdgeInsets.fromLTRB(20, 4, 20, 20),
                  children: [
                    _buildHeader(l10n),
                    const SizedBox(height: 8),
                    for (final message in messages)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 16),
                        child: _ChatBubble(message: message),
                      ),
                    if (controller.isAiTyping)
                      const Padding(
                        padding: EdgeInsets.only(bottom: 16),
                        child: _TypingIndicatorBubble(),
                      ),
                    if (showQuickQuestions) _buildQuickQuestions(controller, l10n),
                  ],
                ),
              ),
              _buildInputBar(controller, l10n),
            ],
          ),
        ),
      ),
      bottomNavigationBar: AppBottomNav(
        selectedIndex: _selectedBottomIndex,
        onTap: _handleBottomNavTap,
      ),
    );
  }

  /// شريط علوي: سهم رجوع فقط (بدون نص "Back to AI Hub")
  Widget _buildTopBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(10, 6, 10, 0),
      child: Row(
        children: [
          InkWell(
            onTap: () => Navigator.of(context).maybePop(),
            borderRadius: BorderRadius.circular(14),
            child: const Padding(
              padding: EdgeInsets.all(12),
              child: Icon(
                Icons.arrow_back_rounded,
                color: AppColors.textPrimary,
                size: 22,
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// عنوان الشاشة ووصفها
  Widget _buildHeader(AppLocalizations l10n) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(0, 8, 0, 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l10n.aiStrategyAssistantTitle, style: AppTextStyles.heading1),
          const SizedBox(height: 8),
          Text(
            l10n.aiChatSubtitle,
            style: AppTextStyles.subtitle.copyWith(fontSize: 16),
          ),
        ],
      ),
    );
  }

  /// قسم "Quick questions" — أسئلة جاهزة تُرسل مباشرة عند الضغط
  Widget _buildQuickQuestions(AiChatController controller, AppLocalizations l10n) {
    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            l10n.quickQuestionsLabel,
            style: AppTextStyles.label.copyWith(fontSize: 15),
          ),
          const SizedBox(height: 14),
          for (final question in controller.quickQuestions)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: _QuickQuestionChip(
                label: question,
                onTap: () => controller.sendMessage(question),
              ),
            ),
        ],
      ),
    );
  }

  /// شريط الإدخال السفلي: حقل نص + زر إرسال
  Widget _buildInputBar(AiChatController controller, AppLocalizations l10n) {
    final isSendEnabled = !controller.isAiTyping;

    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      decoration: BoxDecoration(
        color: AppColors.bgSurface.withOpacity(0.9),
        border: Border(
          top: BorderSide(color: AppColors.fieldBorder.withOpacity(0.18)),
        ),
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _inputController,
              enabled: isSendEnabled,
              textInputAction: TextInputAction.send,
              style: AppTextStyles.fieldText,
              onSubmitted: (_) => _handleSend(controller),
              decoration: InputDecoration(
                hintText: l10n.askAboutStrategiesHint,
                filled: true,
                fillColor: AppColors.bgDeep.withOpacity(0.55),
                isDense: true,
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 20,
                  vertical: 16,
                ),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(30),
                  borderSide: BorderSide(
                    color: AppColors.fieldBorder.withOpacity(0.4),
                  ),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(30),
                  borderSide: BorderSide(
                    color: AppColors.fieldBorder.withOpacity(0.4),
                  ),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(30),
                  borderSide: const BorderSide(
                    color: AppColors.fieldBorderFocus,
                    width: 1.4,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: 10),
          _SendButton(
            enabled: isSendEnabled,
            onTap: () => _handleSend(controller),
          ),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════
// Sub-widgets - مكونات فرعية
// ═══════════════════════════════════════════════════════════

/// فقاعة رسالة واحدة — تختلف بالمحاذاة واللون حسب المُرسِل
class _ChatBubble extends StatelessWidget {
  const _ChatBubble({required this.message});

  final ChatMessageModel message;

  @override
  Widget build(BuildContext context) {
    return message.isUser ? _buildUserBubble() : _buildAiBubble();
  }

  Widget _buildAiBubble() {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _AiAvatar(),
        const SizedBox(width: 14),
        Flexible(
          child: Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: AppColors.bgSurface.withOpacity(0.92),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(4),
                topRight: Radius.circular(22),
                bottomLeft: Radius.circular(22),
                bottomRight: Radius.circular(22),
              ),
              border: Border.all(
                color: AppColors.fieldBorder.withOpacity(0.35),
              ),
            ),
            child: Text(
              message.text,
              style: AppTextStyles.bodyLarge.copyWith(height: 1.5),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildUserBubble() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        Flexible(
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  AppColors.gradientMid.withOpacity(0.30),
                  AppColors.accentCyan.withOpacity(0.16),
                ],
              ),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(22),
                topRight: Radius.circular(4),
                bottomLeft: Radius.circular(22),
                bottomRight: Radius.circular(22),
              ),
              border: Border.all(
                color: AppColors.gradientMid.withOpacity(0.4),
              ),
            ),
            child: Text(
              message.text,
              style: AppTextStyles.bodyLarge.copyWith(height: 1.4),
            ),
          ),
        ),
      ],
    );
  }
}

/// أفاتار الـ AI: دائرة خضراء فاتحة + أيقونة المخ
class _AiAvatar extends StatelessWidget {
  const _AiAvatar();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 44,
      height: 44,
      padding: const EdgeInsets.all(9),
      decoration: const BoxDecoration(
        color: AppColors.gradientMid,
        shape: BoxShape.circle,
      ),
      child: Image.asset(
        'assets/images/strategy_assistant.png',
        color: AppColors.bgDeep,
      ),
    );
  }
}

/// فقاعة "AI يكتب..." — ثلاث نقاط بتنبض بالتناوب أثناء انتظار الرد
class _TypingIndicatorBubble extends StatefulWidget {
  const _TypingIndicatorBubble();

  @override
  State<_TypingIndicatorBubble> createState() =>
      _TypingIndicatorBubbleState();
}

class _TypingIndicatorBubbleState extends State<_TypingIndicatorBubble>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1200),
  )..repeat();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _AiAvatar(),
        const SizedBox(width: 14),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
          decoration: BoxDecoration(
            color: AppColors.bgSurface.withOpacity(0.92),
            borderRadius: const BorderRadius.only(
              topLeft: Radius.circular(4),
              topRight: Radius.circular(22),
              bottomLeft: Radius.circular(22),
              bottomRight: Radius.circular(22),
            ),
            border: Border.all(color: AppColors.fieldBorder.withOpacity(0.35)),
          ),
          child: AnimatedBuilder(
            animation: _controller,
            builder: (context, _) {
              return Row(
                mainAxisSize: MainAxisSize.min,
                children: List.generate(3, (i) {
                  final t = (_controller.value - (i * 0.2)) % 1.0;
                  final pulse = (1 - (t - 0.5).abs() * 2).clamp(0.0, 1.0);
                  final opacity = 0.3 + 0.7 * pulse;
                  return Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 3),
                    child: Opacity(
                      opacity: opacity,
                      child: Container(
                        width: 8,
                        height: 8,
                        decoration: const BoxDecoration(
                          color: AppColors.accentCyan,
                          shape: BoxShape.circle,
                        ),
                      ),
                    ),
                  );
                }),
              );
            },
          ),
        ),
      ],
    );
  }
}

/// شريحة سؤال سريع — بالضغط عليها تُرسَل كسؤال مباشرة
class _QuickQuestionChip extends StatelessWidget {
  const _QuickQuestionChip({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(30),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 17),
        decoration: BoxDecoration(
          color: AppColors.bgMid.withOpacity(0.85),
          borderRadius: BorderRadius.circular(30),
          border: Border.all(color: AppColors.gradientMid.withOpacity(0.4)),
        ),
        child: Text(
          label,
          style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w600),
        ),
      ),
    );
  }
}

/// زر الإرسال الدائري بأقصى يمين شريط الإدخال
class _SendButton extends StatelessWidget {
  const _SendButton({required this.enabled, required this.onTap});

  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: enabled ? onTap : null,
      customBorder: const CircleBorder(),
      child: Container(
        width: 52,
        height: 52,
        decoration: BoxDecoration(
          color: enabled
              ? AppColors.gradientMid
              : AppColors.gradientMid.withOpacity(0.35),
          shape: BoxShape.circle,
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
