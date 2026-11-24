// اختبارات H3: تحليل صورة الشارت كإجراء رئيسي بالمساعد - البصمة، التحقق من
// الصورة، الحد اليومي (العدّاد، حدّ اليوم، الحفظ)، تحويل 429، نفس الصورة =
// نفس النتيجة بدون ما تنحسب، الـ ViewModel (إلغاء، ضغطتين، بدون اتصال،
// سباق)، تطابق الأرقام مع إشارة الاستراتيجية المحفوظة، والواجهة.

import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:trading_app/core/data/clock.dart';
import 'package:trading_app/core/data/json.dart';
import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/data/sha256.dart';
import 'package:trading_app/core/format/formatters.dart';
import 'package:trading_app/core/network/api_exception.dart';
import 'package:trading_app/core/storage/preferences_provider.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/core/widgets/direction_badge.dart';
import 'package:trading_app/core/widgets/not_advice_notice.dart';
import 'package:trading_app/features/assistant/data/assistant_repository.dart';
import 'package:trading_app/features/assistant/data/chart_analysis_dto.dart';
import 'package:trading_app/features/assistant/data/chart_analysis_repository.dart';
import 'package:trading_app/features/assistant/data/chart_image_picker.dart';
import 'package:trading_app/features/assistant/models/assistant_models.dart';
import 'package:trading_app/features/assistant/models/chart_analysis.dart';
import 'package:trading_app/features/assistant/view_models/assistant_view_model.dart';
import 'package:trading_app/features/assistant/view_models/chart_quota_view_model.dart';
import 'package:trading_app/features/assistant/views/assistant_screen.dart';
import 'package:trading_app/features/assistant/widgets/chat_messages.dart';
import 'package:trading_app/features/forecast/data/forecast_repository.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/markets/models/market_models.dart';
import 'package:trading_app/features/markets/views/market_screen.dart';
import 'package:trading_app/features/signals/models/analysis_method.dart';
import 'package:trading_app/features/signals/models/opportunity.dart';
import 'package:trading_app/features/signals/models/signal_plan.dart';
import 'package:trading_app/features/signals/models/signal_profile.dart';
import 'package:trading_app/features/signals/data/signal_profile_repository.dart';
import 'package:trading_app/l10n/app_localizations.dart';

import '../../helpers/test_app.dart';

/// PNG 1×1 حقيقي؛ [salt] بيضيف بايتات بالآخر (صورة تانية = بصمة تانية)
Uint8List _png([int salt = 0]) => Uint8List.fromList([
      ...base64Decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='),
      if (salt > 0) ...List.filled(salt, salt & 0xff),
    ]);

final _jpeg = Uint8List.fromList([0xFF, 0xD8, 0xFF, 0xE0, 0, 0x10, 0x4A, 0x46, 0x49, 0x46, 0, 1]);

final _en = AppLocalizations(const Locale('en'));

/// اختيار صورة وهمي (بدل الكاميرا / المعرض)
class _FakePicker extends ChartImagePicker {
  _FakePicker(this.next);

  ChartPick next;

  @override
  Future<ChartPick> pick(ChartImageSource source) async => next;
}

/// مصدر تحليل بنتحكّم فيه: [hold] = الطلب بيستنّى لحد ما نكمّله، [latency] = تأخير حقيقي
class _ScriptedRepo implements ChartAnalysisRepository {
  _ScriptedRepo({
    this.latency = Duration.zero,
    ChartAnalysisQuota? quota,
  }) : quotaValue = quota ?? ChartAnalysisQuota(used: 2, limit: 5, resetAt: nextLocalMidnight(kTestNow));

  String? symbol = 'EUR/USD';
  Timeframe? timeframe = Timeframe.h1;
  final Duration latency;
  ChartAnalysisQuota quotaValue;
  Object? error;
  bool hold = false;
  final calls = <String>[];
  final pending = <Completer<ChartAnalysisOutcome>>[];

  ChartAnalysisOutcome outcome(String sha) {
    quotaValue = ChartAnalysisQuota(used: quotaValue.used + 1, limit: quotaValue.limit, resetAt: quotaValue.resetAt);
    return ChartAnalysisOutcome(
      analysis: ChartImageAnalysis(
        imageSha256: sha,
        symbol: symbol,
        timeframe: timeframe,
        pattern: ChartPattern.triangle,
        trend: PictureTrend.rising,
        analysedAt: kTestNow,
      ),
      quota: quotaValue,
      fromCache: false,
    );
  }

  @override
  Future<ChartAnalysisQuota> quota() async => quotaValue;

  @override
  Future<ChartImageAnalysis?> cached(String sha256) async => null;

  @override
  Future<ChartAnalysisOutcome> analyze(ChartImageUpload image, {ChartAnalysisCancelToken? cancel}) async {
    calls.add(image.sha256);
    if (latency > Duration.zero) await Future<void>.delayed(latency);
    if (error case final e?) throw e;
    if (hold) {
      final c = Completer<ChartAnalysisOutcome>();
      pending.add(c);
      return c.future;
    }
    return outcome(image.sha256);
  }
}

Future<ProviderContainer> _container({
  ChartAnalysisRepository? repo,
  ChartAnalysisRepository Function(SharedPreferences prefs)? repoFrom,
  ChartImagePicker? picker,
}) async {
  TestWidgetsFlutterBinding.ensureInitialized();
  final scope = await testScope(
    const SizedBox(),
    overrides: [
      if (repo != null) chartAnalysisRepositoryProvider.overrideWithValue(repo),
      if (repoFrom != null)
        chartAnalysisRepositoryProvider.overrideWith((ref) => repoFrom(ref.watch(sharedPreferencesProvider))),
      chartImagePickerProvider.overrideWithValue(picker ?? _FakePicker(ChartPicked('/tmp/chart.png', _png()))),
    ],
  );
  final c = ProviderContainer(overrides: scope.overrides);
  addTearDown(c.dispose);
  c.listen(assistantViewModelProvider, (_, __) {});
  c.listen(chartQuotaProvider, (_, __) {});
  return c;
}

SimulatedChartAnalysisRepository _simulated(SharedPreferences prefs, {String user = 'test-user', DateTime Function()? clock}) =>
    SimulatedChartAnalysisRepository(prefs, userId: user, clock: clock ?? () => kTestNow);

ChartImageUpload _upload(Uint8List bytes) =>
    ChartImageUpload(bytes: bytes, sha256: sha256Hex(bytes), fileName: 'chart.png');

/// آراء الاستراتيجية (الـ provider بيضل عايش طول الاختبار)
Future<List<Opportunity>> _opps(ProviderContainer c, String symbol) {
  c.listen(opportunitiesProvider(symbol), (_, __) {});
  return c.read(opportunitiesProvider(symbol).future);
}

AssistantReply _lastReply(ProviderContainer c) => c.read(assistantViewModelProvider).messages.whereType<AssistantReply>().last;

void main() {
  group('SHA-256 + image validation', () {
    test('sha256Hex matches the standard test vectors', () {
      expect(sha256Hex(const []), 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855');
      expect(sha256Hex(utf8.encode('abc')), 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
      expect(
        sha256Hex(utf8.encode('abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq')),
        '248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1',
      );
      expect(sha256Hex(_png(1)), isNot(sha256Hex(_png(2))));
    });

    test('validateChartImage: PNG and JPG pass; other formats, garbage, empty and > 10 MB are rejected', () {
      expect(validateChartImage(_png()), isNull);
      expect(validateChartImage(_jpeg), isNull);
      expect(validateChartImage(Uint8List.fromList(ascii.encode('GIF89a\x01\x00\x01\x00'))), ChartImageProblem.type);
      expect(validateChartImage(Uint8List.fromList(ascii.encode('RIFF\x00\x00\x00\x00WEBPVP8 '))), ChartImageProblem.type);
      expect(validateChartImage(Uint8List.fromList(ascii.encode('\x00\x00\x00\x18ftypheic'))), ChartImageProblem.type);
      expect(validateChartImage(Uint8List.fromList(utf8.encode('just some text, not an image'))), ChartImageProblem.unreadable);
      expect(validateChartImage(Uint8List(0)), ChartImageProblem.unreadable);
      final big = Uint8List(kChartImageMaxBytes + 1)..setRange(0, 8, _png());
      expect(validateChartImage(big), ChartImageProblem.size);
      final exact = Uint8List(kChartImageMaxBytes)..setRange(0, 8, _png());
      expect(validateChartImage(exact), isNull);
    });
  });

  group('Daily limit (simulated repository)', () {
    late SharedPreferences prefs;
    setUp(() async {
      SharedPreferences.setMockInitialValues({});
      prefs = await SharedPreferences.getInstance();
    });

    test('quota resets at the next local midnight and at() rolls over', () {
      final q = ChartAnalysisQuota.fresh(kTestNow);
      final local = kTestNow.toLocal();
      expect(q.resetAt, DateTime(local.year, local.month, local.day + 1));
      expect((q.used, q.limit, q.remaining, q.reached), (0, 5, 5, false));
      final full = ChartAnalysisQuota(used: 5, limit: 5, resetAt: q.resetAt);
      expect(full.reached, isTrue);
      expect(full.remaining, 0);
      expect(full.at(q.resetAt.subtract(const Duration(minutes: 1))), full);
      expect(full.at(q.resetAt).used, 0);
      expect(full.at(q.resetAt).resetAt, q.resetAt.add(const Duration(days: 1)));
    });

    test('counts each new image, stops at 5 with the reset time, and persists', () async {
      final repo = _simulated(prefs);
      expect((await repo.quota()).used, 0);
      for (var i = 1; i <= 5; i++) {
        final out = await repo.analyze(_upload(_png(i)));
        expect(out.fromCache, isFalse);
        expect(out.quota.used, i);
      }
      await expectLater(
        repo.analyze(_upload(_png(6))),
        throwsA(isA<DailyLimitReachedException>()
            .having((e) => e.resetAt, 'resetAt', nextLocalMidnight(kTestNow))),
      );
      // "إعادة تشغيل": repository جديد على نفس التخزين
      final restarted = _simulated(prefs);
      expect((await restarted.quota()).used, 5);
      expect((await restarted.quota()).reached, isTrue);
    });

    test('the counter is per user', () async {
      final a = _simulated(prefs, user: 'a');
      for (var i = 1; i <= 5; i++) {
        await a.analyze(_upload(_png(i)));
      }
      final b = _simulated(prefs, user: 'b');
      expect((await b.quota()).used, 0);
      expect((await b.analyze(_upload(_png(9)))).quota.used, 1);
    });

    test('a new day resets the counter (day boundary)', () async {
      var now = kTestNow;
      final repo = _simulated(prefs, clock: () => now);
      for (var i = 1; i <= 5; i++) {
        await repo.analyze(_upload(_png(i)));
      }
      final reset = nextLocalMidnight(kTestNow);
      now = reset.subtract(const Duration(seconds: 1));
      expect((await repo.quota()).reached, isTrue);
      now = reset;
      final fresh = await repo.quota();
      expect(fresh.used, 0);
      expect(fresh.resetAt, nextLocalMidnight(reset));
      expect((await repo.analyze(_upload(_png(7)))).quota.used, 1);
    });

    test('the same image returns the saved result and is not counted, even at the limit', () async {
      final repo = _simulated(prefs);
      final first = await repo.analyze(_upload(_png(1)));
      final again = await repo.analyze(_upload(_png(1)));
      expect(again.fromCache, isTrue);
      expect(again.analysis, first.analysis);
      expect(again.quota.used, 1);
      for (var i = 2; i <= 5; i++) {
        await repo.analyze(_upload(_png(i)));
      }
      final atLimit = await repo.analyze(_upload(_png(1)));
      expect(atLimit.fromCache, isTrue);
      expect(atLimit.quota.used, 5);
      expect(await repo.cached(sha256Hex(_png(3))), isNotNull);
      expect(await repo.cached(sha256Hex(_png(42))), isNull);
    });

    test('a cancelled analysis is not counted or saved', () async {
      final repo = SimulatedChartAnalysisRepository(prefs,
          userId: 'test-user', clock: () => kTestNow, latency: const Duration(milliseconds: 20));
      final cancel = ChartAnalysisCancelToken();
      final future = repo.analyze(_upload(_png(1)), cancel: cancel);
      cancel.cancel();
      await expectLater(future, throwsA(isA<ChartAnalysisCancelledException>()));
      expect((await repo.quota()).used, 0);
      expect(await repo.cached(sha256Hex(_png(1))), isNull);
    });

    test('corrupted storage = a fresh day, nothing cached', () async {
      await prefs.setString('${SimulatedChartAnalysisRepository.quotaKeyPrefix}test-user', '{not json');
      await prefs.setString('${SimulatedChartAnalysisRepository.cacheKeyPrefix}test-user', '[{"image_sha256": 3}]');
      final repo = _simulated(prefs);
      expect((await repo.quota()).used, 0);
      expect(await repo.cached('x'), isNull);
    });

    test('the simulated reading is deterministic and only uses product symbols and model timeframes', () {
      for (var i = 0; i < 40; i++) {
        final sha = sha256Hex(_png(i));
        final a = SimulatedChartAnalysisRepository.simulate(sha, kTestNow);
        expect(a, SimulatedChartAnalysisRepository.simulate(sha, kTestNow));
        if (a.hasInstrument) {
          expect(kProductSymbols, contains(a.symbol));
          expect(Timeframe.modelTimeframes, contains(a.timeframe));
        } else {
          expect(a.symbol, isNull);
          expect(a.timeframe, isNull);
        }
      }
    });
  });

  group('429 mapping + DTO', () {
    test('ApiException.rateLimited → DailyLimitReachedException with the server reset time', () {
      final reset = DateTime.utc(2026, 10, 22, 0, 0);
      final mapped = mapChartAnalysisError(
        ApiException(ApiErrorKind.rateLimited, statusCode: 429, resetAt: reset),
        now: kTestNow,
      );
      expect(mapped, isA<DailyLimitReachedException>().having((e) => e.resetAt, 'resetAt', reset));
      // بدون وقت من الخادم: أول اليوم الجاي
      expect(
        mapChartAnalysisError(const ApiException(ApiErrorKind.rateLimited, statusCode: 429), now: kTestNow),
        isA<DailyLimitReachedException>().having((e) => e.resetAt, 'resetAt', nextLocalMidnight(kTestNow)),
      );
      expect(mapChartAnalysisError(const ApiException(ApiErrorKind.network), now: kTestNow),
          isA<ChartAnalysisOfflineException>());
      expect(mapChartAnalysisError(const ApiException(ApiErrorKind.timeout), now: kTestNow),
          isA<ChartAnalysisOfflineException>());
      const server = ApiException(ApiErrorKind.server, statusCode: 500);
      expect(mapChartAnalysisError(server, now: kTestNow), same(server));
      final other = StateError('x');
      expect(mapChartAnalysisError(other, now: kTestNow), same(other));
    });

    test('a real HTTP 429 with Retry-After maps end to end (E1 → feature)', () async {
      final request = RequestOptions(path: '/assistant/chart-analyses');
      final dio = DioException(
        requestOptions: request,
        type: DioExceptionType.badResponse,
        response: Response<Object?>(
          requestOptions: request,
          statusCode: 429,
          headers: Headers.fromMap({'retry-after': ['3600']}),
          data: {'detail': 'Daily limit reached'},
        ),
      );
      final api = ApiException.fromDio(dio, now: () => kTestNow);
      expect(api.kind, ApiErrorKind.rateLimited);
      await expectLater(
        Future<void>.error(api).mapChartAnalysisErrors(() => kTestNow),
        throwsA(isA<DailyLimitReachedException>()
            .having((e) => e.resetAt, 'resetAt', kTestNow.add(const Duration(hours: 1)))),
      );
    });

    test('DTO round trip; unknown symbol or missing timeframe = no instrument; bad items = null', () {
      final a = ChartImageAnalysis(
        imageSha256: 'abc',
        symbol: 'XAU/USD',
        timeframe: Timeframe.h4,
        pattern: ChartPattern.wedge,
        trend: PictureTrend.falling,
        analysedAt: kTestNow,
      );
      expect(ChartAnalysisDto.fromJson(Json(ChartAnalysisDto.toJson(a))), a);
      final base = ChartAnalysisDto.toJson(a);
      expect(ChartAnalysisDto.fromJson(Json({...base, 'symbol': 'BTC/USD'}))!.hasInstrument, isFalse);
      expect(ChartAnalysisDto.fromJson(Json({...base, 'timeframe': null}))!.symbol, isNull);
      expect(ChartAnalysisDto.fromJson(Json({...base, 'pattern': 'cup'})), isNull);
      expect(ChartAnalysisDto.fromJson(Json({...base, 'image_sha256': ''})), isNull);
      final q = ChartAnalysisQuota(used: 3, limit: 5, resetAt: DateTime(2026, 10, 22));
      expect(ChartAnalysisDto.quotaFromJson(Json(ChartAnalysisDto.quotaToJson(q))), q);
      expect(ChartAnalysisDto.quotaFromJson(const Json({'limit': 0, 'used': 0, 'reset_at': '2026-10-22T00:00:00Z'})), isNull);
    });
  });

  group('AssistantViewModel: chart flow', () {
    test('pick → preview with hash; rejected and invalid images say why and keep no preview', () async {
      final picker = _FakePicker(ChartPicked('/tmp/a.png', _png(3)));
      final scope = await _container(repo: _ScriptedRepo(), picker: picker);
      final vm = scope.read(assistantViewModelProvider.notifier);
      expect(await vm.pickChart(ChartImageSource.gallery), isNull);
      final draft = scope.read(assistantViewModelProvider).draft!;
      expect(draft.sha256, sha256Hex(_png(3)));
      expect(draft.typeLabel, 'PNG');
      expect(draft.fileName, 'a.png');
      vm.removeChart();
      picker.next = const ChartPickRejected(ChartImageProblem.size);
      expect(await vm.pickChart(ChartImageSource.camera), ChartImageProblem.size);
      picker.next = ChartPicked('/tmp/a.gif', Uint8List.fromList(ascii.encode('GIF89a\x01\x00\x01\x00')));
      expect(await vm.pickChart(ChartImageSource.gallery), ChartImageProblem.type);
      picker.next = ChartPicked('/tmp/a.png', Uint8List.fromList([1, 2, 3, 4, 5, 6, 7, 8, 9]));
      expect(await vm.pickChart(ChartImageSource.gallery), ChartImageProblem.unreadable);
      picker.next = const ChartPickCancelled();
      expect(await vm.pickChart(ChartImageSource.gallery), isNull);
      expect(scope.read(assistantViewModelProvider).draft, isNull);
    });

    test('Analyze → image + labelled reply in the chat, preview cleared, counter updated', () async {
      final repo = _ScriptedRepo();
      final c = await _container(repo: repo);
      final vm = c.read(assistantViewModelProvider.notifier);
      await vm.pickChart(ChartImageSource.gallery);
      await vm.analyzeChart();
      final state = c.read(assistantViewModelProvider);
      expect(state.draft, isNull);
      expect(state.chartStatus, ChartStatus.idle);
      expect(state.messages.first, isA<UserImage>());
      final reply = _lastReply(c);
      expect(reply.answer.kind, ReplyKind.chart);
      expect(reply.symbol, 'EUR/USD');
      expect(reply.answer.chart!.timeframe, Timeframe.h1);
      expect(c.read(chartQuotaProvider).value!.used, 3);
    });

    test('a double tap on Analyze sends once', () async {
      final repo = _ScriptedRepo()..hold = true;
      final c = await _container(repo: repo);
      final vm = c.read(assistantViewModelProvider.notifier);
      await vm.pickChart(ChartImageSource.gallery);
      final first = vm.analyzeChart();
      final second = vm.analyzeChart();
      await Future<void>.delayed(Duration.zero);
      expect(repo.calls, hasLength(1));
      repo.pending.single.complete(repo.outcome(repo.calls.single));
      await Future.wait([first, second]);
      expect(c.read(assistantViewModelProvider).messages.whereType<AssistantReply>(), hasLength(1));
    });

    test('Cancel while analyzing keeps the preview and drops the late result', () async {
      final repo = _ScriptedRepo()..hold = true;
      final c = await _container(repo: repo);
      final vm = c.read(assistantViewModelProvider.notifier);
      await vm.pickChart(ChartImageSource.gallery);
      final run = vm.analyzeChart();
      await Future<void>.delayed(Duration.zero);
      expect(c.read(assistantViewModelProvider).analyzing, isTrue);
      vm.cancelChart();
      expect(c.read(assistantViewModelProvider).chartStatus, ChartStatus.idle);
      repo.pending.single.complete(repo.outcome(repo.calls.single));
      await run;
      final state = c.read(assistantViewModelProvider);
      expect(state.messages, isEmpty);
      expect(state.draft, isNotNull);
    });

    test('race: only the latest request updates the chat', () async {
      final repo = _ScriptedRepo()..hold = true;
      final c = await _container(repo: repo);
      final vm = c.read(assistantViewModelProvider.notifier);
      await vm.pickChart(ChartImageSource.gallery);
      final first = vm.analyzeChart();
      await Future<void>.delayed(Duration.zero);
      vm.cancelChart();
      repo.symbol = 'XAU/USD';
      final second = vm.analyzeChart();
      await Future<void>.delayed(Duration.zero);
      expect(repo.pending, hasLength(2));
      // الأحدث بيخلص أول، القديم بعده
      repo.pending[1].complete(repo.outcome(repo.calls[1]));
      await second;
      repo.symbol = 'EUR/USD';
      repo.pending[0].complete(repo.outcome(repo.calls[0]));
      await first;
      final replies = c.read(assistantViewModelProvider).messages.whereType<AssistantReply>().toList();
      expect(replies, hasLength(1));
      expect(replies.single.symbol, 'XAU/USD');
    });

    test('offline: says why and sends nothing', () async {
      final repo = _ScriptedRepo();
      final c = await _container(repo: repo);
      final vm = c.read(assistantViewModelProvider.notifier);
      await vm.pickChart(ChartImageSource.gallery);
      c.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      await vm.analyzeChart();
      expect(repo.calls, isEmpty);
      final state = c.read(assistantViewModelProvider);
      expect(state.chartStatus, ChartStatus.offline);
      expect(state.messages, isEmpty);
      expect(state.draft, isNotNull);
    });

    test('DailyLimitReachedException → limit state with its reset time; text chat still works', () async {
      final reset = nextLocalMidnight(kTestNow);
      final repo = _ScriptedRepo()..error = DailyLimitReachedException(reset);
      final c = await _container(repo: repo);
      final vm = c.read(assistantViewModelProvider.notifier);
      await c.read(chartQuotaProvider.future);
      c.listen(clockProvider, (_, __) {});
      await c.read(clockProvider.future);
      await vm.pickChart(ChartImageSource.gallery);
      await vm.analyzeChart();
      final quota = c.read(chartQuotaNowProvider)!;
      expect(quota.reached, isTrue);
      expect(quota.resetAt, reset);
      expect(c.read(assistantViewModelProvider).chartStatus, ChartStatus.idle);
      expect(c.read(assistantViewModelProvider).draft, isNotNull);
      await vm.send('Explain the signal');
      expect(_lastReply(c).answer.kind, ReplyKind.explain);
    });

    test('a failure offers Try again, which sends the same image again', () async {
      final repo = _ScriptedRepo()..error = StateError('down');
      final c = await _container(repo: repo);
      final vm = c.read(assistantViewModelProvider.notifier);
      await vm.pickChart(ChartImageSource.gallery);
      await vm.analyzeChart();
      expect(c.read(assistantViewModelProvider).chartStatus, ChartStatus.failed);
      repo.error = null;
      await vm.analyzeChart();
      expect(repo.calls.toSet(), hasLength(1));
      expect(c.read(assistantViewModelProvider).messages.whereType<AssistantReply>(), hasLength(1));
    });

    test('same image (simulated store): the draft is marked saved and the result does not use the limit', () async {
      late SimulatedChartAnalysisRepository repo;
      final scope = await _container(repoFrom: (prefs) => repo = _simulated(prefs));
      final vm = scope.read(assistantViewModelProvider.notifier);
      await vm.pickChart(ChartImageSource.gallery);
      expect(scope.read(assistantViewModelProvider).draft!.cached, isFalse);
      await vm.analyzeChart();
      expect((await repo.quota()).used, 1);
      await vm.pickChart(ChartImageSource.gallery);
      expect(scope.read(assistantViewModelProvider).draft!.cached, isTrue);
      await vm.analyzeChart();
      expect((await repo.quota()).used, 1);
      final replies = scope.read(assistantViewModelProvider).messages.whereType<AssistantReply>().toList();
      expect(replies, hasLength(2));
      expect(replies.last.answer.chart!.fromCache, isTrue);
      expect(replies.last.answer.chart!.analysis, replies.first.answer.chart!.analysis);
    });
  });

  group('Consistency with the saved strategy', () {
    test('chart replies use the same signal, levels and forecast as Signals for that instrument + timeframe', () async {
      var detected = 0;
      for (final method in AnalysisMethod.knownIds) {
        final repo = _ScriptedRepo();
        final c = await _container(repo: repo);
        await c.read(signalProfileProvider.notifier).save(SignalProfile.defaults.copyWith(methodId: method));
        final vm = c.read(assistantViewModelProvider.notifier);
        final forecasts = SimulatedForecastRepository(source: c.read(simulatedMarketSourceProvider));
        final instruments = await c.read(instrumentsProvider.future);
        final now = c.read(simulatedMarketSourceProvider).now();
        for (final symbol in kProductSymbols) {
          final list = await _opps(c, symbol);
          final instrument = instruments.firstWhere((i) => i.symbol == symbol);
          for (final tf in Timeframe.modelTimeframes) {
            repo
              ..symbol = symbol
              ..timeframe = tf;
            await vm.pickChart(ChartImageSource.gallery);
            await vm.analyzeChart();
            final chart = _lastReply(c).answer.chart!;
            expect(chart.methodId, method);
            final expected = list.where((o) => o.timeframe == tf && o.isDetected && !o.isStale(now)).firstOrNull;
            if (expected == null) {
              expect(chart.signal, isNull, reason: '$method $symbol $tf');
              expect(chart.plan, isNull);
              continue;
            }
            detected++;
            final signal = chart.signal!;
            expect(signal.id, expected.id);
            expect(signal.direction, expected.direction);
            expect(signal.probability, expected.probability);
            final plan = SignalPlan.of(expected, instrument);
            expect(chart.plan!.entry, plan.entry);
            expect(chart.plan!.target, plan.target);
            expect(chart.plan!.stop, plan.stop);
            final text = _lastReply(c).answer.text;
            expect(text, contains(Formatters.percent(expected.probability)));
            final forecast = await forecasts.forecast(symbol, tf, methodId: method);
            expect(forecast, isNotNull);
            expect(forecast!.direction, signal.direction);
            expect(forecast.probability, signal.probability);
            expect(forecast.signalId, signal.id);
          }
        }
      }
      expect(detected, greaterThan(0), reason: 'at least one detected signal must be compared');
    });

    test('a text answer quotes the strongest signal of the saved strategy', () async {
      final c = await _container(repo: _ScriptedRepo());
      await c.read(signalProfileProvider.notifier).save(SignalProfile.defaults.copyWith(methodId: AnalysisMethod.rsiReversalId));
      final list = await _opps(c, 'EUR/USD');
      final best = ModelRead.from(list, c.read(simulatedMarketSourceProvider).now()).best;
      await c.read(assistantViewModelProvider.notifier).send('x', kind: ReplyKind.explain);
      final text = _lastReply(c).answer.text;
      if (best == null) {
        expect(text, _en.asstExplainNone('EUR/USD'));
      } else {
        expect(text, contains(Formatters.percent(best.probability)));
        expect(text, contains(best.timeframe.label));
      }
    });

    test('reading text: "high probability" only from 70% (forecast rule), never "guarantee"; no instrument = no numbers', () {
      final analysis = ChartImageAnalysis(
        imageSha256: 'x',
        symbol: 'EUR/USD',
        timeframe: Timeframe.h1,
        pattern: ChartPattern.flag,
        trend: PictureTrend.sideways,
        analysedAt: kTestNow,
      );
      Opportunity signal(double p) => Opportunity(
            id: 's',
            symbol: 'EUR/USD',
            timeframe: Timeframe.h1,
            status: OpportunityStatus.detected,
            direction: SignalDirection.long,
            setupType: SetupType.trendFollowing,
            riskLevel: RiskLevel.medium,
            probability: p,
            entryZone: const PriceZone(1.1, 1.1002),
            stopLossZone: const PriceZone(1.098, 1.0982),
            takeProfitZone: const PriceZone(1.104, 1.1042),
            riskReward: 2,
            generatedAt: kTestNow,
            validUntil: kTestNow.add(const Duration(hours: 4)),
          );
      const eur = Instrument(symbol: 'EUR/USD', kind: MarketKind.forex, precision: 5);
      for (final locale in ['en', 'ar']) {
        final l10n = AppLocalizations(Locale(locale));
        final high = chartReadingText(
            l10n,
            ChartAnalysisReply(analysis: analysis, instrument: eur, signal: signal(0.7), methodId: 'ma_crossover', fromCache: false),
            methodName: 'MA Crossover');
        final low = chartReadingText(
            l10n,
            ChartAnalysisReply(analysis: analysis, instrument: eur, signal: signal(0.69), methodId: 'ma_crossover', fromCache: false),
            methodName: 'MA Crossover');
        expect(high, contains(l10n.chartReadHigh));
        expect(low, isNot(contains(l10n.chartReadHigh)));
        expect(high, contains('70%'));
        for (final t in [high, low]) {
          expect(t.toLowerCase(), isNot(contains('guarantee')));
          expect(t, isNot(contains('مضمون')));
        }
        final none = chartReadingText(
          l10n,
          ChartAnalysisReply(
            analysis: ChartImageAnalysis(
              imageSha256: 'y',
              pattern: ChartPattern.range,
              trend: PictureTrend.falling,
              analysedAt: kTestNow,
            ),
            methodId: 'ma_crossover',
            fromCache: false,
          ),
          methodName: 'MA Crossover',
        );
        expect(none, l10n.chartReadNoInstrument(l10n.chartPatternRange, l10n.chartTrendFalling));
        expect(none, isNot(contains('%')));
      }
    });
  });

  group('Assistant screen (H3)', () {
    const latency = Duration(milliseconds: 400);

    Future<_ScriptedRepo> pump(
      WidgetTester tester, {
      String locale = 'en',
      String theme = 'light',
      _ScriptedRepo? repo,
      ChartPick? pick,
      Map<String, Object> prefs = const {},
    }) async {
      usePhoneSize(tester);
      final r = repo ?? _ScriptedRepo(latency: latency);
      await tester.pumpWidget(await testScope(
        const TestApp(home: AssistantScreen()),
        locale: locale,
        prefs: {themeModeStorageKey: theme, ...prefs},
        overrides: [
          assistantRepositoryProvider.overrideWithValue(RuleBasedAssistantRepository(latency: latency)),
          chartAnalysisRepositoryProvider.overrideWithValue(r),
          chartImagePickerProvider.overrideWithValue(_FakePicker(pick ?? ChartPicked('/tmp/chart.png', _png()))),
        ],
      ));
      await tester.pumpAndSettle();
      return r;
    }

    Future<void> show(WidgetTester tester, Finder finder) async {
      // برّا الشاشة: سكرول لفوق شوي (الزر الرئيسي صار معاينة أطول)، وإلا لتحت
      final list = find.byType(Scrollable).first;
      for (var i = 0; i < 8 && finder.evaluate().isEmpty; i++) {
        await tester.drag(list, const Offset(0, 150));
        await tester.pumpAndSettle();
      }
      if (finder.evaluate().isEmpty) await scrollTo(tester, finder);
      await tester.ensureVisible(finder);
      await tester.pumpAndSettle();
    }

    Future<void> pickFromGallery(WidgetTester tester) async {
      await show(tester, find.text('Analyze a chart image'));
      await tester.tap(find.text('Analyze a chart image'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Choose from gallery'));
      await tester.pumpAndSettle();
    }

    Future<void> analyze(WidgetTester tester) async {
      await show(tester, find.text('Analyze'));
      await tester.tap(find.text('Analyze'));
      await tester.pump();
    }

    Future<void> finish(WidgetTester tester) async {
      await tester.pump(latency);
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pumpAndSettle();
    }

    testWidgets('empty state leads with the chart action and counter; suggestions and context chip stay', (tester) async {
      await pump(tester);
      final action = find.text('Analyze a chart image');
      expect(action, findsOneWidget);
      expect(find.text('2 of 5 analyses today'), findsOneWidget);
      expect(find.bySemanticsLabel('Context: EUR/USD'), findsOneWidget);
      expect(find.text('Or ask a question'), findsOneWidget);
      final suggestion = find.text('Explain the current analysis');
      await show(tester, find.text('Size the risk for my capital'));
      expect(suggestion, findsOneWidget);
      expect(tester.getTopLeft(action).dy, lessThan(tester.getTopLeft(suggestion).dy));
      expect(tester.takeException(), isNull);
    });

    testWidgets('pick → preview with Remove; Remove clears it', (tester) async {
      await pump(tester);
      await pickFromGallery(tester);
      expect(find.bySemanticsLabel(RegExp('Chart image to analyze')), findsWidgets);
      expect(find.text('PNG · 0.1 MB'), findsOneWidget);
      expect(find.text('Analyze'), findsOneWidget);
      await show(tester, find.text('Remove'));
      await tester.tap(find.text('Remove'));
      await tester.pumpAndSettle();
      expect(find.text('Analyze'), findsNothing);
      expect(find.text('Analyze a chart image'), findsOneWidget);
    });

    testWidgets('Analyze → announced progress with Cancel → labelled result card with notice and Open market',
        (tester) async {
      final semantics = tester.ensureSemantics();
      await pump(tester);
      await pickFromGallery(tester);
      await analyze(tester);
      expect(find.text('Analyzing the chart image…'), findsOneWidget);
      expect(find.byType(LinearProgressIndicator), findsOneWidget);
      final progress = tester.getSemantics(find.bySemanticsLabel('Analyzing the chart image…'));
      expect(progress.flagsCollection.isLiveRegion, isTrue);
      expect(find.text('Cancel'), findsOneWidget);
      await finish(tester);
      expect(find.byType(ReplyCard), findsOneWidget);
      expect(find.text('Chart analysis · EUR/USD · 1h'), findsOneWidget);
      for (final label in ['Trend', 'Key levels', 'Pattern']) {
        expect(find.text(label), findsOneWidget);
      }
      expect(find.text('Triangle'), findsOneWidget);
      expect(find.descendant(of: find.byType(ReplyCard), matching: find.byType(NotAdviceNotice)), findsOneWidget);
      expect(find.text('Signals are for educational purposes and are not investment advice.'), findsOneWidget);
      await show(tester, find.text('Open market'));
      await tester.tap(find.text('Open market'));
      await tester.pumpAndSettle();
      expect(find.byType(MarketScreen), findsOneWidget);
      semantics.dispose();
    });

    testWidgets('Cancel stops the analysis and keeps the preview', (tester) async {
      await pump(tester);
      await pickFromGallery(tester);
      await analyze(tester);
      await tester.tap(find.text('Cancel'));
      await finish(tester);
      expect(find.byType(ReplyCard), findsNothing);
      expect(find.text('Analyze'), findsOneWidget);
    });

    testWidgets('at the daily limit: action disabled with the reset time, text chat still works', (tester) async {
      final reset = nextLocalMidnight(kTestNow);
      await pump(tester, repo: _ScriptedRepo(latency: latency, quota: ChartAnalysisQuota(used: 5, limit: 5, resetAt: reset)));
      final limitText = 'Daily limit reached. Resets at ${Formatters.clock(reset)}. You can still ask questions in the chat.';
      expect(find.text(limitText), findsOneWidget);
      final button = tester.widget<ButtonStyleButton>(
          find.ancestor(of: find.text('Analyze a chart image'), matching: find.bySubtype<ButtonStyleButton>()));
      expect(button.onPressed, isNull);
      // المحادثة شغّالة
      await show(tester, find.text('Explain the current analysis'));
      await tester.tap(find.text('Explain the current analysis'));
      await finish(tester);
      expect(find.byType(ReplyCard), findsOneWidget);
      // بالمحادثة: الإرفاق معطّل والسطر فوق حقل الكتابة
      expect(tester.widget<IconButton>(find.widgetWithIcon(IconButton, Icons.add_photo_alternate_outlined)).onPressed,
          isNull);
      expect(find.text(limitText), findsOneWidget);
      expect(tester.widget<TextField>(find.byType(TextField)).enabled, isTrue);
    });

    testWidgets('DailyLimitReachedException during Analyze shows the limit state', (tester) async {
      final reset = nextLocalMidnight(kTestNow);
      final repo = _ScriptedRepo(latency: latency)..error = DailyLimitReachedException(reset);
      await pump(tester, repo: repo);
      await pickFromGallery(tester);
      await analyze(tester);
      await finish(tester);
      expect(find.textContaining('Daily limit reached. Resets at ${Formatters.clock(reset)}.'), findsOneWidget);
      final analyzeButton = tester.widget<ButtonStyleButton>(
          find.ancestor(of: find.text('Analyze'), matching: find.bySubtype<ButtonStyleButton>()));
      expect(analyzeButton.onPressed, isNull);
      expect(find.byType(ReplyCard), findsNothing);
    });

    testWidgets('offline: Analyze disabled with the reason; nothing is sent', (tester) async {
      final repo = await pump(tester);
      await pickFromGallery(tester);
      final container = ProviderScope.containerOf(tester.element(find.byType(AssistantScreen)));
      container.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      await tester.pumpAndSettle();
      final analyzeButton = tester.widget<ButtonStyleButton>(
          find.ancestor(of: find.text('Analyze'), matching: find.bySubtype<ButtonStyleButton>()));
      expect(analyzeButton.onPressed, isNull);
      expect(find.text('You are offline. The assistant needs a connection.'), findsWidgets);
      await container.read(assistantViewModelProvider.notifier).analyzeChart();
      await tester.pumpAndSettle();
      expect(find.text('You are offline. Nothing was sent.'), findsOneWidget);
      expect(repo.calls, isEmpty);
    });

    testWidgets('a failure shows Try again', (tester) async {
      final repo = _ScriptedRepo(latency: latency)..error = StateError('down');
      await pump(tester, repo: repo);
      await pickFromGallery(tester);
      await analyze(tester);
      await finish(tester);
      expect(find.text('The chart could not be analyzed.'), findsOneWidget);
      repo.error = null;
      await show(tester, find.text('Try again'));
      await tester.tap(find.text('Try again'));
      await tester.pump();
      await finish(tester);
      expect(find.byType(ReplyCard), findsOneWidget);
    });

    testWidgets('no instrument in the picture: picture trend only, no levels, no Open market', (tester) async {
      await pump(tester, repo: _ScriptedRepo(latency: latency)..symbol = null..timeframe = null);
      await pickFromGallery(tester);
      await analyze(tester);
      await finish(tester);
      expect(find.text('Chart analysis'), findsOneWidget);
      expect(find.text('Rising, in the picture only'), findsOneWidget);
      expect(find.text('None without a setup'), findsOneWidget);
      expect(find.text('Open market'), findsNothing);
    });

    testWidgets('reduced motion: progress is text only (no moving bar)', (tester) async {
      tester.platformDispatcher.accessibilityFeaturesTestValue = const FakeAccessibilityFeatures(disableAnimations: true);
      addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
      await pump(tester);
      await pickFromGallery(tester);
      await analyze(tester);
      expect(find.text('Analyzing the chart image…'), findsOneWidget);
      expect(find.byType(LinearProgressIndicator), findsNothing);
      await finish(tester);
    });

    for (final (locale, theme) in [('en', 'light'), ('en', 'dark'), ('ar', 'light'), ('ar', 'dark')]) {
      testWidgets('text scale 2.0 ($locale, $theme): empty state, preview and result fit, 48 dp targets',
          (tester) async {
        useLargeText(tester);
        final l10n = AppLocalizations(Locale(locale));
        await pump(tester, locale: locale, theme: theme);
        expect(tester.takeException(), isNull);
        await show(tester, find.text(l10n.chartActionTitle));
        await tester.tap(find.text(l10n.chartActionTitle));
        await tester.pumpAndSettle();
        await tester.tap(find.text(l10n.chooseFromGallery));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
        await show(tester, find.text(l10n.chartAnalyze));
        await tester.tap(find.text(l10n.chartAnalyze));
        await tester.pump();
        await finish(tester);
        expect(find.byType(ReplyCard), findsOneWidget);
        expect(find.text(l10n.chartKeyLevels), findsOneWidget);
        if (locale == 'ar') {
          expect(Directionality.of(tester.element(find.byType(ReplyCard))), TextDirection.rtl);
        }
        await tester.drag(find.byType(ListView).first, const Offset(0, 3000));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
      });
    }
  });
}
