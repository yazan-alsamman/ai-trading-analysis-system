import 'dart:async';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/network_status.dart';
import '../data/expert_chat_repository.dart';
import '../models/chat_message.dart';
import 'expert_subscriptions_view_model.dart';

/// أول تحميل للمحادثة بدون اتصال - بترجع تحمّل لحالها لما يرجع
final class ChatOfflineException implements Exception {
  const ChatOfflineException();
}

/// مفتوحة (مشترك) أو مقفولة ("Subscribe to chat")
enum ChatAccess { open, locked }

/// نتيجة "Send" / "Try again": [accepted] = الحقل بيفضى؛ غير هيك المسودة بتضل
enum ChatSendResult { accepted, ignored, offline, locked }

@immutable
final class ExpertChatState {
  const ExpertChatState.locked()
      : access = ChatAccess.locked,
        conversation = null,
        messages = const [];

  const ExpertChatState.open(ChatConversation this.conversation, this.messages) : access = ChatAccess.open;

  final ChatAccess access;
  final ChatConversation? conversation;

  /// الأقدم أول
  final List<ChatMessage> messages;

  ExpertChatState withMessages(List<ChatMessage> messages) => ExpertChatState.open(conversation!, messages);
}

/// ViewModel محادثة خبير (instance لكل خبير، بينحذف لما الشاشة تتسكّر).
///
/// - قاعدة الوصول: بدون اشتراك فيه `chat` الحالة [ChatAccess.locked] (ولا طلب
///   بينبعت)؛ الاشتراك أو الإلغاء بيعيد البناء.
/// - الإرسال: رسالتك بتطلع فورًا "Sending" → "Sent" أو "Not sent" مع إعادة
///   محاولة بنفس `client_id` (ما بتتكرر). بدون اتصال: ما في شي بينبعت والمسودة بتضل.
/// - ضغطتين ورا بعض على Send بنفس النص = رسالة وحدة.
/// - سكّرت الشاشة والرسالة عم تنبعت: الـ repository بيكمّل، والنتيجة ما بتنكتب
///   على ViewModel انحذف (token لكل بناء).
class ExpertChatViewModel extends AutoDisposeFamilyAsyncNotifier<ExpertChatState, String> {
  Object? _token;
  StreamSubscription<ChatMessage>? _incoming;
  final Set<Future<void>> _deliveries = {};
  final Random _random = Random.secure();

  @override
  Future<ExpertChatState> build(String expertId) async {
    final token = Object();
    _token = token;
    ref.onDispose(() {
      if (_token == token) _token = null;
      _incoming?.cancel();
      _incoming = null;
    });
    final repo = ref.watch(expertChatRepositoryProvider);
    ref.listen(networkStatusProvider, (_, status) {
      if (status == NetworkStatus.online && state.error is ChatOfflineException) ref.invalidateSelf();
    });

    final allowed =
        await ref.watch(expertSubscriptionsProvider.selectAsync((m) => m[expertId]?.allowsChat ?? false));
    if (!allowed || _token != token) return const ExpertChatState.locked();
    if (ref.read(networkStatusProvider) == NetworkStatus.offline) throw const ChatOfflineException();

    try {
      final conversation = await repo.open(expertId);
      final messages = await repo.history(conversation);
      if (_token != token) return const ExpertChatState.locked();
      _incoming = repo.incoming(conversation).listen(_upsert);
      return ExpertChatState.open(conversation, messages);
    } on ChatAccessDeniedException {
      return const ExpertChatState.locked();
    }
  }

  bool get _offline => ref.read(networkStatusProvider) == NetworkStatus.offline;

  /// كل الإرسالات الجارية خلصت (للاختبارات)
  @visibleForTesting
  Future<void> get idle => Future.wait(_deliveries.toList());

  ChatSendResult send(String text) {
    final current = state.valueOrNull;
    final conversation = current?.conversation;
    if (current == null || conversation == null) return ChatSendResult.locked;
    final body = text.trim();
    if (body.isEmpty || body.length > kChatMessageMaxLength) return ChatSendResult.ignored;
    // ضغطة تانية والأولى لسّا عم تنبعت بنفس النص = نفس الرسالة
    if (current.messages.any((m) => m.fromMe && m.status == ChatMessageStatus.sending && m.body == body)) {
      return ChatSendResult.ignored;
    }
    if (_offline) return ChatSendResult.offline;
    final clientId = _clientId();
    final pending = ChatMessage(
      id: 'local-$clientId',
      conversationId: conversation.id,
      senderId: conversation.userId,
      body: body,
      createdAt: DateTime.now().toUtc(),
      fromMe: true,
      clientId: clientId,
      status: ChatMessageStatus.sending,
    );
    state = AsyncData(current.withMessages([...current.messages, pending]));
    _deliver(conversation, pending);
    return ChatSendResult.accepted;
  }

  /// "Try again" على رسالة ما انبعتت - نفس `client_id`
  ChatSendResult retry(String clientId) {
    final current = state.valueOrNull;
    final conversation = current?.conversation;
    if (current == null || conversation == null) return ChatSendResult.locked;
    ChatMessage? failed;
    for (final m in current.messages) {
      if (m.clientId == clientId && m.status == ChatMessageStatus.failed) failed = m;
    }
    if (failed == null) return ChatSendResult.ignored;
    if (_offline) return ChatSendResult.offline;
    _upsert(failed.withStatus(ChatMessageStatus.sending));
    _deliver(conversation, failed);
    return ChatSendResult.accepted;
  }

  void _deliver(ChatConversation conversation, ChatMessage pending) {
    final token = _token;
    final repo = ref.read(expertChatRepositoryProvider);
    late final Future<void> delivery;
    delivery = () async {
      try {
        final sent = await repo.send(conversation, body: pending.body, clientId: pending.clientId!);
        if (token != null && _token == token) _upsert(sent);
      } on Object {
        if (token != null && _token == token) _markFailed(pending.clientId!);
      } finally {
        _deliveries.remove(delivery);
      }
    }();
    _deliveries.add(delivery);
  }

  /// رسالة جديدة أو محدّثة (نفس الـ id، أو نفس `client_id` = رسالتك يلي كانت عم تنبعت)
  void _upsert(ChatMessage message) {
    final current = state.valueOrNull;
    if (current == null || current.conversation == null) return;
    final list = [...current.messages];
    final i = list.indexWhere(
      (m) => m.id == message.id || (message.clientId != null && m.clientId == message.clientId),
    );
    if (i >= 0) {
      list[i] = message;
    } else {
      list.add(message);
    }
    state = AsyncData(current.withMessages(list));
  }

  void _markFailed(String clientId) {
    final current = state.valueOrNull;
    if (current == null || current.conversation == null) return;
    state = AsyncData(current.withMessages([
      for (final m in current.messages)
        m.clientId == clientId && m.status == ChatMessageStatus.sending ? m.withStatus(ChatMessageStatus.failed) : m,
    ]));
  }

  /// UUID v4 (`client_id` بالـ backend لازم يكون UUID)
  String _clientId() {
    final b = List<int>.generate(16, (_) => _random.nextInt(256));
    b[6] = (b[6] & 0x0f) | 0x40;
    b[8] = (b[8] & 0x3f) | 0x80;
    final h = b.map((x) => x.toRadixString(16).padLeft(2, '0')).join();
    return '${h.substring(0, 8)}-${h.substring(8, 12)}-${h.substring(12, 16)}-${h.substring(16, 20)}-${h.substring(20)}';
  }
}

final expertChatViewModelProvider =
    AsyncNotifierProvider.autoDispose.family<ExpertChatViewModel, ExpertChatState, String>(ExpertChatViewModel.new);
