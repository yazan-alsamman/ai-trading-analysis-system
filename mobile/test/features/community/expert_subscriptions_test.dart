// T2: اشتراكات الخبراء - تحويل الـ DTO (`PlanRead` / `ExpertCard` / `SubscriptionRead`)،
// الحفظ المحلي (بيضل بعد إعادة التشغيل، تالف → فاضي)، قاعدة الوصول، والـ ViewModel
// (ضغطتين = طلب واحد، بدون اتصال ما بيتغيّر شي، إلغاء + Undo).

import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:trading_app/core/data/json.dart';
import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/storage/preferences_provider.dart';
import 'package:trading_app/features/community/data/expert_subscriptions_repository.dart';
import 'package:trading_app/features/community/data/experts_repository.dart';
import 'package:trading_app/features/community/models/expert.dart';
import 'package:trading_app/features/community/models/expert_plan.dart';
import 'package:trading_app/features/community/models/expert_subscription.dart';
import 'package:trading_app/features/community/view_models/expert_subscriptions_view_model.dart';

import '../../helpers/test_app.dart';

Map<String, Object?> planRow({Object? price = '29.00', bool? active = true, Object? perks}) => {
      'id': 'plan-1',
      'expert_id': 'expert-1',
      'name': 'Gold desk',
      'description': 'Views on gold',
      'price': price,
      'currency': 'USD',
      'interval': 'month',
      'trial_days': 0,
      'perks': perks ?? {'chat': true, 'premium_posts': false, 'signals_feed': false},
      'is_active': active,
      'created_at': '2026-10-01T10:00:00Z',
    };

Map<String, Object?> subscriptionRow({String status = 'active', Map<String, Object?>? perks, String expertId = 'expert-1'}) => {
      'id': 'sub-1',
      'expert': {'id': expertId, 'display_name': 'Lina Haddad', 'role': 'expert'},
      'plan': {'id': 'plan-1', 'name': 'Gold desk'},
      'status': status,
      'price': '29.00',
      'currency': 'USD',
      'interval': 'month',
      'perks': perks ?? {'chat': true},
      'current_period_start': '2026-10-01T10:00:00Z',
      'current_period_end': '2026-10-31T10:00:00Z',
      'cancel_at_period_end': false,
      'canceled_at': null,
      'next_charge_at': null,
      'grace_ends_at': null,
      'ended_at': null,
      'payment_method': {'brand': 'visa', 'last4': '4242'},
      'created_at': '2026-10-01T10:00:00Z',
      'invoices': [],
    };

Future<Expert> lina() async => (await const SimulatedExpertsRepository().experts(languageCode: 'en')).first;

/// بيعدّ الطلبات (ضغطتين = طلب واحد)
final class CountingRepository implements ExpertSubscriptionsRepository {
  CountingRepository(this.inner);

  final ExpertSubscriptionsRepository inner;
  int subscribes = 0;
  int cancels = 0;

  @override
  Future<List<ExpertSubscription>> mine() => inner.mine();

  @override
  Future<ExpertSubscription> subscribe({required Expert expert, required ExpertPlan plan}) {
    subscribes++;
    return inner.subscribe(expert: expert, plan: plan);
  }

  @override
  Future<ExpertSubscription> cancel(String subscriptionId) {
    cancels++;
    return inner.cancel(subscriptionId);
  }

  @override
  Future<ExpertSubscription> resume(String subscriptionId) => inner.resume(subscriptionId);
}

void main() {
  group('DTOs', () {
    test('PlanRead: Decimal price as text, perks, interval', () {
      final plan = expertPlanFromJson(Json(planRow()))!;
      expect(plan.price, 29);
      expect(plan.currency, 'USD');
      expect(plan.interval, PlanInterval.month);
      expect(plan.includesChat, isTrue);
      expect(plan.description, 'Views on gold');
    });

    test('PlanRead: inactive, missing price or unknown interval → null', () {
      expect(expertPlanFromJson(Json(planRow(active: false))), isNull);
      expect(expertPlanFromJson(Json(planRow(price: null))), isNull);
      expect(expertPlanFromJson(Json({...planRow(), 'interval': 'week'})), isNull);
      expect(expertPlanFromJson(Json(planRow(price: '-1'))), isNull);
    });

    test('PlanBrief without perks falls back to the backend defaults (chat on)', () {
      final brief = expertPlanFromJson(const Json({
        'id': 'p',
        'name': 'Basic',
        'price': 9.5,
        'currency': 'EUR',
        'interval': 'year',
        'trial_days': 7,
      }))!;
      expect(brief.includesChat, isTrue);
      expect(brief.interval, PlanInterval.year);
      expect(brief.trialDays, 7);
    });

    test('ExpertCard / ExpertDetail field names (display_name, response_time_hint, plans, chat_enabled)', () {
      final expert = expertFromJson(Json({
        'id': 'expert-1',
        'display_name': 'Lina Haddad',
        'headline': 'Gold analyst',
        'markets': ['XAU/USD', 'gold'],
        'languages': ['Arabic'],
        'chat_enabled': false,
        'response_time_hint': 'Within a day',
        'plans': [planRow(active: false), {...planRow(), 'id': 'plan-2'}],
        'is_subscribed': true,
      }))!;
      expect(expert.name, 'Lina Haddad');
      expect(expert.availability, 'Within a day');
      expect(expert.chatEnabled, isFalse);
      expect(expert.markets, ['XAU/USD']);
      // أول خطة فعّالة
      expect(expert.plan?.id, 'plan-2');
    });

    test('ExpertCard with only cheapest_plan uses it; no plan at all → null', () {
      final withBrief = expertFromJson(const Json({
        'id': 'e',
        'display_name': 'A',
        'headline': 'B',
        'response_time_hint': 'C',
        'cheapest_plan': {'id': 'p', 'name': 'Basic', 'price': '5.00', 'currency': 'USD', 'interval': 'month'},
      }))!;
      expect(withBrief.plan?.price, 5);
      final none = expertFromJson(const Json({'id': 'e', 'display_name': 'A', 'headline': 'B', 'response_time_hint': 'C'}))!;
      expect(none.plan, isNull);
      expect(none.chatEnabled, isTrue);
    });

    test('SubscriptionRead → domain; card data is never kept', () {
      final s = expertSubscriptionFromJson(Json(subscriptionRow()))!;
      expect(s.expertId, 'expert-1');
      expect(s.planName, 'Gold desk');
      expect(s.status, SubscriptionStatus.active);
      expect(s.price, 29);
      expect(s.allowsChat, isTrue);
      final stored = expertSubscriptionToJson(s);
      expect(stored['payment_method'], isNull);
      expect(jsonEncode(stored), isNot(contains('4242')));
      expect(expertSubscriptionFromJson(Json(stored))?.id, 'sub-1');
    });

    test('access rule: past_due keeps chat, canceled / expired / no chat perk do not', () {
      ExpertSubscription? parse(String status, [Map<String, Object?>? perks]) =>
          expertSubscriptionFromJson(Json(subscriptionRow(status: status, perks: perks)));
      expect(parse('trialing')!.allowsChat, isTrue);
      expect(parse('past_due')!.allowsChat, isTrue);
      expect(parse('canceled')!.allowsChat, isFalse);
      expect(parse('expired')!.allowsChat, isFalse);
      expect(parse('active', {'chat': false})!.allowsChat, isFalse);
      expect(parse('active', {'chat': false})!.isEntitled, isTrue);
    });

    test('SubscriptionRead: unknown status or missing expert → null', () {
      expect(expertSubscriptionFromJson(Json(subscriptionRow(status: 'paused'))), isNull);
      expect(expertSubscriptionFromJson(Json({...subscriptionRow(), 'expert': null})), isNull);
      expect(expertSubscriptionFromJson(Json({...subscriptionRow(), 'current_period_end': 'x'})), isNull);
    });
  });

  group('LocalExpertSubscriptionsRepository', () {
    late SharedPreferences prefs;

    setUp(() async {
      SharedPreferences.setMockInitialValues({});
      prefs = await SharedPreferences.getInstance();
    });

    test('subscribe is saved and survives a restart (new instance, same storage)', () async {
      final expert = await lina();
      final s = await LocalExpertSubscriptionsRepository(prefs).subscribe(expert: expert, plan: expert.plan!);
      expect(s.allowsChat, isTrue);
      final afterRestart = await LocalExpertSubscriptionsRepository(prefs).mine();
      expect(afterRestart.single.id, s.id);
      expect(afterRestart.single.allowsChat, isTrue);
    });

    test('subscribing twice keeps one subscription', () async {
      final expert = await lina();
      final repo = LocalExpertSubscriptionsRepository(prefs);
      final a = await repo.subscribe(expert: expert, plan: expert.plan!);
      final b = await repo.subscribe(expert: expert, plan: expert.plan!);
      expect(b.id, a.id);
      expect(await repo.mine(), hasLength(1));
    });

    test('cancel ends access and persists; resume brings the same subscription back', () async {
      final expert = await lina();
      final repo = LocalExpertSubscriptionsRepository(prefs);
      final s = await repo.subscribe(expert: expert, plan: expert.plan!);
      await repo.cancel(s.id);
      final canceled = (await LocalExpertSubscriptionsRepository(prefs).mine()).single;
      expect(canceled.status, SubscriptionStatus.canceled);
      expect(canceled.allowsChat, isFalse);
      await repo.resume(s.id);
      final resumed = (await LocalExpertSubscriptionsRepository(prefs).mine()).single;
      expect(resumed.id, s.id);
      expect(resumed.allowsChat, isTrue);
    });

    test('corrupted or wrong-shaped storage → no subscriptions (never throws)', () async {
      for (final raw in ['{not json', '{"a": 1}', '42']) {
        SharedPreferences.setMockInitialValues({LocalExpertSubscriptionsRepository.storageKey: raw});
        final p = await SharedPreferences.getInstance();
        expect(await LocalExpertSubscriptionsRepository(p).mine(), isEmpty, reason: raw);
      }
    });

    test('invalid items and a second row for the same expert are dropped', () async {
      SharedPreferences.setMockInitialValues({
        LocalExpertSubscriptionsRepository.storageKey: jsonEncode([
          subscriptionRow(),
          {...subscriptionRow(status: 'canceled'), 'id': 'sub-old'},
          {'id': 'broken'},
          'text',
          subscriptionRow(expertId: 'expert-2'),
        ]),
      });
      final p = await SharedPreferences.getInstance();
      final list = await LocalExpertSubscriptionsRepository(p).mine();
      expect(list.map((s) => s.id), ['sub-1', 'sub-1']);
      expect(list.map((s) => s.expertId), ['expert-1', 'expert-2']);
    });
  });

  group('ExpertSubscriptionsViewModel', () {
    late ProviderContainer container;
    late CountingRepository repo;

    setUp(() async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      repo = CountingRepository(LocalExpertSubscriptionsRepository(prefs, latency: const Duration(milliseconds: 5)));
      container = ProviderContainer(overrides: [
        connectivityOverride(),
        sharedPreferencesProvider.overrideWithValue(prefs),
        expertSubscriptionsRepositoryProvider.overrideWithValue(repo),
      ]);
      addTearDown(container.dispose);
      await container.read(expertSubscriptionsProvider.future);
    });

    ExpertSubscriptionsViewModel vm() => container.read(expertSubscriptionsProvider.notifier);

    test('a double tap on Subscribe sends one request', () async {
      final expert = await lina();
      final results = await Future.wait([vm().subscribe(expert), vm().subscribe(expert)]);
      expect(repo.subscribes, 1);
      expect(results.whereType<ExpertSubscription>(), hasLength(1));
      expect(container.read(expertSubscriptionProvider(expert.id)).valueOrNull?.allowsChat, isTrue);
      // مشترك أصلًا: ما في طلب تاني
      await vm().subscribe(expert);
      expect(repo.subscribes, 1);
    });

    test('offline: nothing is sent and nothing changes', () async {
      final expert = await lina();
      container.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      await expectLater(vm().subscribe(expert), throwsA(isA<ExpertsOfflineException>()));
      expect(repo.subscribes, 0);
      expect(container.read(expertSubscriptionProvider(expert.id)).valueOrNull, isNull);
      expect(await repo.mine(), isEmpty);
    });

    test('unsubscribe returns the previous subscription; Undo restores it', () async {
      final expert = await lina();
      await vm().subscribe(expert);
      final previous = await vm().unsubscribe(expert.id);
      expect(previous?.allowsChat, isTrue);
      expect(container.read(expertSubscriptionProvider(expert.id)).valueOrNull?.allowsChat, isFalse);
      await vm().undoUnsubscribe(previous!);
      expect(container.read(expertSubscriptionProvider(expert.id)).valueOrNull?.allowsChat, isTrue);
      expect((await repo.mine()).single.allowsChat, isTrue);
    });

    test('unsubscribe twice quickly cancels once; not subscribed → null', () async {
      final expert = await lina();
      expect(await vm().unsubscribe(expert.id), isNull);
      await vm().subscribe(expert);
      await Future.wait([vm().unsubscribe(expert.id), vm().unsubscribe(expert.id)]);
      expect(repo.cancels, 1);
    });

    test('an expert without a plan cannot be subscribed to', () async {
      const noPlan = Expert(
        id: 'x',
        name: 'X',
        headline: 'h',
        specialties: [],
        markets: [],
        languages: [],
        availability: 'a',
      );
      expect(await vm().subscribe(noPlan), isNull);
      expect(repo.subscribes, 0);
    });

    test('state is read back after a restart (new container, same storage)', () async {
      final expert = await lina();
      await vm().subscribe(expert);
      final prefs = container.read(sharedPreferencesProvider);
      final fresh = ProviderContainer(overrides: [connectivityOverride(), sharedPreferencesProvider.overrideWithValue(prefs)]);
      addTearDown(fresh.dispose);
      final map = await fresh.read(expertSubscriptionsProvider.future);
      expect(map[expert.id]?.allowsChat, isTrue);
    });
  });
}
