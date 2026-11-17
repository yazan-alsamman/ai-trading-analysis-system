import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/shell/shell_tab.dart';
import '../../../core/data/low_data_mode.dart';

import '../../../core/data/app_lifecycle.dart';
import '../../../core/data/network_status.dart';
import '../../signals/data/caching_signals_repository.dart';
import '../../signals/data/signal_profile_repository.dart';
import '../../signals/data/signals_repository.dart';
import '../../signals/models/model_accuracy.dart';
import '../../signals/models/opportunity.dart';
import '../../../core/database/cache_support.dart';
import '../../../core/database/database_providers.dart';
import '../../../core/database/user_cache_guard.dart';
import '../models/market_models.dart';
import 'caching_market_data_repository.dart';
import 'market_cache.dart';
import 'market_data_repository.dart';
import 'simulated_market_source.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';

/// مصدر الأسعار المحاكى المشترك (Home + شاشة السوق + آراء النموذج)
final simulatedMarketSourceProvider = Provider<SimulatedMarketSource>(
  (ref) => SimulatedMarketSource(),
);

/// H5a: كاش السوق بـ Drift (مفتاح واحد متل ApiFeature). شغّال = الأسعار
/// والشموع بتنكتب بالكاش وبترجع منه بدون اتصال أو لما المصدر يفشل (كمان
/// مع المحاكاة، حتى الـ offline ينعرض). مطفي = المصدر مباشرة متل قبل.
const bool kMarketOfflineCache = true;

final marketCacheEnabledProvider = Provider<bool>((ref) => kMarketOfflineCache);

/// ساعة الكاش (وقت الكتابة + حدّ كتابة النبضات) - الاختبارات بتثبّتها
final marketCacheClockProvider = Provider<DateTime Function()>((ref) => DateTime.now);

/// كاش الأسعار والشموع (القاعدة بتنفتح أول ما ينكتب/ينقرأ شي)
final marketCacheProvider = Provider<MarketCache>(
  (ref) => MarketCache(ref.watch(appDatabaseProvider), maxCandlesPerSeries: LiveCandlesNotifier.limit),
);

/// المصدر نفسه (محاكاة أو API) - الـ repository الوحيد يلي بيتبدّل بالـ API
/// (تأخير بسيط حتى حالات التحميل تبيّن). الشاشات بتقرأ [marketDataRepositoryProvider].
final marketSourceRepositoryProvider = Provider<MarketDataRepository>(
  (ref) => apiSource<MarketDataRepository>(
    ref,
    ApiFeature.markets,
    simulated: () => SimulatedMarketDataRepository(
      source: ref.watch(simulatedMarketSourceProvider),
      latency: const Duration(milliseconds: 350),
    ),
  ),
);

/// يلي بتقرأه الشاشات: المصدر، وفوقه طبقة الكاش (H5a) إذا [kMarketOfflineCache]،
/// فالمحاكاة والـ API الحقيقي الاتنين بينحفظوا.
final marketDataRepositoryProvider = Provider<MarketDataRepository>(createMarketDataRepository);

/// منطق [marketDataRepositoryProvider] (الاختبارات بترجّعه بعد override المحاكاة)
MarketDataRepository createMarketDataRepository(Ref ref) {
  final source = ref.watch(marketSourceRepositoryProvider);
  if (!ref.watch(marketCacheEnabledProvider)) return source;
  final caching = CachingMarketDataRepository(
    source: source,
    cache: ref.watch(marketCacheProvider),
    isOffline: () => ref.read(networkStatusProvider) == NetworkStatus.offline,
    clock: ref.watch(marketCacheClockProvider),
  );
  ref.onDispose(caching.servingCache.dispose);
  return caching;
}

/// آخر قراءة أسعار إجت من الكاش وإحنا متصلين (المصدر فشل) → الشارة "Stale"
final marketServingCacheProvider = Provider<bool>((ref) {
  final repo = ref.watch(marketDataRepositoryProvider);
  if (repo is! CachingMarketDataRepository) return false;
  void changed() => ref.invalidateSelf();
  repo.servingCache.addListener(changed);
  ref.onDispose(() => repo.servingCache.removeListener(changed));
  return repo.servingCache.value;
});

/// H5a: الأسعار المعروضة مش حيّة (بدون اتصال، أو من الكاش لأنو المصدر فشل)
/// → سطر "Last updated" وشارة الحالة. الكاش مطفي = false دايمًا (متل قبل).
final marketShowingSavedProvider = Provider<bool>((ref) {
  if (!ref.watch(marketCacheEnabledProvider)) return false;
  return ref.watch(networkStatusProvider) == NetworkStatus.offline || ref.watch(marketServingCacheProvider);
});

/// Settings → Developer (debug): بيمسح الأسعار والشموع المحفوظة
Future<void> clearMarketCache(WidgetRef ref) async {
  final repo = ref.read(marketDataRepositoryProvider);
  if (repo is CachingMarketDataRepository) await repo.flushWrites();
  await ref.read(marketCacheProvider).clear();
}

/// مصدر الإشارات نفسه (محاكاة أو API) - الـ repository يلي بيتبدّل بالـ API
final signalsSourceRepositoryProvider = Provider<SignalsRepository>((ref) {
  // H5c: المحاكاة بتحفظ "requested by you" بالذاكرة → نسخة جديدة لكل حساب
  ref.watch(cacheOwnerProvider);
  return apiSource(
    ref,
    ApiFeature.signals,
    simulated: () => SimulatedSignalsRepository(source: ref.watch(simulatedMarketSourceProvider)),
  );
});

/// H5b: كاش الإشارات (نفس قاعدة Drift)
final signalsCacheProvider = Provider<SignalsCache>((ref) => SignalsCache(ref.watch(appDatabaseProvider)));

/// يلي بتقرأه الشاشات: المصدر، وفوقه طبقة الكاش (H5b، نفس مفتاح
/// [kMarketOfflineCache]). صاحب الصفوف الخاصة = الحساب الداخل.
final signalsRepositoryProvider = Provider<SignalsRepository>(createSignalsRepository);

/// منطق [signalsRepositoryProvider] (الاختبارات بترجّعه)
SignalsRepository createSignalsRepository(Ref ref) {
  final source = ref.watch(signalsSourceRepositoryProvider);
  if (!ref.watch(marketCacheEnabledProvider)) return source;
  final caching = CachingSignalsRepository(
    source: source,
    cache: ref.watch(signalsCacheProvider),
    isOffline: () => ref.read(networkStatusProvider) == NetworkStatus.offline,
    owner: ref.watch(cacheOwnerProvider),
    ownerStillCurrent: ownerStillCurrent(ref, ref.read(cacheOwnerProvider)),
    clock: ref.watch(marketCacheClockProvider),
  );
  ref.onDispose(caching.savedAt.dispose);
  return caching;
}

/// H5b: وقت النسخة المحفوظة المعروضة لمفتاح الإشارات (`feed`، `item:<id>`،
/// `read:<SYMBOL>:<method>`) - null = حيّة (أو الكاش مطفي)
final signalsSavedAtProvider = Provider.family<DateTime?, String>((ref, key) {
  final repo = ref.watch(signalsRepositoryProvider);
  return watchSavedAt(ref, repo is CachingSignalsRepository ? repo.savedAt : null, key);
});

/// الأدوات (بترتيب الـ repository)
///
/// H5a (الكاش شغّال): انبنت بدون اتصال (من الكاش أو ما في كاش) → لما يرجع
/// الاتصال بتتحمّل من جديد لحالها.
final instrumentsProvider = FutureProvider<List<Instrument>>((ref) {
  if (ref.read(marketCacheEnabledProvider) && ref.read(networkStatusProvider) == NetworkStatus.offline) {
    ref.listen<NetworkStatus>(networkStatusProvider, (previous, next) {
      if (next == NetworkStatus.online) ref.invalidateSelf();
    });
  }
  return ref.watch(marketDataRepositoryProvider).instruments();
});

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
  /// الأسعار الحالية من وقت ما كان في اتصال (أو من الكاش)؟ لما يرجع الاتصال
  /// منجيب لقطة جديدة لحالنا بدل ما نستنّى أول نبضة
  bool _stale = false;

  @override
  Future<Map<String, Quote>> build() async {
    final repo = ref.watch(marketDataRepositoryProvider);
    final offline = ref.watch(networkStatusProvider) == NetworkStatus.offline;
    final paused = !ref.watch(appActiveProvider);
    // H5b: Low data mode = تحديث واحد كل 5 ثواني (صفر = كل نبضة). التبديل بيعيد
    // الاشتراك بس (الأسعار الحالية بتضل)، فالإطفاء بيرجّع النبضات فورًا.
    final interval = ref.watch(quoteUpdateIntervalProvider);
    final previous = state.valueOrNull;
    var disposed = false;
    ref.onDispose(() => disposed = true);

    // الكاش مطفي: متل قبل H5a بالظبط (ما في لقطة جديدة لما يرجع الاتصال)
    final cacheOn = ref.read(marketCacheEnabledProvider);

    if ((offline || paused) && previous != null) {
      _stale = cacheOn && (_stale || offline);
      return previous;
    }
    final Map<String, Quote> snapshot;
    if (previous == null) {
      snapshot = {for (final q in await repo.quotes()) q.symbol: q};
    } else {
      // رجع الاتصال: لقطة جديدة فوق القديمة (فشل = منضل على القديمة والنبضات بتكمّل)
      snapshot = _stale ? mergeNewerQuotes(previous, await _freshOr(repo, previous)) : previous;
    }
    _stale = cacheOn && offline;
    if (disposed || offline || paused) return snapshot;

    void apply(Iterable<Quote> batch) {
      final current = state.valueOrNull ?? snapshot;
      final merged = mergeNewerQuotes(current, batch);
      if (!identical(merged, current)) state = AsyncData(merged);
    }

    // H5b: بالـ Low data mode النبضات بتتجمّع (آخر سعر لكل أداة) وبتنطبّق مرة
    // بأول نبضة، بعدين مرة كل [interval] على الأكتر
    Map<String, Quote>? pending;
    Timer? window;
    void flush() {
      final batch = pending;
      pending = null;
      if (batch != null) apply(batch.values);
    }

    final sub = repo.ticks().listen(
      (batch) {
        if (batch.isEmpty) return;
        if (interval == Duration.zero) return apply(batch);
        final buffer = pending ??= {};
        for (final q in batch) {
          buffer[q.symbol] = q;
        }
        if (window != null) return;
        flush();
        window = Timer.periodic(interval, (timer) {
          if (pending == null) {
            timer.cancel();
            window = null;
          } else {
            flush();
          }
        });
      },
      // نبضة فاشلة ما بتمسح الأسعار - الحالة بتبيّن بشارة التدفّق
      onError: (Object e, StackTrace st) => ref.read(_tickErrorProvider.notifier).state = true,
    );
    ref.onDispose(() {
      sub.cancel();
      window?.cancel();
    });
    return snapshot;
  }

  static Future<Iterable<Quote>> _freshOr(MarketDataRepository repo, Map<String, Quote> previous) async {
    try {
      return await repo.quotes();
    } catch (_) {
      return previous.values;
    }
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

/// وقت آخر سعر وصل (أحدث سعر بالقائمة) - سطر "Last updated" بالـ Home
final latestQuoteTimeProvider = Provider<DateTime?>((ref) {
  final quotes = ref.watch(liveQuotesProvider).valueOrNull;
  if (quotes == null || quotes.isEmpty) return null;
  return quotes.values.map((q) => q.time).reduce((a, b) => a.isAfter(b) ? a : b);
});

/// سعر أداة وحدة - الصف بيعيد بناء نفسه بس لما سعره هو يتغيّر
final quoteProvider = Provider.family<Quote?, String>(
  (ref, symbol) => ref.watch(liveQuotesProvider.select((v) => v.valueOrNull?[symbol])),
);

/// حالة التدفّق للشارة (Live / Offline / ...)
final feedStatusProvider = Provider<FeedStatus>((ref) {
  if (ref.watch(networkStatusProvider) == NetworkStatus.offline) return FeedStatus.offline;
  // بيانات من الكاش وإحنا متصلين: مش Live أبدًا
  if (ref.watch(marketServingCacheProvider)) return FeedStatus.stale;
  if (ref.watch(_tickErrorProvider)) return FeedStatus.error;
  return ref.watch(liveQuotesProvider).when(
        data: (_) => FeedStatus.live,
        loading: () => FeedStatus.connecting,
        error: (_, __) => FeedStatus.error,
      );
});

/// إغلاقات آخر 24 ساعة (شمعة ساعة) للـ sparkline
final sparklineProvider = FutureProvider.autoDispose.family<List<double>, String>((ref, symbol) async {
  // H5a: انبنى بدون اتصال (من الكاش أو فاضي) → بيتحمّل من جديد لما يرجع الاتصال
  // H5b: بالـ Low data mode بيستنّى لحد ما الـ Home يبيّن
  if (ref.read(marketCacheEnabledProvider) && ref.read(networkStatusProvider) == NetworkStatus.offline) {
    reloadWhenBackOnline(ref, tab: ShellTab.home, needed: () => true, reload: ref.invalidateSelf);
  }
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
  /// أكبر نافذة شموع (العادي، وحدّ الكاش لكل سلسلة)
  static const int limit = 300;

  @override
  Future<List<Candle>> build((String, Timeframe) arg) async {
    final (symbol, timeframe) = arg;
    // H5b: نافذة أصغر بالـ Low data mode (التبديل بيعيد التحميل بالنافذة الجديدة)
    final window = ref.watch(candleWindowProvider);
    // H5a (الكاش شغّال): انبنت بدون اتصال (من الكاش) أو فشلت → لما يرجع
    // الاتصال بتتحمّل من جديد لحالها
    if (ref.read(marketCacheEnabledProvider)) {
      final builtOffline = ref.read(networkStatusProvider) == NetworkStatus.offline;
      ref.listen<NetworkStatus>(networkStatusProvider, (previous, next) {
        if (previous == NetworkStatus.offline && next == NetworkStatus.online && (builtOffline || state.hasError)) {
          ref.invalidateSelf();
        }
      });
    }
    final candles = await ref.watch(marketDataRepositoryProvider).candles(symbol, timeframe, limit: window);
    ref.listen<Quote?>(quoteProvider(symbol), (_, quote) {
      final current = state.valueOrNull;
      if (quote == null || current == null) return;
      final merged = mergeTick(current, quote, timeframe, maxLength: window);
      if (merged == null) {
        ref.invalidateSelf(); // فجوة (التطبيق كان بالخلفية): تحميل من جديد
      } else if (!identical(merged, current)) {
        state = AsyncData(merged);
      }
    });
    return candles;
  }
}

/// H5b: كم شمعة بالرسم بالـ Low data mode
const int kLowDataCandleWindow = 120;

/// نافذة شموع الرسم: [LiveCandlesNotifier.limit] عادةً، أصغر بالـ Low data mode
final candleWindowProvider = Provider<int>(
  (ref) => ref.watch(lowDataModeProvider) ? kLowDataCandleWindow : LiveCandlesNotifier.limit,
);

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
