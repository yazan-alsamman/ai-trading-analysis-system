import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// الـ SharedPreferences بتنقرأ مرة وحدة بـ main() قبل runApp وبتنمرّر
/// عبر override هون - هيك أي ViewModel بيقرأ قيمته المحفوظة من أول فريم
/// (بدون "وميض" بالقيمة الافتراضية).
///
/// لازم ينعمل إلو override بـ main() وبالاختبارات.
final sharedPreferencesProvider = Provider<SharedPreferences>(
  (ref) => throw UnimplementedError(
    'sharedPreferencesProvider must be overridden in ProviderScope',
  ),
);
