import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/data/json.dart';
import '../../../core/storage/preferences_provider.dart';
import '../models/risk_limits.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';

/// مصدر رأس المال والحدود - بيتبدّل بتنفيذ API (إعدادات الحساب) بعدين
abstract interface class RiskLimitsRepository {
  /// متزامن حتى القيمة المحفوظة تطلع من أول فريم
  RiskLimits read();

  Future<void> save(RiskLimits limits);
}

/// محفوظ على الجهاز (SharedPreferences) لحد ما ينربط الحساب
final class LocalRiskLimitsRepository implements RiskLimitsRepository {
  const LocalRiskLimitsRepository(this.prefs);

  static const storageKey = 'risk_limits';

  final SharedPreferences prefs;

  @override
  RiskLimits read() {
    final raw = prefs.getString(storageKey);
    if (raw == null) return RiskLimits.defaults;
    try {
      final json = Json.from(jsonDecode(raw));
      return json == null ? RiskLimits.defaults : RiskLimits.fromJson(json);
    } on FormatException {
      return RiskLimits.defaults;
    }
  }

  @override
  Future<void> save(RiskLimits limits) => prefs.setString(storageKey, jsonEncode(limits.toJson()));
}

final riskLimitsRepositoryProvider = Provider<RiskLimitsRepository>(
  (ref) => apiSource(
    ref,
    ApiFeature.riskLimits,
    simulated: () => LocalRiskLimitsRepository(ref.watch(sharedPreferencesProvider)),
  ),
);

/// الحدود الحالية - Settings بتعدّلها، وحساب الحجم بيقرأ منها
class RiskLimitsNotifier extends Notifier<RiskLimits> {
  @override
  RiskLimits build() => ref.watch(riskLimitsRepositoryProvider).read();

  /// بيرمي [ArgumentError] لو القيم مش صالحة (الـ sheet بتتحقق قبل)
  Future<void> save(RiskLimits limits) async {
    if (validateRiskLimits(limits).isNotEmpty) {
      throw ArgumentError.value(limits, 'limits', 'invalid risk limits');
    }
    await ref.read(riskLimitsRepositoryProvider).save(limits);
    state = limits;
  }
}

final riskLimitsProvider = NotifierProvider<RiskLimitsNotifier, RiskLimits>(RiskLimitsNotifier.new);
