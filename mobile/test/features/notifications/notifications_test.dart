// اختبارات مركز الإشعارات (Stage C): الـ DTO، القائمة والفلاتر، السحب
// (مقروء / حذف + Undo)، "تعليم الكل"، شارة الجرس، قسم Alerts، العربي والخط الكبير.

import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/core/data/json.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/core/widgets/app_illustration.dart';
import 'package:trading_app/features/alerts/models/price_alert.dart';
import 'package:trading_app/features/alerts/view_models/alerts_view_model.dart';
import 'package:trading_app/features/markets/views/market_screen.dart';
import 'package:trading_app/features/notifications/data/notifications_repository.dart';
import 'package:trading_app/features/notifications/models/app_notification.dart';
import 'package:trading_app/features/notifications/views/notifications_screen.dart';
import 'package:trading_app/features/notifications/view_models/notifications_view_model.dart';
import 'package:trading_app/features/notifications/widgets/notification_row.dart';

import '../../helpers/test_app.dart';

/// مستودع فاضي (حالة الفراغ)
final class _EmptyNotifications implements NotificationsRepository {
  @override
  Future<List<AppNotification>> list({required String languageCode}) async => const [];
  @override
  Future<void> setRead(String id, {required bool read}) async {}
  @override
  Future<void> markAllRead() async {}
  @override
  Future<void> delete(String id) async {}
  @override
  Future<void> restore(String id) async {}
  @override
  Future<bool> addPriceAlert(PriceAlertNotice notice) async => false;
}

final class _FailingNotifications extends _EmptyNotifications {
  @override
  Future<List<AppNotification>> list({required String languageCode}) async => throw StateError('offline');
}

Future<void> pumpNotifications(
  WidgetTester tester, {
  String locale = 'en',
  String theme = 'light',
  double height = 1200,
  List<Override> overrides = const [],
}) async {
  usePhoneSize(tester, height: height);
  await tester.pumpWidget(await testScope(
    const TestApp(home: NotificationsScreen()),
    locale: locale,
    prefs: {themeModeStorageKey: theme},
    overrides: overrides,
  ));
  await tester.pumpAndSettle();
}

void main() {
  group('NotificationDto', () {
    test('maps backend types to the three kinds and reads data.symbol', () {
      AppNotification? map(Map<String, Object?> m) => NotificationDto(Json(m)).toDomain();
      final base = {'id': 'n', 'title': 'T', 'body': 'B', 'created_at': '2026-10-21T10:00:00Z'};
      expect(map({...base, 'type': 'price_alert'})!.kind, NotificationKind.priceAlert);
      expect(map({...base, 'type': 'signal', 'data': {'symbol': 'eur/usd'}})!.symbol, 'EUR/USD');
      expect(map({...base, 'type': 'backtest_completed'})!.kind, NotificationKind.system);
      expect(map({...base, 'type': 'signal', 'read_at': '2026-10-21T11:00:00Z'})!.isRead, isTrue);
    });

    test('invalid items are dropped, never thrown', () {
      AppNotification? map(Map<String, Object?> m) => NotificationDto(Json(m)).toDomain();
      expect(map({'id': 'n', 'type': 'signal', 'title': '', 'created_at': '2026-10-21T10:00:00Z'}), isNull);
      expect(map({'id': 'n', 'type': 'signal', 'title': 'T'}), isNull);
      expect(map({'type': 'signal', 'title': 'T', 'created_at': 'x'}), isNull);
    });
  });

  for (final theme in ['light', 'dark']) {
    testWidgets('inbox lists kinds with unread dots and relative times ($theme)', (tester) async {
      await pumpNotifications(tester, theme: theme);
      expect(find.byType(NotificationRow), findsNWidgets(6));
      expect(find.text('Inbox · 3'), findsOneWidget);
      expect(find.text('EUR/USD · Long on 1h'), findsOneWidget);
      expect(find.text('12m ago'), findsOneWidget);
      expect(find.text('2d ago'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('filter chips narrow the list by kind', (tester) async {
    await pumpNotifications(tester);
    await tester.tap(find.widgetWithText(ChoiceChip, 'Price alerts'));
    await tester.pumpAndSettle();
    expect(find.byType(NotificationRow), findsNWidgets(2));
    await tester.tap(find.widgetWithText(ChoiceChip, 'Opportunities'));
    await tester.pumpAndSettle();
    expect(find.byType(NotificationRow), findsNWidgets(2));
    await tester.tap(find.widgetWithText(ChoiceChip, 'System'));
    await tester.pumpAndSettle();
    expect(find.byType(NotificationRow), findsNWidgets(2));
    await tester.tap(find.widgetWithText(ChoiceChip, 'All'));
    await tester.pumpAndSettle();
    expect(find.byType(NotificationRow), findsNWidgets(6));
  });

  testWidgets('swipe from the start toggles read and the row stays', (tester) async {
    await pumpNotifications(tester);
    final row = find.byType(NotificationRow).first;
    await tester.drag(row, const Offset(500, 0));
    await tester.pumpAndSettle();
    expect(find.byType(NotificationRow), findsNWidgets(6));
    expect(find.text('Inbox · 2'), findsOneWidget);
  });

  testWidgets('swipe from the end deletes, Undo puts it back in place', (tester) async {
    await pumpNotifications(tester);
    await tester.drag(find.byType(NotificationRow).first, const Offset(-500, 0));
    await tester.pumpAndSettle();
    expect(find.byType(NotificationRow), findsNWidgets(5));
    expect(find.text('Notification deleted'), findsOneWidget);
    await tester.tap(find.text('Undo'));
    await tester.pumpAndSettle();
    expect(find.byType(NotificationRow), findsNWidgets(6));
    expect(
      tester.widget<NotificationRow>(find.byType(NotificationRow).first).notification.title,
      'EUR/USD · Long on 1h',
    );
  });

  testWidgets('screen reader gets read and delete as custom actions', (tester) async {
    final semantics = tester.ensureSemantics();
    await pumpNotifications(tester);
    final node = tester.getSemantics(find.byType(NotificationRow).first);
    final labels = node.getSemanticsData().customSemanticsActionIds!.map(
          (id) => CustomSemanticsAction.getAction(id)!.label,
        );
    expect(labels, containsAll(['Mark as read', 'Delete']));
    expect(node.label, startsWith('Unread, Opportunities, EUR/USD · Long on 1h'));
    semantics.dispose();
  });

  testWidgets('mark all as read clears the count and hides the action', (tester) async {
    await pumpNotifications(tester);
    await tester.tap(find.byTooltip('Mark all as read'));
    await tester.pumpAndSettle();
    expect(find.text('Inbox'), findsOneWidget);
    expect(find.byTooltip('Mark all as read'), findsNothing);
  });

  testWidgets('tapping an instrument notification opens its Market screen and marks it read', (tester) async {
    await pumpNotifications(tester);
    await tester.tap(find.text('EUR/USD · Long on 1h'));
    await tester.pumpAndSettle();
    expect(find.byType(MarketScreen), findsOneWidget);
    final container = ProviderScope.containerOf(tester.element(find.byType(MarketScreen)));
    expect(container.read(unreadNotificationsProvider), 2);
  });

  testWidgets('empty inbox shows the illustration and copy', (tester) async {
    await pumpNotifications(tester, overrides: [notificationsRepositoryProvider.overrideWithValue(_EmptyNotifications())]);
    expect(find.text('You’re all caught up'), findsOneWidget);
    expect(find.byType(AppIllustration), findsOneWidget);
  });

  testWidgets('load failure shows an error with retry', (tester) async {
    await pumpNotifications(tester, overrides: [notificationsRepositoryProvider.overrideWithValue(_FailingNotifications())]);
    expect(find.text('Notifications could not be loaded.'), findsOneWidget);
    expect(find.text('Try again'), findsOneWidget);
  });

  group('Alerts segment', () {
    testWidgets('empty: explains how to create one', (tester) async {
      await pumpNotifications(tester);
      await tester.tap(find.text('Alerts'));
      await tester.pumpAndSettle();
      expect(find.text('No price alerts'), findsOneWidget);
      expect(find.byType(AppIllustration), findsOneWidget);
    });

    testWidgets('lists alerts of every instrument with their symbol', (tester) async {
      await pumpNotifications(tester);
      final container = ProviderScope.containerOf(tester.element(find.byType(NotificationsScreen)));
      final vm = container.read(alertsViewModelProvider.notifier);
      await vm.create(const AlertDraft(symbol: 'EUR/USD', condition: AlertCondition.crossesAbove, value: 1.2));
      await vm.create(const AlertDraft(symbol: 'XAU/USD', condition: AlertCondition.crossesBelow, value: 2000));
      await tester.pumpAndSettle();
      expect(find.text('Alerts · 2'), findsOneWidget);
      await tester.tap(find.text('Alerts · 2'));
      await tester.pumpAndSettle();
      expect(find.textContaining('EUR/USD ·'), findsOneWidget);
      expect(find.textContaining('XAU/USD ·'), findsOneWidget);
    });
  });

  testWidgets('the Home bell shows the unread count and opens the centre', (tester) async {
    usePhoneSize(tester);
    await tester.pumpWidget(await testScope(const TestApp()));
    await settleMocks(tester);
    expect(find.byTooltip('Notifications, 3 unread'), findsOneWidget);
    await tester.tap(find.byTooltip('Notifications, 3 unread'));
    await tester.pumpAndSettle();
    expect(find.byType(NotificationsScreen), findsOneWidget);
    await tester.tap(find.byTooltip('Mark all as read'));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(BackButton));
    await tester.pumpAndSettle();
    expect(find.byTooltip('Notifications'), findsOneWidget);
  });

  testWidgets('Arabic: RTL, translated, no overflow', (tester) async {
    await pumpNotifications(tester, locale: 'ar', theme: 'dark');
    expect(find.text('الوارد · 3'), findsOneWidget);
    expect(find.text('EUR/USD · صعود على 1h'), findsOneWidget);
    expect(Directionality.of(tester.element(find.byType(NotificationsScreen))), TextDirection.rtl);
    expect(tester.takeException(), isNull);
  });

  for (final locale in ['en', 'ar']) {
    testWidgets('largest font ($locale): both segments scroll without overflow', (tester) async {
      useLargeText(tester);
      await pumpNotifications(tester, locale: locale, height: 812);
      await tester.drag(find.byType(ListView).first, const Offset(0, -3000));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      await tester.tap(find.text(locale == 'en' ? 'Alerts' : 'التنبيهات'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });
  }
}
