import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../providers/app_providers.dart';
import 'api_client.dart';
import 'api_config.dart';
import 'auth_interceptor.dart';
import 'latency_interceptor.dart';
import '../data/low_data_mode.dart';
import 'token_store.dart';

// ═══════════════════════════════════════════════════════════
// Network Providers (E1)
// ═══════════════════════════════════════════════════════════

/// الإعدادات من --dart-define (الاختبارات بتعمل override)
final apiConfigProvider = Provider<ApiConfig>((ref) => ApiConfig.fromEnvironment());

/// نقطة التبديل لكل ميزة: الـ API الحقيقي ولا المحاكاة (USE_REAL_API)
final useRealApiProvider = Provider.family<bool, ApiFeature>(
  (ref, feature) => ref.watch(apiConfigProvider).usesRealApi(feature),
);

/// الـ access + refresh tokens بالتخزين الآمن
final tokenStoreProvider = Provider<TokenStore>((ref) => TokenStore(ref.watch(secureStorageServiceProvider)));

/// للاختبارات بس: adapter وهمي بدل الشبكة (null = الشبكة الحقيقية)
final apiHttpAdapterProvider = Provider<HttpClientAdapter?>((ref) => null);

/// العميل الوحيد للـ backend: token عكل طلب، refresh مرة وحدة عند 401،
/// وإذا الـ refresh انرفض → AuthController.endSession (Welcome، الجلسة انمسحت)
final apiClientProvider = Provider<ApiClient>((ref) {
  final client = ApiClient(config: ref.watch(apiConfigProvider), adapter: ref.watch(apiHttpAdapterProvider));
  client.dio.interceptors.add(AuthInterceptor(
    dio: client.dio,
    tokens: ref.watch(tokenStoreProvider),
    onSessionExpired: () => ref.read(authControllerProvider).endSession(),
  ));
  // H5b: مدة كل طلب → اقتراح الـ Low data mode على اتصال بطيء
  client.dio.interceptors.add(LatencyInterceptor(ref.read(slowConnectionProvider.notifier).record));
  ref.onDispose(client.close);
  return client;
});

/// المكان الوحيد بكل ملف providers يلي بيختار المصدر:
///
///   final alertsRepositoryProvider = Provider<AlertsRepository>((ref) => apiSource(
///         ref, ApiFeature.alerts,
///         simulated: () => InMemoryAlertsRepository(),
///         // real: () => ApiAlertsRepository(ref.watch(apiClientProvider)),  ← مرحلة الربط
///       ));
///
/// ميزة مفعّلة بـ USE_REAL_API وما إلها [real] لسّا → بتضل محاكاة (مع تحذير).
T apiSource<T>(Ref ref, ApiFeature feature, {required T Function() simulated, T Function()? real}) {
  if (!ref.watch(useRealApiProvider(feature))) return simulated();
  if (real == null) {
    debugPrint('apiSource: ${feature.name} has no real repository yet, using the simulated one');
    return simulated();
  }
  return real();
}
