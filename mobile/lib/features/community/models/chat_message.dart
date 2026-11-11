import 'package:flutter/foundation.dart';

/// أطول رسالة بالتطبيق (الـ backend بيقبل لحد 4000: `MESSAGE_MAX`)
const int kChatMessageMaxLength = 1000;

/// حالة رسالتك محليًا (رسائل الخبير دايمًا [sent])
enum ChatMessageStatus { sending, sent, failed }

/// محادثة مع خبير (`ConversationRead` بـ backend/app/schemas/chat.py)
@immutable
final class ChatConversation {
  const ChatConversation({
    required this.id,
    required this.expertId,
    required this.userId,
    this.canSend = true,
  });

  final String id;
  final String expertId;

  /// المستخدم (المشترك) - رسالة من هالـ id = رسالتك
  final String userId;
  final bool canSend;
}

/// رسالة بمحادثة خبير (`MessageRead`). [clientId] بيعمله التطبيق، وإعادة
/// المحاولة بنفس الـ [clientId] ما بتكرر الرسالة (متل الـ backend).
@immutable
final class ChatMessage {
  const ChatMessage({
    required this.id,
    required this.conversationId,
    required this.senderId,
    required this.body,
    required this.createdAt,
    required this.fromMe,
    this.clientId,
    this.status = ChatMessageStatus.sent,
  });

  final String id;
  final String conversationId;
  final String senderId;
  final String body;
  final DateTime createdAt;
  final bool fromMe;
  final String? clientId;
  final ChatMessageStatus status;

  ChatMessage withStatus(ChatMessageStatus status) => ChatMessage(
        id: id,
        conversationId: conversationId,
        senderId: senderId,
        body: body,
        createdAt: createdAt,
        fromMe: fromMe,
        clientId: clientId,
        status: status,
      );
}
