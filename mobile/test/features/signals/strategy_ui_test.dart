// A3b: واجهة "Strategy" (قسم طريقة التحليل بالـ sheet، سطر البطاقة) و
// "Request analysis" (الـ sheet بحالاتها، الضغطة المزدوجة، الإلغاء، بدون اتصال،
// تغيير الطريقة لطلب واحد ما بينحفظ، النتيجة المحايدة، التنقّل للتفاصيل،
// "Strategy used"، شارة "Requested by you"، سطر Backtest)، EN/AR وخط كبير.

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:trading_app/app/router/app_routes.dart';
import 'package:trading_app/app/shell/shell_tab.dart';
import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/core/widgets/app_button.dart';
import 'package:trading_app/core/widgets/not_advice_notice.dart';
import 'package:trading_app/features/backtest/data/backtest_repository.dart';
import 'package:trading_app/features/backtest/views/backtest_screen.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/markets/data/simulated_market_source.dart';
import 'package:trading_app/features/markets/models/market_models.dart';
import 'package:trading_app/features/markets/views/market_screen.dart';
import 'package:trading_app/features/signals/data/signal_profile_repository.dart';
import 'package:trading_app/features/signals/data/signals_repository.dart';
import 'package:trading_app/features/signals/models/analysis_method.dart';
import 'package:trading_app/features/signals/models/analysis_request.dart';
import 'package:trading_app/features/signals/models/model_accuracy.dart';
import 'package:trading_app/features/signals/models/opportunity.dart';
import 'package:trading_app/features/signals/models/signal_profile.dart';
import 'package:trading_app/features/signals/view_models/signal_detail_view_model.dart';
import 'package:trading_app/features/signals/views/signal_detail_screen.dart';
import 'package:trading_app/features/signals/views/signals_screen.dart';
import 'package:trading_app/features/signals/widgets/request_analysis_sheet.dart';
import 'package:trading_app/features/signals/widgets/signal_row.dart';
import 'package:trading_app/features/signals/widgets/strategy_bar.dart';
import 'package:trading_app/features/signals/widgets/strategy_sheet.dart';

import '../../helpers/test_app.dart';

final _source = SimulatedMarketSource(clock: () => kTestNow);

/// أول (أداة، إطار) قراءتها بـ [method] مكتشفة / محايدة على [kTestNow]
AnalysisRequest _find({required bool detected, String method = AnalysisMethod.maCrossoverId}) {
  final repo = SimulatedSignalsRepository(source: _source);
  for (final symbol in kProductSymbols) {
    for (final (i, json) in repo.opportunitiesJson(symbol, methodId: method).indexed) {
      if ((json['status'] == 'detected') == detected) {
        return AnalysisRequest(symbol: symbol, timeframe: Timeframe.modelTimeframes[i], methodId: method);
      }
    }
  }
  throw StateError('no ${detected ? 'detected' : 'neutral'} read at kTestNow');
}

/// مصدر بنتحكّم فيه: الطلب بيوقف عند [pending] (قبل التحليل) وعند [analyzing]
/// (قبل النتيجة) لحد ما نكمّلهن، بعدين نتيجة المحاكى بدون انتظار
final class _Gated implements SignalsRepository {
  _Gated() : sim = SimulatedSignalsRepository(source: _source, requestLatencyScale: 0);

  final SimulatedSignalsRepository sim;
  final calls = <({AnalysisRequest request, AnalysisCancelToken? cancel})>[];
  var pending = Completer<void>();
  var analyzing = Completer<void>();
  Object? fail;

  @override
  bool get isSimulated => true;

  @override
  Future<Opportunity> requestAnalysis(
    AnalysisRequest request, {
    AnalysisCancelToken? cancel,
    void Function(AnalysisStage stage)? onStage,
  }) async {
    calls.add((request: request, cancel: cancel));
    onStage?.call(AnalysisStage.pending);
    await pending.future;
    if (cancel?.isCancelled ?? false) throw const AnalysisCancelledException();
    onStage?.call(AnalysisStage.analyzing);
    await analyzing.future;
    if (cancel?.isCancelled ?? false) throw const AnalysisCancelledException();
    if (fail case final error?) throw error;
    return sim.requestAnalysis(request, cancel: cancel);
  }

  @override
  Future<List<Opportunity>> opportunities(String symbol, {String methodId = AnalysisMethod.defaultId}) =>
      sim.opportunities(symbol, methodId: methodId);

  @override
  Future<List<Opportunity>> feed(SignalProfile profile) => sim.feed(profile);

  @override
  Future<Opportunity?> opportunity(String id) => sim.opportunity(id);

  @override
  Future<ModelAccuracy> accuracy() => sim.accuracy();
}

Override _instant() => signalsRepositoryProvider.overrideWith(
      (ref) => SimulatedSignalsRepository(source: ref.watch(simulatedMarketSourceProvider), requestLatencyScale: 0),
    );

Map<String, Object> _stored(SignalProfile profile) =>
    {LocalSignalProfileRepository.storageKey: jsonEncode(profile.toJson())};

/// RSI Reversal + 3 أدوات + فوق 65%
final _rsi = SignalProfile.defaults.copyWith(
  methodId: AnalysisMethod.rsiReversalId,
  symbols: {'EUR/USD', 'XAU/USD', 'GBP/USD'},
  minProbability: 0.65,
);

Future<ProviderContainer> _pumpSignals(
  WidgetTester tester, {
  String locale = 'en',
  String theme = 'light',
  Map<String, Object> prefs = const {},
  List<Override> overrides = const [],
  double height = 1800,
}) async {
  usePhoneSize(tester, height: height);
  await tester.pumpWidget(await testScope(
    const TestApp(home: SignalsScreen()),
    locale: locale,
    prefs: {themeModeStorageKey: theme, ...prefs},
    overrides: [
      backtestRepositoryProvider.overrideWith(
        (ref) => SimulatedBacktestRepository(source: ref.watch(simulatedMarketSourceProvider), step: Duration.zero),
      ),
      ...overrides,
    ],
  ));
  await tester.pumpAndSettle();
  return ProviderScope.containerOf(tester.element(find.byType(SignalsScreen, skipOffstage: false)));
}

Finder _inRequest(Finder finder) => find.descendant(of: find.byType(RequestAnalysisSheet), matching: finder);
Finder _inStrategy(Finder finder) => find.descendant(of: find.byType(StrategySheet), matching: finder);

Future<void> _tap(WidgetTester tester, Finder finder) async {
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

Future<void> _openRequest(WidgetTester tester, {String label = 'Request analysis'}) async {
  await tester.tap(find.widgetWithText(OutlinedButton, label));
  await tester.pumpAndSettle();
}

Future<void> _pick(WidgetTester tester, AnalysisRequest r) async {
  await _tap(tester, _inRequest(find.widgetWithText(ChoiceChip, r.symbol)));
  await _tap(tester, _inRequest(find.widgetWithText(ChoiceChip, r.timeframe.label)));
}

AppButton _analyzeButton(WidgetTester tester) =>
    tester.widget<AppButton>(_inRequest(find.byWidgetPredicate((w) => w is AppButton && w.label == 'Analyze')));

void main() {
  group('Strategy sheet: analysis method', () {
    testWidgets('first section = 3 methods with descriptions; Save stays open; the card follows', (tester) async {
      final c = await _pumpSignals(tester);
      await tester.tap(find.byType(StrategyBar));
      await tester.pumpAndSettle();

      // أول قسم قبل الأدوات
      final method = _inStrategy(find.text('Analysis method'));
      expect(method, findsOneWidget);
      expect(tester.getTopLeft(method).dy, lessThan(tester.getTopLeft(_inStrategy(find.text('Instruments'))).dy));
      // A3c: الطرق الفنية بس، النموذج مش خيار
      for (final name in ['MA Crossover', 'RSI Reversal']) {
        expect(_inStrategy(find.bySemanticsLabel(RegExp('^${RegExp.escape(name)}\\. .+'))), findsOneWidget);
      }
      expect(_inStrategy(find.textContaining('AI model')), findsNothing);
      expect(_inStrategy(find.byWidgetPredicate((w) => w is Semantics && w.properties.inMutuallyExclusiveGroup == true)),
          findsNWidgets(2));
      expect(find.text('Follows the trend when the 10-period average crosses the 30-period average.'), findsOneWidget);

      // الافتراضي محدّد، والطريقة بتنعلن كـ radio
      final ma = tester.getSemantics(find.bySemanticsLabel(RegExp(r'^MA Crossover\. ')));
      expect(ma, isSemantics(isChecked: true, hasCheckedState: true, isInMutuallyExclusiveGroup: true));

      await _tap(tester, _inStrategy(find.text('RSI Reversal')));
      final rsi = tester.getSemantics(find.bySemanticsLabel(RegExp(r'^RSI Reversal\. ')));
      expect(rsi, isSemantics(isChecked: true));
      await _tap(tester, _inStrategy(find.text('Save')));

      expect(find.byType(StrategySheet), findsOneWidget); // ما بتتسكّر
      expect(_inStrategy(find.text('Saved')), findsOneWidget);
      expect(c.read(signalProfileProvider).methodId, AnalysisMethod.rsiReversalId);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString(LocalSignalProfileRepository.storageKey), contains('"method_id":"rsi_reversal"'));
      expect(find.text('RSI Reversal · all instruments · above 60%', skipOffstage: false), findsOneWidget);
    });

    testWidgets('Remove strategy → the default method everywhere; Undo restores RSI Reversal', (tester) async {
      final c = await _pumpSignals(tester, prefs: _stored(_rsi));
      expect(find.text('RSI Reversal · 3 instruments · above 65%'), findsOneWidget);
      await tester.tap(find.byType(StrategyBar));
      await tester.pumpAndSettle();
      final rsi = tester.getSemantics(find.bySemanticsLabel(RegExp(r'^RSI Reversal\. ')));
      expect(rsi, isSemantics(isChecked: true));

      await _tap(tester, _inStrategy(find.text('Remove strategy')));
      expect(find.byType(StrategySheet), findsNothing);
      expect(find.text('Default: MA Crossover · all instruments'), findsOneWidget);
      expect(c.read(signalProfileProvider).methodId, AnalysisMethod.maCrossoverId);

      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();
      expect(find.text('RSI Reversal · 3 instruments · above 65%'), findsOneWidget);
      expect(c.read(signalProfileProvider), _rsi);
    });
  });

  group('Strategy card', () {
    testWidgets('one summary line: the default (EN)', (tester) async {
      await _pumpSignals(tester);
      expect(find.text('Default: MA Crossover · all instruments'), findsOneWidget);
      expect(find.bySemanticsLabel('Strategy. Default: MA Crossover · all instruments'), findsOneWidget);
      expect(find.textContaining('AI model'), findsNothing);
    });

    testWidgets('one summary line: the default (AR)', (tester) async {
      await _pumpSignals(tester, locale: 'ar');
      expect(find.text('الافتراضي: تقاطع المتوسطات · كل الأدوات'), findsOneWidget);
      expect(find.text('الاستراتيجية'), findsOneWidget);
    });

    testWidgets('one summary line: a saved method, instruments and minimum (EN + AR)', (tester) async {
      await _pumpSignals(tester, prefs: _stored(_rsi));
      expect(find.text('RSI Reversal · 3 instruments · above 65%'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
      await _pumpSignals(tester, locale: 'ar', prefs: _stored(_rsi));
      expect(find.text('انعكاس RSI · 3 أدوات · فوق 65%'), findsOneWidget);
    });

    for (final locale in ['en', 'ar']) {
      testWidgets('largest font ($locale): the line wraps, nothing cut off', (tester) async {
        useLargeText(tester);
        await _pumpSignals(tester, locale: locale, prefs: _stored(_rsi), height: 2400);
        final line =
            find.text(locale == 'en' ? 'RSI Reversal · 3 instruments · above 65%' : 'انعكاس RSI · 3 أدوات · فوق 65%');
        expect(line, findsOneWidget);
        final text = tester.widget<Text>(line);
        expect(text.maxLines, isNull);
        expect(text.overflow, isNot(TextOverflow.ellipsis));
        expect(tester.takeException(), isNull);
      });
    }
  });

  group('Request analysis sheet', () {
    testWidgets('header button: a double tap opens one sheet; nothing picked = Analyze off; notice shown',
        (tester) async {
      await _pumpSignals(tester);
      final open = find.widgetWithText(OutlinedButton, 'Request analysis');
      expect(open, findsOneWidget);
      await tester.tap(open);
      await tester.tap(open, warnIfMissed: false);
      await tester.pumpAndSettle();
      expect(find.byType(RequestAnalysisSheet), findsOneWidget);

      expect(_inRequest(find.text('Pick an instrument to analyze.')), findsOneWidget);
      expect(_analyzeButton(tester).onPressed, isNull);
      for (final symbol in kProductSymbols) {
        expect(tester.widget<ChoiceChip>(_inRequest(find.widgetWithText(ChoiceChip, symbol))).selected, isFalse);
      }
      // الإطار الافتراضي 1h، والطريقة المحفوظة ظاهرة كافتراضي
      expect(tester.widget<ChoiceChip>(_inRequest(find.widgetWithText(ChoiceChip, '1h'))).selected, isTrue);
      expect(_inRequest(find.text('MA Crossover · from your saved strategy')), findsOneWidget);
      // "Change for this request": الطرق الفنية بس
      await _tap(tester, _inRequest(find.text('Change for this request')));
      expect(_inRequest(find.bySemanticsLabel(RegExp(r'^(MA Crossover|RSI Reversal)\. '))), findsNWidgets(2));
      expect(_inRequest(find.textContaining('AI model')), findsNothing);
      expect(_inRequest(find.byType(NotAdviceNotice)), findsOneWidget);
    });

    testWidgets('steps: pending → analyzing (announced); a double tap on Analyze sends one request', (tester) async {
      final repo = _Gated();
      await _pumpSignals(tester, overrides: [signalsRepositoryProvider.overrideWithValue(repo)]);
      await _openRequest(tester);
      final request = _find(detected: true);
      await _pick(tester, request);

      final analyze = _inRequest(find.widgetWithText(FilledButton, 'Analyze'));
      await tester.ensureVisible(analyze);
      await tester.pumpAndSettle();
      await tester.tap(analyze);
      await tester.tap(analyze, warnIfMissed: false);
      await tester.pump();
      expect(repo.calls, hasLength(1));
      expect(repo.calls.single.request, request);

      final pending = _inRequest(find.bySemanticsLabel('Sending your request…'));
      expect(pending, findsOneWidget);
      expect(tester.getSemantics(pending).flagsCollection.isLiveRegion, isTrue);
      expect(_inRequest(find.text('Cancel')), findsOneWidget);

      repo.pending.complete();
      await tester.pump();
      await tester.pump();
      final step = 'Analyzing ${request.symbol} · ${request.timeframe.label} with MA Crossover…';
      expect(_inRequest(find.bySemanticsLabel(step)), findsOneWidget);

      repo.analyzing.complete();
      await tester.pumpAndSettle();
      expect(repo.calls, hasLength(1));
      expect(find.byType(SignalDetailScreen), findsOneWidget);
    });

    testWidgets('failed: a message + Try again sends a new request', (tester) async {
      final repo = _Gated()
        ..fail = StateError('boom')
        ..pending.complete()
        ..analyzing.complete();
      await _pumpSignals(tester, overrides: [signalsRepositoryProvider.overrideWithValue(repo)]);
      await _openRequest(tester);
      await _pick(tester, _find(detected: true));
      await _tap(tester, _inRequest(find.widgetWithText(FilledButton, 'Analyze')));

      expect(_inRequest(find.text('The analysis didn’t finish. Nothing was saved.')), findsOneWidget);
      final retry = _inRequest(find.widgetWithText(FilledButton, 'Try again'));
      expect(retry, findsOneWidget);
      repo.fail = null;
      await _tap(tester, retry);
      expect(repo.calls, hasLength(2));
      expect(find.byType(SignalDetailScreen), findsOneWidget);
    });

    testWidgets('offline: says why and sends nothing', (tester) async {
      final repo = _Gated();
      await _pumpSignals(tester, overrides: [
        signalsRepositoryProvider.overrideWithValue(repo),
        connectivityOverride(FakeConnectivitySource(NetworkStatus.offline)),
      ]);
      await _openRequest(tester);
      await _pick(tester, _find(detected: true));
      await _tap(tester, _inRequest(find.widgetWithText(FilledButton, 'Analyze')));

      expect(_inRequest(find.text('You’re offline, so nothing was sent. Connect, then try again.')), findsOneWidget);
      expect(repo.calls, isEmpty);
      expect(find.byType(RequestAnalysisSheet), findsOneWidget);
    });

    testWidgets('closing the sheet cancels the request; nothing opens afterwards', (tester) async {
      final repo = _Gated();
      await _pumpSignals(tester, overrides: [signalsRepositoryProvider.overrideWithValue(repo)]);
      await _openRequest(tester);
      await _pick(tester, _find(detected: true));
      final analyze = _inRequest(find.widgetWithText(FilledButton, 'Analyze'));
      await tester.ensureVisible(analyze);
      await tester.pumpAndSettle();
      await tester.tap(analyze);
      await tester.pump();
      expect(repo.calls, hasLength(1));

      await tester.tap(_inRequest(find.byType(CloseButton)));
      await tester.pumpAndSettle();
      expect(find.byType(RequestAnalysisSheet), findsNothing);
      expect(repo.calls.single.cancel!.isCancelled, isTrue);

      repo.pending.complete();
      repo.analyzing.complete();
      await tester.pumpAndSettle();
      expect(find.byType(SignalDetailScreen), findsNothing);
      expect(find.byType(SignalsScreen), findsOneWidget);
    });

    testWidgets('"Change for this request" uses another method once and never saves it', (tester) async {
      final repo = _Gated()
        ..pending.complete()
        ..analyzing.complete();
      final c = await _pumpSignals(tester, overrides: [signalsRepositoryProvider.overrideWithValue(repo)]);
      await _openRequest(tester);
      await _pick(tester, _find(detected: true, method: AnalysisMethod.rsiReversalId));

      await _tap(tester, _inRequest(find.text('Change for this request')));
      expect(
        _inRequest(find.text('This applies to this request only. Your saved strategy doesn’t change.')),
        findsOneWidget,
      );
      await _tap(tester, _inRequest(find.text('RSI Reversal')));
      expect(_inRequest(find.text('RSI Reversal · this request only')), findsOneWidget);
      await _tap(tester, _inRequest(find.widgetWithText(FilledButton, 'Analyze')));

      expect(repo.calls.single.request.methodId, AnalysisMethod.rsiReversalId);
      expect(c.read(signalProfileProvider).methodId, AnalysisMethod.maCrossoverId);
      expect(c.read(hasCustomStrategyProvider), isFalse);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString(LocalSignalProfileRepository.storageKey), isNull);
      // النتيجة بالتفاصيل بتقول أي طريقة انستعملت
      expect(find.byType(SignalDetailScreen), findsOneWidget);
      expect(find.text('Strategy used: RSI Reversal'), findsOneWidget);
      expect(find.text('Default: MA Crossover · all instruments', skipOffstage: false), findsOneWidget);
    });

    testWidgets('neutral: "No clear setup right now" with the reason, inside the sheet (no navigation)',
        (tester) async {
      await _pumpSignals(tester, overrides: [_instant()]);
      await _openRequest(tester);
      final request = _find(detected: false);
      await _pick(tester, request);
      await _tap(tester, _inRequest(find.widgetWithText(FilledButton, 'Analyze')));

      expect(find.byType(SignalDetailScreen), findsNothing);
      expect(find.byType(RequestAnalysisSheet), findsOneWidget);
      expect(_inRequest(find.text('No clear setup right now')), findsOneWidget);
      expect(_inRequest(find.textContaining('show no confirmed cross yet')), findsOneWidget);
      expect(_inRequest(find.text('Try another timeframe or method, or check again later.')), findsOneWidget);
      expect(_inRequest(find.textContaining('Strategy used: MA Crossover')), findsOneWidget);
      expect(_inRequest(find.byType(NotAdviceNotice)), findsOneWidget);
      // اختيار تاني بيمسح النتيجة القديمة
      final other = Timeframe.modelTimeframes.firstWhere((tf) => tf != request.timeframe);
      await _tap(tester, _inRequest(find.widgetWithText(ChoiceChip, other.label)));
      expect(_inRequest(find.text('No clear setup right now')), findsNothing);
    });
  });

  group('result → Signal detail', () {
    testWidgets('detected: the detail opens (Hero tag, Strategy used, 3 reasons first); the list tags it',
        (tester) async {
      final c = await _pumpSignals(tester, overrides: [_instant()], height: 2400);
      await _openRequest(tester);
      final request = _find(detected: true);
      await _pick(tester, request);
      await _tap(tester, _inRequest(find.widgetWithText(FilledButton, 'Analyze')));

      expect(find.byType(RequestAnalysisSheet), findsNothing);
      final screen = tester.widget<SignalDetailScreen>(find.byType(SignalDetailScreen));
      expect(screen.signalId, startsWith(SimulatedSignalsRepository.requestedPrefix));
      expect(screen.symbol, request.symbol);
      expect(find.byWidgetPredicate((w) => w is Hero && w.tag == SignalRow.heroTag(screen.signalId)), findsOneWidget);
      expect(find.text('Strategy used: MA Crossover'), findsOneWidget);
      expect(find.byType(NotAdviceNotice), findsOneWidget);

      final detail = (await c.read(signalDetailViewModelProvider(screen.signalId).future))!;
      expect(detail.rationale.length, greaterThan(3));
      expect(find.text('More reasons (${detail.rationale.length - 3})'), findsOneWidget);
      expect(find.textContaining('Influence: '), findsNWidgets(3));

      await tester.pageBack();
      await tester.pumpAndSettle();
      final row = find.byWidgetPredicate((w) => w is SignalRow && w.signal.id == screen.signalId);
      expect(row, findsOneWidget);
      expect(find.descendant(of: row, matching: find.text('Requested by you')), findsOneWidget);
      expect(find.byType(RequestedTag), findsOneWidget);
      expect(find.bySemanticsLabel(RegExp(r'Requested by you$')), findsOneWidget);
      expect(find.byType(NotAdviceNotice), findsOneWidget);
    });

    testWidgets('from the Market screen: the instrument is pre-selected and the detail opens in the same tab',
        (tester) async {
      final request = _find(detected: true);
      usePhoneSize(tester, height: 2400);
      await tester.pumpWidget(await testScope(
        TestApp(initialRoute: AppRoutes.market(request.symbol)),
        overrides: [_instant()],
      ));
      await settleMocks(tester);
      expect(find.byType(MarketScreen), findsOneWidget);

      await _tap(tester, find.widgetWithText(OutlinedButton, 'Request analysis'));
      expect(find.byType(RequestAnalysisSheet), findsOneWidget);
      expect(tester.widget<ChoiceChip>(_inRequest(find.widgetWithText(ChoiceChip, request.symbol))).selected, isTrue);
      expect(_inRequest(find.text('Pick an instrument to analyze.')), findsNothing);

      await _tap(tester, _inRequest(find.widgetWithText(ChoiceChip, request.timeframe.label)));
      await _tap(tester, _inRequest(find.widgetWithText(FilledButton, 'Analyze')));
      await settleMocks(tester);

      expect(find.byType(SignalDetailScreen), findsOneWidget);
      final path = testRouter(tester).state.uri.path;
      expect(path, startsWith('/home/signal/'));
      expect(find.byType(NavigationBar), findsOneWidget); // نفس التبويب، الشريط ظاهر

      await tester.pageBack();
      await settleMocks(tester);
      expect(find.byType(MarketScreen), findsOneWidget);
    });

    test('detail paths: Signals keeps /signals/:id, other tabs use /<tab>/signal/:id', () {
      expect(AppRoutes.signalDetail('A/B-1', symbol: 'EUR/USD'), '/signals/A%2FB-1?symbol=EUR%2FUSD');
      expect(AppRoutes.signalDetail('x', symbol: 'XAU/USD', tab: ShellTab.home), '/home/signal/x?symbol=XAU%2FUSD');
      expect(AppRoutes.signalDetail('x', symbol: 'XAU/USD', tab: ShellTab.community),
          '/community/signal/x?symbol=XAU%2FUSD');
      expect(AppRoutes.signalDetail('x', symbol: 'XAU/USD', tab: ShellTab.profile), '/signals/x?symbol=XAU%2FUSD');
    });
  });

  group('Backtest', () {
    testWidgets('"Using your saved strategy · RSI Reversal"', (tester) async {
      await _pumpSignals(tester, prefs: _stored(_rsi));
      await tester.tap(find.byType(StrategyBar));
      await tester.pumpAndSettle();
      await _tap(tester, _inStrategy(find.text('Test on past data')));
      expect(find.byType(BacktestScreen), findsOneWidget);
      expect(find.text('Using your saved strategy · RSI Reversal'), findsOneWidget);
    });
  });

  group('accessibility', () {
    for (final theme in ['light', 'dark']) {
      for (final locale in ['en', 'ar']) {
        testWidgets('request sheet at text scale 2.0 ($locale, $theme): fits, 48 dp, labelled', (tester) async {
          useLargeText(tester);
          final handle = tester.ensureSemantics();
          final repo = _Gated();
          await _pumpSignals(
            tester,
            locale: locale,
            theme: theme,
            overrides: [signalsRepositoryProvider.overrideWithValue(repo)],
            height: 4000,
          );
          await _openRequest(tester, label: locale == 'en' ? 'Request analysis' : 'طلب تحليل');
          expect(find.byType(RequestAnalysisSheet), findsOneWidget);
          await _tap(tester, _inRequest(find.widgetWithText(ChoiceChip, 'EUR/USD')));
          await _tap(tester, _inRequest(find.text(locale == 'en' ? 'Change for this request' : 'غيّرها لهذا الطلب')));
          expect(tester.takeException(), isNull);
          await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
          await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
          handle.dispose();
        });
      }
    }

    testWidgets('reduced motion: the step bar is static (no endless animation)', (tester) async {
      tester.platformDispatcher.accessibilityFeaturesTestValue =
          const FakeAccessibilityFeatures(disableAnimations: true);
      addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
      final repo = _Gated();
      await _pumpSignals(tester, overrides: [signalsRepositoryProvider.overrideWithValue(repo)]);
      await _openRequest(tester);
      await _pick(tester, _find(detected: true));
      await tester.tap(_inRequest(find.widgetWithText(FilledButton, 'Analyze')));
      await tester.pumpAndSettle(); // بيخلص: ما في حركة لا نهائية
      expect(tester.widget<LinearProgressIndicator>(find.byType(LinearProgressIndicator)).value, isNotNull);
      repo.pending.complete();
      repo.analyzing.complete();
      await tester.pumpAndSettle();
    });
  });
}
