import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../../core/data/json.dart';
import '../models/market_models.dart';
import 'market_cache.dart';
import 'market_data_repository.dart';
import 'market_dtos.dart';

/// بدون اتصال وما في نسخة محفوظة - الشاشة بتبيّن حالة "غير متصل"
final class MarketOfflineException implements Exception {
  const MarketOfflineException();

  @override
  String toString() => 'MarketOfflineException';
}

/// Decorator فوق أي [MarketDataRepository] (محاكاة أو API): بيكتب الأسعار
/// والشموع بالكاش (Drift) وبيرجّعها لما المصدر يفشل أو ما في اتصال.
///
/// - بدون اتصال: ما منطلب من المصدر أبدًا، الكاش مباشرة (أو
///   [MarketOfflineException] إذا فاضي) - هيك المحاكاة كمان بتوري الـ offline.
/// - المصدر فشل: الكاش؛ إذا فاضي → الخطأ الأصلي.
/// - الكتابة بالخلفية (ما منستناها) وأي خطأ كاش بينبلع: الكاش ما بيوقّف شاشة.
/// - النبضات الحيّة: آخر سعر لكل أداة بيتجمّع وبينكتب دفعة وحدة كل
///   [tickWriteInterval] على الأكتر (مش كتابة لكل نبضة)، والباقي بينكتب لما
///   الاشتراك يتسكّر.
/// - [servingCache]: آخر قراءة أسعار إجت من الكاش؟ (الشارة ما بتقول Live)
class CachingMarketDataRepository implements MarketDataRepository {
  CachingMarketDataRepository({
    required this.source,
    required this.cache,
    required this.isOffline,
    DateTime Function()? clock,
    this.tickWriteInterval = const Duration(seconds: 5),
  }) : _clock = clock ?? DateTime.now;

  final MarketDataRepository source;
  final MarketCache cache;
  final bool Function() isOffline;
  final DateTime Function() _clock;
  final Duration tickWriteInterval;

  final ValueNotifier<bool> servingCache = ValueNotifier(false);

  /// كتابات لسّا شغّالة (الاختبارات بتستنّاها بـ [flushWrites])
  final Set<Future<void>> _writes = {};

  final Map<String, Quote> _pendingTicks = {};
  DateTime? _lastTickWrite;

  /// كم مرة انكتبت دفعة نبضات (الاختبارات)
  @visibleForTesting
  int tickWrites = 0;

  @override
  bool get isSimulated => source.isSimulated;

  @override
  Future<List<Instrument>> instruments() async {
    if (!isOffline()) {
      try {
        return await source.instruments();
      } catch (error) {
        return _instrumentsFromCache(error);
      }
    }
    return _instrumentsFromCache(const MarketOfflineException());
  }

  @override
  Future<List<Quote>> quotes() async {
    if (!isOffline()) {
      try {
        final quotes = await source.quotes();
        servingCache.value = false;
        _write(() => cache.saveQuotes(quotes, _clock()));
        return quotes;
      } catch (error) {
        return _quotesFromCache(error);
      }
    }
    return _quotesFromCache(const MarketOfflineException());
  }

  @override
  Future<List<Candle>> candles(String symbol, Timeframe timeframe, {int limit = 300}) async {
    if (!isOffline()) {
      try {
        final candles = await source.candles(symbol, timeframe, limit: limit);
        _write(() => cache.saveCandles(symbol, timeframe, candles, _clock()));
        return candles;
      } catch (error) {
        return _candlesFromCache(symbol, timeframe, limit, error);
      }
    }
    return _candlesFromCache(symbol, timeframe, limit, const MarketOfflineException());
  }

  @override
  Stream<List<Quote>> ticks() {
    late final StreamController<List<Quote>> controller;
    StreamSubscription<List<Quote>>? sub;
    controller = StreamController<List<Quote>>(
      onListen: () {
        sub = source.ticks().listen(
          (batch) {
            if (batch.isNotEmpty) {
              servingCache.value = false;
              _bufferTicks(batch);
            }
            controller.add(batch);
          },
          onError: controller.addError,
          onDone: controller.close,
        );
      },
      onPause: () => sub?.pause(),
      onResume: () => sub?.resume(),
      onCancel: () async {
        await sub?.cancel();
        _flushTicks();
      },
    );
    return controller.stream;
  }

  /// بيستنّى كل الكتابات الحالية (الاختبارات + قبل مسح الكاش)
  Future<void> flushWrites() async {
    _flushTicks();
    while (_writes.isNotEmpty) {
      await Future.wait(_writes.toList());
    }
  }

  // ── داخلي ──────────────────────────────────────────────────

  void _bufferTicks(List<Quote> batch) {
    for (final q in batch) {
      _pendingTicks[q.symbol] = q;
    }
    final now = _clock();
    final last = _lastTickWrite;
    if (last == null || now.difference(last) >= tickWriteInterval) _flushTicks(now);
  }

  void _flushTicks([DateTime? at]) {
    if (_pendingTicks.isEmpty) return;
    final batch = _pendingTicks.values.toList();
    _pendingTicks.clear();
    final now = at ?? _clock();
    _lastTickWrite = now;
    tickWrites++;
    _write(() => cache.saveQuotes(batch, now));
  }

  void _write(Future<void> Function() write) {
    late final Future<void> future;
    future = Future(write).catchError((Object error) {
      debugPrint('MarketCache: write failed: $error');
    }).whenComplete(() => _writes.remove(future));
    _writes.add(future);
  }

  Future<T?> _read<T>(Future<T?> Function() read) async {
    try {
      return await read();
    } catch (error) {
      debugPrint('MarketCache: read failed: $error');
      return null;
    }
  }

  Future<List<Quote>> _quotesFromCache(Object error) async {
    final cached = await _read(cache.readQuotes);
    if (cached == null) throw error;
    servingCache.value = true;
    return cached.value;
  }

  Future<List<Candle>> _candlesFromCache(String symbol, Timeframe timeframe, int limit, Object error) async {
    final cached = await _read(() => cache.readCandles(symbol, timeframe, limit: limit));
    if (cached == null) throw error;
    return cached.value;
  }

  /// الأدوات مش محفوظة بجدول: بدون مصدر منبنيها من أسعار الكاش (نفس
  /// الدقة الافتراضية تبع الـ DTO)، بترتيب المنتج
  Future<List<Instrument>> _instrumentsFromCache(Object error) async {
    final cached = await _read(cache.readQuotes);
    if (cached == null) throw error;
    final symbols = {for (final q in cached.value) q.symbol};
    final ordered = [
      ...kProductSymbols.where(symbols.contains),
      ...symbols.where((s) => !kProductSymbols.contains(s)),
    ];
    return mapValid(
      [
        for (final s in ordered)
          {'symbol': s, 'market': s.startsWith('XAU') ? 'commodity' : 'forex', 'is_active': true},
      ],
      (m) => InstrumentDto.fromJson(Json(m)).toDomain(),
    );
  }
}
