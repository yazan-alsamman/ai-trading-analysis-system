// A3a + A3c: الاستراتيجية = طريقة تحليل فنية + الفلاتر (النموذج مش خيار: دايمًا
// شغّال). كتالوج الطرق (MA Crossover، RSI Reversal)، حفظ الطريقة (مع الترحيل من
// `ai_model` والبيانات التالفة)، القائمة لكل طريقة، Backtest حتمي لكل طريقة،
// و Insights ما بتتأثر.

import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:trading_app/core/data/json.dart';
import 'package:trading_app/core/storage/preferences_provider.dart';
import 'package:trading_app/core/widgets/direction_badge.dart';
import 'package:trading_app/features/backtest/data/backtest_repository.dart';
import 'package:trading_app/features/backtest/models/backtest.dart';
import 'package:trading_app/features/backtest/view_models/backtest_view_model.dart';
import 'package:trading_app/features/insights/data/insights_repository.dart';
import 'package:trading_app/features/insights/models/track_record.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/markets/data/simulated_market_source.dart';
import 'package:trading_app/features/markets/models/market_models.dart';
import 'package:trading_app/features/signals/data/analysis_methods_repository.dart';
import 'package:trading_app/features/signals/data/signal_profile_repository.dart';
import 'package:trading_app/features/signals/data/signals_repository.dart';
import 'package:trading_app/features/signals/data/simulated_outcomes.dart';
import 'package:trading_app/features/signals/models/analysis_method.dart';
import 'package:trading_app/features/signals/models/opportunity.dart';
import 'package:trading_app/features/signals/models/signal_profile.dart';
import 'package:trading_app/features/signals/models/signal_rationale.dart';
import 'package:trading_app/features/signals/view_models/signal_detail_view_model.dart';
import 'package:trading_app/features/signals/view_models/signals_feed_view_model.dart';

import '../../helpers/test_app.dart';

const _technical = [AnalysisMethod.maCrossoverId, AnalysisMethod.rsiReversalId];

/// قراءة قابلة للمقارنة: (اتجاه، احتمال، عائد)
(SignalDirection, double, double) _read(Opportunity o) => (o.direction, o.probability, o.riskReward);

final class _MemoryProfiles implements SignalProfileRepository {
  _MemoryProfiles([SignalProfile? saved]) : saved = saved ?? SignalProfile.defaults;

  SignalProfile saved;
  var saves = 0;

  @override
  SignalProfile read() => saved;

  @override
  Future<void> save(SignalProfile profile) async {
    saves++;
    saved = profile;
  }

  @override
  Future<void> clear() async => saved = SignalProfile.defaults;
}

ProviderContainer _container({SignalProfile? saved, _MemoryProfiles? profiles}) {
  final container = ProviderContainer(overrides: [
    connectivityOverride(),
    ...simulatedMarketOverrides(),
    signalProfileRepositoryProvider.overrideWithValue(profiles ?? _MemoryProfiles(saved)),
    backtestRepositoryProvider.overrideWith(
      (ref) => SimulatedBacktestRepository(source: ref.watch(simulatedMarketSourceProvider), step: Duration.zero),
    ),
  ]);
  addTearDown(container.dispose);
  return container;
}

BacktestRequest _wide(BacktestPeriod period, String methodId) => BacktestRequest(
      symbols: kProductSymbols.toSet(),
      timeframes: Timeframe.modelTimeframes.toSet(),
      directions: const {SignalDirection.long, SignalDirection.short},
      minProbability: 0,
      minRiskReward: 0,
      period: period,
      methodId: methodId,
    );

void main() {
  final source = SimulatedMarketSource(clock: () => kTestNow);

  group('AnalysisMethod catalog', () {
    test('lists exactly the technical methods: MA Crossover and RSI Reversal (EN); no AI model', () async {
      final list = await const SimulatedAnalysisMethodsRepository().list();
      expect(AnalysisMethod.knownIds, [AnalysisMethod.maCrossoverId, AnalysisMethod.rsiReversalId]);
      expect(list.map((m) => m.id), AnalysisMethod.knownIds);
      expect(list.map((m) => m.name), ['MA Crossover', 'RSI Reversal']);
      expect(list.map((m) => m.kind), everyElement(AnalysisMethodKind.technical));
      expect(AnalysisMethodKind.values, [AnalysisMethodKind.technical]);
      expect(AnalysisMethod.isKnown(AnalysisMethod.legacyAiModelId), isFalse);
      for (final m in list) {
        expect(m.description, isNotEmpty);
        expect(m.description.contains('\n'), isFalse, reason: 'one line');
      }
    });

    test('Arabic names and descriptions; an unknown language falls back to English', () async {
      const repo = SimulatedAnalysisMethodsRepository();
      final ar = await repo.list(language: 'ar');
      expect(ar.map((m) => m.id), AnalysisMethod.knownIds);
      expect(ar.map((m) => m.name), ['تقاطع المتوسطات', 'انعكاس RSI']);
      expect(ar.every((m) => m.description.isNotEmpty), isTrue);
      expect((await repo.list(language: 'fr')).first.name, 'MA Crossover');
    });

    test('the DTO drops invalid, unknown or wrongly typed items (the old AI model too)', () {
      final parsed = analysisMethodsFromJson([
        {'id': 'ai_model', 'name': 'AI', 'description': 'd', 'kind': 'ai'},
        {'id': 'rsi_reversal', 'name': 'RSI', 'description': 'd', 'kind': 'ai'},
        {'id': 'ma_crossover', 'name': 'MA', 'description': 'd', 'kind': 'technical'},
        {'id': 'macd', 'name': 'MACD', 'description': 'd', 'kind': 'technical'},
        {'id': 'rsi_reversal', 'name': '', 'description': 'd', 'kind': 'technical'},
        {'id': 'ma_crossover', 'name': 'MA', 'description': 'd', 'kind': 'quantum'},
        'oops',
        42,
      ]);
      expect(parsed.single.id, AnalysisMethod.maCrossoverId);
      expect(parsed.single.kind, AnalysisMethodKind.technical);
      expect(analysisMethodsFromJson({'id': 'ai_model'}), isEmpty);
    });

    test('analysisMethodsProvider reads the repository per language', () async {
      final container = _container();
      final en = await container.read(analysisMethodsProvider('en').future);
      final ar = await container.read(analysisMethodsProvider('ar').future);
      expect(en.length, 2);
      expect(ar.first.name, isNot(en.first.name));
    });
  });

  group('Strategy persistence (method + filters)', () {
    test('the default strategy = MA Crossover + all 8 instruments + the existing filters', () {
      final d = SignalProfile.defaults;
      expect(AnalysisMethod.defaultId, AnalysisMethod.maCrossoverId);
      expect(d.methodId, AnalysisMethod.maCrossoverId);
      expect(d.toJson()['method_id'], 'ma_crossover');
      expect(d.symbols, kProductSymbols.toSet());
      expect(d.minProbability, 0.6);
      expect(d.minRiskReward, 1.5);
      expect(d.isValid, isTrue);
    });

    for (final id in AnalysisMethod.knownIds) {
      test('round trip keeps the method ($id) and the filters', () {
        final p = SignalProfile.defaults.copyWith(methodId: id, symbols: {'EUR/USD'}, minProbability: 0.7);
        final back = SignalProfile.fromJson(Json(jsonDecode(jsonEncode(p.toJson())) as Map<String, Object?>));
        expect(back, p);
        expect(back.methodId, id);
        expect(p.toJson()['method_id'], id);
      });
    }

    test('a stored profile without method_id (before A3) loads as MA Crossover, filters kept', () async {
      final legacy = {
        ...SignalProfile.defaults.copyWith(symbols: {'XAU/USD'}).toJson()
      }..remove('method_id');
      SharedPreferences.setMockInitialValues({LocalSignalProfileRepository.storageKey: jsonEncode(legacy)});
      final repo = LocalSignalProfileRepository(await SharedPreferences.getInstance());
      final read = repo.read();
      expect(read.methodId, AnalysisMethod.maCrossoverId);
      expect(read.symbols, {'XAU/USD'});
      expect(read, isNot(SignalProfile.defaults));
    });

    test('migration (A3c): a stored ai_model, unknown or empty method loads as MA Crossover, filters kept', () async {
      final custom = SignalProfile.defaults.copyWith(symbols: {'XAU/USD'}, minProbability: 0.7).toJson();
      for (final method in [AnalysisMethod.legacyAiModelId, 'macd', '']) {
        SharedPreferences.setMockInitialValues({
          LocalSignalProfileRepository.storageKey: jsonEncode({...custom, 'method_id': method})
        });
        final repo = LocalSignalProfileRepository(await SharedPreferences.getInstance());
        final read = repo.read();
        expect(read.methodId, AnalysisMethod.maCrossoverId, reason: method);
        expect(read.symbols, {'XAU/USD'}, reason: method);
        expect(read.minProbability, 0.7, reason: method);
      }
      // الافتراضي القديم (النموذج + الفلاتر الافتراضية) = الافتراضي الجديد (ما في استراتيجية خاصة)
      final oldDefault = {...SignalProfile.defaults.toJson(), 'method_id': AnalysisMethod.legacyAiModelId};
      SharedPreferences.setMockInitialValues({LocalSignalProfileRepository.storageKey: jsonEncode(oldDefault)});
      final repo = LocalSignalProfileRepository(await SharedPreferences.getInstance());
      expect(repo.read(), SignalProfile.defaults);
    });

    test('corrupted data falls back to the default (no crash)', () async {
      final custom = SignalProfile.defaults.copyWith(symbols: {'XAU/USD'}).toJson();
      for (final raw in [
        '{not json',
        '[]',
        '"text"',
        jsonEncode({...custom, 'method_id': 7}),
        jsonEncode({
          ...custom,
          'method_id': const ['ai_model']
        }),
        jsonEncode({...custom, 'symbols': 'EUR/USD'}),
        jsonEncode({...custom, 'min_probability': 'high'}),
      ]) {
        SharedPreferences.setMockInitialValues({LocalSignalProfileRepository.storageKey: raw});
        final repo = LocalSignalProfileRepository(await SharedPreferences.getInstance());
        expect(repo.read(), SignalProfile.defaults, reason: raw);
      }
    });

    test('a method-only change is a saved strategy; it stays until removed; Remove → MA Crossover default', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      ProviderContainer open() {
        final c = ProviderContainer(overrides: [sharedPreferencesProvider.overrideWithValue(prefs)]);
        addTearDown(c.dispose);
        return c;
      }

      final first = open();
      final rsi = SignalProfile.defaults.copyWith(methodId: AnalysisMethod.rsiReversalId);
      await first.read(signalProfileProvider.notifier).save(rsi);
      expect(first.read(hasCustomStrategyProvider), isTrue);

      // "إعادة تشغيل": container جديد على نفس التخزين
      final second = open();
      expect(second.read(signalProfileProvider).methodId, AnalysisMethod.rsiReversalId);
      final previous = await second.read(signalProfileProvider.notifier).remove();
      expect(previous.methodId, AnalysisMethod.rsiReversalId);
      expect(second.read(signalProfileProvider), SignalProfile.defaults);
      expect(second.read(signalProfileProvider).methodId, AnalysisMethod.maCrossoverId);
      expect(open().read(hasCustomStrategyProvider), isFalse);
    });

    test('saving an unknown method is rejected', () async {
      final container = _container();
      expect(
        () => container.read(signalProfileProvider.notifier).save(SignalProfile.defaults.copyWith(methodId: 'x')),
        throwsArgumentError,
      );
    });
  });

  group('Signals feed per method', () {
    final repo = SimulatedSignalsRepository(source: source);

    test('every signal carries a technical method (default MA Crossover, never AI) and the model probability', () {
      for (final symbol in kProductSymbols) {
        final byDefault = repo.opportunitiesJson(symbol);
        expect(byDefault, repo.opportunitiesJson(symbol, methodId: AnalysisMethod.maCrossoverId));
        for (final method in AnalysisMethod.knownIds) {
          for (final json in repo.opportunitiesJson(symbol, methodId: method)) {
            expect(json['methodId'], method);
            expect(json['id'], endsWith('@$method'));
            expect(json['probability'], inExclusiveRange(0, 1));
          }
        }
      }
      expect(repo.opportunitiesJson('EUR/USD', methodId: AnalysisMethod.legacyAiModelId), isEmpty);
    });

    test('technical methods: deterministic, own ids, own indicator, and a different read', () async {
      for (final method in _technical) {
        var differs = 0;
        for (final symbol in kProductSymbols) {
          final a = await repo.opportunities(symbol, methodId: method);
          final b = await SimulatedSignalsRepository(source: source).opportunities(symbol, methodId: method);
          final other = await repo.opportunities(symbol, methodId: _technical.firstWhere((m) => m != method));
          expect(a.map(_read), b.map(_read), reason: 'same bucket, same numbers');
          for (final (i, o) in a.indexed) {
            expect(o.methodId, method);
            expect(o.id, endsWith('@$method'));
            expect(o.id.split('@').first, other[i].id.split('@').first, reason: 'same instrument, timeframe, bucket');
            expect(o.indicator, isNotNull);
            if (_read(o) != _read(other[i])) differs++;
          }
        }
        expect(differs, greaterThan(12), reason: '$method differs from the other method on most of the 24 reads');
      }
    });

    test('RSI Reversal reads RSI: oversold → Long, overbought → Short, mid-range → no signal', () async {
      for (final symbol in kProductSymbols) {
        for (final o in await repo.opportunities(symbol, methodId: AnalysisMethod.rsiReversalId)) {
          final rsi = o.indicator!;
          expect(rsi, inInclusiveRange(0, 100));
          if (o.isDetected) {
            expect(o.direction, rsi <= 50 ? SignalDirection.long : SignalDirection.short);
            expect(rsi <= 35 || rsi >= 65, isTrue);
          }
        }
      }
    });

    test('opportunity(id) gives the same numbers for every method; bad ids → null', () async {
      for (final method in AnalysisMethod.knownIds) {
        for (final o in await repo.opportunities('XAU/USD', methodId: method)) {
          final again = await repo.opportunity(o.id);
          expect(again, isNotNull, reason: o.id);
          expect(_read(again!), _read(o));
          expect(again.methodId, method);
          expect(again.entryZone, o.entryZone);
        }
      }
      final base = (await repo.opportunities('EUR/USD')).first.id.split('@').first;
      expect(await repo.opportunity(base), isNull, reason: 'an id without a method (before A3c) is not found');
      expect(await repo.opportunity('$base@ai_model'), isNull, reason: 'the AI model is not a method');
      expect(await repo.opportunity('$base@macd'), isNull);
      expect(await repo.opportunity('@rsi_reversal'), isNull);
    });

    test('feed(profile) uses the strategy method and its filters', () async {
      for (final method in AnalysisMethod.knownIds) {
        final profile = SignalProfile.defaults.copyWith(methodId: method, minProbability: 0, minRiskReward: 0);
        final feed = await repo.feed(profile);
        expect(feed, isNotEmpty, reason: method);
        expect(feed.every((o) => o.methodId == method && o.isDetected), isTrue);
      }
      final byDefault = await repo.feed(SignalProfile.defaults);
      final ma = await repo.feed(SignalProfile.defaults.copyWith(methodId: AnalysisMethod.maCrossoverId));
      final rsi = await repo.feed(SignalProfile.defaults.copyWith(methodId: AnalysisMethod.rsiReversalId));
      expect(byDefault.map((o) => o.id), ma.map((o) => o.id));
      expect(rsi.map((o) => o.id), isNot(ma.map((o) => o.id)));
    });

    test('list, detail and Market model read show the same numbers for the saved strategy', () async {
      for (final method in AnalysisMethod.knownIds) {
        final container = _container(
          saved: SignalProfile.defaults.copyWith(methodId: method, minProbability: 0, minRiskReward: 0),
        );
        container.listen(signalsFeedViewModelProvider, (_, __) {});
        final feed = await container.read(signalsFeedViewModelProvider.future);
        final signal = feed.first;
        expect(signal.methodId, method);

        final market = await container.read(opportunitiesProvider(signal.symbol).future);
        final same = market.firstWhere((o) => o.id == signal.id);
        expect(_read(same), _read(signal));

        // تفاصيل بدون القائمة (من المعرّف مباشرة)
        final fresh = _container(saved: SignalProfile.defaults.copyWith(methodId: method));
        final sub = fresh.listen(signalDetailViewModelProvider(signal.id), (_, __) {});
        final detail = (await fresh.read(signalDetailViewModelProvider(signal.id).future))!;
        expect(_read(detail.signal), _read(signal));
        expect(detail.methodId, method);
        sub.close();
      }
    });

    test('changing the saved method recomputes the Market read', () async {
      final container = _container();
      container.listen(opportunitiesProvider('EUR/USD'), (_, __) {});
      final ma = await container.read(opportunitiesProvider('EUR/USD').future);
      await container
          .read(signalProfileProvider.notifier)
          .save(SignalProfile.defaults.copyWith(methodId: AnalysisMethod.rsiReversalId));
      final rsi = await container.read(opportunitiesProvider('EUR/USD').future);
      expect(ma.every((o) => o.methodId == AnalysisMethod.maCrossoverId), isTrue);
      expect(rsi.every((o) => o.methodId == AnalysisMethod.rsiReversalId), isTrue);
    });

    test('reasons follow the method (MA cross / RSI); the model reasons are always there', () async {
      final now = source.now();
      for (final (method, type) in [
        (AnalysisMethod.maCrossoverId, MaCrossReason),
        (AnalysisMethod.rsiReversalId, RsiReason),
      ]) {
        final feed =
            await repo.feed(SignalProfile.defaults.copyWith(methodId: method, minProbability: 0, minRiskReward: 0));
        final reasons = buildSignalRationale(feed.first, siblings: null, now: now);
        expect(reasons.map((r) => r.runtimeType), contains(type));
        // احتمال النموذج والعائد : المخاطرة بكل إشارة، مهما كانت الطريقة
        expect(reasons.map((r) => r.runtimeType), containsAll([ChanceReason, RewardRiskReason]));
        expect(reasons.length, greaterThanOrEqualTo(kTopReasons));
      }
    });
  });

  group('Backtest per method', () {
    final repo = SimulatedBacktestRepository(source: source, step: Duration.zero);

    // A3c: كان "AI model بدون فلاتر = Insights"؛ النموذج مش طريقة، فالقاعدة صارت:
    // حتمي ونفس النتيجة بكل مكان (المحرّك، الـ repository، الـ ViewModel) لنفس
    // الاستراتيجية والفترة.
    for (final period in [BacktestPeriod.d30, BacktestPeriod.d90]) {
      for (final method in _technical) {
        test('$method, no filters, ${period.days} days: deterministic and identical across screens', () async {
          final request = _wide(period, method);
          final a = await repo.run(request);
          final b = await SimulatedBacktestRepository(source: source, step: Duration.zero).run(request);
          expect(
              (b.signals, b.hits, b.avgRiskReward, b.maxDrawdown), (a.signals, a.hits, a.avgRiskReward, a.maxDrawdown));
          final outcomes = SimulatedOutcomes(source);
          final last = outcomes.lastFullDay;
          final cells = outcomes.total(last - period.days + 1, last, methodId: method);
          expect((a.signals, a.hits), (cells.resolved, cells.hits));

          // نفس الاستراتيجية من شاشة Backtest (الـ ViewModel) = نفس النتيجة
          final container = _container(
            saved: SignalProfile.defaults.copyWith(
              methodId: method,
              timeframes: Timeframe.modelTimeframes.toSet(),
              directions: const {SignalDirection.long, SignalDirection.short},
              minProbability: 0,
              minRiskReward: 0,
            ),
          );
          container.listen(backtestViewModelProvider, (_, __) {});
          final vm = container.read(backtestViewModelProvider.notifier)..selectPeriod(period);
          await vm.run();
          final status = container.read(backtestViewModelProvider).status as BacktestDone;
          expect((status.result.signals, status.result.hits, status.result.maxDrawdown),
              (a.signals, a.hits, a.maxDrawdown));
        });
      }
    }

    test('technical methods: deterministic and different from each other', () async {
      final seen = <(int, int, double?)>{};
      for (final method in _technical) {
        final a = await repo.run(_wide(BacktestPeriod.y1, method));
        final b = await SimulatedBacktestRepository(source: source, step: Duration.zero)
            .run(_wide(BacktestPeriod.y1, method));
        expect(
            (b.signals, b.hits, b.avgRiskReward, b.maxDrawdown), (a.signals, a.hits, a.avgRiskReward, a.maxDrawdown));
        expect(a.signals, greaterThan(kMinTrackSample));
        expect(seen.add((a.signals, a.hits, a.avgRiskReward)), isTrue, reason: '$method gives its own result');
      }
    });

    test('the model record (Insights) has its own cells; methods never read them', () {
      final outcomes = SimulatedOutcomes(source);
      final last = outcomes.lastFullDay;
      expect(SimulatedOutcomes.methodSalt(null), 0);
      for (final method in _technical) {
        expect(SimulatedOutcomes.methodSalt(method), isNot(0));
      }
      final model = outcomes.total(last - 89, last);
      for (final method in _technical) {
        final cells = outcomes.total(last - 89, last, methodId: method);
        expect((cells.resolved, cells.hits), isNot((model.resolved, model.hits)), reason: method);
      }
      for (var day = last - 30; day <= last; day++) {
        for (final s in kProductSymbols) {
          for (final tf in Timeframe.modelTimeframes) {
            expect(outcomes.cell(s, tf, day, methodId: null), outcomes.cell(s, tf, day));
          }
        }
      }
    });

    test('the request carries the method (body method_id); unknown method = invalid', () {
      final saved = SignalProfile.defaults.copyWith(methodId: AnalysisMethod.maCrossoverId);
      final request = BacktestRequest.from(saved, symbols: saved.symbols, period: BacktestPeriod.d90);
      expect(request.methodId, AnalysisMethod.maCrossoverId);
      expect(request.toJson()['method_id'], AnalysisMethod.maCrossoverId);
      final override =
          BacktestRequest.from(saved, symbols: saved.symbols, period: BacktestPeriod.d90, methodId: 'rsi_reversal');
      expect(override.methodId, AnalysisMethod.rsiReversalId);
      expect(_wide(BacktestPeriod.d90, 'macd').isValid, isFalse);
    });

    test('Backtest pre-fills the saved method; a session change is never saved', () async {
      final profiles = _MemoryProfiles(SignalProfile.defaults.copyWith(methodId: AnalysisMethod.rsiReversalId));
      final container = _container(profiles: profiles);
      container.listen(backtestViewModelProvider, (_, __) {});
      expect(container.read(backtestViewModelProvider).methodId, AnalysisMethod.rsiReversalId);

      final vm = container.read(backtestViewModelProvider.notifier);
      vm.selectMethod(AnalysisMethod.maCrossoverId);
      vm.selectMethod('macd'); // مش معروفة: ما بتتغيّر
      expect(container.read(backtestViewModelProvider).methodId, AnalysisMethod.maCrossoverId);
      await vm.run();
      final status = container.read(backtestViewModelProvider).status;
      expect(status, isA<BacktestDone>());
      expect(container.read(backtestViewModelProvider).request.methodId, AnalysisMethod.maCrossoverId);

      expect(profiles.saves, 0);
      expect(container.read(signalProfileProvider).methodId, AnalysisMethod.rsiReversalId);
    });

    test('changing the method mid-run cancels it and returns to idle', () async {
      final container = ProviderContainer(overrides: [
        connectivityOverride(),
        ...simulatedMarketOverrides(),
        signalProfileRepositoryProvider.overrideWithValue(_MemoryProfiles()),
      ]);
      addTearDown(container.dispose);
      container.listen(backtestViewModelProvider, (_, __) {});
      final vm = container.read(backtestViewModelProvider.notifier);
      final run = vm.run();
      expect(container.read(backtestViewModelProvider).isRunning, isTrue);
      vm.selectMethod(AnalysisMethod.rsiReversalId); // مختلفة عن الافتراضي (MA)
      await run;
      expect(container.read(backtestViewModelProvider).status, isA<BacktestIdle>());
    });
  });

  group('Insights is the AI model track record', () {
    test('the accuracy line and Insights do not change with the saved method', () async {
      final ai = _container();
      final rsi = _container(saved: SignalProfile.defaults.copyWith(methodId: AnalysisMethod.rsiReversalId));
      final a = await ai.read(modelAccuracyProvider.future);
      final b = await rsi.read(modelAccuracyProvider.future);
      expect((b.resolved, b.hits), (a.resolved, a.hits));
      final record = await SimulatedInsightsRepository(source: source).trackRecord(InsightsPeriod.d90);
      expect((record.overall.resolved, record.overall.hits), (a.resolved, a.hits));
    });
  });
}
