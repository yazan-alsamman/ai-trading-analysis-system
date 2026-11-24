import 'package:flutter/foundation.dart';

/// نوع السوق - نفس `MarketType` بالـ backend (المنتج فوركس + ذهب بس)
enum MarketKind { forex, commodity }

/// الأدوات الثمانية بالمنتج (قاعدة المنتج: فوركس + ذهب بس)، بترتيب العرض
const List<String> kProductSymbols = [
  'EUR/USD',
  'XAU/USD',
  'GBP/USD',
  'USD/JPY',
  'USD/CHF',
  'AUD/USD',
  'USD/CAD',
  'NZD/USD',
];

/// أداة مالية (immutable). [symbol] بصيغة الـ backend: `EUR/USD`، `XAU/USD`.
/// الاسم الكامل المترجم من `AppLocalizations.instrumentName(symbol)`.
@immutable
final class Instrument {
  const Instrument({
    required this.symbol,
    required this.kind,
    required this.precision,
    this.id,
  });

  /// معرّف الـ backend (UUID) - null بالمصدر المحاكى
  final String? id;
  final String symbol;
  final MarketKind kind;

  /// خانات السعر: 5 للأزواج، 3 للين، 2 للذهب
  final int precision;

  String get base => symbol.split('/').first;

  String get quote => symbol.split('/').last;

  String format(double price) => price.toStringAsFixed(precision);

  @override
  bool operator ==(Object other) => other is Instrument && other.symbol == symbol;

  @override
  int get hashCode => symbol.hashCode;
}

/// الأطر الزمنية بالرسم: 1m · 15m · 1h · 4h · 1D ([apiValue] نفس الـ backend)
enum Timeframe {
  m1('1m', '1m', Duration(minutes: 1)),
  m15('15m', '15m', Duration(minutes: 15)),
  h1('1h', '1h', Duration(hours: 1)),
  h4('4h', '4h', Duration(hours: 4)),
  d1('1d', '1D', Duration(days: 1));

  const Timeframe(this.apiValue, this.label, this.duration);

  final String apiValue;
  final String label;
  final Duration duration;

  /// الأطر يلي النموذج بيحلّل عليها (نفس الويب)
  static const modelTimeframes = [m15, h1, h4];

  static Timeframe? fromApi(String? value) {
    for (final tf in values) {
      if (tf.apiValue == value?.toLowerCase()) return tf;
    }
    return null;
  }

  /// بداية الشمعة يلي فيها [time] (UTC)
  DateTime bucketStart(DateTime time) {
    final ms = time.toUtc().millisecondsSinceEpoch;
    final size = duration.inMilliseconds;
    return DateTime.fromMillisecondsSinceEpoch(ms - ms % size, isUtc: true);
  }
}

/// شمعة OHLC - [time] بداية الشمعة (UTC). الصالحة بس بتوصل لهون (الـ mapper بيفلتر)
@immutable
final class Candle {
  const Candle({
    required this.time,
    required this.open,
    required this.high,
    required this.low,
    required this.close,
    required this.volume,
  });

  final DateTime time;
  final double open;
  final double high;
  final double low;
  final double close;
  final double volume;

  bool get isBullish => close >= open;

  /// نفس الشمعة مع سعر حي جديد (high/low بيتوسّعوا إذا لزم)
  Candle withPrice(double price) => Candle(
        time: time,
        open: open,
        high: price > high ? price : high,
        low: price < low ? price : low,
        close: price,
        volume: volume,
      );

  @override
  bool operator ==(Object other) =>
      other is Candle &&
      other.time == time &&
      other.open == open &&
      other.high == high &&
      other.low == low &&
      other.close == close &&
      other.volume == volume;

  @override
  int get hashCode => Object.hash(time, open, high, low, close, volume);
}

/// آخر سعر + السعر قبل 24 ساعة (للتغيّر)
@immutable
final class Quote {
  const Quote({
    required this.symbol,
    required this.price,
    required this.reference,
    required this.time,
  });

  final String symbol;
  final double price;

  /// السعر قبل 24 ساعة
  final double reference;
  final DateTime time;

  /// نسبة التغيّر خلال 24 ساعة (+0.45 = +0.45%)
  double get changePercent => reference == 0 ? 0 : (price - reference) / reference * 100;

  @override
  bool operator ==(Object other) =>
      other is Quote &&
      other.symbol == symbol &&
      other.price == price &&
      other.reference == reference &&
      other.time == time;

  @override
  int get hashCode => Object.hash(symbol, price, reference, time);
}

/// حالة تدفّق الأسعار (نفس حالات الويب)
enum FeedStatus { connecting, live, delayed, stale, marketClosed, offline, error }
