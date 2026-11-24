// اختبارات قائمة Signals (D1b): صف الفرصة (الاتجاه بسهم وكلمة، الاحتمال،
// الإطار، العمر، شارة النموذج، Hero، القارئ الصوتي، 48dp) وحالات القائمة
// (تحميل، فاضية، خطأ، بدون اتصال، سحب للتحديث) بالثيمين وبالعربي وبالخط الكبير.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/core/data/json.dart';
import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/core/widgets/app_illustration.dart';
import 'package:trading_app/core/widgets/feedback_states.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/signals/data/opportunity_dto.dart';
import 'package:trading_app/features/signals/data/signals_repository.dart';
import 'package:trading_app/features/signals/models/analysis_method.dart';
import 'package:trading_app/features/signals/models/analysis_request.dart';
import 'package:trading_app/features/signals/models/model_accuracy.dart';
import 'package:trading_app/features/signals/models/opportunity.dart';
import 'package:trading_app/features/signals/models/signal_profile.dart';
import 'package:trading_app/features/signals/views/signals_screen.dart';
import 'package:trading_app/features/signals/widgets/signal_row.dart';
import 'package:trading_app/features/signals/widgets/strategy_sheet.dart';

import '../../helpers/test_app.dart';

Opportunity signal(
  String id, {
  String symbol = 'EUR/USD',
  String tf = '1h',
  String direction = 'long',
  double probability = 0.72,
  Duration age = const Duration(minutes: 12),
}) =>
    OpportunityDto.fromJson(Json({
      'id': id,
      'symbol': symbol,
      'timeframe': tf,
      'status': 'detected',
      'direction': direction,
      'probability': probability,
      'entryZone': {'low': 1.0800, 'high': 1.0810},
      'stopLossZone': {'low': 1.0750, 'high': 1.0760},
      'takeProfitZone': {'low': 1.0900, 'high': 1.0910},
      'riskReward': 2,
      'generatedAt': kTestNow.subtract(age).millisecondsSinceEpoch,
      'validUntil': kTestNow.add(const Duration(hours: 2)).millisecondsSinceEpoch,
    })).toDomain()!;

/// مصدر إشارات بنتحكّم فيه: [onFeed] بيقرّر نتيجة كل طلب قائمة
final class _Signals implements SignalsRepository {
  _Signals(this.onFeed);

  Future<List<Opportunity>> Function() onFeed;

  @override
  bool get isSimulated => true;

  @override
  Future<List<Opportunity>> feed(SignalProfile profile) => onFeed();

  @override
  Future<ModelAccuracy> accuracy() async => const ModelAccuracy(resolved: 200, hits: 116, windowDays: 90);

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
  Future<Opportunity?> opportunity(String id) async => null;
}

class _StartsOffline extends NetworkStatusViewModel {
  @override
  NetworkStatus build() => NetworkStatus.offline;
}

final _three = [
  signal('a', probability: 0.78),
  signal('b', symbol: 'XAU/USD', tf: '4h', direction: 'short', probability: 0.7, age: const Duration(hours: 3)),
  signal('c', symbol: 'USD/JPY', tf: '15m', probability: 0.64, age: Duration.zero),
];

Future<void> pumpList(
  WidgetTester tester,
  SignalsRepository repo, {
  String locale = 'en',
  Map<String, Object> prefs = const {},
  List<Override> overrides = const [],
  bool settle = true,
}) async {
  usePhoneSize(tester, height: 1200);
  await tester.pumpWidget(await testScope(
    const TestApp(home: SignalsScreen()),
    locale: locale,
    prefs: prefs,
    overrides: [signalsRepositoryProvider.overrideWithValue(repo), ...overrides],
  ));
  settle ? await tester.pumpAndSettle() : await tester.pump();
}

Future<void> pumpRow(WidgetTester tester, Opportunity o, {String locale = 'en', VoidCallback? onTap}) async {
  usePhoneSize(tester);
  await tester.pumpWidget(await testScope(
    TestApp(home: Scaffold(body: Center(child: SignalRow(signal: o, now: kTestNow, onTap: onTap)))),
    locale: locale,
  ));
  await tester.pumpAndSettle();
}

ProviderContainer containerOf(WidgetTester tester) =>
    ProviderScope.containerOf(tester.element(find.byType(SignalsScreen)));

void main() {
  group('SignalRow', () {
    testWidgets('instrument, arrow + direction word, probability, timeframe, age and model tag', (tester) async {
      await pumpRow(tester, signal('a'));
      expect(find.text('EUR/USD'), findsOneWidget);
      expect(find.text('Long'), findsOneWidget);
      expect(find.byIcon(Icons.arrow_upward_rounded), findsOneWidget);
      expect(find.text('72%'), findsOneWidget);
      expect(find.text('1h · 12m ago'), findsOneWidget);
      expect(find.text('Model output'), findsOneWidget);
      expect(tester.getSize(find.byType(SignalRow)).height, greaterThanOrEqualTo(48));
    });

    testWidgets('short: down arrow + word, never colour alone', (tester) async {
      await pumpRow(tester, signal('b', direction: 'short'));
      expect(find.text('Short'), findsOneWidget);
      expect(find.byIcon(Icons.arrow_downward_rounded), findsOneWidget);
    });

    testWidgets('one screen-reader label; not a button until the detail exists', (tester) async {
      final handle = tester.ensureSemantics();
      await pumpRow(tester, signal('a'));
      final node = tester.getSemantics(find.byType(SignalRow));
      expect(
        node.label,
        'EUR/USD, Euro / US Dollar. Long, 72% chance, 1h, 12m ago. Model output',
      );
      expect(node, isSemantics(isButton: false, label: node.label));
      expect(find.byIcon(Icons.chevron_right_rounded), findsNothing);
      handle.dispose();
    });

    testWidgets('with onTap: a button with a hint and a chevron', (tester) async {
      final handle = tester.ensureSemantics();
      var taps = 0;
      await pumpRow(tester, signal('a'), onTap: () => taps++);
      final node = tester.getSemantics(find.byType(SignalRow));
      expect(node, isSemantics(isButton: true, hint: 'Opens the signal', label: node.label));
      await tester.tap(find.byType(SignalRow));
      expect(taps, 1);
      handle.dispose();
    });

    testWidgets('Hero on the instrument, one tag per signal', (tester) async {
      await pumpRow(tester, signal('a'));
      final hero = tester.widget<Hero>(find.byType(Hero));
      expect(hero.tag, SignalRow.heroTag('a'));
    });

    testWidgets('Arabic: RTL with the Arabic direction word', (tester) async {
      await pumpRow(tester, signal('a'), locale: 'ar');
      expect(find.text('صعود'), findsOneWidget);
      expect(Directionality.of(tester.element(find.byType(SignalRow))), TextDirection.rtl);
    });

    testWidgets('largest font fits (ar)', (tester) async {
      useLargeText(tester);
      await pumpRow(tester, signal('b', symbol: 'XAU/USD', direction: 'short'), locale: 'ar');
      expect(tester.takeException(), isNull);
    });
  });

  group('Signals list states', () {
    testWidgets('loading: skeleton rows, no signals yet', (tester) async {
      final gate = Completer<List<Opportunity>>();
      await pumpList(tester, _Signals(() => gate.future));
      expect(find.byType(SignalRowSkeleton), findsNWidgets(4));
      expect(find.byType(SignalRow), findsNothing);
      gate.complete(_three);
      await tester.pumpAndSettle();
      await tester.pump(const Duration(seconds: 1)); // آخر مؤقّتات الدخول المتدرّج
      expect(find.byType(SignalRowSkeleton), findsNothing);
      expect(find.byType(SignalRow), findsNWidgets(3));
    });

    testWidgets('data: rows in the given order with the Simulated label', (tester) async {
      await pumpList(tester, _Signals(() async => _three));
      expect(find.text('Opportunities'), findsOneWidget);
      expect(find.text('Simulated'), findsNWidgets(2)); // سطر الدقة + القائمة
      final symbols = tester.widgetList<SignalRow>(find.byType(SignalRow)).map((r) => r.signal.id);
      expect(symbols, ['a', 'b', 'c']);
      expect(find.text('4h · 3h ago'), findsOneWidget);
      expect(find.text('15m · Just now'), findsOneWidget);
    });

    testWidgets('reduced motion: rows show at once', (tester) async {
      tester.platformDispatcher.accessibilityFeaturesTestValue = const FakeAccessibilityFeatures(disableAnimations: true);
      addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
      await pumpList(tester, _Signals(() async => _three), settle: false);
      await tester.pump();
      expect(find.byType(SignalRow), findsNWidgets(3));
      expect(find.byType(Animate), findsNothing); // بدون fade/طلوع
    });

    testWidgets('empty: illustrated state, and its button opens Strategy', (tester) async {
      await pumpList(tester, _Signals(() async => const []));
      expect(find.text('No signals match your strategy'), findsOneWidget);
      expect(find.byType(AppIllustration), findsOneWidget);
      await tester.tap(find.descendant(of: find.byType(EmptyState), matching: find.text('Strategy')));
      await tester.pumpAndSettle();
      expect(find.byType(StrategySheet), findsOneWidget);
    });

    testWidgets('error: Try again loads the list', (tester) async {
      final repo = _Signals(() async => throw StateError('server'));
      await pumpList(tester, repo);
      expect(find.text('Signals could not be loaded.'), findsOneWidget);
      expect(find.byType(SignalRow), findsNothing);

      repo.onFeed = () async => _three;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Signals could not be loaded.'), findsNothing);
      expect(find.byType(SignalRow), findsNWidgets(3));
    });

    testWidgets('offline: offline state, then loads by itself when back online', (tester) async {
      var calls = 0;
      await pumpList(
        tester,
        _Signals(() async {
          calls++;
          return _three;
        }),
        overrides: [networkStatusProvider.overrideWith(_StartsOffline.new)],
      );
      expect(find.text('You’re offline'), findsOneWidget);
      expect(find.text('Signals will load when you’re back online.'), findsOneWidget);
      expect(calls, 0); // ما انبعت شي

      containerOf(tester).read(networkStatusProvider.notifier).set(NetworkStatus.online);
      await tester.pumpAndSettle();
      expect(find.byType(SignalRow), findsNWidgets(3));
    });

    testWidgets('pull to refresh: new rows; a failure keeps the list and shows a snackbar', (tester) async {
      final repo = _Signals(() async => _three);
      await pumpList(tester, repo);

      repo.onFeed = () async => [_three.first];
      await tester.fling(find.byType(CustomScrollView), const Offset(0, 500), 1200);
      await tester.pumpAndSettle();
      expect(find.byType(SignalRow), findsOneWidget);

      repo.onFeed = () async => throw StateError('server');
      await tester.fling(find.byType(CustomScrollView), const Offset(0, 500), 1200);
      await tester.pumpAndSettle();
      expect(find.byType(SignalRow), findsOneWidget);
      expect(find.widgetWithText(SnackBar, 'Signals could not be loaded.'), findsOneWidget);
    });

    testWidgets('pull to refresh offline: nothing sent, offline snackbar', (tester) async {
      await pumpList(tester, _Signals(() async => _three));
      containerOf(tester).read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      await tester.fling(find.byType(CustomScrollView), const Offset(0, 500), 1200);
      await tester.pumpAndSettle();
      expect(find.byType(SignalRow), findsNWidgets(3));
      expect(find.text('You’re offline. Try again when connected.'), findsOneWidget);
    });

    for (final mode in ['light', 'dark']) {
      for (final locale in ['en', 'ar']) {
        testWidgets('largest font: list fits ($mode, $locale)', (tester) async {
          useLargeText(tester);
          await pumpList(tester, _Signals(() async => _three), locale: locale, prefs: {themeModeStorageKey: mode});
          await tester.drag(find.byType(CustomScrollView), const Offset(0, -3000));
          await tester.pumpAndSettle();
          expect(find.byType(SignalRow), findsWidgets);
          expect(tester.takeException(), isNull);
        });
      }
    }
  });
}
