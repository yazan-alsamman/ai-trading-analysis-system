import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/storage/preferences_provider.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/features/notifications/data/notification_permission_service.dart';
import 'package:trading_app/features/notifications/data/notification_preferences_repository.dart';
import 'package:trading_app/features/notifications/data/notifications_repository.dart';
import 'package:trading_app/features/notifications/data/push_device_repository.dart';
import 'package:trading_app/features/notifications/data/telegram_link_repository.dart';
import 'package:trading_app/features/notifications/models/app_notification.dart' as app;
import 'package:trading_app/features/notifications/models/notification_preferences.dart';
import 'package:trading_app/features/notifications/models/telegram_link.dart';
import 'package:trading_app/features/notifications/view_models/notifications_view_model.dart';
import 'package:trading_app/features/notifications/view_models/push_permission_view_model.dart';
import 'package:trading_app/features/notifications/view_models/telegram_link_view_model.dart';
import 'package:trading_app/features/notifications/views/notification_preferences_screen.dart';
import 'package:trading_app/features/notifications/widgets/push_channel_tile.dart';
import 'package:trading_app/features/notifications/widgets/telegram_connect_sheet.dart';

import '../../helpers/test_app.dart';

/// مستودع بيعدّ الطلبات (فوق المحاكاة الحقيقية)
class CountingTelegramRepository implements TelegramLinkRepository {
  CountingTelegramRepository(this.inner);

  final SimulatedTelegramLinkRepository inner;
  var codeRequests = 0;
  var checks = 0;
  var unlinks = 0;

  @override
  Future<TelegramLinkStatus> status() => inner.status();

  @override
  Future<TelegramLinkCode> requestCode() {
    codeRequests++;
    return inner.requestCode();
  }

  @override
  Future<TelegramLinkStatus> checkCode(String code) {
    checks++;
    return inner.checkCode(code);
  }

  @override
  Future<void> unlink() {
    unlinks++;
    return inner.unlink();
  }

  @override
  Future<void> restore(TelegramLinked link) => inner.restore(link);
}

const _delay = Duration(milliseconds: 1500);

Future<void> flush() async {
  for (var i = 0; i < 5; i++) {
    await Future<void>.delayed(Duration.zero);
  }
}

Map<String, Object> linkedPrefs({String? handle = '@trader_demo'}) => {
      SimulatedTelegramLinkRepository.storageKey:
          jsonEncode({'linked': true, 'handle': handle, 'linked_at': kTestNow.toIso8601String()}),
    };

void main() {
  late FakeClock clock;
  late SharedPreferences prefs;
  late CountingTelegramRepository repo;
  late FakeConnectivitySource network;

  Future<ProviderContainer> container({
    Map<String, Object> values = const {},
    List<Override> overrides = const [],
  }) async {
    SharedPreferences.setMockInitialValues(values);
    prefs = await SharedPreferences.getInstance();
    network = FakeConnectivitySource();
    repo = CountingTelegramRepository(
      SimulatedTelegramLinkRepository(prefs: prefs, clock: clock.call, codeFor: testTelegramCode),
    );
    final c = ProviderContainer(overrides: [
      sharedPreferencesProvider.overrideWithValue(prefs),
      connectivityOverride(network),
      telegramClockProvider.overrideWithValue(clock.call),
      telegramLinkRepositoryProvider.overrideWithValue(repo),
      ...overrides,
    ]);
    addTearDown(c.dispose);
    c.listen(networkStatusProvider, (_, __) {});
    await flush();
    return c;
  }

  setUp(() => clock = FakeClock());

  group('Telegram link: code and countdown', () {
    test('a code is valid 10 minutes, counts down, and is deterministic per request', () async {
      final c = await container();
      final code = await c.read(telegramLinkRepositoryProvider).requestCode();
      expect(code.code, 'TGK001');
      expect(code.botUsername, SimulatedTelegramLinkRepository.botUsername);
      expect(code.expiresAt, kTestNow.add(const Duration(minutes: 10)));
      expect(code.remaining(clock()), const Duration(minutes: 10));
      clock.advance(const Duration(minutes: 9, seconds: 59));
      expect(code.remaining(clock()), const Duration(seconds: 1));
      expect(code.isExpiredAt(clock()), isFalse);
      clock.advance(const Duration(seconds: 1));
      expect(code.isExpiredAt(clock()), isTrue);
      expect(code.remaining(clock()), Duration.zero);
      expect((await c.read(telegramLinkRepositoryProvider).requestCode()).code, 'TGK002');
    });

    test('an expired code is never reusable; a new code works; a replaced code is dead too', () async {
      final c = await container();
      final r = c.read(telegramLinkRepositoryProvider);
      final first = await r.requestCode();
      clock.advance(TelegramLinkCode.validity);
      await expectLater(r.checkCode(first.code), throwsA(isA<TelegramCodeExpiredException>()));
      clock.advance(-const Duration(minutes: 5));
      await expectLater(r.checkCode(first.code), throwsA(isA<TelegramCodeExpiredException>()),
          reason: 'still dead even if the clock goes back');

      final second = await r.requestCode();
      final third = await r.requestCode();
      await expectLater(r.checkCode(second.code), throwsA(isA<TelegramCodeExpiredException>()),
          reason: 'a newer code replaces it');
      expect(await r.checkCode(third.code), isA<TelegramLinked>());
      await expectLater(r.checkCode(third.code), throwsA(isA<TelegramCodeExpiredException>()),
          reason: 'used once');
      expect(repo.inner.issuedCodes.toSet(), hasLength(3));
    });

    test('controller: expired code → check sends nothing, "Get a new code" gives a new one', () async {
      final c = await container();
      c.listen(telegramCodeProvider, (_, __) {});
      final vm = c.read(telegramCodeProvider.notifier);
      await vm.requestCode();
      expect(c.read(telegramCodeProvider).code!.code, 'TGK001');
      clock.advance(const Duration(minutes: 10));
      vm.check();
      expect(c.read(telegramCodeProvider).issue, TelegramCodeIssue.expired);
      expect(c.read(telegramCodeProvider).checking, isFalse);
      expect(repo.checks, 0);
      await vm.requestCode();
      expect(c.read(telegramCodeProvider).code!.code, 'TGK002');
      expect(c.read(telegramCodeProvider).issue, isNull);
    });

    test('code expires while the check waits → "Code expired", not connected', () async {
      final c = await container(overrides: [telegramCheckDelayProvider.overrideWithValue(Duration.zero)]);
      c.listen(telegramCodeProvider, (_, __) {});
      final vm = c.read(telegramCodeProvider.notifier);
      await vm.requestCode();
      vm.check();
      clock.advance(const Duration(minutes: 11));
      await Future<void>.delayed(const Duration(milliseconds: 5));
      await flush();
      expect(c.read(telegramCodeProvider).issue, TelegramCodeIssue.expired);
      expect(c.read(telegramLinkProvider).valueOrNull, const TelegramNotLinked());
    });
  });

  group('Telegram link: connect / disconnect', () {
    test('Check connects after a short delay, turns the Telegram channel on, and survives a restart', () async {
      final c = await container(overrides: [telegramCheckDelayProvider.overrideWithValue(const Duration(milliseconds: 20))]);
      c.listen(telegramCodeProvider, (_, __) {});
      expect(await c.read(telegramLinkProvider.future), const TelegramNotLinked());
      expect(c.read(telegramChannelActiveProvider), isFalse);
      await c.read(telegramCodeProvider.notifier).requestCode();
      c.read(telegramCodeProvider.notifier).check();
      expect(c.read(telegramCodeProvider).checking, isTrue);
      expect(repo.checks, 0, reason: 'nothing sent before the delay');
      await Future<void>.delayed(const Duration(milliseconds: 40));
      await flush();
      expect(repo.checks, 1);
      final link = c.read(telegramLinkProvider).requireValue as TelegramLinked;
      expect(link.handle, '@trader_demo');
      expect(c.read(notificationPreferencesProvider).channels, contains(NotificationChannel.telegram));
      expect(c.read(telegramChannelActiveProvider), isTrue);

      // إعادة تشغيل: نفس التخزين، container جديد
      final restarted = ProviderContainer(overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        connectivityOverride(),
        telegramLinkRepositoryProvider.overrideWith((ref) => SimulatedTelegramLinkRepository(prefs: prefs)),
      ]);
      addTearDown(restarted.dispose);
      expect(await restarted.read(telegramLinkProvider.future), isA<TelegramLinked>());
      expect(restarted.read(telegramChannelActiveProvider), isTrue);
    });

    test('a double tap on Check acts once', () async {
      final c = await container(overrides: [telegramCheckDelayProvider.overrideWithValue(Duration.zero)]);
      c.listen(telegramCodeProvider, (_, __) {});
      final vm = c.read(telegramCodeProvider.notifier);
      await Future.wait([vm.requestCode(), vm.requestCode()]);
      expect(repo.codeRequests, 1, reason: 'double tap on Get code = one request');
      vm
        ..check()
        ..check();
      await Future<void>.delayed(const Duration(milliseconds: 5));
      await flush();
      expect(repo.checks, 1);
      expect(c.read(telegramLinkProvider).valueOrNull, isA<TelegramLinked>());
    });

    test('closing the sheet (dispose) cancels a pending check: nothing sent, not connected', () async {
      final c = await container(overrides: [telegramCheckDelayProvider.overrideWithValue(const Duration(milliseconds: 20))]);
      final sub = c.listen(telegramCodeProvider, (_, __) {});
      await c.read(telegramCodeProvider.notifier).requestCode();
      c.read(telegramCodeProvider.notifier).check();
      sub.close();
      await flush();
      await Future<void>.delayed(const Duration(milliseconds: 40));
      await flush();
      expect(repo.checks, 0);
      expect(await c.read(telegramLinkProvider.future), const TelegramNotLinked());
      expect(prefs.getString(SimulatedTelegramLinkRepository.storageKey), isNull);
    });

    test('offline: no code request, no check, no disconnect, and it says why', () async {
      final c = await container(values: linkedPrefs());
      c.listen(telegramCodeProvider, (_, __) {});
      network.emit(NetworkStatus.offline);
      await flush();
      await c.read(telegramCodeProvider.notifier).requestCode();
      expect(c.read(telegramCodeProvider).issue, TelegramCodeIssue.offline);
      expect(repo.codeRequests, 0);

      await c.read(telegramLinkProvider.future);
      await expectLater(c.read(telegramLinkProvider.notifier).disconnect(), throwsA(isA<TelegramOfflineException>()));
      expect(repo.unlinks, 0);
      expect(c.read(telegramLinkProvider).requireValue, isA<TelegramLinked>());
    });

    test('disconnect turns the channel off; Undo restores the link and the channel (on or off)', () async {
      for (final wasOn in [true, false]) {
        final c = await container(values: {
          ...linkedPrefs(),
          LocalNotificationPreferencesRepository.storageKey: jsonEncode({
            'channels': ['inApp', if (wasOn) 'telegram'],
            'kinds': ['priceAlert'],
          }),
        });
        final vm = c.read(telegramLinkProvider.notifier);
        final before = await c.read(telegramLinkProvider.future) as TelegramLinked;
        final undo = await vm.disconnect();
        expect(undo, isNotNull);
        expect(undo!.channelWasOn, wasOn);
        expect(c.read(telegramLinkProvider).requireValue, const TelegramNotLinked());
        expect(c.read(notificationPreferencesProvider).channels, isNot(contains(NotificationChannel.telegram)));
        expect(prefs.getString(SimulatedTelegramLinkRepository.storageKey), isNull);

        await vm.undoDisconnect(undo);
        expect(c.read(telegramLinkProvider).requireValue, before);
        expect(c.read(notificationPreferencesProvider).channels.contains(NotificationChannel.telegram), wasOn);
        expect(await SimulatedTelegramLinkRepository(prefs: prefs).status(), before, reason: 'restored on disk too');
      }
    });

    test('a double tap on Disconnect sends one request', () async {
      final c = await container(values: linkedPrefs());
      await c.read(telegramLinkProvider.future);
      final vm = c.read(telegramLinkProvider.notifier);
      final results = await Future.wait([vm.disconnect(), vm.disconnect()]);
      expect(repo.unlinks, 1);
      expect(results.whereType<TelegramDisconnect>(), hasLength(1));
    });

    test('stored Telegram channel without a link is not active (the toggle is off)', () async {
      final c = await container(values: {
        LocalNotificationPreferencesRepository.storageKey: jsonEncode({
          'channels': ['telegram'],
          'kinds': ['priceAlert'],
        }),
      });
      await c.read(telegramLinkProvider.future);
      expect(c.read(telegramChannelActiveProvider), isFalse);
    });
  });

  group('Notification permission', () {
    Future<(ProviderContainer, SimulatedNotificationPermissionService)> permissionContainer({bool allow = true}) async {
      SharedPreferences.setMockInitialValues({});
      final p = await SharedPreferences.getInstance();
      final service = SimulatedNotificationPermissionService(p, allow: allow);
      final c = ProviderContainer(overrides: [
        sharedPreferencesProvider.overrideWithValue(p),
        connectivityOverride(),
        notificationPermissionServiceProvider.overrideWithValue(service),
      ]);
      addTearDown(c.dispose);
      await c.read(pushPermissionProvider.future);
      return (c, service);
    }

    test('first turn-on shows "Why we ask" once; Continue → system asks → granted → Push on', () async {
      final (c, service) = await permissionContainer();
      expect(c.read(pushPermissionProvider).requireValue, PushPermission.notAsked);
      expect(c.read(pushChannelActiveProvider), isFalse, reason: 'default Push is stored on, but not allowed yet');
      var explained = 0;
      final result = await c.read(pushPermissionProvider.notifier).enable(explain: () async {
        explained++;
        return true;
      });
      expect(result, PushPermission.granted);
      expect(explained, 1);
      expect(service.requests, 1);
      expect(c.read(pushChannelActiveProvider), isTrue);

      // مرة تانية: مسموح، ما في شرح ولا سؤال
      await c.read(pushPermissionProvider.notifier).disable();
      expect(c.read(pushChannelActiveProvider), isFalse);
      await c.read(pushPermissionProvider.notifier).enable(explain: () async => throw StateError('no explain'));
      expect(service.requests, 1);
      expect(c.read(pushChannelActiveProvider), isTrue);
    });

    test('"Not now" asks nothing and keeps Push off', () async {
      final (c, service) = await permissionContainer();
      final result = await c.read(pushPermissionProvider.notifier).enable(explain: () async => false);
      expect(result, PushPermission.notAsked);
      expect(service.requests, 0);
      expect(c.read(notificationPreferencesProvider).channels, isNot(contains(NotificationChannel.push)));
    });

    test('denied → asked again (no explanation) → blocked → never asked again', () async {
      final (c, service) = await permissionContainer(allow: false);
      final vm = c.read(pushPermissionProvider.notifier);
      expect(await vm.enable(explain: () async => true), PushPermission.denied);
      expect(c.read(pushChannelActiveProvider), isFalse);
      expect(await vm.enable(explain: () async => throw StateError('shown only the first time')), PushPermission.blocked);
      expect(await vm.enable(explain: () async => true), PushPermission.blocked);
      expect(service.requests, 2);
      expect(c.read(notificationPreferencesProvider).channels, isNot(contains(NotificationChannel.push)));
    });

    test('a double tap on the Push toggle asks once', () async {
      final (c, service) = await permissionContainer();
      final vm = c.read(pushPermissionProvider.notifier);
      final results = await Future.wait([vm.enable(explain: () async => true), vm.enable(explain: () async => true)]);
      expect(results.whereType<PushPermission>(), hasLength(1));
      expect(service.requests, 1);
    });
  });

  group('Device token registration', () {
    late SimulatedPushDeviceRepository devices;
    late SimulatedPushTokenSource tokens;

    Future<ProviderContainer> start({
      PushPermission permission = PushPermission.granted,
      Map<String, Object> values = const {},
      NetworkStatus status = NetworkStatus.online,
    }) async {
      SharedPreferences.setMockInitialValues(values);
      final p = await SharedPreferences.getInstance();
      devices = SimulatedPushDeviceRepository();
      tokens = SimulatedPushTokenSource();
      network = FakeConnectivitySource(status);
      final c = ProviderContainer(overrides: [
        sharedPreferencesProvider.overrideWithValue(p),
        connectivityOverride(network),
        notificationPermissionServiceProvider.overrideWithValue(SimulatedNotificationPermissionService(p, initial: permission)),
        pushDeviceRepositoryProvider.overrideWithValue(devices),
        pushTokenSourceProvider.overrideWithValue(tokens),
      ]);
      addTearDown(c.dispose);
      prefs = p;
      c.listen(networkStatusProvider, (_, __) {});
      c.listen(pushRegistrationProvider, (_, __) {});
      await c.read(pushPermissionProvider.future);
      await flush();
      return c;
    }

    test('Push on + allowed → registerDeviceToken called once per token', () async {
      final c = await start();
      expect(devices.registered, ['simulated-device-token-1']);
      expect(c.read(pushRegistrationProvider), PushRegistration.registered);
      await c.read(pushRegistrationProvider.notifier).sync();
      await c.read(pushRegistrationProvider.notifier).sync();
      expect(devices.registered, hasLength(1));

      // token جديد (FCM refresh) = طلب جديد واحد
      tokens.value = 'simulated-device-token-2';
      await c.read(pushRegistrationProvider.notifier).sync();
      expect(devices.registered, ['simulated-device-token-1', 'simulated-device-token-2']);
    });

    test('already registered before a restart → not sent again', () async {
      await start(values: {PushRegistrationController.registeredKey: 'simulated-device-token-1'});
      expect(devices.registered, isEmpty);
    });

    test('offline → kept pending (stored), sent once when back online', () async {
      final c = await start(status: NetworkStatus.offline);
      expect(devices.registered, isEmpty);
      expect(c.read(pushRegistrationProvider), PushRegistration.pending);
      expect(prefs.getString(PushRegistrationController.pendingKey), 'simulated-device-token-1');
      network.emit(NetworkStatus.online);
      await flush();
      expect(devices.registered, ['simulated-device-token-1']);
      expect(prefs.getString(PushRegistrationController.pendingKey), isNull);
      network
        ..emit(NetworkStatus.offline)
        ..emit(NetworkStatus.online);
      await flush();
      expect(devices.registered, hasLength(1));
    });

    test('Push off, or not allowed → no registration attempted', () async {
      await start(values: {
        LocalNotificationPreferencesRepository.storageKey: jsonEncode({
          'channels': ['inApp'],
          'kinds': ['priceAlert'],
        }),
      });
      expect(devices.registered, isEmpty);
      for (final permission in [PushPermission.notAsked, PushPermission.denied, PushPermission.blocked]) {
        final c = await start(permission: permission);
        expect(devices.registered, isEmpty, reason: permission.name);
        expect(c.read(pushRegistrationProvider), PushRegistration.off);
      }
    });

    test('turning Push on later registers then (once)', () async {
      final c = await start(values: {
        LocalNotificationPreferencesRepository.storageKey: jsonEncode({
          'channels': ['inApp'],
          'kinds': ['priceAlert'],
        }),
      });
      await c.read(notificationPreferencesProvider.notifier).setChannel(NotificationChannel.push, true);
      await flush();
      expect(devices.registered, hasLength(1));
    });
  });

  group('In-app notifications follow the preferences', () {
    Future<List<app.AppNotification>> listWith(Map<String, Object?> stored) async {
      SharedPreferences.setMockInitialValues({LocalNotificationPreferencesRepository.storageKey: jsonEncode(stored)});
      FlutterSecureStorage.setMockInitialValues({'app_locale': 'en'});
      final p = await SharedPreferences.getInstance();
      final c = ProviderContainer(overrides: [
        sharedPreferencesProvider.overrideWithValue(p),
        connectivityOverride(),
        notificationsRepositoryProvider.overrideWithValue(SimulatedNotificationsRepository(clock: () => kTestNow)),
      ]);
      addTearDown(c.dispose);
      return c.read(notificationsViewModelProvider.future);
    }

    test('in-app on + all kinds → everything; opportunity kind off → no opportunities; in-app off → system only',
        () async {
      final all = await listWith({'channels': ['inApp'], 'kinds': ['priceAlert', 'opportunity', 'system']});
      expect(all.map((n) => n.kind).toSet(), app.NotificationKind.values.toSet());

      final noOpp = await listWith({'channels': ['inApp'], 'kinds': ['priceAlert', 'system']});
      expect(noOpp.where((n) => n.kind == app.NotificationKind.opportunity), isEmpty);
      expect(noOpp.where((n) => n.kind == app.NotificationKind.priceAlert), isNotEmpty);

      final noInApp = await listWith({'channels': ['push'], 'kinds': ['priceAlert', 'opportunity', 'system']});
      expect(noInApp.map((n) => n.kind).toSet(), {app.NotificationKind.system});
    });
  });

  // ── Widgets ────────────────────────────────────────────────

  group('Notification preferences screen', () {
    late FakeClock widgetClock;
    late CountingTelegramRepository widgetRepo;

    Future<void> pump(
      WidgetTester tester, {
      Map<String, Object> values = const {},
      String locale = 'en',
      List<Override> overrides = const [],
      double height = 1600,
    }) async {
      usePhoneSize(tester, height: height);
      widgetClock = FakeClock();
      await tester.pumpWidget(await testScope(
        const TestApp(home: NotificationPreferencesScreen()),
        prefs: values,
        locale: locale,
        overrides: [
          telegramClockProvider.overrideWithValue(widgetClock.call),
          telegramLinkRepositoryProvider.overrideWith((ref) => widgetRepo = CountingTelegramRepository(
                SimulatedTelegramLinkRepository(
                  prefs: ref.watch(sharedPreferencesProvider),
                  clock: widgetClock.call,
                  codeFor: testTelegramCode,
                ),
              )),
          ...overrides,
        ],
      ));
      await tester.pumpAndSettle();
    }

    Finder telegramSwitch() => find.descendant(
          of: find.ancestor(of: find.text('Telegram'), matching: find.byType(MergeSemantics)),
          matching: find.byType(Switch),
        );

    Finder pushSwitch() => find.descendant(
          of: find.ancestor(of: find.text('Push'), matching: find.byType(MergeSemantics)),
          matching: find.byType(Switch),
        );

    Future<void> openSheet(WidgetTester tester) async {
      await tester.tap(find.text('Connect Telegram'));
      await tester.pumpAndSettle();
    }

    testWidgets('not connected: Telegram toggle disabled with the reason; Connect opens the sheet with a code',
        (tester) async {
      await pump(tester);
      expect(find.text('Connect Telegram first to turn this on.'), findsOneWidget);
      expect(tester.widget<Switch>(telegramSwitch()).onChanged, isNull);
      expect(tester.widget<Switch>(telegramSwitch()).value, isFalse);

      await openSheet(tester);
      expect(find.byType(TelegramConnectSheet), findsOneWidget);
      expect(find.text('TGK001'), findsOneWidget);
      expect(find.text('@${SimulatedTelegramLinkRepository.botUsername}'), findsOneWidget);
      expect(find.text('Valid for 10:00'), findsOneWidget);
      expect(find.text('Check connection'), findsOneWidget);
      expect(find.text('Simulated'), findsOneWidget);
    });

    testWidgets('countdown ticks, then "Code expired" → "Get a new code" gives a new code', (tester) async {
      await pump(tester);
      await openSheet(tester);
      widgetClock.advance(const Duration(minutes: 8, seconds: 30));
      await tester.pump(const Duration(seconds: 1));
      expect(find.text('Valid for 1:30'), findsOneWidget);
      expect(find.bySemanticsLabel('Valid for about 2 min'), findsOneWidget, reason: 'spoken in minutes, not seconds');

      widgetClock.advance(const Duration(minutes: 1, seconds: 30));
      await tester.pump(const Duration(seconds: 1));
      expect(find.text('Code expired'), findsOneWidget);
      expect(find.text('TGK001'), findsNothing);
      expect(find.text('Check connection'), findsNothing);
      await tester.tap(find.text('Get a new code'));
      await tester.pumpAndSettle();
      expect(find.text('TGK002'), findsOneWidget);
      expect(find.text('Valid for 10:00'), findsOneWidget);
    });

    testWidgets('Check connection → connected: sheet closes, snackbar, handle shown, toggle on and enabled',
        (tester) async {
      await pump(tester);
      await openSheet(tester);
      await tester.tap(find.text('Check connection'));
      await tester.tap(find.text('Check connection'), warnIfMissed: false);
      await tester.pump();
      expect(widgetRepo.checks, 0);
      await tester.pump(_delay);
      await tester.pumpAndSettle();
      expect(widgetRepo.checks, 1);
      expect(find.byType(TelegramConnectSheet), findsNothing);
      expect(find.text('Telegram connected. Telegram notifications are on.'), findsOneWidget);
      expect(find.text('Connected as @trader_demo'), findsOneWidget);
      expect(tester.widget<Switch>(telegramSwitch()).value, isTrue);
      expect(tester.widget<Switch>(telegramSwitch()).onChanged, isNotNull);
      expect(find.text('Disconnect'), findsOneWidget);
    });

    testWidgets('Disconnect → channel off → Undo restores the link and the channel', (tester) async {
      await pump(tester, values: {
        ...linkedPrefs(),
        LocalNotificationPreferencesRepository.storageKey: jsonEncode({
          'channels': ['inApp', 'telegram'],
          'kinds': ['priceAlert', 'opportunity', 'system'],
        }),
      });
      expect(tester.widget<Switch>(telegramSwitch()).value, isTrue);
      await tester.tap(find.text('Disconnect'));
      await tester.pumpAndSettle();
      expect(find.text('Telegram disconnected. Telegram notifications are off.'), findsOneWidget);
      expect(tester.widget<Switch>(telegramSwitch()).value, isFalse);
      expect(tester.widget<Switch>(telegramSwitch()).onChanged, isNull);
      expect(find.text('Connect Telegram'), findsOneWidget);

      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();
      expect(find.text('Connected as @trader_demo'), findsOneWidget);
      expect(tester.widget<Switch>(telegramSwitch()).value, isTrue);
    });

    testWidgets('a double tap on Connect opens one sheet and requests one code', (tester) async {
      await pump(tester);
      await tester.tap(find.text('Connect Telegram'));
      await tester.tap(find.text('Connect Telegram'), warnIfMissed: false);
      await tester.pumpAndSettle();
      expect(find.byType(TelegramConnectSheet), findsOneWidget);
      expect(widgetRepo.codeRequests, 1);
    });

    testWidgets('closing the sheet cancels a pending check', (tester) async {
      await pump(tester);
      await openSheet(tester);
      await tester.tap(find.text('Check connection'));
      await tester.pump();
      await tester.tap(find.byTooltip('Close'));
      await tester.pumpAndSettle();
      await tester.pump(_delay * 2);
      await tester.pumpAndSettle();
      expect(widgetRepo.checks, 0);
      expect(find.text('Connect Telegram first to turn this on.'), findsOneWidget);
    });

    testWidgets('offline: the sheet says why and requests nothing; Try again works when back online',
        (tester) async {
      final source = FakeConnectivitySource(NetworkStatus.offline);
      await pump(tester, overrides: [connectivityOverride(source)]);
      // بالتطبيق شريط "غير متصل" بالـ shell بيقرأ الحالة من الأول
      ProviderScope.containerOf(tester.element(find.byType(NotificationPreferencesScreen))).read(networkStatusProvider);
      await tester.pumpAndSettle();
      await openSheet(tester);
      expect(find.text('You’re offline, so nothing was sent. Try again when you’re online.'), findsOneWidget);
      expect(widgetRepo.codeRequests, 0);
      source.emit(NetworkStatus.online);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('TGK001'), findsOneWidget);
    });

    testWidgets('Copy puts the code on the clipboard; the code reads left-to-right in Arabic', (tester) async {
      String? copied;
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, (call) async {
        if (call.method == 'Clipboard.setData') copied = (call.arguments as Map)['text'] as String;
        return null;
      });
      addTearDown(() => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, null));
      await pump(tester, locale: 'ar');
      await tester.tap(find.text('ربط تيليغرام'));
      await tester.pumpAndSettle();
      final code = find.text('TGK001');
      expect(code, findsOneWidget);
      expect(Directionality.of(tester.element(code)), TextDirection.ltr);
      expect(Directionality.of(tester.element(find.text('التحقق من الربط'))), TextDirection.rtl);
      await tester.tap(find.bySemanticsLabel('نسخ الرمز'));
      await tester.pump();
      expect(copied, 'TGK001');
      expect(find.text('تم النسخ'), findsOneWidget);
      await tester.pump(const Duration(seconds: 3));
    });

    testWidgets('Push not asked: first turn-on shows "Why we ask"; Continue → on', (tester) async {
      await pump(tester, values: {SimulatedNotificationPermissionService.storageKey: PushPermission.notAsked.name});
      expect(tester.widget<Switch>(pushSwitch()).value, isFalse);
      await tester.tap(find.text('Push'));
      await tester.pumpAndSettle();
      expect(find.byType(PushExplanationSheet), findsOneWidget);
      expect(find.text('Why we ask'), findsOneWidget);
      expect(find.textContaining('guarantee'), findsNothing);
      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();
      expect(find.byType(PushExplanationSheet), findsNothing);
      expect(tester.widget<Switch>(pushSwitch()).value, isTrue);
    });

    testWidgets('Push "Not now" keeps it off', (tester) async {
      await pump(tester, values: {SimulatedNotificationPermissionService.storageKey: PushPermission.notAsked.name});
      await tester.tap(find.text('Push'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Not now'));
      await tester.pumpAndSettle();
      expect(tester.widget<Switch>(pushSwitch()).value, isFalse);
    });

    testWidgets('Push denied: short state + settings hint, toggle still usable; blocked: only the hint, disabled',
        (tester) async {
      await pump(tester, values: {SimulatedNotificationPermissionService.storageKey: PushPermission.denied.name});
      expect(find.text('Not allowed on this phone'), findsOneWidget);
      expect(find.text('To use Push, allow notifications for this app in your phone’s Settings.'), findsOneWidget);
      expect(tester.widget<Switch>(pushSwitch()).onChanged, isNotNull);

      await pump(tester, values: {SimulatedNotificationPermissionService.storageKey: PushPermission.blocked.name});
      expect(find.text('Not allowed on this phone'), findsNothing);
      expect(find.text('To use Push, allow notifications for this app in your phone’s Settings.'), findsOneWidget);
      expect(tester.widget<Switch>(pushSwitch()).onChanged, isNull);
      expect(tester.widget<Switch>(pushSwitch()).value, isFalse);
    });

    testWidgets('Telegram status error → Try again', (tester) async {
      var fail = true;
      await pump(tester, overrides: [
        telegramLinkRepositoryProvider.overrideWith((ref) {
          final inner = SimulatedTelegramLinkRepository(prefs: ref.watch(sharedPreferencesProvider));
          return _FailingStatus(inner, () => fail);
        }),
      ]);
      expect(find.text('Couldn’t check your Telegram connection.'), findsOneWidget);
      fail = false;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Connect Telegram'), findsOneWidget);
    });

    for (final locale in ['en', 'ar']) {
      for (final dark in [false, true]) {
        testWidgets('text scale 2.0 ($locale, ${dark ? 'dark' : 'light'}): screen + both sheets fit, 48 dp, labelled',
            (tester) async {
          useLargeText(tester);
          final handle = tester.ensureSemantics();
          await pump(
            tester,
            locale: locale,
            height: 812,
            values: {
              SimulatedNotificationPermissionService.storageKey: PushPermission.denied.name,
              if (dark) themeModeStorageKey: ThemeMode.dark.name,
            },
          );
          expect(tester.takeException(), isNull);
          await tester.drag(find.byType(ListView), const Offset(0, -3000));
          await tester.pumpAndSettle();
          expect(tester.takeException(), isNull);

          final connect = find.text(locale == 'ar' ? 'ربط تيليغرام' : 'Connect Telegram');
          await tester.ensureVisible(connect);
          await tester.pumpAndSettle();
          expect(tester.getSize(find.ancestor(of: connect, matching: find.byType(OutlinedButton))).height,
              greaterThanOrEqualTo(48));
          await tester.tap(connect);
          await tester.pumpAndSettle();
          expect(tester.takeException(), isNull);
          await tester.drag(find.byType(SingleChildScrollView).last, const Offset(0, -2000));
          await tester.pumpAndSettle();
          expect(tester.takeException(), isNull);
          final check = find.text(locale == 'ar' ? 'التحقق من الربط' : 'Check connection');
          expect(check, findsOneWidget);
          expect(tester.getSize(find.ancestor(of: check, matching: find.byType(FilledButton))).height,
              greaterThanOrEqualTo(48));
          expect(find.bySemanticsLabel(locale == 'ar' ? 'نسخ الرمز' : 'Copy code'), findsOneWidget);
          for (final button in find.byType(ButtonStyleButton).evaluate()) {
            expect(tester.getSize(find.byWidget(button.widget)).height, greaterThanOrEqualTo(48));
          }
          await tester.tap(find.byTooltip(locale == 'ar' ? 'إغلاق' : 'Close'));
          await tester.pumpAndSettle();
          handle.dispose();
        });
      }
    }

    for (final locale in ['en', 'ar']) {
      testWidgets('"Why we ask" at text scale 2.0 ($locale): fits, buttons 48 dp', (tester) async {
        useLargeText(tester);
        await pump(
          tester,
          locale: locale,
          height: 812,
          values: {SimulatedNotificationPermissionService.storageKey: PushPermission.notAsked.name},
        );
        final push = find.text(locale == 'ar' ? 'إشعارات الهاتف' : 'Push');
        await tester.tap(push.first);
        await tester.pumpAndSettle();
        expect(find.byType(PushExplanationSheet), findsOneWidget);
        expect(tester.takeException(), isNull);
        await tester.drag(find.byType(SingleChildScrollView).last, const Offset(0, -2000));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        for (final button in find.descendant(of: find.byType(PushExplanationSheet), matching: find.byType(ButtonStyleButton)).evaluate()) {
          expect(tester.getSize(find.byWidget(button.widget)).height, greaterThanOrEqualTo(48));
        }
      });
    }

    testWidgets('reduced motion: the sheet is fully open on the next frame', (tester) async {
      tester.platformDispatcher.accessibilityFeaturesTestValue = const FakeAccessibilityFeatures(disableAnimations: true);
      addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
      await pump(tester);
      await tester.tap(find.text('Connect Telegram'));
      await tester.pump();
      await tester.pump();
      final opened = tester.getTopLeft(find.byType(TelegramConnectSheet)).dy;
      await tester.pump(const Duration(milliseconds: 100));
      expect(tester.getTopLeft(find.byType(TelegramConnectSheet)).dy, opened, reason: 'no slide-in');
      expect(tester.hasRunningAnimations, isFalse);
    });
  });
}

class _FailingStatus implements TelegramLinkRepository {
  _FailingStatus(this.inner, this.fail);

  final TelegramLinkRepository inner;
  final bool Function() fail;

  @override
  Future<TelegramLinkStatus> status() async {
    if (fail()) throw Exception('status failed');
    return inner.status();
  }

  @override
  Future<TelegramLinkCode> requestCode() => inner.requestCode();

  @override
  Future<TelegramLinkStatus> checkCode(String code) => inner.checkCode(code);

  @override
  Future<void> unlink() => inner.unlink();

  @override
  Future<void> restore(TelegramLinked link) => inner.restore(link);
}
