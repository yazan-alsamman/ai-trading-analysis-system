import 'package:flutter/foundation.dart';

// ═══════════════════════════════════════════════════════════
// API Config - إعدادات الاتصال بالـ backend (E1)
// ═══════════════════════════════════════════════════════════
//
// كل شي بينضبط وقت البناء بـ --dart-define، وما في ولا سر بالكود:
//   flutter run --dart-define=API_BASE_URL=https://api.example.com/api/v1
//   flutter run --dart-define=USE_REAL_API=auth,markets
// بدون API_BASE_URL العنوان وهمي واضح (نطاق .invalid ما بيوصل لأي مكان)،
// وبدون USE_REAL_API كل الميزات محاكاة.

/// كل ميزة إلها repository بخريطة الـ API (HANDOFF §6a) - الاسم هو يلي
/// بينكتب بـ USE_REAL_API
enum ApiFeature {
  auth,
  markets,
  signals,
  forecast,
  insights,
  backtest,
  signalProfile,
  workspaces,
  alerts,
  riskLimits,
  notificationPreferences,
  notifications,
  telegramLink,
  pushDevices,
  news,
  posts,
  experts,
  expertSubscriptions,
  expertChat,
  membership,
  assistant,
}

@immutable
final class ApiConfig {
  const ApiConfig({
    required this.baseUrl,
    this.connectTimeout = const Duration(seconds: 10),
    this.sendTimeout = const Duration(seconds: 20),
    this.receiveTimeout = const Duration(seconds: 20),
    this.realApi = const {},
  });

  /// عنوان وهمي واضح للتطوير - طلب عليه بيفشل كـ network (ما بيوصل لحدا)
  static const String fakeDevBaseUrl = 'https://api.trading-app.invalid/api/v1';

  /// من --dart-define (API_BASE_URL و USE_REAL_API)
  factory ApiConfig.fromEnvironment() => ApiConfig(
        baseUrl: const String.fromEnvironment('API_BASE_URL', defaultValue: fakeDevBaseUrl),
        realApi: parseRealApi(const String.fromEnvironment('USE_REAL_API')),
      );

  final String baseUrl;
  final Duration connectTimeout;
  final Duration sendTimeout;
  final Duration receiveTimeout;

  /// الميزات يلي بتستخدم الـ API الحقيقي (الباقي محاكاة) - افتراضيًا ولا وحدة
  final Set<ApiFeature> realApi;

  bool usesRealApi(ApiFeature feature) => realApi.contains(feature);

  /// "auth, markets" → {auth, markets}؛ اسم غلط بيتجاهل (مع تحذير بالـ debug)
  static Set<ApiFeature> parseRealApi(String raw) {
    final result = <ApiFeature>{};
    for (final part in raw.split(',')) {
      final name = part.trim();
      if (name.isEmpty) continue;
      final feature = ApiFeature.values.where((f) => f.name == name).firstOrNull;
      if (feature == null) {
        debugPrint('ApiConfig: unknown USE_REAL_API feature "$name" ignored');
      } else {
        result.add(feature);
      }
    }
    return result;
  }
}
