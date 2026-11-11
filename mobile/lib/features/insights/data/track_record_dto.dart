import '../../../core/data/json.dart';
import '../../markets/models/market_models.dart';
import '../../signals/data/signals_repository.dart';
import '../../signals/models/model_accuracy.dart';
import '../models/track_record.dart';

/// شكل الـ API لسجل النموذج (`GET /insights/track-record?window_days=`) → domain.
///
/// ```json
/// {"window_days": 30, "resolved": 64, "hits": 37,
///  "by_symbol": [{"symbol": "EUR/USD", "resolved": 9, "hits": 5}],
///  "by_timeframe": [{"timeframe": "1h", "resolved": 20, "hits": 12}],
///  "series": [{"start": 1760000000000, "days": 3, "resolved": 7, "hits": 4}]}
/// ```
///
/// الإجمالي بنفس قواعد سطر الدقة ([modelAccuracyFromJson]): ناقص أو غير منطقي
/// أو فترة مش 7 / 30 / 90 → null. الصفوف الغلط (أداة أو إطار مش معروف، hits >
/// resolved) بتنشال؛ المكرّر بينحسب أول مرة بس.
TrackRecord? trackRecordFromJson(Json json) {
  final overall = modelAccuracyFromJson(json);
  final period = InsightsPeriod.fromDays(overall?.windowDays);
  if (overall == null || period == null) return null;

  ModelAccuracy? row(Json row) {
    final resolved = row.integer('resolved');
    final hits = row.integer('hits');
    if (resolved == null || hits == null || resolved < 0 || hits < 0 || hits > resolved) return null;
    return ModelAccuracy(resolved: resolved, hits: hits, windowDays: period.days);
  }

  final symbols = <String, ModelAccuracy>{};
  for (final item in json.objects('by_symbol')) {
    final symbol = item.string('symbol')?.trim().toUpperCase();
    final accuracy = row(item);
    if (symbol == null || accuracy == null || !kProductSymbols.contains(symbol)) continue;
    symbols.putIfAbsent(symbol, () => accuracy);
  }

  final timeframes = <Timeframe, ModelAccuracy>{};
  for (final item in json.objects('by_timeframe')) {
    final timeframe = Timeframe.fromApi(item.string('timeframe'));
    final accuracy = row(item);
    if (timeframe == null || accuracy == null || !Timeframe.modelTimeframes.contains(timeframe)) continue;
    timeframes.putIfAbsent(timeframe, () => accuracy);
  }

  final series = <int, AccuracyPoint>{};
  for (final item in json.objects('series')) {
    final start = item.epochMillis('start');
    final days = item.integer('days');
    final accuracy = row(item);
    if (start == null || days == null || days <= 0 || accuracy == null) continue;
    series.putIfAbsent(start.millisecondsSinceEpoch, () => AccuracyPoint(start: start, days: days, accuracy: accuracy));
  }

  return TrackRecord(
    period: period,
    overall: overall,
    byInstrument: [
      for (final symbol in kProductSymbols)
        if (symbols[symbol] case final accuracy?) InstrumentAccuracy(symbol: symbol, accuracy: accuracy),
    ],
    byTimeframe: [
      for (final timeframe in Timeframe.modelTimeframes)
        if (timeframes[timeframe] case final accuracy?) TimeframeAccuracy(timeframe: timeframe, accuracy: accuracy),
    ],
    series: series.values.toList()..sort((a, b) => a.start.compareTo(b.start)),
  );
}
