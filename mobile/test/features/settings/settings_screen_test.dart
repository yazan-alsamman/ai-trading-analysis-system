// اختبارات Settings (Stage B): المظهر، اللغة، رأس المال والحدود، Developer،
// وتفضيلات الإشعارات.

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:trading_app/core/data/json.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/features/notifications/data/notification_preferences_repository.dart';
import 'package:trading_app/features/notifications/models/notification_preferences.dart';
import 'package:trading_app/features/notifications/views/notification_preferences_screen.dart';
import 'package:trading_app/features/risk/data/risk_limits_repository.dart';
import 'package:trading_app/features/risk/models/risk_limits.dart';
import 'package:trading_app/features/settings/views/settings_screen.dart';
import 'package:trading_app/providers/locale_provider.dart';

import '../../helpers/test_app.dart';

Future<void> pumpSettings(
  WidgetTester tester, {
  Map<String, Object> prefs = const {},
  String locale = 'en',
  double height = 812,
}) async {
  usePhoneSize(tester, height: height);
  await tester.pumpWidget(await testScope(const TestApp(home: SettingsScreen()), prefs: prefs, locale: locale));
  await tester.pumpAndSettle();
}

ProviderContainer containerOf(WidgetTester tester) =>
    ProviderScope.containerOf(tester.element(find.byType(SettingsScreen)));

void main() {
  for (final mode in ['light', 'dark']) {
    for (final locale in ['en', 'ar']) {
      testWidgets('renders every group ($mode, $locale)', (tester) async {
        await pumpSettings(tester, prefs: {themeModeStorageKey: mode}, locale: locale, height: 1400);
        expect(find.byType(SettingsScreen), findsOneWidget);
        expect(find.text(locale == 'en' ? 'Capital & risk limits' : 'رأس المال وحدود المخاطرة'), findsOneWidget);
        // "Simulate offline" باقي لحد B12 (debug بس)
        expect(find.text(locale == 'en' ? 'Simulate offline' : 'محاكاة عدم الاتصال'), findsOneWidget);
        expect(tester.takeException(), isNull);
      });
    }
  }

  testWidgets('largest font: no overflow', (tester) async {
    useLargeText(tester);
    await pumpSettings(tester);
    await tester.drag(find.byType(CustomScrollView), const Offset(0, -3000));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });

  testWidgets('Appearance applies and saves the theme', (tester) async {
    await pumpSettings(tester);
    await tester.tap(find.text('Dark'));
    await tester.pumpAndSettle();

    expect(containerOf(tester).read(themeModeProvider), ThemeMode.dark);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString(themeModeStorageKey), 'dark');
    expect(Theme.of(tester.element(find.byType(SettingsScreen))).brightness, Brightness.dark);
  });

  testWidgets('Language sheet switches to Arabic (RTL)', (tester) async {
    await pumpSettings(tester);
    await tester.tap(find.text('Language'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('العربية').last);
    await tester.pumpAndSettle();

    expect(containerOf(tester).read(localeProvider).languageCode, 'ar');
    expect(find.text('الإعدادات'), findsOneWidget);
    expect(Directionality.of(tester.element(find.byType(SettingsScreen))), TextDirection.rtl);
    expect(tester.takeException(), isNull);
  });

  group('Capital & risk limits', () {
    testWidgets('summary says the capital is not set by default', (tester) async {
      await pumpSettings(tester);
      expect(find.text('Capital not set · 1% per trade · 3% a day'), findsOneWidget);
    });

    testWidgets('the sheet saves new limits, persists them and confirms', (tester) async {
      await pumpSettings(tester, height: 1400);
      await tester.tap(find.text('Capital & risk limits'));
      await tester.pumpAndSettle();

      final fields = find.byType(TextField);
      await tester.enterText(fields.at(0), '25000');
      await tester.enterText(fields.at(1), '0.5');
      await tester.enterText(fields.at(2), '2');
      await tester.tap(find.text('Save'));
      await tester.pumpAndSettle();

      expect(find.text('Risk limits saved'), findsOneWidget);
      expect(find.text('USD 25,000.00 · 0.5% per trade · 2% a day'), findsOneWidget);
      final saved = containerOf(tester).read(riskLimitsProvider);
      expect(saved, const RiskLimits(capital: 25000, maxRiskPerTradePct: 0.5, dailyLossLimitPct: 2));
      final prefs = await SharedPreferences.getInstance();
      expect(jsonDecode(prefs.getString(LocalRiskLimitsRepository.storageKey)!)['capital'], 25000);
    });

    testWidgets('invalid values show errors and nothing is saved', (tester) async {
      await pumpSettings(tester, height: 1400);
      await tester.tap(find.text('Capital & risk limits'));
      await tester.pumpAndSettle();

      final fields = find.byType(TextField);
      await tester.enterText(fields.at(1), '25');
      await tester.enterText(fields.at(2), '0.1');
      await tester.tap(find.text('Save'));
      await tester.pumpAndSettle();

      expect(find.text('Enter a value from 0.1% to 10%'), findsOneWidget);
      expect(find.text('Enter a value from 0.5% to 20%'), findsOneWidget);
      expect(containerOf(tester).read(riskLimitsProvider), RiskLimits.defaults);

      // الحد اليومي أصغر من مخاطرة الصفقة
      await tester.enterText(fields.at(1), '2');
      await tester.enterText(fields.at(2), '1');
      await tester.pumpAndSettle();
      expect(find.text('The daily limit must be at least the risk per trade'), findsOneWidget);
    });

    testWidgets('saved limits are read back on the next launch', (tester) async {
      await pumpSettings(tester, prefs: {
        LocalRiskLimitsRepository.storageKey:
            jsonEncode(const RiskLimits(capital: 5000, maxRiskPerTradePct: 2, dailyLossLimitPct: 6).toJson()),
      });
      expect(find.text('USD 5,000.00 · 2% per trade · 6% a day'), findsOneWidget);
    });
  });

  group('Notification preferences', () {
    testWidgets('opens from Settings with channels and kinds (no promotions)', (tester) async {
      await pumpSettings(tester);
      await tester.tap(find.text('Notification preferences'));
      await tester.pumpAndSettle();
      expect(find.byType(NotificationPreferencesScreen), findsOneWidget);
      for (final label in ['Push', 'In the app', 'Email', 'Telegram', 'Price alerts', 'Opportunities', 'System']) {
        expect(find.text(label), findsOneWidget, reason: label);
      }
      expect(find.textContaining('Promotion'), findsNothing);
    });

    testWidgets('a toggle applies at once and is saved', (tester) async {
      usePhoneSize(tester, height: 1400);
      await tester.pumpWidget(await testScope(const TestApp(home: NotificationPreferencesScreen())));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Email'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('System'));
      await tester.pumpAndSettle();

      final container = ProviderScope.containerOf(tester.element(find.byType(NotificationPreferencesScreen)));
      final prefs = container.read(notificationPreferencesProvider);
      expect(prefs.channels, contains(NotificationChannel.email));
      expect(prefs.kinds, isNot(contains(NotificationKind.system)));
      final stored = await SharedPreferences.getInstance();
      expect(stored.getString(LocalNotificationPreferencesRepository.storageKey), contains('email'));
    });

    testWidgets('turning every channel off warns that nothing will arrive', (tester) async {
      usePhoneSize(tester, height: 1400);
      await tester.pumpWidget(await testScope(const TestApp(home: NotificationPreferencesScreen())));
      await tester.pumpAndSettle();
      expect(find.textContaining('every channel off'), findsNothing);

      await tester.tap(find.text('Push'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('In the app'));
      await tester.pumpAndSettle();
      expect(find.textContaining('every channel off'), findsOneWidget);
    });

    testWidgets('largest font in Arabic: no overflow', (tester) async {
      useLargeText(tester);
      usePhoneSize(tester);
      await tester.pumpWidget(await testScope(const TestApp(home: NotificationPreferencesScreen()), locale: 'ar'));
      await tester.pumpAndSettle();
      await tester.drag(find.byType(ListView), const Offset(0, -3000));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });
  });

  test('stored notification preferences: unknown values dropped, corrupt → defaults', () {
    expect(
      NotificationPreferences.fromJson(const Json({
        'channels': ['email', 'fax'],
        'kinds': <Object?>[],
      })),
      const NotificationPreferences(channels: {NotificationChannel.email}, kinds: {}),
    );
    expect(NotificationPreferences.fromJson(const Json({'channels': 'push'})), NotificationPreferences.defaults);
  });
}
