// H4a: حالات تنبيه السعر Active → Triggered → Expired (State pattern)، الفحص
// على النبضات ومرة وحدة بس، الفحص عند الرجوع من الخلفية، الانتهاء (حتى
// والتطبيق مسكّر)، "Set again"، إشعار واحد بالضبط، Undo بيرجّع الحالة
// السابقة، التخزين بعد إعادة التشغيل، وأقسام Active / History بالواجهة.

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:trading_app/core/data/json.dart';
import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/storage/preferences_provider.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/features/alerts/data/alerts_repository.dart';
import 'package:trading_app/features/alerts/models/price_alert.dart';
import 'package:trading_app/features/alerts/view_models/alert_trigger.dart';
import 'package:trading_app/features/alerts/view_models/alerts_view_model.dart';
import 'package:trading_app/features/alerts/widgets/alerts_section.dart';
import 'package:trading_app/features/markets/data/market_data_repository.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/markets/models/market_models.dart';
import 'package:trading_app/features/markets/views/market_screen.dart';
import 'package:trading_app/features/notifications/data/notifications_repository.dart';
import 'package:trading_app/features/notifications/models/app_notification.dart';
import 'package:trading_app/features/notifications/view_models/notifications_view_model.dart';
import 'package:trading_app/features/notifications/views/notifications_screen.dart';

import '../../helpers/test_app.dart';

PriceAlert alertOf(
  String id, {
  String symbol = 'EUR/USD',
  AlertCondition condition = AlertCondition.crossesAbove,
  double value = 1.1,
  AlertStatus status = AlertStatus.active,
  Duration age = const Duration(hours: 1),
  DateTime? expiresAt,
  DateTime? triggeredAt,
  double? triggeredPrice,
  bool armed = true,
  String? note,
}) =>
    PriceAlert(
      id: id,
      symbol: symbol,
      condition: condition,
      value: value,
      status: status,
      createdAt: kTestNow.subtract(age),
      expiresAt: expiresAt,
      lastTriggeredAt: triggeredAt,
      triggeredPrice: triggeredPrice,
      armed: armed,
      note: note,
    );

Map<String, Object> storedAlerts(List<PriceAlert> list) =>
    {LocalAlertsRepository.storageKey: jsonEncode([for (final a in list) PriceAlertDto.toJson(a)])};

Quote q(String symbol, double price, [DateTime? at]) =>
    Quote(symbol: symbol, price: price, reference: price, time: at ?? kTestNow);

Future<SharedPreferences> prefsWith([Map<String, Object> values = const {}]) async {
  SharedPreferences.setMockInitialValues(values);
  return SharedPreferences.getInstance();
}

/// يخلّص كل الـ microtasks (طابور الـ ViewModel + التخزين الوهمي)
Future<void> flush() async {
  for (var i = 0; i < 20; i++) {
    await Future<void>.delayed(Duration.zero);
  }
}

/// سوق بنبضات يدوية
final class ManualMarket implements MarketDataRepository {
  final controller = StreamController<List<Quote>>.broadcast();
  List<Quote> snapshot = [q('EUR/USD', 1.08)];
  int quoteCalls = 0;

  @override
  bool get isSimulated => true;
  @override
  Future<List<Instrument>> instruments() async =>
      const [Instrument(symbol: 'EUR/USD', kind: MarketKind.forex, precision: 5)];
  @override
  Future<List<Candle>> candles(String symbol, Timeframe timeframe, {int limit = 300}) async => const [];
  @override
  Future<List<Quote>> quotes() async {
    quoteCalls++;
    return snapshot;
  }

  @override
  Stream<List<Quote>> ticks() => controller.stream;
}

/// repository محلي بتعديل/فحص بنتحكّم متى بيخلص
final class GatedRepo extends LocalAlertsRepository {
  GatedRepo(super.prefs, {super.clock});

  Completer<void>? setActiveGate;
  Completer<void>? applyGate;
  int applyCalls = 0;

  @override
  Future<PriceAlert> setActive(String id, {required bool active}) async {
    await setActiveGate?.future;
    return super.setActive(id, active: active);
  }

  @override
  Future<PriceAlert?> applyPrice(String id, {required double price, required DateTime at}) async {
    applyCalls++;
    await applyGate?.future;
    return super.applyPrice(id, price: price, at: at);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('state machine', () {
    test('allowed transitions only: Active ⇄ Paused, Active → Triggered, Active/Paused → Expired', () {
      expect(AlertStatus.active.next, {AlertStatus.paused, AlertStatus.triggered, AlertStatus.expired});
      expect(AlertStatus.paused.next, {AlertStatus.active, AlertStatus.expired});
      expect(AlertStatus.triggered.next, isEmpty);
      expect(AlertStatus.expired.next, isEmpty);
      expect(AlertStatus.paused.canMoveTo(AlertStatus.triggered), isFalse, reason: 'a paused alert never fires');

      final a = alertOf('a');
      final fired = a.moveTo(AlertStatus.triggered, at: kTestNow, price: 1.1002)!;
      expect(fired.state, isA<AlertTriggered>());
      expect(fired.lastTriggeredAt, kTestNow);
      expect(fired.triggeredPrice, 1.1002);
      expect(fired.moveTo(AlertStatus.triggered), isNull, reason: 'never twice');
      expect(fired.moveTo(AlertStatus.active), isNull);
      expect(a.moveTo(AlertStatus.expired)!.moveTo(AlertStatus.triggered), isNull, reason: 'expired never fires');
    });

    test('each state owns its actions: pause/resume only Active/Paused, Set again only Triggered, delete everywhere', () {
      expect(alertOf('a').state.actions, {AlertAction.pause, AlertAction.delete});
      expect(alertOf('a', status: AlertStatus.paused).state.actions, {AlertAction.resume, AlertAction.delete});
      expect(alertOf('a', status: AlertStatus.triggered, triggeredAt: kTestNow).state.actions,
          {AlertAction.setAgain, AlertAction.delete});
      expect(alertOf('a', status: AlertStatus.expired).state.actions, {AlertAction.delete});
    });

    test('crossing and reactsTo: rising ≥ level, falling ≤ level; unarmed waits for the start side', () {
      final up = alertOf('u', value: 1.1);
      expect(up.crossedBy(1.0999), isFalse);
      expect(up.crossedBy(1.1), isTrue);
      final down = alertOf('d', condition: AlertCondition.crossesBelow, value: 1.1);
      expect(down.crossedBy(1.1001), isFalse);
      expect(down.crossedBy(1.0999), isTrue);
      final waiting = alertOf('w', value: 1.1, armed: false);
      expect(waiting.reactsTo(1.2), isFalse, reason: 'still past the level: no fire');
      expect(waiting.reactsTo(1.05), isTrue, reason: 'back on the start side: arm');
      expect(alertOf('p', status: AlertStatus.paused).reactsTo(1.2), isFalse);
    });

    test('splitAlerts: Active (incl. paused, newest first) then History (newest event first)', () {
      final split = splitAlerts([
        alertOf('old-active', age: const Duration(hours: 5)),
        alertOf('t-old', status: AlertStatus.triggered, triggeredAt: kTestNow.subtract(const Duration(hours: 3))),
        alertOf('paused', status: AlertStatus.paused, age: const Duration(minutes: 5)),
        alertOf('expired', status: AlertStatus.expired, expiresAt: kTestNow.subtract(const Duration(hours: 1))),
        alertOf('t-new', status: AlertStatus.triggered, triggeredAt: kTestNow.subtract(const Duration(minutes: 30))),
      ]);
      expect(split.active.map((a) => a.id), ['paused', 'old-active']);
      expect(split.history.map((a) => a.id), ['t-new', 'expired', 't-old']);
    });

    test('Set again: same level, direction and note; waits for a new cross when the price is past it', () {
      final fired = alertOf('t',
          value: 1.1,
          note: 'breakout',
          status: AlertStatus.triggered,
          triggeredAt: kTestNow,
          expiresAt: kTestNow.add(const Duration(days: 6)),
          age: const Duration(days: 1));
      final later = kTestNow.add(const Duration(hours: 2));
      final again = AlertDraft.again(fired, now: later, current: 1.1003);
      expect(again.condition, AlertCondition.crossesAbove);
      expect(again.value, 1.1);
      expect(again.note, 'breakout');
      expect(again.expiresAt, later.add(const Duration(days: 7)), reason: 'same length of time');
      expect(again.armed, isFalse);
      expect(AlertDraft.again(fired, now: later, current: 1.09).armed, isTrue);
      expect(AlertDraft.again(alertOf('x', status: AlertStatus.triggered), now: later).armed, isFalse,
          reason: 'unknown price: wait for the start side');
    });

    test('DTO: H4a fields round trip; legacy rows derive the state; unknown status is dropped', () {
      final a = alertOf('a',
          status: AlertStatus.triggered,
          triggeredAt: kTestNow,
          triggeredPrice: 1.10012,
          expiresAt: kTestNow.add(const Duration(days: 1)),
          armed: false);
      expect(PriceAlertDto(Json(PriceAlertDto.toJson(a))).toDomain(), a);
      final legacy = {
        'id': 'l',
        'instrument': {'symbol': 'EUR/USD'},
        'condition': 'crosses_above',
        'value': 1.1,
        'created_at': '2026-10-19T10:00:00Z',
      };
      expect(PriceAlertDto(Json({...legacy, 'is_active': true})).toDomain()!.status, AlertStatus.active);
      expect(PriceAlertDto(Json({...legacy, 'is_active': false})).toDomain()!.status, AlertStatus.paused);
      expect(PriceAlertDto(Json({...legacy, 'status': 'snoozed'})).toDomain(), isNull);
      final body = PriceAlertDto.createBody(
          AlertDraft(symbol: 'EUR/USD', condition: AlertCondition.crossesAbove, value: 1.1, expiresAt: kTestNow));
      expect(body['expires_at'], kTestNow.toIso8601String());
      expect(body['repeat'], 'once');
    });
  });

  group('LocalAlertsRepository', () {
    test('applyPrice triggers once on the saved version and stores when + at what price', () async {
      final repo = LocalAlertsRepository(await prefsWith(), clock: () => kTestNow);
      final a = await repo.create(const AlertDraft(symbol: 'EUR/USD', condition: AlertCondition.crossesAbove, value: 1.1));
      expect(await repo.applyPrice(a.id, price: 1.0999, at: kTestNow), isNull);
      final fired = await repo.applyPrice(a.id, price: 1.10004, at: kTestNow);
      expect(fired!.status, AlertStatus.triggered);
      expect(fired.triggeredPrice, 1.10004);
      expect(await repo.applyPrice(a.id, price: 1.2, at: kTestNow), isNull, reason: 'never twice');
      expect(await repo.applyPrice(a.id, price: 1.0, at: kTestNow), isNull);
      expect((await repo.setActive(a.id, active: false)).status, AlertStatus.triggered, reason: 'no pause after fire');
    });

    test('an alert past its expiry never triggers, even if the price crosses', () async {
      final repo = LocalAlertsRepository(await prefsWith(), clock: () => kTestNow);
      final a = await repo.create(AlertDraft(
          symbol: 'EUR/USD', condition: AlertCondition.crossesAbove, value: 1.1, expiresAt: kTestNow.add(const Duration(days: 1))));
      final late = kTestNow.add(const Duration(days: 1));
      final result = await repo.applyPrice(a.id, price: 1.5, at: late);
      expect(result!.status, AlertStatus.expired);
      expect(await repo.applyPrice(a.id, price: 1.5, at: late), isNull);
    });

    test('expireDue: Active and Paused past expiry → Expired; Triggered stays', () async {
      final repo = LocalAlertsRepository(
          await prefsWith(storedAlerts([
            alertOf('a', expiresAt: kTestNow),
            alertOf('p', status: AlertStatus.paused, expiresAt: kTestNow.subtract(const Duration(minutes: 1))),
            alertOf('t', status: AlertStatus.triggered, triggeredAt: kTestNow, expiresAt: kTestNow),
            alertOf('later', expiresAt: kTestNow.add(const Duration(minutes: 1))),
          ])),
          clock: () => kTestNow);
      final changed = await repo.expireDue(kTestNow);
      expect(changed.map((a) => a.id).toSet(), {'a', 'p'});
      final byId = {for (final a in await repo.list()) a.id: a.status};
      expect(byId, {'a': AlertStatus.expired, 'p': AlertStatus.expired, 't': AlertStatus.triggered, 'later': AlertStatus.active});
    });

    test('unarmed (Set again past the level) arms on the start side, then fires on the next cross', () async {
      final repo = LocalAlertsRepository(await prefsWith(), clock: () => kTestNow);
      final a = await repo.create(
          const AlertDraft(symbol: 'EUR/USD', condition: AlertCondition.crossesAbove, value: 1.1, armed: false));
      expect(await repo.applyPrice(a.id, price: 1.1005, at: kTestNow), isNull);
      expect((await repo.applyPrice(a.id, price: 1.0995, at: kTestNow))!.armed, isTrue);
      expect((await repo.applyPrice(a.id, price: 1.1001, at: kTestNow))!.status, AlertStatus.triggered);
    });

    test('states survive a restart (same storage, new repository); corrupted storage = no alerts', () async {
      final prefs = await prefsWith();
      final first = LocalAlertsRepository(prefs, clock: () => kTestNow);
      final a = await first.create(const AlertDraft(symbol: 'EUR/USD', condition: AlertCondition.crossesAbove, value: 1.1));
      final b = await first.create(const AlertDraft(symbol: 'XAU/USD', condition: AlertCondition.crossesBelow, value: 2000));
      await first.applyPrice(a.id, price: 1.11, at: kTestNow);
      await first.setActive(b.id, active: false);

      final reopened = LocalAlertsRepository(prefs, clock: () => kTestNow);
      final byId = {for (final x in await reopened.list()) x.id: x};
      expect(byId[a.id]!.status, AlertStatus.triggered);
      expect(byId[a.id]!.triggeredPrice, 1.11);
      expect(byId[b.id]!.status, AlertStatus.paused);

      await prefs.setString(LocalAlertsRepository.storageKey, '{not json');
      expect(await LocalAlertsRepository(prefs).list(), isEmpty);
      await prefs.setString(LocalAlertsRepository.storageKey, jsonEncode([1, {'id': 'x'}]));
      expect(await LocalAlertsRepository(prefs).list(), isEmpty);
    });

    test('delete returns the saved version; restore puts it back with that state', () async {
      final repo = LocalAlertsRepository(await prefsWith(), clock: () => kTestNow);
      final a = await repo.create(const AlertDraft(symbol: 'EUR/USD', condition: AlertCondition.crossesAbove, value: 1.1));
      await repo.applyPrice(a.id, price: 1.2, at: kTestNow);
      final deleted = await repo.delete(a.id);
      expect(deleted!.status, AlertStatus.triggered);
      expect(await repo.delete(a.id), isNull);
      await repo.restore(deleted);
      expect((await repo.list()).single.status, AlertStatus.triggered);
    });
  });

  group('AlertsViewModel', () {
    late SharedPreferences prefs;
    late GatedRepo repo;
    late ProviderContainer c;
    late DateTime now;

    Future<void> setUpWith([Map<String, Object> values = const {}]) async {
      prefs = await prefsWith(values);
      now = kTestNow;
      repo = GatedRepo(prefs, clock: () => now);
      c = ProviderContainer(overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        alertsRepositoryProvider.overrideWithValue(repo),
        alertsClockProvider.overrideWithValue(() => now),
      ]);
      addTearDown(c.dispose);
      c.listen(alertsViewModelProvider, (_, __) {});
      await c.read(alertsViewModelProvider.future);
    }

    AlertsViewModel vm() => c.read(alertsViewModelProvider.notifier);
    PriceAlert byId(String id) => c.read(alertsViewModelProvider).requireValue.firstWhere((a) => a.id == id);

    test('expiry passed while the app was closed → Expired on the next start (at its expiry time)', () async {
      final expiry = kTestNow.subtract(const Duration(hours: 2));
      await setUpWith(storedAlerts([alertOf('a', expiresAt: expiry), alertOf('b')]));
      expect(byId('a').status, AlertStatus.expired);
      expect((byId('a').state as AlertExpired).at, expiry);
      expect(byId('b').status, AlertStatus.active);
      final reopened = LocalAlertsRepository(prefs);
      expect((await reopened.list()).firstWhere((a) => a.id == 'a').status, AlertStatus.expired, reason: 'saved');
    });

    test('rapid ticks around the level: triggers exactly once', () async {
      await setUpWith(storedAlerts([alertOf('a', value: 1.1)]));
      final results = await Future.wait([
        for (final p in [1.1001, 1.0999, 1.1002, 1.0998, 1.1003]) vm().checkQuotes({'EUR/USD': q('EUR/USD', p)}),
      ]);
      expect(results.expand((r) => r).map((a) => a.id), ['a']);
      expect(byId('a').status, AlertStatus.triggered);
      expect(byId('a').triggeredPrice, 1.1001);
      expect(await vm().checkQuotes({'EUR/USD': q('EUR/USD', 1.2)}), isEmpty);
    });

    test('a tick while the alert is being edited: the edit wins, the check uses the saved version', () async {
      await setUpWith(storedAlerts([alertOf('a', value: 1.1)]));
      repo.setActiveGate = Completer();
      final pausing = vm().setActive('a', active: false);
      expect(byId('a').status, AlertStatus.paused, reason: 'optimistic');
      final check = vm().checkQuotes({'EUR/USD': q('EUR/USD', 1.2)});
      repo.setActiveGate!.complete();
      await pausing;
      expect(await check, isEmpty);
      expect(byId('a').status, AlertStatus.paused);
      expect((await repo.list()).single.status, AlertStatus.paused);
    });

    test('deleting while it triggers: no resurrection; Undo restores Triggered (its real state)', () async {
      await setUpWith(storedAlerts([alertOf('a', value: 1.1)]));
      repo.applyGate = Completer();
      final check = vm().checkQuotes({'EUR/USD': q('EUR/USD', 1.2)});
      await flush();
      final removing = vm().remove('a');
      expect(c.read(alertsViewModelProvider).requireValue, isEmpty);
      repo.applyGate!.complete();
      expect((await check).single.id, 'a', reason: 'it fired before the delete was saved');
      final removed = (await removing)!;
      expect(c.read(alertsViewModelProvider).requireValue, isEmpty, reason: 'a late check does not bring it back');
      expect(removed.status, AlertStatus.triggered);
      await vm().undoRemove(removed);
      expect(byId('a').status, AlertStatus.triggered);
    });

    test('Undo of a delete restores the previous state (paused / expired), not a fresh Active', () async {
      await setUpWith(storedAlerts([
        alertOf('p', status: AlertStatus.paused),
        alertOf('e', status: AlertStatus.expired, expiresAt: kTestNow.subtract(const Duration(days: 1))),
      ]));
      for (final id in ['p', 'e']) {
        final before = byId(id);
        final removed = await vm().remove(id);
        await vm().undoRemove(removed!);
        expect(byId(id), before);
      }
    });

    test('expiry while running: the next check expires it and it never fires', () async {
      await setUpWith(storedAlerts([alertOf('a', value: 1.1, expiresAt: kTestNow.add(const Duration(days: 1)))]));
      now = kTestNow.add(const Duration(days: 1, seconds: 1));
      expect(await vm().checkQuotes({'EUR/USD': q('EUR/USD', 1.5, now)}), isEmpty);
      expect(byId('a').status, AlertStatus.expired);
    });

    test('Set again: a new Active alert, the triggered one stays in History; no instant re-fire', () async {
      await setUpWith(storedAlerts([alertOf('a', value: 1.1)]));
      await vm().checkQuotes({'EUR/USD': q('EUR/USD', 1.1002)});
      final again = (await vm().setAgain(byId('a'), current: q('EUR/USD', 1.1002)))!;
      expect(again.id, isNot('a'));
      expect(again.status, AlertStatus.active);
      expect(again.value, 1.1);
      expect(again.condition, AlertCondition.crossesAbove);
      expect(byId('a').status, AlertStatus.triggered);
      expect(await vm().checkQuotes({'EUR/USD': q('EUR/USD', 1.1002)}), isEmpty, reason: 'waits for a new cross');
      await vm().checkQuotes({'EUR/USD': q('EUR/USD', 1.0990)});
      final fired = await vm().checkQuotes({'EUR/USD': q('EUR/USD', 1.1001)});
      expect(fired.single.id, again.id);
      expect(await vm().setAgain(byId('a').moveTo(AlertStatus.expired) ?? alertOf('x', status: AlertStatus.expired)),
          isNull, reason: 'only a triggered alert can be set again');
    });

    test('no work on ticks that change nothing (no repository call)', () async {
      await setUpWith(storedAlerts([alertOf('a', value: 1.1)]));
      await vm().checkQuotes({'EUR/USD': q('EUR/USD', 1.05)});
      await vm().checkQuotes({'XAU/USD': q('XAU/USD', 3000)});
      expect(repo.applyCalls, 0);
    });
  });

  group('trigger from the quote stream + notification', () {
    late ManualMarket market;
    late SharedPreferences prefs;
    late SimulatedNotificationsRepository notifications;
    late ProviderContainer c;
    final binding = TestWidgetsFlutterBinding.instance;
    void lifecycle(List<AppLifecycleState> states) => states.forEach(binding.handleAppLifecycleStateChanged);

    Future<void> start([Map<String, Object> values = const {}]) async {
      market = ManualMarket();
      prefs = await prefsWith(values);
      // اللغة (localeProvider) بتنقرأ من التخزين الآمن
      FlutterSecureStorage.setMockInitialValues({'app_locale': 'en'});
      notifications = SimulatedNotificationsRepository(clock: () => kTestNow, prefs: prefs);
      c = ProviderContainer(overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        connectivityOverride(),
        marketDataRepositoryProvider.overrideWithValue(market),
        notificationsRepositoryProvider.overrideWithValue(notifications),
        alertsClockProvider.overrideWithValue(() => kTestNow),
      ]);
      addTearDown(() {
        lifecycle(const [AppLifecycleState.resumed]);
        c.dispose();
      });
      await c.read(instrumentsProvider.future);
      c.listen(notificationsViewModelProvider, (_, __) {});
      await c.read(notificationsViewModelProvider.future);
      c.listen(alertTriggerProvider, (_, __) {});
      await c.read(alertsViewModelProvider.future);
      await c.read(liveQuotesProvider.future);
      await flush();
    }

    List<AppNotification> alertNotifications() => [
          for (final n in c.read(notificationsViewModelProvider).requireValue)
            if (n.id.startsWith('alert-')) n,
        ];

    test('a tick across the level → Triggered + exactly one price-alert notification that opens the instrument',
        () async {
      await start(storedAlerts([alertOf('a', value: 1.085)]));
      market.controller.add([q('EUR/USD', 1.0849, kTestNow.add(const Duration(seconds: 2)))]);
      await flush();
      expect(alertNotifications(), isEmpty);

      for (final p in [1.08512, 1.0849, 1.0853, 1.0851]) {
        market.controller.add([q('EUR/USD', p, kTestNow.add(const Duration(seconds: 5)))]);
      }
      await flush();
      final alert = c.read(alertsViewModelProvider).requireValue.single;
      expect(alert.status, AlertStatus.triggered);
      expect(alert.triggeredPrice, 1.08512);
      final list = alertNotifications();
      expect(list, hasLength(1));
      expect(list.single.kind, NotificationKind.priceAlert);
      expect(list.single.symbol, 'EUR/USD');
      expect(list.single.title, 'EUR/USD reached 1.08500');
      expect(list.single.body, contains('1.08512'));
      expect(c.read(unreadNotificationsProvider), 4, reason: '3 seeded + the new one');

      // إعادة تشغيل: ما في إشعار تاني (التنبيه محفوظ Triggered والإشعار محفوظ)
      expect(await SimulatedNotificationsRepository(prefs: prefs).addPriceAlert(PriceAlertNotice(
              alertId: 'a', symbol: 'EUR/USD', level: '1.08500', price: '1.08512', at: kTestNow)),
          isFalse);
    });

    test('H4b: in-app channel or price-alert kind off → Triggered, but no in-app notification', () async {
      for (final stored in [
        {'channels': ['push', 'email'], 'kinds': ['priceAlert', 'opportunity', 'system']},
        {'channels': ['inApp'], 'kinds': ['opportunity', 'system']},
      ]) {
        await start({
          ...storedAlerts([alertOf('a', value: 1.085)]),
          'notification_preferences': jsonEncode(stored),
        });
        market.controller.add([q('EUR/USD', 1.0853, kTestNow.add(const Duration(seconds: 5)))]);
        await flush();
        expect(c.read(alertsViewModelProvider).requireValue.single.status, AlertStatus.triggered);
        expect(alertNotifications(), isEmpty, reason: '$stored');
        expect(await notifications.list(languageCode: 'en'), isNot(contains(predicate<AppNotification>((n) => n.id == 'alert-a'))));
      }
    });

    test('crossed while in the background → triggers once on resume (fresh price, no tick needed)', () async {
      await start(storedAlerts([alertOf('a', value: 1.085)]));
      lifecycle(const [AppLifecycleState.inactive, AppLifecycleState.hidden, AppLifecycleState.paused]);
      await flush();
      expect(market.controller.hasListener, isFalse, reason: 'ticks stop in the background');
      market.snapshot = [q('EUR/USD', 1.0861, kTestNow.add(const Duration(hours: 9)))];
      expect(c.read(alertsViewModelProvider).requireValue.single.status, AlertStatus.active);

      lifecycle(const [AppLifecycleState.hidden, AppLifecycleState.inactive, AppLifecycleState.resumed]);
      await flush();
      final alert = c.read(alertsViewModelProvider).requireValue.single;
      expect(alert.status, AlertStatus.triggered);
      expect(alert.triggeredPrice, 1.0861);
      expect(alertNotifications(), hasLength(1));

      // رجوع تاني + نبضات: لسّا إشعار واحد
      lifecycle(const [AppLifecycleState.inactive, AppLifecycleState.hidden, AppLifecycleState.paused]);
      lifecycle(const [AppLifecycleState.hidden, AppLifecycleState.inactive, AppLifecycleState.resumed]);
      market.controller.add([q('EUR/USD', 1.09, kTestNow.add(const Duration(hours: 10)))]);
      await flush();
      expect(alertNotifications(), hasLength(1));
    });

    test('resumed after a long background with the expiry passed → Expired, no notification', () async {
      await start(storedAlerts([alertOf('a', value: 1.085, expiresAt: kTestNow.subtract(const Duration(seconds: 1)))]));
      expect(c.read(alertsViewModelProvider).requireValue.single.status, AlertStatus.expired);
      market.controller.add([q('EUR/USD', 1.2, kTestNow.add(const Duration(seconds: 3)))]);
      await flush();
      expect(alertNotifications(), isEmpty);
    });
  });

  group('SimulatedNotificationsRepository.addPriceAlert', () {
    final notice = PriceAlertNotice(alertId: 'a1', symbol: 'XAU/USD', level: '2400.00', price: '2400.55', at: kTestNow);

    test('one notification per alert, stored across restarts with read/deleted; text in the request language',
        () async {
      final prefs = await prefsWith();
      final repo = SimulatedNotificationsRepository(clock: () => kTestNow, prefs: prefs);
      expect(await repo.addPriceAlert(notice), isTrue);
      expect(await repo.addPriceAlert(notice), isFalse);
      final en = (await repo.list(languageCode: 'en')).first;
      expect(en.id, 'alert-a1');
      expect(en.title, 'XAU/USD reached 2400.00');
      final ar = (await repo.list(languageCode: 'ar')).first;
      expect(ar.title, 'XAU/USD بلغ 2400.00');
      await repo.setRead('alert-a1', read: true);

      final reopened = SimulatedNotificationsRepository(clock: () => kTestNow, prefs: prefs);
      final again = (await reopened.list(languageCode: 'en')).where((n) => n.id == 'alert-a1').single;
      expect(again.isRead, isTrue);
      await reopened.delete('alert-a1');
      final third = SimulatedNotificationsRepository(clock: () => kTestNow, prefs: prefs);
      expect((await third.list(languageCode: 'en')).where((n) => n.id == 'alert-a1'), isEmpty);
      expect(await third.addPriceAlert(notice), isFalse, reason: 'a deleted one is not created again');
    });
  });

  group('screens', () {
    final history = [
      alertOf('active', symbol: 'EUR/USD', value: 1.2, expiresAt: kTestNow.add(const Duration(days: 1))),
      alertOf('paused', symbol: 'GBP/USD', condition: AlertCondition.crossesBelow, value: 1.1, status: AlertStatus.paused),
      alertOf('t-new',
          symbol: 'XAU/USD',
          value: 2400,
          status: AlertStatus.triggered,
          triggeredAt: kTestNow.subtract(const Duration(minutes: 30)),
          triggeredPrice: 2400.55),
      alertOf('expired',
          symbol: 'AUD/USD', value: 0.7, status: AlertStatus.expired, expiresAt: kTestNow.subtract(const Duration(hours: 1))),
      alertOf('t-old',
          symbol: 'USD/JPY',
          condition: AlertCondition.crossesBelow,
          value: 149,
          status: AlertStatus.triggered,
          triggeredAt: kTestNow.subtract(const Duration(hours: 3)),
          triggeredPrice: 148.987),
    ];

    Future<void> pumpAlerts(
      WidgetTester tester, {
      String locale = 'en',
      String theme = 'light',
      double height = 1600,
      List<Override> overrides = const [],
    }) async {
      usePhoneSize(tester, height: height);
      await tester.pumpWidget(await testScope(
        const TestApp(home: NotificationsScreen()),
        locale: locale,
        prefs: {themeModeStorageKey: theme, ...storedAlerts(history)},
        overrides: overrides,
      ));
      await tester.pumpAndSettle();
      await tester.tap(find.text(locale == 'en' ? 'Alerts · 2' : 'التنبيهات · 2'));
      await tester.pumpAndSettle();
    }

    testWidgets('Notifications → Alerts: Active section, then History newest first; count = active only',
        (tester) async {
      await pumpAlerts(tester);
      expect(top(tester, find.text('Active alerts')), lessThan(top(tester, find.text('Alert history'))));
      expect(top(tester, find.textContaining('EUR/USD · Rises')), lessThan(top(tester, find.text('Alert history'))));
      expect(top(tester, find.textContaining('GBP/USD · Falls')), lessThan(top(tester, find.text('Alert history'))));
      final xau = top(tester, find.textContaining('XAU/USD · Rises'));
      final aud = top(tester, find.textContaining('AUD/USD · Rises'));
      final jpy = top(tester, find.textContaining('USD/JPY · Falls'));
      expect(top(tester, find.text('Alert history')), lessThan(xau));
      expect(xau, lessThan(aud));
      expect(aud, lessThan(jpy));

      expect(find.textContaining('Triggered at 2400.55'), findsOneWidget);
      expect(find.textContaining('Triggered at 148.987'), findsOneWidget);
      expect(find.textContaining('Expired ·'), findsOneWidget);
      expect(find.textContaining('Active · Until '), findsOneWidget);
      expect(find.text('Set again'), findsNWidgets(2));
      expect(find.byTooltip('Pause'), findsOneWidget);
      expect(find.byTooltip('Resume'), findsOneWidget);
    });

    testWidgets('semantics: the state is part of each row ("Active", "Triggered at …", "Expired")', (tester) async {
      final handle = tester.ensureSemantics();
      await pumpAlerts(tester);
      expect(find.bySemanticsLabel(RegExp(r'^EUR/USD · Rises to 1\.20000, Active\. Until ')), findsOneWidget);
      expect(find.bySemanticsLabel(RegExp(r'^XAU/USD · Rises to 2400\.00, Triggered at 2400\.55\. ')), findsOneWidget);
      expect(find.bySemanticsLabel(RegExp(r'^AUD/USD · Rises to 0\.70000, Expired\. ')), findsOneWidget);
      expect(find.bySemanticsLabel(RegExp(r'^GBP/USD · Falls to 1\.10000, Paused')), findsOneWidget);
      handle.dispose();
    });

    testWidgets('Set again → a new Active alert; the triggered one stays in History', (tester) async {
      await pumpAlerts(tester);
      await tester.tap(find.text('Set again').first);
      await tester.pumpAndSettle();
      expect(find.text('Alert set: XAU/USD at 2400.00'), findsOneWidget);
      expect(find.text('Alerts · 3'), findsOneWidget);
      expect(find.textContaining('XAU/USD · Rises'), findsNWidgets(2));
      expect(find.textContaining('Triggered at 2400.55'), findsOneWidget);
    });

    testWidgets('delete from History + Undo brings it back Triggered (not a fresh Active)', (tester) async {
      await pumpAlerts(tester);
      await tester.drag(find.textContaining('XAU/USD · Rises'), const Offset(-600, 0));
      await tester.pumpAndSettle();
      expect(find.textContaining('XAU/USD · Rises'), findsNothing);
      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Triggered at 2400.55'), findsOneWidget);
      expect(find.text('Alerts · 2'), findsOneWidget);
    });

    testWidgets('only History left: the Active heading says there are none', (tester) async {
      usePhoneSize(tester, height: 1400);
      await tester.pumpWidget(await testScope(
        const TestApp(home: NotificationsScreen()),
        prefs: storedAlerts([history[2]]),
      ));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Alerts'));
      await tester.pumpAndSettle();
      expect(find.text('No active alerts.'), findsOneWidget);
      expect(find.text('Alert history'), findsOneWidget);
    });

    testWidgets('offline: the Alerts list says why alerts are not checked', (tester) async {
      await pumpAlerts(tester, overrides: [connectivityOverride(FakeConnectivitySource(NetworkStatus.offline))]);
      expect(find.text('You’re offline. Alerts are checked again when prices update.'), findsOneWidget);
    });

    for (final (locale, theme) in [('en', 'light'), ('ar', 'dark'), ('en', 'dark'), ('ar', 'light')]) {
      testWidgets('largest font ($locale, $theme): sections fit, nothing cut off, actions ≥ 48 dp', (tester) async {
        useLargeText(tester);
        await pumpAlerts(tester, locale: locale, theme: theme, height: 3600);
        expect(tester.takeException(), isNull);
        final rows = find.descendant(of: find.byType(AlertRow), matching: find.byType(RichText));
        expect(rows, findsWidgets);
        for (final element in rows.evaluate()) {
          final paragraph = element.renderObject! as RenderParagraph;
          expect(paragraph.didExceedMaxLines, isFalse, reason: '"${paragraph.text.toPlainText()}" is cut off');
        }
        for (final button in [...find.byType(TextButton).evaluate(), ...find.byType(IconButton).evaluate()]) {
          final size = tester.getSize(find.byWidget(button.widget));
          expect(size.width, greaterThanOrEqualTo(48));
          expect(size.height, greaterThanOrEqualTo(48));
        }
        if (locale == 'ar') {
          expect(find.textContaining('تم التنبيه عند 2400.55'), findsOneWidget);
          expect(find.text('اضبطه مجددًا'), findsNWidgets(2));
          expect(Directionality.of(tester.element(find.byType(AlertRow).first)), TextDirection.rtl);
        }
      });
    }

    testWidgets('Market screen: Active then History for this instrument; Set alert with a 1 week expiry',
        (tester) async {
      usePhoneSize(tester, height: 2600);
      await tester.pumpWidget(await testScope(
        const TestApp(home: MarketScreen(symbol: 'XAU/USD')),
        prefs: storedAlerts(history),
      ));
      await tester.pumpAndSettle();
      expect(find.text('Alert history'), findsOneWidget);
      expect(find.text('Active alerts'), findsNothing, reason: 'no active alert for XAU/USD yet');

      await tester.tap(find.text('Set alert'));
      await tester.pumpAndSettle();
      expect(find.text('No expiry'), findsOneWidget);
      await tester.tap(find.text('1 week'));
      await tester.pumpAndSettle();
      expect(tester.widget<ChoiceChip>(find.widgetWithText(ChoiceChip, '1 week')).selected, isTrue);
      await tester.tap(find.text('Create alert'));
      await tester.pumpAndSettle();

      final container = ProviderScope.containerOf(tester.element(find.byType(MarketScreen)));
      final created = container
          .read(alertsViewModelProvider)
          .requireValue
          .firstWhere((a) => a.symbol == 'XAU/USD' && a.status == AlertStatus.active);
      expect(created.expiresAt, kTestNow.add(const Duration(days: 7)));
      expect(find.text('Active alerts'), findsOneWidget);
      expect(top(tester, find.text('Active alerts')), lessThan(top(tester, find.text('Alert history'))));
      expect(find.textContaining('Active · Until '), findsOneWidget);
    });
  });
}

double top(WidgetTester tester, Finder f) => tester.getTopLeft(f).dy;
