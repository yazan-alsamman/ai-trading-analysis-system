// اختبارات شاشة تفاصيل الإشارة (D1c): المحتوى (الاتجاه، الاحتمال، الخطة
// بالنقاط والعائد : المخاطرة، الأسباب، الرسم، الصلاحية، التحذير)، الحالات
// (تحميل، مش موجودة، خطأ، بدون اتصال، منتهية، بتنتهي والشاشة مفتوحة)،
// الإجراءات، التنقّل من القائمة (Hero + ضغطة مزدوجة) بالثيمين وبالعربي
// وبالخط الكبير ومع تقليل الحركة.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/app/router/app_navigator.dart';
import 'package:trading_app/core/data/json.dart';
import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/format/formatters.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/core/widgets/feedback_states.dart';
import 'package:trading_app/features/alerts/widgets/set_alert_sheet.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/markets/views/market_screen.dart';
import 'package:trading_app/features/markets/widgets/price_chart.dart';
import 'package:trading_app/features/risk/widgets/size_trade_sheet.dart';
import 'package:trading_app/features/signals/data/opportunity_dto.dart';
import 'package:trading_app/features/signals/data/signals_repository.dart';
import 'package:trading_app/features/signals/models/analysis_method.dart';
import 'package:trading_app/features/signals/models/analysis_request.dart';
import 'package:trading_app/features/signals/models/model_accuracy.dart';
import 'package:trading_app/features/signals/models/opportunity.dart';
import 'package:trading_app/features/signals/models/signal_profile.dart';
import 'package:trading_app/features/signals/views/signal_detail_screen.dart';
import 'package:trading_app/features/signals/views/signals_screen.dart';
import 'package:trading_app/features/signals/widgets/signal_row.dart';

import '../../helpers/test_app.dart';

Opportunity signal(
  String id, {
  String tf = '1h',
  String direction = 'long',
  Duration validFor = const Duration(hours: 1),
}) =>
    OpportunityDto.fromJson(Json({
      'id': id,
      'symbol': 'EUR/USD',
      'timeframe': tf,
      'status': 'detected',
      'direction': direction,
      'probability': 0.7,
      'entryZone': {'low': 1.0800, 'high': 1.0810},
      'stopLossZone': {'low': 1.0750, 'high': 1.0760},
      'takeProfitZone': {'low': 1.0900, 'high': 1.0910},
      'riskReward': 2,
      'generatedAt': kTestNow.subtract(const Duration(minutes: 12)).millisecondsSinceEpoch,
      'validUntil': kTestNow.add(validFor).millisecondsSinceEpoch,
    })).toDomain()!;

/// مصدر إشارات بنتحكّم فيه
final class FakeSignals implements SignalsRepository {
  final byId = <String, Opportunity>{};
  Object? error;
  Completer<Opportunity?>? gate;
  var detailCalls = 0;

  @override
  bool get isSimulated => true;

  @override
  Future<List<Opportunity>> feed(SignalProfile profile) async => byId.values.toList();

  @override
  Future<Opportunity?> opportunity(String id) async {
    detailCalls++;
    if (gate case final g?) return g.future;
    if (error case final e?) throw e;
    return byId[id];
  }

  @override
  Future<Opportunity> requestAnalysis(
    AnalysisRequest request, {
    AnalysisCancelToken? cancel,
    void Function(AnalysisStage stage)? onStage,
  }) =>
      throw UnimplementedError();

  @override
  Future<List<Opportunity>> opportunities(String symbol, {String methodId = AnalysisMethod.defaultId}) async => [
        for (final o in byId.values)
          if (o.symbol == symbol) o,
      ];

  @override
  Future<ModelAccuracy> accuracy() async => const ModelAccuracy(resolved: 200, hits: 116, windowDays: 90);
}

class _StartsOffline extends NetworkStatusViewModel {
  @override
  NetworkStatus build() => NetworkStatus.offline;
}

/// شاشة بزر بيفتح التفاصيل بالـ helper الحقيقي (حتى الرجوع إلو مكان)
class _Launcher extends StatelessWidget {
  const _Launcher(this.id);

  final String id;

  @override
  Widget build(BuildContext context) => Scaffold(
        body: Center(
          child: TextButton(
            onPressed: () => context.pushSignalDetail(id, symbol: 'EUR/USD'),
            child: const Text('open'),
          ),
        ),
      );
}

Future<void> pumpDetail(
  WidgetTester tester,
  FakeSignals repo, {
  String id = 's',
  String locale = 'en',
  String theme = 'light',
  double height = 2000,
  bool offline = false,
  bool settle = true,
}) async {
  usePhoneSize(tester, height: height);
  await tester.pumpWidget(await testScope(
    TestApp(home: _Launcher(id)),
    locale: locale,
    prefs: {themeModeStorageKey: theme},
    overrides: [
      signalsRepositoryProvider.overrideWithValue(repo),
      if (offline) networkStatusProvider.overrideWith(_StartsOffline.new),
    ],
  ));
  await tester.pumpAndSettle();
  await tester.tap(find.text('open'));
  settle ? await tester.pumpAndSettle() : await tester.pump();
}

FakeSignals withSignal({Duration validFor = const Duration(hours: 1)}) => FakeSignals()
  ..byId['s'] = signal('s', validFor: validFor)
  ..byId['s-4h'] = signal('s-4h', tf: '4h');

void main() {
  group('content', () {
    testWidgets('header, direction + probability, validity, plan, reasons, chart and disclaimer', (tester) async {
      await pumpDetail(tester, withSignal());
      expect(find.byType(SignalDetailScreen), findsOneWidget);
      expect(find.text('EUR/USD'), findsOneWidget);
      expect(find.text('Euro / US Dollar'), findsOneWidget);
      expect(find.text('Long'), findsOneWidget);
      expect(find.text('70%'), findsOneWidget);
      final until = Formatters.clock(kTestNow.add(const Duration(hours: 1)).toLocal());
      expect(find.text('Generated 12m ago · Valid until $until'), findsOneWidget);
      expect(find.text('Simulated'), findsOneWidget);

      expect(find.text('1.08000 – 1.08100'), findsOneWidget);
      expect(find.text('1.09050'), findsOneWidget);
      expect(find.text('100 pips from entry'), findsOneWidget);
      expect(find.text('1.07550'), findsOneWidget);
      expect(find.text('50 pips from entry'), findsOneWidget);
      expect(find.text('1 : 2.0'), findsOneWidget);

      // 4th strongest of 4: behind "More reasons (1)" (pre-audit: top 3 first)
      expect(find.text('Price has been rising on the 1h chart.'), findsNothing);
      expect(find.text('More reasons (1)'), findsOneWidget);
      expect(find.text('2 of 2 timeframes point the same way.'), findsOneWidget);
      expect(find.textContaining('About 7 in 10'), findsOneWidget);
      expect(find.text('The target is 2× as far away as the stop.'), findsOneWidget);

      final chart = tester.widget<PriceChart>(find.byType(PriceChart));
      expect(chart.height, PriceChart.compactHeight);
      expect(chart.read?.id, 's');
      expect(find.text('Signals are for educational purposes and are not investment advice.'), findsOneWidget);
      expect(find.text('Expired'), findsNothing);
    });

    testWidgets('screen reader: header, one summary label, plan lines; buttons ≥ 48dp', (tester) async {
      final handle = tester.ensureSemantics();
      await pumpDetail(tester, withSignal());
      expect(find.bySemanticsLabel('EUR/USD, Euro / US Dollar'), findsOneWidget);
      expect(find.bySemanticsLabel('Long, 70% chance the target is reached before the stop, 1h'), findsOneWidget);
      expect(find.bySemanticsLabel('Target, 1.09050, 100 pips from entry'), findsOneWidget);
      for (final label in ['Size this trade', 'Set alert', 'Open market']) {
        final size = tester.getSize(find.ancestor(of: find.text(label), matching: find.byWidgetPredicate((w) => w is ButtonStyleButton)));
        expect(size.height, greaterThanOrEqualTo(48), reason: label);
      }
      handle.dispose();
    });

    for (final locale in ['en', 'ar']) {
      for (final theme in ['light', 'dark']) {
        testWidgets('largest font fits ($locale, $theme)', (tester) async {
          useLargeText(tester);
          await pumpDetail(tester, withSignal(), locale: locale, theme: theme, height: 4000);
          expect(tester.takeException(), isNull);
          expect(find.byType(PriceChart), findsOneWidget);
        });
      }
    }

    testWidgets('Arabic: RTL with Arabic words', (tester) async {
      await pumpDetail(tester, withSignal(), locale: 'ar');
      expect(find.text('صعود'), findsOneWidget);
      expect(find.text('100 نقطة عن الدخول'), findsOneWidget);
      expect(find.text('100 نقطة عن الدخول'), findsOneWidget);
      expect(Directionality.of(tester.element(find.byType(SignalDetailScreen))), TextDirection.rtl);
    });
  });

  group('states', () {
    testWidgets('loading: skeletons, then the signal', (tester) async {
      final repo = withSignal()..gate = Completer<Opportunity?>();
      await pumpDetail(tester, repo, settle: false);
      await tester.pump();
      expect(find.byType(Skeleton), findsWidgets);
      expect(find.text('1.09050'), findsNothing);
      // العنوان (Hero) موجود من أول إطار
      expect(find.text('EUR/USD'), findsOneWidget);

      repo.gate!.complete(repo.byId['s']);
      await tester.pumpAndSettle();
      expect(find.text('1.09050'), findsOneWidget);
    });

    testWidgets('not found: message, and Back to Signals closes the screen', (tester) async {
      await pumpDetail(tester, FakeSignals(), id: 'missing');
      expect(find.text('Signal not available'), findsOneWidget);
      await tester.tap(find.text('Back to Signals'));
      await tester.pumpAndSettle();
      expect(find.byType(SignalDetailScreen), findsNothing);
      expect(find.text('open'), findsOneWidget);
    });

    testWidgets('error: Try again loads the signal', (tester) async {
      final repo = withSignal()..error = StateError('server');
      await pumpDetail(tester, repo);
      expect(find.byType(ErrorState), findsOneWidget);
      expect(find.text('The signal could not be loaded.'), findsOneWidget);

      repo.error = null;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('1.09050'), findsOneWidget);
    });

    testWidgets('offline: nothing sent, loads by itself when back online', (tester) async {
      final repo = withSignal();
      await pumpDetail(tester, repo, offline: true);
      expect(find.text('You’re offline'), findsOneWidget);
      expect(repo.detailCalls, 0);

      ProviderScope.containerOf(tester.element(find.byType(SignalDetailScreen))).read(networkStatusProvider.notifier).set(NetworkStatus.online);
      await tester.pumpAndSettle();
      expect(find.text('1.09050'), findsOneWidget);
      expect(repo.detailCalls, 1);
    });

    testWidgets('expired when opened: marked, levels kept, no sizing, Open market is the main action', (tester) async {
      await pumpDetail(tester, withSignal(validFor: const Duration(minutes: -5)));
      expect(find.text('Expired'), findsOneWidget);
      expect(find.text('This signal has expired'), findsOneWidget);
      expect(find.text('1.09050'), findsOneWidget);
      expect(find.byType(PriceChart), findsOneWidget);
      expect(find.text('Size this trade'), findsNothing);
      expect(find.widgetWithText(FilledButton, 'Open market'), findsOneWidget);
      expect(find.text('Set alert'), findsOneWidget);
    });

    testWidgets('expires while open: the timer flips it to expired', (tester) async {
      final repo = withSignal(validFor: const Duration(minutes: 30));
      await pumpDetail(tester, repo);
      expect(find.text('Expired'), findsNothing);
      expect(find.text('Size this trade'), findsOneWidget);

      await tester.pump(const Duration(minutes: 31));
      await tester.pumpAndSettle();
      expect(find.text('Expired'), findsOneWidget);
      expect(find.text('This signal has expired'), findsOneWidget);
      expect(find.text('Size this trade'), findsNothing);
      expect(repo.detailCalls, 1);
    });
  });

  group('actions', () {
    testWidgets('Size this trade opens the sizing sheet with the plan', (tester) async {
      await pumpDetail(tester, withSignal());
      await tester.tap(find.text('Size this trade'));
      await tester.pumpAndSettle();
      final sheet = tester.widget<SizeTradeSheet>(find.byType(SizeTradeSheet));
      expect(sheet.read.id, 's');
      expect(sheet.instrument.symbol, 'EUR/USD');
    });

    testWidgets('Set alert opens the alert sheet', (tester) async {
      await pumpDetail(tester, withSignal());
      await tester.tap(find.text('Set alert'));
      await tester.pumpAndSettle();
      expect(find.byType(SetAlertSheet), findsOneWidget);
    });

    for (final locale in ['en', 'ar']) {
      for (final expired in [false, true]) {
        testWidgets('largest font ($locale, ${expired ? 'expired' : 'active'}): full labels, never ellipsized',
            (tester) async {
          useLargeText(tester);
          final validFor = expired ? const Duration(minutes: -5) : const Duration(hours: 1);
          await pumpDetail(tester, withSignal(validFor: validFor), locale: locale, height: 4000);
          expect(tester.takeException(), isNull);
          final labels = locale == 'en'
              ? ['Open market', 'Set alert', if (!expired) 'Size this trade']
              : ['افتح السوق', 'ضبط تنبيه', if (!expired) 'احسب حجم الصفقة'];
          for (final label in labels) {
            final finder = find.text(label);
            expect(finder, findsOneWidget, reason: label);
            final text = tester.widget<Text>(finder);
            expect(text.overflow, isNot(TextOverflow.ellipsis), reason: label);
            expect(text.maxLines, isNull, reason: label);
            expect(tester.renderObject<RenderParagraph>(finder).didExceedMaxLines, isFalse, reason: label);
            final button = find.ancestor(of: finder, matching: find.byWidgetPredicate((w) => w is ButtonStyleButton));
            expect(tester.getSize(button).height, greaterThanOrEqualTo(48), reason: label);
          }
          // المنتهية: "افتح السوق" بيضل الزر الرئيسي
          expect(
            find.ancestor(of: find.text(labels.first), matching: find.byType(FilledButton)),
            expired ? findsOneWidget : findsNothing,
          );
        });
      }
    }

    testWidgets('Open market opens the instrument', (tester) async {
      await pumpDetail(tester, withSignal());
      await tester.tap(find.text('Open market'));
      await tester.pumpAndSettle();
      expect(find.byType(MarketScreen), findsOneWidget);
    });
  });

  group('navigation', () {
    testWidgets('a list row opens its detail once (double tap), Hero tag shared, back returns', (tester) async {
      usePhoneSize(tester, height: 1200);
      final repo = FakeSignals()..byId['s'] = signal('s');
      await tester.pumpWidget(await testScope(
        const TestApp(home: SignalsScreen()),
        overrides: [signalsRepositoryProvider.overrideWithValue(repo)],
      ));
      await tester.pumpAndSettle();
      final row = find.byType(SignalRow);
      await tester.tap(row);
      await tester.tap(row, warnIfMissed: false);
      await tester.pumpAndSettle();
      expect(find.byType(SignalDetailScreen), findsOneWidget);
      final hero = tester.widget<Hero>(
        find.descendant(of: find.byType(SignalDetailScreen), matching: find.byType(Hero)),
      );
      expect(hero.tag, SignalRow.heroTag('s'));
      // من القائمة: بدون طلب
      expect(repo.detailCalls, 0);

      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.byType(SignalDetailScreen), findsNothing);
      expect(find.byType(SignalRow), findsOneWidget);
    });

    testWidgets('reduced motion: no Hero flight, sections show at once', (tester) async {
      tester.platformDispatcher.accessibilityFeaturesTestValue = const FakeAccessibilityFeatures(disableAnimations: true);
      addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
      await pumpDetail(tester, withSignal());
      final mode = tester.widget<HeroMode>(
        find.ancestor(of: find.byType(Hero), matching: find.byType(HeroMode)).first,
      );
      expect(mode.enabled, isFalse);
      expect(find.text('1.09050'), findsOneWidget);
    });

    testWidgets('a signal path without its symbol shows the unknown-route screen', (tester) async {
      usePhoneSize(tester);
      await tester.pumpWidget(await testScope(const TestApp(home: SizedBox())));
      testRouter(tester).push('${AppRoutes.signals}/s');
      await tester.pumpAndSettle();
      expect(find.byType(SignalDetailScreen), findsNothing);
      expect(find.textContaining('Route not found'), findsOneWidget);
    });
  });
}
