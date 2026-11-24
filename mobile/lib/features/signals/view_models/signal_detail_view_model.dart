import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/network_status.dart';
import '../../../core/database/cache_support.dart';
import '../../markets/data/market_providers.dart';
import '../data/caching_signals_repository.dart';
import '../data/signals_repository.dart';
import '../models/opportunity.dart';
import '../models/signal_detail.dart';
import 'signals_feed_view_model.dart';

/// ViewModel شاشة تفاصيل إشارة (instance لكل معرّف، بينحذف لما الشاشة تتسكّر).
///
/// الحالات: تحميل → [SignalDetail] (أو `expired` لما تخلص صلاحيتها) → null
/// (مش موجودة أو ما عاد فيها فرصة) → خطأ → بدون اتصال ([SignalsOfflineException]).
///
/// - جاي من القائمة: الإشارة من القائمة المحمّلة (بدون طلب، وبتشتغل بدون اتصال).
/// - غير هيك: طلب للـ repository، وبدون اتصال ما في طلب؛ بيرجع يحمّل لحالو
///   لما يرجع الاتصال.
/// - إشارة بتخلص والشاشة مفتوحة: مؤقّت على [Opportunity.validUntil] بيعلّمها
///   منتهية بدون إعادة تحميل.
/// - بعد كل `await`: إذا انعاد البناء أو انحذفت، النتيجة بتنرمى وما في مؤقّت.
class SignalDetailViewModel extends AutoDisposeFamilyAsyncNotifier<SignalDetail?, String> {
  Timer? _expiry;

  @override
  Future<SignalDetail?> build(String id) async {
    final repo = ref.watch(signalsRepositoryProvider);
    var disposed = false;
    ref.onDispose(() {
      disposed = true;
      _expiry?.cancel();
    });
    ref.listen(networkStatusProvider, (_, status) {
      if (status != NetworkStatus.online) return;
      // H5b: كمان لما المعروض نسخة محفوظة
      final saved = repo is CachingSignalsRepository && repo.savedAt[CachingSignalsRepository.itemKey(id)] != null;
      if (state.error is SignalsOfflineException || saved) ref.invalidateSelf();
    });

    final signal = _fromFeed(id) ?? await _fetch(repo, id);
    if (disposed || signal == null || !signal.isDetected) return null;

    await ref.read(instrumentsProvider.future);
    if (disposed) return null;
    final instrument = ref.read(instrumentProvider(signal.symbol));
    if (instrument == null) return null;

    final siblings = await _siblings(repo, signal.symbol, signal.methodId);
    if (disposed) return null;

    // نفس "الآن" تبع رأي النموذج بالـ Home وشاشة السوق
    final now = ref.read(simulatedMarketSourceProvider).now();
    final detail = SignalDetail.of(signal, instrument: instrument, siblings: siblings, now: now);
    if (!detail.expired) {
      _expiry = Timer(detail.validUntil.difference(now) + const Duration(milliseconds: 1), _expire);
    }
    return detail;
  }

  Future<void> retry() async {
    ref.invalidateSelf();
    await future;
  }

  void _expire() {
    final detail = state.valueOrNull;
    if (detail != null) state = AsyncData(detail.markExpired());
  }

  Future<Opportunity?> _fetch(SignalsRepository repo, String id) async {
    // H5b: فوق الكاش بدون اتصال الـ repository بيرجّع الإشارة المحفوظة
    if (repo is! CachingSignalsRepository && ref.read(networkStatusProvider) == NetworkStatus.offline) {
      throw const SignalsOfflineException();
    }
    try {
      return await repo.opportunity(id);
    } on NoSavedDataException {
      throw const SignalsOfflineException();
    }
  }

  /// باقي أطر الأداة لسبب "كم إطار متّفق" - فشلها ما بيوقّف الشاشة (السبب بيغيب)
  Future<List<Opportunity>?> _siblings(SignalsRepository repo, String symbol, String methodId) async {
    try {
      // نفس طريقة الإشارة (نفس أرقام شاشة السوق لنفس الاستراتيجية)
      return await repo.opportunities(symbol, methodId: methodId);
    } on Object {
      return null;
    }
  }

  Opportunity? _fromFeed(String id) {
    if (!ref.exists(signalsFeedViewModelProvider)) return null;
    for (final o in ref.read(signalsFeedViewModelProvider).valueOrNull ?? const <Opportunity>[]) {
      if (o.id == id) return o;
    }
    return null;
  }
}

final signalDetailViewModelProvider =
    AsyncNotifierProvider.autoDispose.family<SignalDetailViewModel, SignalDetail?, String>(SignalDetailViewModel.new);
