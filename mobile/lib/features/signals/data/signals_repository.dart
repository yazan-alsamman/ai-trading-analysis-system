import 'dart:math' as math;

import '../../../core/data/json.dart';
import '../../markets/data/simulated_market_source.dart';
import '../../markets/models/market_models.dart';
import '../models/analysis_method.dart';
import '../models/analysis_request.dart';
import '../models/model_accuracy.dart';
import '../models/opportunity.dart';
import '../models/signal_feed.dart';
import '../models/signal_profile.dart';
import 'analysis_engine.dart';
import 'opportunity_dto.dart';
import 'simulated_outcomes.dart';

/// إلغاء طلب تحليل شغّال (المستخدم لغاه، أو طلب أحدث، أو سكّرت الشاشة)
final class AnalysisCancelToken {
  bool _cancelled = false;

  bool get isCancelled => _cancelled;

  void cancel() => _cancelled = true;
}

/// الطلب انلغى قبل ما يخلص (ما في نتيجة، وما انحفظ شي)
final class AnalysisCancelledException implements Exception {
  const AnalysisCancelledException();
}

/// مصدر آراء النموذج والطرق الفنية - بيتبدّل بتنفيذ API (`GET /opportunities?symbol=`)
abstract interface class SignalsRepository {
  /// بيانات محاكاة؟ (الشاشات بتبيّن "Simulated" متل الـ Home وشاشة السوق)
  /// API: ما في endpoint، تنفيذ الـ API بيرجّع false.
  /// TODO(API): بيروح مع المصدر المحاكى لما ينربط `GET /opportunities`.
  bool get isSimulated;

  /// رأي طريقة [methodId] على [symbol] لكل إطار من [Timeframe.modelTimeframes].
  /// API: `GET /opportunities?symbol=&method_id=`.
  /// TODO(API): `method_id` مش موجود بالـ backend لسّا (بدونو = الطريقة الافتراضية).
  Future<List<Opportunity>> opportunities(String symbol, {String methodId = AnalysisMethod.defaultId});

  /// دقة الإشارات السابقة (`GET /insights/accuracy`) - دايمًا النموذج
  Future<ModelAccuracy> accuracy();

  /// قائمة Signals: الإشارات المطلوبة الصالحة ("requested by you") أول، بعدين
  /// الفرص الحالية من طريقة الاستراتيجية يلي بتطابق فلاترها، مرتّبة بـ [rankSignals].
  /// API: `GET /opportunities?method_id=&symbols=&timeframes=&directions=&min_probability=&min_risk_reward=`
  /// → `OpportunitySchema[]` (عقد الويب + `methodId`، `indicator`، `requestedByYou`).
  /// TODO(API): الـ endpoint مش موجود بالـ backend لسّا؛ لو رجّع بدون فلترة،
  /// التنفيذ بيطبّق [rankSignals] عالجهاز (نفس النتيجة).
  Future<List<Opportunity>> feed(SignalProfile profile);

  /// إشارة وحدة لشاشة التفاصيل (null = مش موجودة أو انشالت).
  /// API: `GET /opportunities/{id}` → `OpportunitySchema` (404 → null).
  /// TODO(API): الـ endpoint مش موجود بالـ backend لسّا.
  Future<Opportunity?> opportunity(String id);

  /// "Request analysis": بيحلّل [request] هلّق. [onStage] بيبلّغ pending ثم
  /// analyzing؛ [cancel] بيوقفه ([AnalysisCancelledException]). النتيجة ممكن
  /// تكون محايدة (`isDetected` false = "No clear setup right now")؛ الإشارة
  /// المكتشفة بتنحفظ مع "requested by you" لحد ما تخلص صلاحيتها، وبتنفتح بمعرّفها.
  /// API: `POST /analysis-requests` (`symbol`, `timeframe`, `method_id`) → `{id, status}`،
  /// بعدين `GET /analysis-requests/{id}` لحد `status` = `done` (مع `OpportunitySchema`) أو `failed`.
  /// TODO(API): الـ endpoints مش موجودين بالـ backend لسّا.
  Future<Opportunity> requestAnalysis(
    AnalysisRequest request, {
    AnalysisCancelToken? cancel,
    void Function(AnalysisStage stage)? onStage,
  });
}

/// شكل الـ API لملخص الدقة → domain (null لو ناقص أو غير منطقي)
ModelAccuracy? modelAccuracyFromJson(Json json) {
  final resolved = json.integer('resolved');
  final hits = json.integer('hits');
  final days = json.integer('window_days');
  if (resolved == null || hits == null || days == null) return null;
  if (resolved < 0 || hits < 0 || hits > resolved || days <= 0) return null;
  return ModelAccuracy(resolved: resolved, hits: hits, windowDays: days);
}

/// فرص محاكاة حتمية مشتقة من نفس دالة السعر بـ [SimulatedMarketSource]
/// (الاتجاه من السعر الفعلي، فالرأي منطقي مع الرسم). كل طريقة من
/// [SimulatedAnalysisEngine].
///
/// المعرّفات: كل إشارة إلها طريقة فنية `SYMBOL-tf-bucket@method` (A3c)، والمطلوبة `req-<معرّف الإشارة>` (بالذاكرة بس:
/// بعد إعادة تشغيل التطبيق ما بتنلاقى → "not found").
final class SimulatedSignalsRepository implements SignalsRepository {
  SimulatedSignalsRepository({required this.source, this.requestLatencyScale = 1});

  final SimulatedMarketSource source;

  /// مضاعف مدة "Request analysis" (0 بالاختبارات = بدون انتظار)
  final double requestLatencyScale;

  static const String requestedPrefix = 'req-';

  /// الإشارات المطلوبة بالذاكرة (معرّف → إشارة) لحد ما تخلص صلاحيتها
  final Map<String, Opportunity> _requested = {};

  SimulatedAnalysisEngine get _engine => SimulatedAnalysisEngine(source);

  @override
  bool get isSimulated => true;

  @override
  Future<List<Opportunity>> opportunities(String symbol, {String methodId = AnalysisMethod.defaultId}) async =>
      opportunitiesFromJson(opportunitiesJson(symbol, methodId: methodId));

  @override
  Future<List<Opportunity>> feed(SignalProfile profile) async {
    final all = [
      for (final symbol in kProductSymbols)
        if (profile.symbols.contains(symbol)) ...await opportunities(symbol, methodId: profile.methodId),
    ];
    final now = source.now();
    final requested = requestedSignals(now);
    final taken = {for (final o in requested) o.id.substring(requestedPrefix.length)};
    return [
      ...requested,
      for (final o in rankSignals(all, profile, now))
        if (!taken.contains(o.id)) o,
    ];
  }

  /// المطلوبة الصالحة، الأحدث أول (القديمة بتنشال من الذاكرة)
  List<Opportunity> requestedSignals(DateTime now) {
    _requested.removeWhere((_, o) => o.isStale(now));
    return _requested.values.toList()..sort((a, b) => b.generatedAt.compareTo(a.generatedAt));
  }

  @override
  Future<Opportunity?> opportunity(String id) async {
    if (id.startsWith(requestedPrefix)) {
      final found = _requested[id];
      if (found == null) return null;
      if (found.isStale(source.now())) {
        _requested.remove(id);
        return null;
      }
      return found;
    }
    final json = opportunityJson(id);
    return json == null ? null : OpportunityDto.fromJson(Json(json)).toDomain();
  }

  @override
  Future<Opportunity> requestAnalysis(
    AnalysisRequest request, {
    AnalysisCancelToken? cancel,
    void Function(AnalysisStage stage)? onStage,
  }) async {
    final spec = source.spec(request.symbol);
    if (!request.isValid || spec == null) throw ArgumentError.value(request, 'request', 'invalid analysis request');
    final tf = request.timeframe;
    final close = tf.bucketStart(source.now());
    final bucket = close.millisecondsSinceEpoch ~/ tf.duration.inMilliseconds;
    final latency = SimulatedAnalysisEngine.requestLatency(spec, tf, request.methodId, bucket) * requestLatencyScale;

    Future<void> wait(Duration d) async {
      if (d > Duration.zero) await Future<void>.delayed(d);
      if (cancel?.isCancelled ?? false) throw const AnalysisCancelledException();
    }

    if (cancel?.isCancelled ?? false) throw const AnalysisCancelledException();
    onStage?.call(AnalysisStage.pending);
    await wait(latency * 0.3);
    onStage?.call(AnalysisStage.analyzing);
    await wait(latency * 0.7);

    final json = _one(spec, tf, Timeframe.modelTimeframes.indexOf(tf), close, request.methodId);
    final base = json['id']! as String;
    final parsed = OpportunityDto.fromJson(Json({
      ...json,
      'id': '$requestedPrefix$base',
      'requestedByYou': true,
    })).toDomain();
    if (parsed == null) throw StateError('invalid analysis payload');
    // المحايدة مش إشارة: ما بتنحفظ ولا بتنفتح بالتفاصيل
    if (parsed.isDetected) _requested[parsed.id] = parsed;
    return parsed;
  }

  @override
  Future<ModelAccuracy> accuracy() async {
    final parsed = modelAccuracyFromJson(Json(accuracyJson()));
    if (parsed == null) throw StateError('invalid accuracy payload');
    return parsed;
  }

  /// ثابتة طول اليوم: آخر 90 يوم مكتمل من [SimulatedOutcomes] (نفس أرقام Insights)
  Map<String, Object?> accuracyJson() {
    final outcomes = SimulatedOutcomes(source);
    const days = 90;
    final last = outcomes.lastFullDay;
    final total = outcomes.total(last - days + 1, last);
    return {'resolved': total.resolved, 'hits': total.hits, 'window_days': days};
  }

  List<Map<String, Object?>> opportunitiesJson(String symbol, {String methodId = AnalysisMethod.defaultId}) {
    final spec = source.spec(symbol);
    if (spec == null || !AnalysisMethod.isKnown(methodId)) return const [];
    final now = source.now();
    return [
      // التحليل على آخر شمعة مسكّرة
      for (final (index, tf) in Timeframe.modelTimeframes.indexed) _one(spec, tf, index, tf.bucketStart(now), methodId),
    ];
  }

  /// نفس الإشارة من معرّفها (`SYMBOL-tf-bucket@method`):
  /// الدالة حتمية فبترجع نفس الأرقام. معرّف غلط أو شمعة لسّا ما سكّرت → null.
  Map<String, Object?>? opportunityJson(String id) {
    // كل إشارة إلها طريقة (A3c): معرّف بدون `@method` (قبل A3c) أو بطريقة مش
    // معروفة (`@ai_model`) = مش موجودة
    final at = id.lastIndexOf('@');
    if (at < 0) return null;
    final methodId = id.substring(at + 1);
    final key = id.substring(0, at);
    if (!AnalysisMethod.isKnown(methodId)) return null;
    final cut = key.lastIndexOf('-');
    if (cut <= 0) return null;
    final bucket = int.tryParse(key.substring(cut + 1));
    final head = key.substring(0, cut);
    final mid = head.lastIndexOf('-');
    if (bucket == null || mid <= 0) return null;
    final spec = source.spec(head.substring(0, mid));
    final tf = Timeframe.fromApi(head.substring(mid + 1));
    final index = tf == null ? -1 : Timeframe.modelTimeframes.indexOf(tf);
    if (spec == null || tf == null || index < 0) return null;
    final signalClose = DateTime.fromMillisecondsSinceEpoch(bucket * tf.duration.inMilliseconds, isUtc: true);
    if (signalClose.isAfter(source.now())) return null;
    return _one(spec, tf, index, signalClose, methodId);
  }

  static String signalId(String symbol, Timeframe tf, int bucket, String methodId) =>
      '$symbol-${tf.apiValue}-$bucket@$methodId';

  Map<String, Object?> _one(
    SimulatedInstrumentSpec spec,
    Timeframe tf,
    int index,
    DateTime signalClose,
    String methodId,
  ) {
    final size = tf.duration;
    final bucket = signalClose.millisecondsSinceEpoch ~/ size.inMilliseconds;
    final price = source.priceAt(spec.symbol, signalClose);
    final read = _engine.read(spec, tf, index, signalClose, methodId);

    final atr = price * spec.dailyVol * math.sqrt(size.inMinutes / 1440) * 1.2;
    final rr = read.riskReward;
    final sign = read.long ? 1 : -1;
    double r(double v) => double.parse(v.toStringAsFixed(spec.precision));
    Map<String, double> zone(double mid, double half) => {'low': r(mid - half), 'high': r(mid + half)};

    return {
      'id': signalId(spec.symbol, tf, bucket, methodId),
      'symbol': spec.symbol,
      'timeframe': tf.apiValue,
      'status': read.detected ? 'detected' : 'not_detected',
      'direction': read.detected ? (read.long ? 'long' : 'short') : 'neutral',
      'setupType': read.setupType,
      'riskLevel': spec.dailyVol >= 0.0065 ? 'high' : 'medium',
      'probability': double.parse(read.probability.toStringAsFixed(2)),
      'entryZone': zone(price, atr * 0.15),
      'stopLossZone': zone(price - sign * atr * 1.1, atr * 0.1),
      'takeProfitZone': zone(price + sign * atr * rr, atr * 0.1),
      'riskReward': double.parse(rr.toStringAsFixed(1)),
      'generatedAt': signalClose.millisecondsSinceEpoch,
      // صالح لحد ما تسكّر 3 شموع كمان
      'validUntil': signalClose.add(size * 3).millisecondsSinceEpoch,
      'methodId': methodId,
      if (read.indicator != null) 'indicator': read.indicator,
      'provenance': 'demo',
    };
  }
}
