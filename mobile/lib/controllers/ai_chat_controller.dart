import 'package:flutter/foundation.dart';
import '../l10n/app_localizations.dart';
import '../models/chat_message_model.dart';

// ═══════════════════════════════════════════════════════════
// AI Chat Controller - متحكم شات AI Strategy Assistant
// ═══════════════════════════════════════════════════════════

/// متحكم إدارة حالة الشات مع AI Strategy Assistant
///
/// مسؤوليات هذا الكلاس:
/// - الاحتفاظ بسجل الرسائل (مستخدم + AI) وترتيبها
/// - إدارة حالة "AI يكتب..." أثناء انتظار الرد
/// - توليد رد الـ AI (حاليًا محاكاة، لحين ربط API حقيقي)
///
/// ⚠️ IMPORTANT: الواجهة (View) لا تتواصل مع أي خدمة مباشرة،
/// كل شي بيمر من هون، بنفس نمط [AuthController]
///
/// ⚠️ ملاحظة على الترجمة: [l10n] يُلتقط لحظة إنشاء المتحكم (لحظة فتح
/// الشاشة) ويُستخدم لرسالة الترحيب والأسئلة السريعة والردود التجريبية.
/// لو المستخدم بدّل لغة التطبيق ووهو بمنتصف محادثة مفتوحة، الرسائل
/// يلي انبعتت أصلاً بتضل بلغتها الأصلية (نفس سلوك أي شات حقيقي)، وبس
/// الرسائل الجديدة بعد فتح شاشة جديدة بتاخد اللغة الجديدة.
final class AiChatController extends ChangeNotifier {
  AiChatController({required AppLocalizations l10n}) : _l10n = l10n {
    _messages.add(
      _buildMessage(text: _l10n.aiChatWelcome, sender: ChatMessageSender.ai),
    );
  }

  final AppLocalizations _l10n;

  // ═══════════════════════════════════════════════════════════
  // Quick Questions - أسئلة سريعة مقترحة تحت الرسالة الترحيبية
  // ═══════════════════════════════════════════════════════════

  List<String> get quickQuestions => [
        _l10n.aiChatQuickQ1,
        _l10n.aiChatQuickQ2,
        _l10n.aiChatQuickQ3,
      ];

  // ═══════════════════════════════════════════════════════════
  // Private State - الحالة الخاصة
  // ═══════════════════════════════════════════════════════════

  final List<ChatMessageModel> _messages = [];
  bool _isAiTyping = false;
  int _messageSeq = 0;

  // ═══════════════════════════════════════════════════════════
  // Public Getters - القيم العامة (للقراءة فقط)
  // ═══════════════════════════════════════════════════════════

  /// نسخة غير قابلة للتعديل من سجل الرسائل
  List<ChatMessageModel> get messages => List.unmodifiable(_messages);

  /// هل الـ AI حاليًا "بيكتب" رد؟
  bool get isAiTyping => _isAiTyping;

  // ═══════════════════════════════════════════════════════════
  // Public Actions - العمليات العامة
  // ═══════════════════════════════════════════════════════════

  /// إرسال رسالة من المستخدم، وتوليد رد AI بعدها
  ///
  /// يتجاهل الاستدعاء إذا كان النص فاضي أو في رد AI قيد الانتظار،
  /// لمنع إرسال أكتر من رسالة بنفس اللحظة
  Future<void> sendMessage(String rawText) async {
    final text = rawText.trim();
    if (text.isEmpty || _isAiTyping) return;

    _messages.add(_buildMessage(text: text, sender: ChatMessageSender.user));
    _isAiTyping = true;
    notifyListeners();

    // TODO: استبدال هذا بـ API call حقيقي عبر AiChatService
    await Future.delayed(const Duration(milliseconds: 1300));

    _messages.add(
      _buildMessage(text: _mockReplyFor(text), sender: ChatMessageSender.ai),
    );
    _isAiTyping = false;
    notifyListeners();
  }

  // ═══════════════════════════════════════════════════════════
  // Private Helper Methods - دوال مساعدة خاصة
  // ═══════════════════════════════════════════════════════════

  ChatMessageModel _buildMessage({
    required String text,
    required ChatMessageSender sender,
  }) {
    _messageSeq++;
    return ChatMessageModel(
      id: 'msg_${DateTime.now().microsecondsSinceEpoch}_$_messageSeq',
      text: text,
      sender: sender,
      timestamp: DateTime.now(),
    );
  }

  /// توليد رد تجريبي بناءً على كلمات مفتاحية بالسؤال (عربي أو إنجليزي)
  /// (بديل مؤقت لحين ربط نموذج AI حقيقي)
  String _mockReplyFor(String question) {
    final normalized = question.toLowerCase();

    final isEurUsd = normalized.contains('eur/usd') ||
        normalized.contains('eur usd') ||
        normalized.contains('يورو');
    final isScalping = normalized.contains('scalping') ||
        normalized.contains('سكالبينج') ||
        normalized.contains('مضاربة سريعة');
    final isRisk = normalized.contains('risk') || normalized.contains('خاطر') || normalized.contains('مخاطر');

    if (isEurUsd) return _l10n.aiChatReplyEurUsd;
    if (isScalping) return _l10n.aiChatReplyScalping;
    if (isRisk) return _l10n.aiChatReplyRisk;
    return _l10n.aiChatReplyDefault;
  }
}
