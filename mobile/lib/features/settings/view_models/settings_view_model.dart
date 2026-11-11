import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/network_status.dart';
import '../../../core/theme/theme_mode_provider.dart';
import '../../../providers/locale_provider.dart';
import '../../risk/data/risk_limits_repository.dart';
import '../../risk/models/risk_limits.dart';

/// كل يلي بتحتاجه شاشة Settings لترسم نفسها
@immutable
final class SettingsState {
  const SettingsState({
    required this.themeMode,
    required this.languageCode,
    required this.riskLimits,
    required this.simulatingOffline,
  });

  final ThemeMode themeMode;
  final String languageCode;
  final RiskLimits riskLimits;

  /// للتطوير بس (قسم Developer)
  final bool simulatingOffline;
}

/// ViewModel شاشة Settings: المظهر، اللغة، رأس المال والحدود، وقسم
/// Developer. الشاشة بترسم بس، وكل فعل بيمر من هون.
class SettingsViewModel extends AutoDisposeNotifier<SettingsState> {
  @override
  SettingsState build() => SettingsState(
        themeMode: ref.watch(themeModeProvider),
        languageCode: ref.watch(localeProvider).languageCode,
        riskLimits: ref.watch(riskLimitsProvider),
        simulatingOffline: ref.watch(simulatedOfflineProvider),
      );

  Future<void> setThemeMode(ThemeMode mode) => ref.read(themeModeProvider.notifier).setThemeMode(mode);

  /// تغيير اللغة - الأخبار والإشعارات بتنحمّل لحالها باللغة الجديدة
  Future<void> setLanguage(String languageCode) async {
    if (languageCode == state.languageCode) return;
    await ref.read(localeProvider.notifier).setLocale(Locale(languageCode));
  }

  Future<void> saveRiskLimits(RiskLimits limits) => ref.read(riskLimitsProvider.notifier).save(limits);

  // TODO(B12): احذف "Simulate offline" بالكامل (هالدالة، NetworkStatusViewModel.set،
  // simulatedOfflineProvider، صف Developer، مفاتيح simulateOffline*، والاختبارات)
  // قبل ما يطلع التطبيق عالـ API الحقيقي. من E1 بيفرض offline فوق مصدر
  // الاتصال الحقيقي (connectivity_plus). ممنوع يطلع بنسخة release.
  void setSimulatedOffline(bool offline) {
    if (!kDebugMode) return;
    ref.read(networkStatusProvider.notifier).set(offline ? NetworkStatus.offline : NetworkStatus.online);
  }
}

final settingsViewModelProvider = AutoDisposeNotifierProvider<SettingsViewModel, SettingsState>(SettingsViewModel.new);
