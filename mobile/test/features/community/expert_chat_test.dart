// T2: محادثة الخبير - DTO (`ConversationRead` / `MessageRead`)، الـ repository المحاكى
// (قاعدة الوصول، `client_id` ما بيتكرر، رد محاكى EN/AR بعد مهلة، بدون اتصال)، والـ
// ViewModel (إرسال، فشل + إعادة محاولة، مسودة بدون اتصال، ضغطتين، تسكير الشاشة وقت الإرسال).

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:trading_app/core/data/json.dart';
import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/storage/preferences_provider.dart';
import 'package:trading_app/features/community/data/expert_chat_repository.dart';
import 'package:trading_app/features/community/data/expert_subscriptions_repository.dart';
import 'package:trading_app/features/community/data/experts_repository.dart';
import 'package:trading_app/features/community/models/chat_message.dart';
import 'package:trading_app/features/community/models/expert.dart';
import 'package:trading_app/features/community/view_models/expert_chat_view_model.dart';
import 'package:trading_app/features/community/view_models/expert_subscriptions_view_model.dart';

import '../../helpers/test_app.dart';

const _conversation = ChatConversation(id: 'conv-expert-1', expertId: 'expert-1', userId: 'me');
const _replyDelay = Duration(milliseconds: 40);

Future<Expert> lina() async => (await const SimulatedExpertsRepository().experts(languageCode: 'en')).first;

/// محادثة محاكاة بمهلات قصيرة؛ [failures] = كم إرسال جاي بيفشل
class TestChatRepository extends SimulatedExpertChatRepository {
  TestChatRepository({required super.hasChatAccess, String language = 'en', super.isOnline})
      : super(
          userId: () => 'me',
          languageCode: () => language,
          latency: const Duration(milliseconds: 5),
          replyDelay: _replyDelay,
        );

  int failures = 0;
  final List<String> sentClientIds = [];

  @override
  Future<ChatMessage> send(ChatConversation conversation, {required String body, required String clientId}) async {
    sentClientIds.add(clientId);
    if (failures > 0) {
      failures--;
      await Future<void>.delayed(const Duration(milliseconds: 5));
      throw const ChatSendException();
    }
    return super.send(conversation, body: body, clientId: clientId);
  }
}

void main() {
  group('DTOs', () {
    test('ConversationRead → domain', () {
      final c = chatConversationFromJson(const Json({
        'id': 'c1',
        'expert_id': 'e1',
        'user_id': 'u1',
        'can_send': false,
        'status': 'open',
      }))!;
      expect((c.id, c.expertId, c.userId, c.canSend), ('c1', 'e1', 'u1', false));
      expect(chatConversationFromJson(const Json({'id': 'c1'})), isNull);
    });

    test('MessageRead: mine vs expert by sender_id; deleted / empty / no date → null', () {
      Map<String, Object?> row({String sender = 'me', Object? body = 'Hi', bool deleted = false, Object? at = '2026-10-21T14:05:00Z'}) =>
          {
            'id': 'm1',
            'conversation_id': 'c1',
            'sender_id': sender,
            'body': body,
            'attachments': [],
            'client_id': 'abc',
            'edited_at': null,
            'deleted': deleted,
            'created_at': at,
          };
      final mine = chatMessageFromJson(Json(row()), myUserId: 'me')!;
      expect(mine.fromMe, isTrue);
      expect(mine.clientId, 'abc');
      expect(mine.status, ChatMessageStatus.sent);
      expect(mine.createdAt, DateTime.utc(2026, 10, 21, 14, 5));
      expect(chatMessageFromJson(Json(row(sender: 'expert-1')), myUserId: 'me')!.fromMe, isFalse);
      expect(chatMessageFromJson(Json(row(deleted: true, body: null)), myUserId: 'me'), isNull);
      expect(chatMessageFromJson(Json(row(body: '   ')), myUserId: 'me'), isNull);
      expect(chatMessageFromJson(Json(row(at: null)), myUserId: 'me'), isNull);
    });
  });

  group('SimulatedExpertChatRepository', () {
    test('access rule: no chat subscription → open / history / send are refused', () async {
      final repo = TestChatRepository(hasChatAccess: (_) async => false);
      addTearDown(repo.dispose);
      await expectLater(repo.open('expert-1'), throwsA(isA<ChatAccessDeniedException>()));
      await expectLater(repo.history(_conversation), throwsA(isA<ChatAccessDeniedException>()));
      await expectLater(repo.send(_conversation, body: 'Hi', clientId: 'a'), throwsA(isA<ChatAccessDeniedException>()));
    });

    test('a retry with the same client_id does not duplicate the message', () async {
      final repo = TestChatRepository(hasChatAccess: (_) async => true);
      addTearDown(repo.dispose);
      final conversation = await repo.open('expert-1');
      final a = await repo.send(conversation, body: 'Hello', clientId: 'same');
      final b = await repo.send(conversation, body: 'Hello', clientId: 'same');
      expect(b.id, a.id);
      expect(await repo.history(conversation), hasLength(1));
    });

    for (final (language, start) in [('en', 'Thanks'), ('ar', 'شكرًا')]) {
      test('the expert answers after a short delay with a canned reply ($language)', () async {
        final repo = TestChatRepository(hasChatAccess: (_) async => true, language: language);
        addTearDown(repo.dispose);
        final conversation = await repo.open('expert-1');
        final incoming = <ChatMessage>[];
        repo.incoming(conversation).listen(incoming.add);
        await repo.send(conversation, body: 'Hi', clientId: 'c1');
        expect(incoming.where((m) => !m.fromMe), isEmpty);
        await Future<void>.delayed(_replyDelay * 2);
        final reply = incoming.where((m) => !m.fromMe).single;
        expect(reply.body, startsWith(start));
        expect(reply.senderId, 'expert-1');
        final history = await repo.history(conversation);
        expect(history.map((m) => m.fromMe), [true, false]);
      });
    }

    test('offline while sending: nothing is stored', () async {
      final repo = TestChatRepository(hasChatAccess: (_) async => true, isOnline: () => false);
      addTearDown(repo.dispose);
      final conversation = await repo.open('expert-1');
      await expectLater(repo.send(conversation, body: 'Hi', clientId: 'x'), throwsA(isA<ChatSendException>()));
      expect(await repo.history(conversation), isEmpty);
    });

    test('dispose cancels pending replies', () async {
      final repo = TestChatRepository(hasChatAccess: (_) async => true);
      final conversation = await repo.open('expert-1');
      await repo.send(conversation, body: 'Hi', clientId: 'x');
      repo.dispose();
      await Future<void>.delayed(_replyDelay * 2);
      expect((await repo.history(conversation)).where((m) => !m.fromMe), isEmpty);
    });
  });

  group('ExpertChatViewModel', () {
    late ProviderContainer container;
    late TestChatRepository chat;
    late Expert expert;

    setUp(() async {
      SharedPreferences.setMockInitialValues({});
      FlutterSecureStorage.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      expert = await lina();
      final subscriptions = LocalExpertSubscriptionsRepository(prefs);
      chat = TestChatRepository(
        hasChatAccess: (id) async => (await subscriptions.mine()).any((s) => s.expertId == id && s.allowsChat),
        isOnline: () => container.read(networkStatusProvider) == NetworkStatus.online,
      );
      container = ProviderContainer(overrides: [
        connectivityOverride(),
        sharedPreferencesProvider.overrideWithValue(prefs),
        expertSubscriptionsRepositoryProvider.overrideWithValue(subscriptions),
        expertChatRepositoryProvider.overrideWithValue(chat),
      ]);
      addTearDown(() {
        container.dispose();
        chat.dispose();
      });
    });

    Future<ProviderSubscription<AsyncValue<ExpertChatState>>> openChat() async {
      final sub = container.listen(expertChatViewModelProvider(expert.id), (_, __) {});
      await container.read(expertChatViewModelProvider(expert.id).future);
      return sub;
    }

    ExpertChatViewModel vm() => container.read(expertChatViewModelProvider(expert.id).notifier);
    List<ChatMessage> messages() => container.read(expertChatViewModelProvider(expert.id)).requireValue.messages;

    Future<void> subscribe() => container.read(expertSubscriptionsProvider.notifier).subscribe(expert);

    test('not subscribed → locked, and nothing can be sent', () async {
      await openChat();
      expect(container.read(expertChatViewModelProvider(expert.id)).requireValue.access, ChatAccess.locked);
      expect(vm().send('Hi'), ChatSendResult.locked);
      expect(chat.sentClientIds, isEmpty);
    });

    test('subscribing unlocks the chat; unsubscribing locks it again', () async {
      await openChat();
      await subscribe();
      await container.read(expertChatViewModelProvider(expert.id).future);
      expect(container.read(expertChatViewModelProvider(expert.id)).requireValue.access, ChatAccess.open);
      await container.read(expertSubscriptionsProvider.notifier).unsubscribe(expert.id);
      await container.read(expertChatViewModelProvider(expert.id).future);
      expect(container.read(expertChatViewModelProvider(expert.id)).requireValue.access, ChatAccess.locked);
    });

    test('send: shows "sending" at once, then "sent", then the simulated reply arrives', () async {
      await subscribe();
      await openChat();
      expect(vm().send('  How do you read gold today?  '), ChatSendResult.accepted);
      expect(messages().single.status, ChatMessageStatus.sending);
      expect(messages().single.body, 'How do you read gold today?');
      await vm().idle;
      expect(messages().single.status, ChatMessageStatus.sent);
      await Future<void>.delayed(_replyDelay * 2);
      expect(messages().map((m) => m.fromMe), [true, false]);
    });

    test('failure → "not sent"; retry uses the same client_id and succeeds', () async {
      await subscribe();
      await openChat();
      chat.failures = 1;
      vm().send('Hello');
      await vm().idle;
      final failed = messages().single;
      expect(failed.status, ChatMessageStatus.failed);
      expect(vm().retry(failed.clientId!), ChatSendResult.accepted);
      expect(messages().single.status, ChatMessageStatus.sending);
      await vm().idle;
      expect(messages().single.status, ChatMessageStatus.sent);
      expect(chat.sentClientIds, [failed.clientId, failed.clientId]);
      expect(await chat.history(const ChatConversation(id: 'conv-expert-1', expertId: 'expert-1', userId: 'me')),
          hasLength(1));
    });

    test('offline: nothing is sent, nothing is added (the screen keeps the draft)', () async {
      await subscribe();
      await openChat();
      container.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      expect(vm().send('Draft text'), ChatSendResult.offline);
      expect(messages(), isEmpty);
      expect(chat.sentClientIds, isEmpty);
    });

    test('offline retry is refused; the message stays "not sent"', () async {
      await subscribe();
      await openChat();
      chat.failures = 1;
      vm().send('Hello');
      await vm().idle;
      container.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      expect(vm().retry(messages().single.clientId!), ChatSendResult.offline);
      expect(messages().single.status, ChatMessageStatus.failed);
    });

    test('a double tap on Send sends one message', () async {
      await subscribe();
      await openChat();
      expect(vm().send('Hi'), ChatSendResult.accepted);
      expect(vm().send('Hi'), ChatSendResult.ignored);
      await vm().idle;
      expect(messages().where((m) => m.fromMe), hasLength(1));
      expect(chat.sentClientIds, hasLength(1));
      // بعد ما وصلت، نفس النص مرة تانية = رسالة جديدة
      expect(vm().send('Hi'), ChatSendResult.accepted);
      await vm().idle;
      expect(chat.sentClientIds, hasLength(2));
    });

    test('empty or too long messages are ignored', () async {
      await subscribe();
      await openChat();
      expect(vm().send('   '), ChatSendResult.ignored);
      expect(vm().send('x' * (kChatMessageMaxLength + 1)), ChatSendResult.ignored);
      expect(messages(), isEmpty);
    });

    test('leaving the screen while sending: no error, the message still arrives', () async {
      await subscribe();
      final sub = await openChat();
      final model = vm();
      model.send('Sent while leaving');
      final delivery = model.idle;
      sub.close();
      await Future<void>.delayed(Duration.zero);
      await delivery;
      // فتح الشاشة من جديد: الرسالة موجودة
      await openChat();
      expect(messages().single.body, 'Sent while leaving');
      expect(messages().single.status, ChatMessageStatus.sent);
    });

    test('offline first load → offline state; back online reloads by itself', () async {
      await subscribe();
      container.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      container.listen(expertChatViewModelProvider(expert.id), (_, __) {});
      await expectLater(
        container.read(expertChatViewModelProvider(expert.id).future),
        throwsA(isA<ChatOfflineException>()),
      );
      container.read(networkStatusProvider.notifier).set(NetworkStatus.online);
      await Future<void>.delayed(Duration.zero);
      final state = await container.read(expertChatViewModelProvider(expert.id).future);
      expect(state.access, ChatAccess.open);
    });
  });
}
