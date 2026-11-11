import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../storage/preferences_provider.dart';

// ═══════════════════════════════════════════════════════════
// Theme Mode - فاتح / داكن / حسب النظام
// ═══════════════════════════════════════════════════════════
//
// الاختيار محفوظ بـ SharedPreferences (مش secure storage - ما في شي سري
// هون)، وبينقرأ متزامن من [sharedPreferencesProvider] فالثيم الصح بيطلع
// من أول فريم.

const themeModeStorageKey = 'app_theme_mode';

class ThemeModeNotifier extends Notifier<ThemeMode> {
  @override
  ThemeMode build() {
    final saved = ref.watch(sharedPreferencesProvider).getString(themeModeStorageKey);
    return ThemeMode.values.firstWhere(
      (mode) => mode.name == saved,
      orElse: () => ThemeMode.system,
    );
  }

  Future<void> setThemeMode(ThemeMode mode) async {
    if (mode == state) return;
    state = mode;
    await ref.read(sharedPreferencesProvider).setString(themeModeStorageKey, mode.name);
  }
}

final themeModeProvider =
    NotifierProvider<ThemeModeNotifier, ThemeMode>(ThemeModeNotifier.new);
