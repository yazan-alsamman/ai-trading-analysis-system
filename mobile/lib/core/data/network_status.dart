import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../network/connectivity_source.dart';

// ═══════════════════════════════════════════════════════════
// Network Status - حالة الاتصال
// ═══════════════════════════════════════════════════════════
//
// المصدر الوحيد لحالة الاتصال بالتطبيق - شريط "غير متصل" وأي شاشة بدها
// تعرف إذا البيانات حيّة أو آخر نسخة محفوظة بتقرأ من هون.
//
// E1: الحالة من مصدر الاتصال الحقيقي ([connectivitySourceProvider]،
// connectivity_plus). قبل أول قراءة = online (ما منحبس الشاشات بلحظة
// الإقلاع). "Simulate offline" (debug بس) بيفرض offline فوق الحالة الحقيقية.

enum NetworkStatus { online, offline }

// TODO(B12): "Simulate offline" (قسم Developer، debug بس) - بينحذف مع
// [NetworkStatusViewModel.set] قبل ما يطلع التطبيق عالـ API الحقيقي.
final simulatedOfflineProvider = StateProvider<bool>((ref) => false);

class NetworkStatusViewModel extends Notifier<NetworkStatus> {
  /// آخر حالة من الجهاز (بدون الفرض تبع debug)
  NetworkStatus _device = NetworkStatus.online;

  @override
  NetworkStatus build() {
    final source = ref.watch(connectivitySourceProvider);
    var changed = false;
    final sub = source.changes().listen(
      (status) {
        changed = true;
        _device = status;
        _publish();
      },
      // مصدر ما بيشتغل (منصة بدون plugin) = منضل على آخر حالة
      onError: (Object error) => debugPrint('NetworkStatus: connectivity stream failed: $error'),
    );
    ref.onDispose(sub.cancel);
    unawaited(source.current().then((status) {
      // تغيير وصل قبل القراءة الأولى أحدث منها
      if (changed) return;
      _device = status;
      _publish();
    }, onError: (Object error) => debugPrint('NetworkStatus: connectivity check failed: $error')));
    ref.listen<bool>(simulatedOfflineProvider, (_, __) => _publish());
    return _effective;
  }

  NetworkStatus get _effective =>
      kDebugMode && ref.read(simulatedOfflineProvider) ? NetworkStatus.offline : _device;

  void _publish() {
    final next = _effective;
    if (next != state) state = next;
  }

  // TODO(B12): "Simulate offline" (debug) والاختبارات هنن المستخدمين الوحيدين:
  // offline = فرض عدم الاتصال، online = رجوع للحالة الحقيقية تبع الجهاز.
  void set(NetworkStatus status) {
    if (!kDebugMode) return;
    ref.read(simulatedOfflineProvider.notifier).state = status == NetworkStatus.offline;
    state = _effective;
  }
}

final networkStatusProvider =
    NotifierProvider<NetworkStatusViewModel, NetworkStatus>(NetworkStatusViewModel.new);
