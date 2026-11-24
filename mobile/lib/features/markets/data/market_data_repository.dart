import 'dart:async';

import '../../../core/data/json.dart';
import '../models/market_models.dart';
import 'market_dtos.dart';
import 'simulated_market_source.dart';

/// مصدر بيانات السوق - الطبقة الوحيدة يلي بتتبدّل لما ينربط الـ API
///
/// الشاشات والـ providers بيعرفوا هالواجهة بس. للربط الحقيقي: اعمل
/// `ApiMarketDataRepository` (Dio + WebSocket) وبدّل `marketDataRepositoryProvider`.
abstract interface class MarketDataRepository {
  /// بيانات محاكاة؟ (الواجهة بتبيّن شارة "Simulated" على كل سعر ورسم)
  bool get isSimulated;

  Future<List<Instrument>> instruments();

  /// آخر [limit] شمعة مرتّبة تصاعديًا (الأخيرة ممكن تكون لسّا مفتوحة)
  Future<List<Candle>> candles(String symbol, Timeframe timeframe, {int limit});

  /// آخر سعر لكل أداة
  Future<List<Quote>> quotes();

  /// تحديثات الأسعار الحيّة (دفعة لكل الأدوات بكل نبضة)
  Stream<List<Quote>> ticks();
}

/// تنفيذ على [SimulatedMarketSource]: نفس مسار DTO → domain متل الـ API
class SimulatedMarketDataRepository implements MarketDataRepository {
  SimulatedMarketDataRepository({
    SimulatedMarketSource? source,
    this.tickInterval = const Duration(milliseconds: 1500),
    this.latency = Duration.zero,
  }) : source = source ?? SimulatedMarketSource();

  final SimulatedMarketSource source;
  final Duration tickInterval;

  /// تأخير مصطنع للطلبات (لتجربة حالات التحميل) - صفر بالاختبارات
  final Duration latency;

  @override
  bool get isSimulated => true;

  Future<void> _wait() => latency == Duration.zero ? Future.value() : Future.delayed(latency);

  @override
  Future<List<Instrument>> instruments() async {
    await _wait();
    return mapValid(source.instrumentsJson(), (m) => InstrumentDto.fromJson(Json(m)).toDomain());
  }

  @override
  Future<List<Candle>> candles(String symbol, Timeframe timeframe, {int limit = 300}) async {
    await _wait();
    return candlesFromJson(Json(source.candlesJson(symbol, timeframe, limit: limit)));
  }

  @override
  Future<List<Quote>> quotes() async {
    await _wait();
    return _mapQuotes(source.quotesJson());
  }

  @override
  Stream<List<Quote>> ticks() =>
      Stream.periodic(tickInterval, (_) => _mapQuotes(source.quotesJson()));

  static List<Quote> _mapQuotes(List<Map<String, Object?>> raw) =>
      mapValid(raw, (m) => QuoteDto.fromJson(Json(m)).toDomain());
}
