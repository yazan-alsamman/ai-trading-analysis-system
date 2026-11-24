import 'dart:math' as math;

import '../models/market_models.dart';

/// مواصفات أداة محاكاة: سعر الأساس، التذبذب اليومي، والـ seed
final class SimulatedInstrumentSpec {
  const SimulatedInstrumentSpec(this.symbol, this.market, this.precision, this.base, this.dailyVol, this.seed);

  final String symbol;
  final String market;
  final int precision;
  final double base;

  /// الانحراف المعياري اليومي للسعر (0.005 = 0.5% باليوم)
  final double dailyVol;
  final int seed;
}

/// مصدر أسعار محاكاة **حتمي** (deterministic): السعر دالة بالوقت بس.
///
/// - نفس اللحظة = نفس السعر دايمًا (بكل تشغيل وبكل شاشة)، فالـ sparkline
///   بالـ Home والسعر والشموع بشاشة السوق متطابقين.
/// - log(price) = مجموع "value noise" على عدة مقاييس زمنية (10 ثواني لـ 180
///   يوم)، كل واحد بوزن من التذبذب اليومي للأداة - شكل واقعي بدون حالة مخزّنة.
/// - الشمعة = عيّنات من نفس الدالة جوّا فترتها، فإغلاق شمعة الساعة = إغلاق
///   شمعة الربع ساعة بنفس اللحظة (الأطر الزمنية متّسقة).
/// - بيرجع أشكال الـ API الخام (JSON) حتى الـ repository يمرّ بنفس طبقة
///   الـ DTO → domain يلي رح يستخدمها الـ API الحقيقي.
/// - المحاكاة شغّالة 24/7 (بدون عطلة الويكند) حتى التحديثات الحيّة تنفحص بأي وقت.
final class SimulatedMarketSource {
  SimulatedMarketSource({DateTime Function()? clock}) : _clock = clock ?? DateTime.now;

  final DateTime Function() _clock;

  static const List<SimulatedInstrumentSpec> specs = [
    SimulatedInstrumentSpec('EUR/USD', 'forex', 5, 1.08762, 0.0045, 11),
    SimulatedInstrumentSpec('XAU/USD', 'commodity', 2, 2045.30, 0.0100, 17),
    SimulatedInstrumentSpec('GBP/USD', 'forex', 5, 1.26541, 0.0055, 23),
    SimulatedInstrumentSpec('USD/JPY', 'forex', 3, 151.284, 0.0060, 29),
    SimulatedInstrumentSpec('USD/CHF', 'forex', 5, 0.88421, 0.0050, 31),
    SimulatedInstrumentSpec('AUD/USD', 'forex', 5, 0.65873, 0.0065, 37),
    SimulatedInstrumentSpec('USD/CAD', 'forex', 5, 1.36218, 0.0045, 41),
    SimulatedInstrumentSpec('NZD/USD', 'forex', 5, 0.60512, 0.0068, 43),
  ];

  /// (الفترة بالثواني، الوزن من التذبذب اليومي)
  static const List<(int, double)> _octaves = [
    (10, 0.012),
    (60, 0.03),
    (300, 0.07),
    (3600, 0.25),
    (21600, 0.5),
    (86400, 0.8),
    (604800, 1.6),
    (2592000, 3.0),
    (15552000, 5.0),
  ];

  /// عيّنات جوّا كل شمعة لحساب high/low
  static const int _samplesPerCandle = 12;

  /// أكتر عدد شموع بطلب واحد (نفس حد الـ backend تقريبًا)
  static const int maxCandles = 1000;

  DateTime now() => _clock().toUtc();

  SimulatedInstrumentSpec? spec(String symbol) {
    for (final s in specs) {
      if (s.symbol == symbol) return s;
    }
    return null;
  }

  // ── أشكال الـ API ─────────────────────────────────────────

  /// متل `GET /instruments` (Page.items)
  List<Map<String, Object?>> instrumentsJson() => [
        for (final s in specs)
          {
            'id': null,
            'symbol': s.symbol,
            'source': 'simulated',
            'market': s.market,
            'base_asset': s.symbol.split('/').first,
            'quote_asset': s.symbol.split('/').last,
            'price_precision': s.precision,
            'is_active': true,
          },
      ];

  /// متل `GET /instruments/{id}/candles` (CandleSeries) - آخر [limit] شمعة
  /// لحد اللحظة الحالية، والأخيرة لسّا مفتوحة (إغلاقها = السعر الحالي)
  Map<String, Object?> candlesJson(String symbol, Timeframe timeframe, {int limit = 300}) {
    final s = spec(symbol);
    final count = limit.clamp(1, maxCandles);
    final now = this.now();
    final size = timeframe.duration;
    final last = timeframe.bucketStart(now);
    final candles = <Map<String, Object?>>[];
    if (s != null) {
      for (var i = count - 1; i >= 0; i--) {
        final start = last.subtract(size * i);
        final end = i == 0 ? now : start.add(size);
        candles.add(_candle(s, start, end, timeframe));
      }
    }
    return {'instrument_id': null, 'timeframe': timeframe.apiValue, 'candles': candles};
  }

  /// متل `GET /market/quotes` - كل الأدوات
  List<Map<String, Object?>> quotesJson() {
    final now = this.now();
    return [for (final s in specs) _quote(s, now)];
  }

  // ── الدالة الأساسية ───────────────────────────────────────

  /// السعر بلحظة [time] (بدون تقريب)
  double priceAt(String symbol, DateTime time) {
    final s = spec(symbol);
    return s == null ? double.nan : _price(s, time);
  }

  double _price(SimulatedInstrumentSpec s, DateTime time) {
    final t = time.toUtc().millisecondsSinceEpoch / 1000;
    var logDeviation = 0.0;
    for (var k = 0; k < _octaves.length; k++) {
      final (period, weight) = _octaves[k];
      logDeviation += weight * s.dailyVol * _noise(s.seed, k, t / period);
    }
    return s.base * math.exp(logDeviation);
  }

  Map<String, Object?> _quote(SimulatedInstrumentSpec s, DateTime now) => {
        'symbol': s.symbol,
        'price': _round(_price(s, now), s.precision),
        'reference': _round(_price(s, now.subtract(const Duration(hours: 24))), s.precision),
        'time': now.millisecondsSinceEpoch / 1000,
        'provenance': 'demo',
      };

  Map<String, Object?> _candle(SimulatedInstrumentSpec s, DateTime start, DateTime end, Timeframe tf) {
    final open = _price(s, start);
    final close = _price(s, end);
    var high = math.max(open, close);
    var low = math.min(open, close);
    final span = end.difference(start).inMilliseconds;
    for (var i = 1; i < _samplesPerCandle; i++) {
      final p = _price(s, start.add(Duration(milliseconds: span * i ~/ _samplesPerCandle)));
      high = math.max(high, p);
      low = math.min(low, p);
    }
    // ذيول صغيرة: العيّنات ما بتلقط أعلى/أدنى نقطة فعلية
    final bucket = start.millisecondsSinceEpoch ~/ tf.duration.inMilliseconds;
    final range = high - low;
    high += range * 0.25 * _hash01(s.seed, 101, bucket);
    low -= range * 0.25 * _hash01(s.seed, 102, bucket);

    final hour = start.hour;
    final busy = hour >= 7 && hour < 17 ? 1.4 : 0.7; // لندن/نيويورك أنشط
    final volume = 1000 * tf.duration.inMinutes * busy * (0.5 + _hash01(s.seed, 103, bucket));
    return {
      'time': start.millisecondsSinceEpoch ~/ 1000,
      'open': _round(open, s.precision),
      'high': _round(high, s.precision),
      'low': _round(low, s.precision),
      'close': _round(close, s.precision),
      'volume': volume.roundToDouble(),
    };
  }

  // ── أدوات ──────────────────────────────────────────────────

  static double _round(double v, int precision) => double.parse(v.toStringAsFixed(precision));

  /// value noise ناعم بين -1 و 1
  static double _noise(int seed, int octave, double x) {
    final i = x.floor();
    final f = x - i;
    final a = _hash01(seed, octave, i) * 2 - 1;
    final b = _hash01(seed, octave, i + 1) * 2 - 1;
    final smooth = f * f * (3 - 2 * f);
    return a + (b - a) * smooth;
  }

  /// hash حتمي 32-bit → [0, 1)
  static double _hash01(int seed, int salt, int i) {
    var h = (seed * 0x9E3779B1 + salt * 0x85EBCA77 + i * 0xC2B2AE3D) & 0xFFFFFFFF;
    h = ((h ^ (h >> 16)) * 0x7FEB352D) & 0xFFFFFFFF;
    h = ((h ^ (h >> 15)) * 0x846CA68B) & 0xFFFFFFFF;
    h = h ^ (h >> 16);
    return h / 4294967296.0;
  }

  /// hash عام لمصادر محاكاة تانية (فرص النموذج) بنفس الخوارزمية
  static double hash01(int seed, int salt, int i) => _hash01(seed, salt, i);
}
