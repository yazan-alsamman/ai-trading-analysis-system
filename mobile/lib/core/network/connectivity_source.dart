import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/network_status.dart';

// ═══════════════════════════════════════════════════════════
// Connectivity Source - مصدر حالة الاتصال الحقيقي (E1، بدل "Simulate offline")
// ═══════════════════════════════════════════════════════════
//
// networkStatusProvider بيقرأ من هون. الجهاز بدون أي شبكة (none / قائمة
// فاضية) = offline؛ أي شبكة (wifi، mobile، ethernet، vpn...) = online.
// ملاحظة: شبكة بدون إنترنت بتبيّن online هون، والطلب نفسه بيفشل كـ
// ApiException(network) → حالة الـ offline تبع الشاشة (`offlineAs`).

abstract interface class ConnectivitySource {
  Future<NetworkStatus> current();

  Stream<NetworkStatus> changes();
}

/// نتيجة connectivity_plus → حالتنا
@visibleForTesting
NetworkStatus networkStatusFrom(List<ConnectivityResult> results) =>
    results.any((r) => r != ConnectivityResult.none) ? NetworkStatus.online : NetworkStatus.offline;

final class DeviceConnectivitySource implements ConnectivitySource {
  DeviceConnectivitySource([Connectivity? connectivity]) : _connectivity = connectivity ?? Connectivity();

  final Connectivity _connectivity;

  @override
  Future<NetworkStatus> current() async => networkStatusFrom(await _connectivity.checkConnectivity());

  @override
  Stream<NetworkStatus> changes() => _connectivity.onConnectivityChanged.map(networkStatusFrom).distinct();
}

final connectivitySourceProvider = Provider<ConnectivitySource>((ref) => DeviceConnectivitySource());
