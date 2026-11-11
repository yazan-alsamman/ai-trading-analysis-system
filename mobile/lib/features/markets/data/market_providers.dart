import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/app_lifecycle.dart';
import '../../../core/data/network_status.dart';
import '../../signals/data/signal_profile_repository.dart';
import '../../signals/data/signals_repository.dart';
import '../../signals/models/model_accuracy.dart';
import '../../signals/models/opportunity.dart';
import '../models/market_models.dart';
import 'market_data_repository.dart';
import 'simulated_market_source.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';

/// مصدر الأسعار المحاكى المشترك (Home + شاشة السوق + آراء النموذج)
final simulatedMarketSourceProvider = Provider<SimulatedMarketSource>(
  (ref) => SimulatedMarketSource(),
);

/// الـ repository الوحيد يلي بيتبدّل بالـ API (تأخير بسيط حتى حالات التحميل تبيّن)
final marketDataRepositoryProvider = Provider<MarketDataRepository>(
  (ref) => apiSource(
    ref,
    ApiFeature.markets,
    simulated: () => SimulatedMarketDataRepository(
      source: ref.watch(simulatedMarketSourceProvider),
      latency: const Duration(milliseconds: 350),
    ),
  ),
);

final signalsRepositoryProvider = Provider<SignalsRepository>(
  (ref) => apiSource(
    ref,
    ApiFeature.signals,
    simulated: () => SimulatedSignalsRepository(source: ref.watch(simulatedMarketSourceProvider)),
  ),
);

/// الأدوات (بترتيب الـ repository)
final instrumentsProvider = FutureProvider<List<Instrument>>(
  (ref) => ref.watch(marketDataRepositoryProvider).instruments(),
);

final instrumentProvider = Provider.family<Instrument?, String>((ref, symbol) {
  final list = ref.watch(instrumentsProvider).valueOrNull ?? const [];
  for (final i in list) {
    if (i.symbol == symbol) return i;
  }
  return null;
});

/// آخر سعر لكل أداة: لقطة أولى، بعدين نبضات حيّة.
///
/// - بدون اتصال: آخر بيانات بتضل ظاهرة والنبضات بتوقف لحد ما يرجع.
/// - التطبيق بالخلفية: النبضات بتوقف كمان، وبترجع لما يرجع (الشموع بتنحمّل
///   من جديد إذا صار في فجوة - [mergeTick]).
/// - النبضات بتندمج بالخريطة (أداة ما وصلها تحديث بتحافظ على آخر سعر).
class LiveQuotesNotifier extends AsyncNotifier<Map<String, Quote>> {
  @override
  Future<Map<String, Quote>> build() async {
    final repo = ref.watch(marketDataRepositoryProvider);
    final offline = ref.watch(networkStatusProvider) == NetworkStatus.offline;
    final paused = !ref.watch(appActiveProvider);
    final previous = state.valueOrNull;
    var disposed = false;
    ref.onDispose(() => disposed = true);

    if ((offline || paused) && previous != null) return previous;
    final snapshot = previous ?? {for (final q in await repo.quotes()) q.symbol: q};
    if (disposed || offline || paused) return snapshot;

    final sub = repo.ticks().listen(
      (batch) {
        if (batch.isEmpty) return;
        final current = state.valueOrNull ?? snapshot;
        final merged = mergeNewerQuotes(current, batch);
        if (!identical(merged, current)) state = AsyncData(merged);
      },
      // نبضة فاشلة ما بتمسح الأسعار - الحالة بتبيّن بشارة التدفّق
      onError: (Object e, StackTrace st) => ref.read(_tickErrorProvider.notifier).state = true,
    );
    ref.onDispose(sub.cancel);
    return snapshot;
  }

  /// سحب للتحديث: لقطة جديدة (بدون مسح القديمة أثناء التحميل). تحديثين
  /// ورا بعض آمنين: سعر أقدم ما بيكتب فوق سعر أحدث.
  Future<void> refresh() async {
    final quotes = await ref.read(marketDataRepositoryProvider).quotes();
    final current = state.valueOrNull ?? const <String, Quote>{};
    state = AsyncData(mergeNewerQuotes(current, quotes));
    ref.read(_tickErrorProvider.notifier).state = false;
  }
}

/// بيدمج أسعار جديدة: كل سعر بيحلّ محل القديم بس إذا وقته مش أقدم.
/// بدون أي تغيير → نفس الخريطة (identical) فما في إعادة بناء.
Map<String, Quote> mergeNewerQuotes(Map<String, Quote> current, Iterable<Quote> incoming) {
  Map<String, Quote>? next;
  for (final q in incoming) {
    final old = (next ?? current)[q.symbol];
    if (old != null && (q.time.isBefore(old.time) || q == old)) continue;
    (next ??= {...current})[q.symbol] = q;
  }
  return next ?? current;
}

final liveQuotesProvider = AsyncNotifierProvider<LiveQuotesNotifier, Map<String, Quote>>(LiveQuotesNotifier.new);

final _tickErrorProvider = StateProvider<bool>((ref) => false);

/// سعر أداة وحدة - الصف بيعيد بناء نفسه بس لما سعره هو يتغيّر
final quoteProvider = Provider.family<Quote?, String>(
  (ref, symbol) => ref.watch(liveQuotesProvider.select((v) => v.valueOrNull?[symbol])),
);

/// حالة التدفّق للشارة (Live / Offline / ...)
final feedStatusProvider = Provider<FeedStatus>((ref) {
  if (ref.watch(networkStatusProvider) == NetworkStatus.offline) return FeedStatus.offline;
  if (ref.watch(_tickErrorProvider)) return FeedStatus.error;
  return ref.watch(liveQuotesProvider).when(
        data: (_) => FeedStatus.live,
        loading: () => FeedStatus.connecting,
        error: (_, __) => FeedStatus.error,
      );
});

/// إغلاقات آخر 24 ساعة (شمعة ساعة) للـ sparkline
final sparklineProvider = FutureProvider.autoDispose.family<List<double>, String>((ref, symbol) async {
  final candles = await ref.watch(marketDataRepositoryProvider).candles(symbol, Timeframe.h1, limit: 25);
  return [for (final c in candles) c.close];
});

/// آراء طريقة الاستراتيجية المحفوظة على أداة (15m / 1h / 4h): نفس أرقام قائمة
/// Signals وشاشة التفاصيل (النموذج بالافتراضي). تغيير الطريقة بس بيعيد الحساب.
final opportunitiesProvider = FutureProvider.autoDispose.family<List<Opportunity>, String>((ref, symbol) {
  final methodId = ref.watch(signalProfileProvider.select((p) => p.methodId));
  return ref.watch(signalsRepositoryProvider).opportunities(symbol, methodId: methodId);
});

/// خلاصة رأي النموذج (الأقوى + كم إطار متّفق) - null لحد ما يوصل
final modelReadProvider = Provider.autoDispose.family<AsyncValue<ModelRead>, String>((ref, symbol) {
  final now = ref.watch(simulatedMarketSourceProvider).now();
  return ref.watch(opportunitiesProvider(symbol)).whenData((list) => ModelRead.from(list, now));
});

/// دقة الإشارات السابقة (سطر الدقة بتبويب Signals)
final modelAccuracyProvider = FutureProvider.autoDispose<ModelAccuracy>(
  (ref) => ref.watch(signalsRepositoryProvider).accuracy(),
);

/// شموع أداة + إطار، والسعر الحي بيندمج بآخر شمعة.
///
/// تبديل الإطار بسرعة آمن: كل (أداة، إطار) إلو instance منفصل autoDispose،
/// فنتيجة طلب قديم ما بتكتب فوق الإطار الجديد.
class LiveCandlesNotifier extends AutoDisposeFamilyAsyncNotifier<List<Candle>, (String, Timeframe)> {
  static const int limit = 300;

  @override
  Future<List<Candle>> build((String, Timeframe) arg) async {
    final (symbol, timeframe) = arg;
    final candles = await ref.watch(marketDataRepositoryProvider).candles(symbol, timeframe, limit: limit);
    ref.listen<Quote?>(quoteProvider(symbol), (_, quote) {
      final current = state.valueOrNull;
      if (quote == null || current == null) return;
      final merged = mergeTick(current, quote, timeframe, maxLength: limit);
      if (merged == null) {
        ref.invalidateSelf(); // فجوة (التطبيق كان بالخلفية): تحميل من جديد
      } else if (!identical(merged, current)) {
        state = AsyncData(merged);
      }
    });
    return candles;
  }
}

final liveCandlesProvider = AsyncNotifierProvider.autoDispose
    .family<LiveCandlesNotifier, List<Candle>, (String, Timeframe)>(LiveCandlesNotifier.new);

/// بيدمج سعر حي بالشموع:
/// - نفس فترة آخر شمعة → بيحدّث close (و high/low)
/// - الفترة التالية مباشرة → شمعة جديدة (وبيشيل الأقدم إذا تجاوزنا [maxLength])
/// - نبضة أقدم من آخر شمعة أو بدون تغيير → نفس القائمة (identical)
/// - فجوة أكتر من شمعة → null (لازم تحميل من جديد)
List<Candle>? mergeTick(List<Candle> candles, Quote quote, Timeframe timeframe, {int maxLength = 300}) {
  if (candles.isEmpty) return candles;
  final bucket = timeframe.bucketStart(quote.time);
  final last = candles.last;
  if (bucket.isBefore(last.time)) return candles;
  if (bucket == last.time) {
    if (last.close == quote.price) return candles;
    return [...candles.take(candles.length - 1), last.withPrice(quote.price)];
  }
  if (bucket != last.time.add(timeframe.duration)) return null;
  final open = last.close;
  final next = Candle(
    time: bucket,
    open: open,
    high: quote.price > open ? quote.price : open,
    low: quote.price < open ? quote.price : open,
    close: quote.price,
    volume: 0,
  );
  final kept = candles.length >= maxLength ? candles.skip(candles.length - maxLength + 1) : candles;
  return [...kept, next];
}
