import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

// ═══════════════════════════════════════════════════════════
// Locale Provider - إدارة لغة التطبيق (عربي / إنجليزي)
// ═══════════════════════════════════════════════════════════
//
// Notifier بسيط بيحمل الـ [Locale] الحالية، وبيحفظها محليًا (نفس
// طريقة SecureStorageService) حتى تضل محفوظة بعد إغلاق التطبيق
// وإعادة فتحه. القيمة الافتراضية عند أول تشغيل هي لغة نظام الجهاز
// (لو مدعومة)، وإلا الإنجليزية.

const _localeStorageKey = 'app_locale';
const _supportedLanguageCodes = ['en', 'ar'];

class LocaleNotifier extends StateNotifier<Locale> {
  LocaleNotifier() : super(const Locale('en')) {
    _loadSavedLocale();
  }

  final _storage = const FlutterSecureStorage();

  Future<void> _loadSavedLocale() async {
    final saved = await _storage.read(key: _localeStorageKey);
    if (saved != null && _supportedLanguageCodes.contains(saved)) {
      state = Locale(saved);
      return;
    }

    // لا توجد لغة محفوظة سابقًا - استخدم لغة نظام الجهاز لو مدعومة
    final deviceLanguageCode =
        WidgetsBinding.instance.platformDispatcher.locale.languageCode;
    if (_supportedLanguageCodes.contains(deviceLanguageCode)) {
      state = Locale(deviceLanguageCode);
    }
  }

  /// تغيير لغة التطبيق وحفظها محليًا
  Future<void> setLocale(Locale locale) async {
    if (!_supportedLanguageCodes.contains(locale.languageCode)) return;
    state = locale;
    await _storage.write(key: _localeStorageKey, value: locale.languageCode);
  }
}

final localeProvider = StateNotifierProvider<LocaleNotifier, Locale>(
  (ref) => LocaleNotifier(),
);
