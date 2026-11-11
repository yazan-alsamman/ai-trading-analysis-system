import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';

/// تسجيل الجهاز لإشعارات Push (H4b). التطبيق بيبعت token الجهاز مرة وحدة لكل
/// token؛ بدون اتصال بيضل "pending" وبينبعت لما يرجع الاتصال.
abstract interface class PushDeviceRepository {
  /// API (مقترح): `POST /me/devices` → body `{token, platform: android|ios}`.
  /// TODO(API): المسار، وهل `DELETE /me/devices/{token}` عند تسجيل الخروج أو
  /// إطفاء Push (سؤال مفتوح لصاحب الـ backend). خطوة الـ FCM بتجيب الـ token الحقيقي.
  Future<void> registerDeviceToken(String token);
}

/// محاكاة: بتسجّل الطلبات بالذاكرة بس (ما في شبكة)
class SimulatedPushDeviceRepository implements PushDeviceRepository {
  SimulatedPushDeviceRepository({this.latency = Duration.zero});

  final Duration latency;

  /// كل token انبعت (للاختبارات: مرة وحدة لكل token)
  final registered = <String>[];

  @override
  Future<void> registerDeviceToken(String token) async {
    if (latency > Duration.zero) await Future<void>.delayed(latency);
    registered.add(token);
  }
}

final pushDeviceRepositoryProvider = Provider<PushDeviceRepository>(
  (ref) => apiSource(
    ref,
    ApiFeature.pushDevices,
    simulated: () => SimulatedPushDeviceRepository(latency: const Duration(milliseconds: 300)),
  ),
);
