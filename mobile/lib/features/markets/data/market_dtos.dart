import '../../../core/data/json.dart';
import '../models/market_models.dart';

// أشكال الـ API الخام (DTO) + تحويلها لـ domain. الواجهة ما بتشوف غير الـ domain.
// المراجع: backend/app/schemas/market.py (InstrumentRead، CandleOut)،
// وعقد الأسعار بـ web/src/services/schemas.ts (QuoteSchema).

/// `InstrumentRead`: id, symbol, source, market, base_asset, quote_asset,
/// price_precision, is_active
final class InstrumentDto {
  const InstrumentDto({
    required this.id,
    required this.symbol,
    required this.market,
    required this.pricePrecision,
    required this.isActive,
  });

  final String? id;
  final String? symbol;
  final String? market;
  final int? pricePrecision;
  final bool? isActive;

  factory InstrumentDto.fromJson(Json json) => InstrumentDto(
        id: json.string('id'),
        symbol: json.string('symbol'),
        market: json.string('market'),
        pricePrecision: json.integer('price_precision'),
        isActive: json.boolean('is_active'),
      );

  Map<String, Object?> toJson() => {
        'id': id,
        'symbol': symbol,
        'market': market,
        'price_precision': pricePrecision,
        'is_active': isActive,
      };

  /// null = مش صالحة للعرض (رمز ناقص، سوق غير مدعوم، أو موقوفة)
  Instrument? toDomain() {
    final s = symbol?.trim().toUpperCase();
    if (s == null || !s.contains('/') || isActive == false) return null;
    final kind = switch (market) {
      'forex' => MarketKind.forex,
      'commodity' => MarketKind.commodity,
      _ => null, // crypto / stock: برا نطاق المنتج
    };
    if (kind == null) return null;
    final precision = pricePrecision ?? _defaultPrecision(s);
    return Instrument(
      id: id,
      symbol: s,
      kind: kind,
      precision: precision.clamp(0, 8),
    );
  }

  static int _defaultPrecision(String symbol) => switch (symbol) {
        'XAU/USD' => 2,
        _ when symbol.endsWith('/JPY') => 3,
        _ => 5,
      };
}

/// `CandleOut`: time (unix seconds UTC), open, high, low, close, volume
final class CandleDto {
  const CandleDto({
    required this.time,
    required this.open,
    required this.high,
    required this.low,
    required this.close,
    required this.volume,
  });

  final DateTime? time;
  final double? open;
  final double? high;
  final double? low;
  final double? close;
  final double? volume;

  factory CandleDto.fromJson(Json json) => CandleDto(
        time: json.dateTime('time'),
        open: json.number('open'),
        high: json.number('high'),
        low: json.number('low'),
        close: json.number('close'),
        volume: json.number('volume'),
      );

  Map<String, Object?> toJson() => {
        'time': time == null ? null : time!.millisecondsSinceEpoch ~/ 1000,
        'open': open,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
      };

  /// null = شمعة ناقصة أو غير منطقية (high < low، سعر ≤ 0...)
  Candle? toDomain() {
    final (t, o, h, l, c) = (time, open, high, low, close);
    if (t == null || o == null || h == null || l == null || c == null) return null;
    if (o <= 0 || h <= 0 || l <= 0 || c <= 0) return null;
    if (h < l || h < o || h < c || l > o || l > c) return null;
    final v = volume;
    return Candle(time: t, open: o, high: h, low: l, close: c, volume: v == null || v < 0 ? 0 : v);
  }
}

/// سلسلة شموع مرتّبة تصاعديًا بدون تكرار - أي شمعة غير صالحة بتنشال
List<Candle> candlesFromJson(Json json) {
  final candles = mapValid(json.objects('candles'), (j) => CandleDto.fromJson(j).toDomain());
  candles.sort((a, b) => a.time.compareTo(b.time));
  final unique = <Candle>[];
  for (final c in candles) {
    if (unique.isNotEmpty && unique.last.time == c.time) {
      unique[unique.length - 1] = c; // الأحدث بيربح
    } else {
      unique.add(c);
    }
  }
  return unique;
}

/// `Quote`: symbol, price, reference (قبل 24 ساعة), time (unix seconds)
final class QuoteDto {
  const QuoteDto({required this.symbol, required this.price, required this.reference, required this.time});

  final String? symbol;
  final double? price;
  final double? reference;
  final DateTime? time;

  factory QuoteDto.fromJson(Json json) => QuoteDto(
        symbol: json.string('symbol'),
        price: json.number('price'),
        reference: json.number('reference'),
        time: json.dateTime('time'),
      );

  Map<String, Object?> toJson() => {
        'symbol': symbol,
        'price': price,
        'reference': reference,
        'time': time == null ? null : time!.millisecondsSinceEpoch / 1000,
      };

  Quote? toDomain() {
    final (s, p, t) = (symbol?.trim().toUpperCase(), price, time);
    if (s == null || s.isEmpty || p == null || p <= 0 || t == null) return null;
    final r = reference;
    // مرجع ناقص = ما في تغيّر معروف (0%) بدل رقم مخترع
    return Quote(symbol: s, price: p, reference: r == null || r <= 0 ? p : r, time: t);
  }
}
