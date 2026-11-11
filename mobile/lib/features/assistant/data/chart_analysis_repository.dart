import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/data/json.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';
import '../../../core/storage/preferences_provider.dart';
import '../../auth/auth_state.dart';
import '../../markets/models/market_models.dart';
import '../models/chart_analysis.dart';
import 'chart_analysis_dto.dart';

/// مصدر تحليل صور الشارت + الحد اليومي - بيتبدّل بتنفيذ API.
///
/// القاعدة: نفس الصورة (نفس [ChartImageUpload.sha256]) = نفس النتيجة المحفوظة،
/// وما بتنحسب من الحد. الحد لكل مستخدم وبيرجع صفر بأول اليوم الجاي.
abstract interface class ChartAnalysisRepository {
  /// العدّاد هلّق (كم تحليل اليوم من الحد، وإيمتى بيرجع صفر).
  /// API: `GET /assistant/chart-analyses/quota` → `{limit, used, reset_at}`.
  /// TODO(API): الـ endpoint مش موجود بالـ backend.
  Future<ChartAnalysisQuota> quota();

  /// نتيجة محفوظة لنفس الصورة (على الجهاز)، أو null.
  /// API: ما في (محلي)؛ الخادم كمان لازم يرجّع نفس النتيجة لنفس `image_sha256` بدون ما يحسبها.
  /// TODO(API): تأكيد مع صاحب الـ backend إن التكرار ما بينحسب من الحد.
  Future<ChartImageAnalysis?> cached(String sha256);

  /// تحليل [image]. نفس الصورة من قبل = النتيجة المحفوظة ([ChartAnalysisOutcome.fromCache]،
  /// بدون طلب وبدون ما تنحسب). بيرمي [DailyLimitReachedException] بالحد،
  /// [ChartAnalysisOfflineException] بدون اتصال، و [ChartAnalysisCancelledException] لما ينلغى.
  /// API: `POST /assistant/chart-analyses` (multipart: `image`, `image_sha256`) →
  /// `{analysis: ChartAnalysisRead, quota: {limit, used, reset_at}}`؛ 429 (مع
  /// `Retry-After` / `RateLimit-Reset`) → [DailyLimitReachedException] عبر
  /// [mapChartAnalysisError]، وإلغاء = `CancelToken` تبع dio.
  /// TODO(API): الـ endpoint مش موجود بالـ backend (§6a)؛ الشكل مقترح ([ChartAnalysisDto]).
  Future<ChartAnalysisOutcome> analyze(ChartImageUpload image, {ChartAnalysisCancelToken? cancel});
}

/// محاكاة على الجهاز (SharedPreferences): 5 تحليلات باليوم لكل مستخدم، والعدّاد
/// والنتائج المحفوظة بيضلّوا بعد إعادة التشغيل. القراءة حتمية من بصمة الصورة.
final class SimulatedChartAnalysisRepository implements ChartAnalysisRepository {
  SimulatedChartAnalysisRepository(
    this.prefs, {
    required this.userId,
    DateTime Function()? clock,
    this.latency = Duration.zero,
    this.dailyLimit = ChartAnalysisQuota.simulatedDailyLimit,
  }) : _clock = clock ?? DateTime.now;

  static const quotaKeyPrefix = 'chart_analysis_quota.';
  static const cacheKeyPrefix = 'chart_analysis_cache.';

  /// أقصى عدد نتائج محفوظة (الأقدم بينشال)
  static const int maxCached = 50;

  final SharedPreferences prefs;

  /// المستخدم الحالي (الحد والنتائج لكل مستخدم)
  final String userId;
  final DateTime Function() _clock;
  final Duration latency;
  final int dailyLimit;

  String get _quotaKey => '$quotaKeyPrefix$userId';
  String get _cacheKey => '$cacheKeyPrefix$userId';

  /// العدّاد المحفوظ؛ مكسور أو من يوم قبل = يوم جديد
  ChartAnalysisQuota _readQuota(DateTime now) {
    final raw = prefs.getString(_quotaKey);
    ChartAnalysisQuota? saved;
    if (raw != null) {
      try {
        if (Json.from(jsonDecode(raw)) case final json?) saved = ChartAnalysisDto.quotaFromJson(json);
      } on FormatException {
        saved = null;
      }
    }
    if (saved == null) return ChartAnalysisQuota.fresh(now, limit: dailyLimit);
    return ChartAnalysisQuota(used: saved.used, limit: dailyLimit, resetAt: saved.resetAt).at(now);
  }

  Future<void> _writeQuota(ChartAnalysisQuota q) =>
      prefs.setString(_quotaKey, jsonEncode(ChartAnalysisDto.quotaToJson(q)));

  /// النتائج المحفوظة بالترتيب (الأقدم أول)
  List<ChartImageAnalysis> _readCache() {
    final raw = prefs.getString(_cacheKey);
    if (raw == null) return const [];
    Object? decoded;
    try {
      decoded = jsonDecode(raw);
    } on FormatException {
      return const [];
    }
    if (decoded is! List) return const [];
    return [
      for (final item in decoded)
        if (Json.from(item) case final json?)
          if (ChartAnalysisDto.fromJson(json) case final a?) a,
    ];
  }

  Future<void> _writeCache(List<ChartImageAnalysis> list) =>
      prefs.setString(_cacheKey, jsonEncode([for (final a in list) ChartAnalysisDto.toJson(a)]));

  @override
  Future<ChartAnalysisQuota> quota() async => _readQuota(_clock());

  @override
  Future<ChartImageAnalysis?> cached(String sha256) async =>
      _readCache().where((a) => a.imageSha256 == sha256).firstOrNull;

  @override
  Future<ChartAnalysisOutcome> analyze(ChartImageUpload image, {ChartAnalysisCancelToken? cancel}) async {
    final hit = await cached(image.sha256);
    if (hit != null) return ChartAnalysisOutcome(analysis: hit, quota: _readQuota(_clock()), fromCache: true);
    final before = _readQuota(_clock());
    if (before.reached) throw DailyLimitReachedException(before.resetAt);
    if (latency > Duration.zero) await Future<void>.delayed(latency);
    if (cancel?.isCancelled ?? false) throw const ChartAnalysisCancelledException();

    final now = _clock();
    // بعد الانتظار: طلب تاني ممكن يكون أخد آخر تحليل
    final current = _readQuota(now);
    if (current.reached) throw DailyLimitReachedException(current.resetAt);
    final analysis = simulate(image.sha256, now);
    final next = ChartAnalysisQuota(used: current.used + 1, limit: current.limit, resetAt: current.resetAt);
    final cache = [..._readCache().where((a) => a.imageSha256 != image.sha256), analysis];
    await _writeQuota(next);
    await _writeCache(cache.length > maxCached ? cache.sublist(cache.length - maxCached) : cache);
    return ChartAnalysisOutcome(analysis: analysis, quota: next, fromCache: false);
  }

  /// قراءة حتمية من البصمة: 5 من 6 صور فيها رمز وإطار (من أدوات المنتج وأطر
  /// النموذج 15m / 1h / 4h)، والشكل وحركة الصورة من بايتات تانية.
  static ChartImageAnalysis simulate(String sha256, DateTime now) {
    int byte(int i) => int.parse(sha256.substring(i * 2, i * 2 + 2), radix: 16);
    final detected = byte(0) % 6 != 0;
    return ChartImageAnalysis(
      imageSha256: sha256,
      symbol: detected ? kProductSymbols[byte(1) % kProductSymbols.length] : null,
      timeframe: detected ? Timeframe.modelTimeframes[byte(2) % Timeframe.modelTimeframes.length] : null,
      pattern: ChartPattern.values[byte(3) % ChartPattern.values.length],
      trend: PictureTrend.values[byte(4) % PictureTrend.values.length],
      analysedAt: now.toUtc(),
    );
  }
}

/// المستخدم الحالي بيحدّد العدّاد والنتائج (تبديل الحساب = عدّاد تاني)
final chartAnalysisRepositoryProvider = Provider<ChartAnalysisRepository>((ref) {
  final auth = ref.watch(authStateProvider);
  final userId = auth is SignedIn ? auth.user.id : 'signed-out';
  return apiSource(
    ref,
    ApiFeature.assistant,
    simulated: () => SimulatedChartAnalysisRepository(
      ref.watch(sharedPreferencesProvider),
      userId: userId,
      latency: const Duration(milliseconds: 1400),
    ),
  );
});
