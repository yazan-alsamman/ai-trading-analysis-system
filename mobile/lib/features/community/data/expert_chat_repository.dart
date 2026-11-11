import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/json.dart';
import '../../../core/data/network_status.dart';
import '../../../providers/locale_provider.dart';
import '../../auth/auth_state.dart';
import '../models/chat_message.dart';
import 'expert_subscriptions_repository.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';

/// ما في اشتراك بميزة المحادثة (الـ backend: 403)
final class ChatAccessDeniedException implements Exception {
  const ChatAccessDeniedException();
}

/// الرسالة ما وصلت (شبكة / خادم) - الواجهة بتعلّمها "Not sent" مع إعادة محاولة
final class ChatSendException implements Exception {
  const ChatSendException();
}

/// مصدر محادثات الخبراء - بيتبدّل بتنفيذ API (`chat.py`) بعدين
abstract interface class ExpertChatRepository {
  /// يفتح (أو يرجّع) محادثتك مع الخبير. بدون اشتراك فيه `chat`: [ChatAccessDeniedException].
  /// API: `POST /conversations` (`expert_id`) → `ConversationRead` (201 / 200، 403 بدون اشتراك).
  /// TODO(API): ربط مع الجلسة (JWT).
  Future<ChatConversation> open(String expertId);

  /// الرسائل، الأقدم أول.
  /// API: `GET /conversations/{id}/messages?limit=50` (الأحدث أول؛ `next_before` للأقدم).
  /// TODO(API): تحميل الأقدم بالسكرول لفوق (`before=`).
  Future<List<ChatMessage>> history(ChatConversation conversation);

  /// بيبعت رسالة. نفس [clientId] مرتين = رسالة وحدة (إعادة المحاولة آمنة).
  /// فشل: [ChatSendException]؛ الاشتراك خلص: [ChatAccessDeniedException].
  /// API: `POST /conversations/{id}/messages` (`body`, `client_id`) → `MessageRead` (201 / 200 للمكرر؛ 403، 422، 429).
  /// TODO(API): ربط مع الجلسة (JWT) + 429 (حدود المحادثة).
  Future<ChatMessage> send(ChatConversation conversation, {required String body, required String clientId});

  /// رسائل جديدة بالمحادثة (رد الخبير، ونسخة رسالتك).
  /// API: WebSocket، الموضوع `chat:{conversation_id}` (حدث `chat_message`).
  /// TODO(API): الاشتراك بالـ WebSocket + `POST /conversations/{id}/read` لمؤشر القراءة.
  Stream<ChatMessage> incoming(ChatConversation conversation);
}

/// `ConversationRead` → domain (null لو ناقص)
ChatConversation? chatConversationFromJson(Json json) {
  final id = json.string('id');
  final expertId = json.string('expert_id');
  final userId = json.string('user_id');
  if (id == null || expertId == null || userId == null) return null;
  return ChatConversation(id: id, expertId: expertId, userId: userId, canSend: json.boolean('can_send') ?? true);
}

/// `MessageRead` → domain (null لو ناقص أو محذوف). [myUserId] = `ConversationRead.user_id`.
ChatMessage? chatMessageFromJson(Json json, {required String myUserId}) {
  final id = json.string('id');
  final conversationId = json.string('conversation_id');
  final senderId = json.string('sender_id');
  final body = json.string('body')?.trim();
  final createdAt = json.dateTime('created_at');
  if (id == null || conversationId == null || senderId == null || createdAt == null) return null;
  if (json.boolean('deleted') == true || body == null || body.isEmpty) return null;
  return ChatMessage(
    id: id,
    conversationId: conversationId,
    senderId: senderId,
    body: body,
    createdAt: createdAt,
    fromMe: senderId == myUserId,
    clientId: json.string('client_id'),
  );
}

/// محادثة محاكاة: الرسائل بالذاكرة (بتضل طول ما التطبيق مفتوح)، والخبير بيرد
/// بعد [replyDelay] برد جاهز (EN/AR حسب لغة الواجهة وقت الرد). كل شي بيطلع
/// كـ JSON حتى الـ mapper ينفحص. الشاشة بتقول "Simulated".
class SimulatedExpertChatRepository implements ExpertChatRepository {
  SimulatedExpertChatRepository({
    required Future<bool> Function(String expertId) hasChatAccess,
    required String Function() userId,
    required String Function() languageCode,
    bool Function()? isOnline,
    DateTime Function()? clock,
    this.latency = Duration.zero,
    this.replyDelay = const Duration(seconds: 2),
  })  : _hasChatAccess = hasChatAccess,
        _userId = userId,
        _languageCode = languageCode,
        _isOnline = isOnline ?? (() => true),
        _clock = clock ?? DateTime.now;

  final Future<bool> Function(String expertId) _hasChatAccess;
  final String Function() _userId;
  final String Function() _languageCode;
  final bool Function() _isOnline;
  final DateTime Function() _clock;
  final Duration latency;
  final Duration replyDelay;

  /// رسائل كل محادثة بشكل `MessageRead`، الأقدم أول
  final Map<String, List<Map<String, Object?>>> _rows = {};
  final Map<String, StreamController<ChatMessage>> _streams = {};
  final Set<Timer> _timers = {};
  var _nextId = 1;

  static String _conversationId(String expertId) => 'conv-$expertId';

  Future<void> _wait() async {
    if (latency > Duration.zero) await Future<void>.delayed(latency);
  }

  ChatConversation _conversation(String expertId) => chatConversationFromJson(Json({
        'id': _conversationId(expertId),
        'expert_id': expertId,
        'user_id': _userId(),
        'status': 'open',
        'can_send': true,
      }))!;

  @override
  Future<ChatConversation> open(String expertId) async {
    await _wait();
    if (!await _hasChatAccess(expertId)) throw const ChatAccessDeniedException();
    return _conversation(expertId);
  }

  @override
  Future<List<ChatMessage>> history(ChatConversation conversation) async {
    await _wait();
    if (!await _hasChatAccess(conversation.expertId)) throw const ChatAccessDeniedException();
    // شكل الصفحة متل الـ API (الأحدث أول) وبعدين بالترتيب للعرض
    final page = {'items': (_rows[conversation.id] ?? const []).reversed.toList(), 'next_before': null};
    return mapValid(Json(page).objects('items'), (j) => chatMessageFromJson(j, myUserId: conversation.userId))
        .reversed
        .toList();
  }

  @override
  Future<ChatMessage> send(ChatConversation conversation, {required String body, required String clientId}) async {
    await _wait();
    // الاتصال انقطع والطلب ماشي → ما وصل
    if (!_isOnline()) throw const ChatSendException();
    if (!await _hasChatAccess(conversation.expertId)) throw const ChatAccessDeniedException();
    final rows = _rows.putIfAbsent(conversation.id, () => []);
    for (final row in rows) {
      if (row['client_id'] == clientId) return chatMessageFromJson(Json(row), myUserId: conversation.userId)!;
    }
    final trimmed = body.trim();
    if (trimmed.isEmpty || trimmed.length > kChatMessageMaxLength) throw ArgumentError.value(body, 'body');
    final row = _row(conversation, senderId: conversation.userId, body: trimmed, clientId: clientId);
    rows.add(row);
    final message = chatMessageFromJson(Json(row), myUserId: conversation.userId)!;
    _emit(conversation, message);
    _scheduleReply(conversation, rows.where((r) => r['sender_id'] == conversation.userId).length - 1);
    return message;
  }

  @override
  Stream<ChatMessage> incoming(ChatConversation conversation) =>
      _streams.putIfAbsent(conversation.id, StreamController<ChatMessage>.broadcast).stream;

  void _emit(ChatConversation conversation, ChatMessage message) {
    final stream = _streams[conversation.id];
    if (stream != null && !stream.isClosed) stream.add(message);
  }

  Map<String, Object?> _row(
    ChatConversation conversation, {
    required String senderId,
    required String body,
    String? clientId,
  }) =>
      {
        'id': 'msg-${_nextId++}',
        'conversation_id': conversation.id,
        'sender_id': senderId,
        'body': body,
        'attachments': const <Object?>[],
        // الـ backend بيرجّع `client_id` للمرسل بس
        'client_id': clientId,
        'edited_at': null,
        'deleted': false,
        'created_at': _clock().toUtc().toIso8601String(),
      };

  void _scheduleReply(ChatConversation conversation, int index) {
    late final Timer timer;
    timer = Timer(replyDelay, () {
      _timers.remove(timer);
      final replies = _languageCode() == 'ar' ? _repliesAr : _repliesEn;
      final row = _row(conversation, senderId: conversation.expertId, body: replies[index % replies.length]);
      _rows.putIfAbsent(conversation.id, () => []).add(row);
      _emit(conversation, chatMessageFromJson(Json(row), myUserId: conversation.userId)!);
    });
    _timers.add(timer);
  }

  /// بيوقّف الردود المعلّقة ويسكّر الـ streams (لما الـ provider ينحذف)
  void dispose() {
    for (final t in _timers) {
      t.cancel();
    }
    _timers.clear();
    for (final s in _streams.values) {
      s.close();
    }
    _streams.clear();
  }

  // ردود جاهزة: رأي شخصي، بدون وعود ولا توصية بصفقة
  static const _repliesEn = [
    'Thanks, I’ve read your message. In my view, start with where the idea would be wrong: that’s where the stop goes. Which timeframe are you looking at?',
    'I’d wait for a candle to close beyond the level rather than react to the first touch. That’s my own opinion, not a recommendation.',
    'I keep the risk on each trade small and fixed, so one wrong idea doesn’t matter much. How much do you usually risk per trade?',
    'Around big data releases I usually step aside until the first move settles. Spreads can widen a lot in those minutes.',
    'Hard to say without seeing it. Tell me the instrument and timeframe and I’ll share how I would read it.',
  ];

  static const _repliesAr = [
    'شكرًا، قرأت رسالتك. برأيي ابدأ بالمكان الذي تصبح فيه الفكرة خاطئة: هناك يوضع وقف الخسارة. على أي إطار زمني تنظر؟',
    'أفضّل انتظار إغلاق شمعة بعد المستوى بدل التفاعل مع أول لمسة. هذا رأيي الشخصي، وليس توصية.',
    'أُبقي المخاطرة في كل صفقة صغيرة وثابتة، فلا تؤثر فكرة خاطئة واحدة كثيرًا. كم تخاطر عادة في الصفقة؟',
    'حول البيانات الاقتصادية الكبيرة أبتعد عادة حتى تهدأ الحركة الأولى. قد يتسع الفارق كثيرًا في تلك الدقائق.',
    'يصعب الحكم دون أن أراه. أخبرني بالأداة والإطار الزمني وسأشاركك كيف أقرؤه.',
  ];
}

final expertChatRepositoryProvider = Provider<ExpertChatRepository>(
  (ref) => apiSource(ref, ApiFeature.expertChat, simulated: () => _simulatedChat(ref)),
);

SimulatedExpertChatRepository _simulatedChat(Ref ref) {
  final repo = SimulatedExpertChatRepository(
    // نفس قاعدة الـ backend: اشتراك مش منتهي فيه `chat`
    hasChatAccess: (expertId) async => (await ref.read(expertSubscriptionsRepositoryProvider).mine())
        .any((s) => s.expertId == expertId && s.allowsChat),
    userId: () => switch (ref.read(authStateProvider)) {
      SignedIn(:final user) => user.id,
      _ => 'me',
    },
    languageCode: () => ref.read(localeProvider).languageCode,
    isOnline: () => ref.read(networkStatusProvider) == NetworkStatus.online,
    latency: const Duration(milliseconds: 500),
    replyDelay: const Duration(seconds: 2),
  );
  ref.onDispose(repo.dispose);
  return repo;
}
