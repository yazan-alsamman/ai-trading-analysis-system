// اختبارات تبويب Signals (Stage B): سطر دقة النموذج + "Strategy" (الفلتر
// المحفوظ)، بالثيمين وبالعربي وبالخط الكبير.

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:trading_app/core/data/json.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/core/widgets/direction_badge.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/markets/models/market_models.dart';
import 'package:trading_app/features/signals/data/signal_profile_repository.dart';
import 'package:trading_app/features/signals/data/signals_repository.dart';
import 'package:trading_app/features/signals/models/analysis_method.dart';
import 'package:trading_app/features/signals/models/analysis_request.dart';
import 'package:trading_app/features/signals/models/model_accuracy.dart';
import 'package:trading_app/features/signals/models/opportunity.dart';
import 'package:trading_app/features/signals/models/signal_profile.dart';
import 'package:trading_app/features/signals/views/signals_screen.dart';
import 'package:trading_app/features/signals/widgets/strategy_sheet.dart';

import '../../helpers/test_app.dart';

Future<void> pumpSignals(
  WidgetTester tester, {
  Map<String, Object> prefs = const {},
  String locale = 'en',
  List<Override> overrides = const [],
}) async {
  usePhoneSize(tester);
  await tester.pumpWidget(await testScope(
    const TestApp(home: SignalsScreen()),
    prefs: prefs,
    locale: locale,
    overrides: overrides,
  ));
  await tester.pumpAndSettle();
}

ProviderContainer containerOf(WidgetTester tester) =>
    ProviderScope.containerOf(tester.element(find.byType(SignalsScreen)));

/// مصدر إشارات بدقة محددة (أو بيفشل)
final class _FakeSignals implements SignalsRepository {
  const _FakeSignals(this.result);

  final ModelAccuracy? result;

  @override
  Future<ModelAccuracy> accuracy() async => result ?? (throw StateError('offline'));

  @override
  bool get isSimulated => true;

  @override
  Future<Opportunity> requestAnalysis(
    AnalysisRequest request, {
    AnalysisCancelToken? cancel,
    void Function(AnalysisStage stage)? onStage,
  }) =>
      throw UnimplementedError();

  @override
  Future<List<Opportunity>> opportunities(String symbol, {String methodId = AnalysisMethod.defaultId}) async => const [];

  @override
  Future<List<Opportunity>> feed(SignalProfile profile) async => const [];

  @override
  Future<Opportunity?> opportunity(String id) async => null;
}

void main() {
  for (final mode in ['light', 'dark']) {
    for (final locale in ['en', 'ar']) {
      testWidgets('accuracy line, strategy card and the list ($mode, $locale)', (tester) async {
        await pumpSignals(tester, prefs: {themeModeStorageKey: mode}, locale: locale);
        expect(find.text(locale == 'en' ? 'Strategy' : 'الاستراتيجية'), findsOneWidget);
        expect(find.textContaining(locale == 'en' ? 'Model accuracy' : 'دقة النموذج'), findsOneWidget);
        expect(find.text(locale == 'en' ? 'Simulated' : 'محاكاة'), findsWidgets);
        expect(tester.takeException(), isNull);
      });
    }
  }

  testWidgets('the accuracy line states the rate, the sample and the window', (tester) async {
    await pumpSignals(tester, overrides: [
      signalsRepositoryProvider.overrideWithValue(
        const _FakeSignals(ModelAccuracy(resolved: 200, hits: 116, windowDays: 90)),
      ),
    ]);
    expect(find.text('Model accuracy 58% · 200 past signals · last 90 days'), findsOneWidget);
    expect(find.text('Share of past signals that reached the target before the stop.'), findsOneWidget);
  });

  testWidgets('no finished signals: no made-up percentage', (tester) async {
    await pumpSignals(tester, overrides: [
      signalsRepositoryProvider.overrideWithValue(
        const _FakeSignals(ModelAccuracy(resolved: 0, hits: 0, windowDays: 90)),
      ),
    ]);
    expect(find.text('No finished signals in the last 90 days yet'), findsOneWidget);
    expect(find.textContaining('Model accuracy'), findsNothing);
  });

  testWidgets('accuracy error shows Try again', (tester) async {
    await pumpSignals(tester, overrides: [signalsRepositoryProvider.overrideWithValue(const _FakeSignals(null))]);
    expect(find.text('Accuracy could not be loaded.'), findsOneWidget);
    expect(find.text('Try again'), findsOneWidget);
  });

  testWidgets('strategy card: the default (all instruments) when nothing is saved', (tester) async {
    await pumpSignals(tester);
    expect(find.text('Default: MA Crossover · all instruments'), findsOneWidget);
  });

  testWidgets('the strategy sheet saves a new filter and persists it', (tester) async {
    usePhoneSize(tester, height: 1600);
    await tester.pumpWidget(await testScope(const TestApp(home: SignalsScreen())));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Strategy'));
    await tester.pumpAndSettle();
    expect(find.byType(StrategySheet), findsOneWidget);
    expect(find.text('Test on past data'), findsOneWidget);
    expect(find.text('Uses your saved strategy. Save first to test your changes.'), findsNothing);

    await tester.tap(find.widgetWithText(FilterChip, 'NZD/USD'));
    await tester.tap(find.widgetWithText(FilterChip, '15m'));
    await tester.tap(find.widgetWithText(FilterChip, 'Short'));
    await tester.pumpAndSettle();
    // تعديلات مش محفوظة: الاختبار بيستعمل المحفوظة، والـ sheet بتقول هيك
    expect(find.text('Uses your saved strategy. Save first to test your changes.'), findsOneWidget);
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();

    // الحفظ ما بيسكّر الـ sheet، والبطاقة وراها بتتحدّث
    expect(find.byType(StrategySheet), findsOneWidget);
    expect(find.text('Saved'), findsOneWidget);
    expect(find.text('MA Crossover · 7 instruments · above 60%'), findsOneWidget);

    final saved = containerOf(tester).read(signalProfileProvider);
    expect(saved.symbols, isNot(contains('NZD/USD')));
    expect(saved.timeframes, {Timeframe.h1, Timeframe.h4});
    expect(saved.directions, {SignalDirection.long});
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString(LocalSignalProfileRepository.storageKey), contains('USD/CAD'));
    expect(prefs.getString(LocalSignalProfileRepository.storageKey), isNot(contains('NZD/USD')));
  });

  testWidgets('nothing picked: a message and Save is off; Reset restores defaults', (tester) async {
    usePhoneSize(tester, height: 1600);
    await tester.pumpWidget(await testScope(const TestApp(home: SignalsScreen())));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Strategy'));
    await tester.pumpAndSettle();

    for (final tf in ['15m', '1h', '4h']) {
      await tester.tap(find.widgetWithText(FilterChip, tf));
    }
    await tester.pumpAndSettle();
    expect(find.text('Pick at least one instrument, timeframe and direction.'), findsOneWidget);
    final save = tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Save'));
    expect(save.onPressed, isNull);

    // قسم الطريقة فوق (A3b): الـ sheet أطول، فمنسكرول للزر
    await tester.ensureVisible(find.text('Reset to defaults'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Reset to defaults'));
    await tester.pumpAndSettle();
    expect(find.text('Pick at least one instrument, timeframe and direction.'), findsNothing);
  });

  testWidgets('largest font: the strategy sheet fits (ar)', (tester) async {
    useLargeText(tester);
    usePhoneSize(tester);
    await tester.pumpWidget(await testScope(const TestApp(home: Scaffold(body: StrategySheet())), locale: 'ar'));
    await tester.pumpAndSettle();
    await tester.drag(find.byType(SingleChildScrollView), const Offset(0, -4000));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });

  group('SignalProfile', () {
    test('json round trip', () {
      final profile = SignalProfile.defaults.copyWith(
        symbols: {'EUR/USD'},
        minProbability: 0.7,
        minRiskReward: 2,
        requireRiskFit: false,
      );
      expect(SignalProfile.fromJson(Json(jsonDecode(jsonEncode(profile.toJson())) as Map<String, Object?>)), profile);
    });

    test('invalid or foreign values fall back to the defaults', () {
      expect(SignalProfile.fromJson(const Json({'symbols': ['BTC/USD']})), SignalProfile.defaults);
      expect(
        SignalProfile.fromJson(Json(SignalProfile.defaults.copyWith(minProbability: 0.99).toJson())),
        SignalProfile.defaults,
      );
    });
  });

  test('accuracy payload: hits above resolved is rejected', () {
    expect(modelAccuracyFromJson(const Json({'resolved': 10, 'hits': 12, 'window_days': 90})), isNull);
    expect(modelAccuracyFromJson(const Json({'resolved': 10, 'hits': 6, 'window_days': 90}))?.hitRate, 0.6);
  });
}
