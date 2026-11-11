import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/data/json.dart';
import '../../../core/storage/preferences_provider.dart';
import '../models/signal_profile.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';

/// مصدر "Strategy" - بيتبدّل بتنفيذ API (تفضيلات الحساب) بعدين.
///
/// الاستراتيجية المحفوظة بتضل فعّالة لحد ما المستخدم يشيلها ([clear])؛ ما في
/// شي بيمسحها لحالو (لا تبديل تبويب ولا اتصال ولا تحديث ولا إعادة تشغيل).
abstract interface class SignalProfileRepository {
  /// المحفوظة، أو [SignalProfile.defaults] لما ما في شي محفوظ
  SignalProfile read();

  Future<void> save(SignalProfile profile);

  /// "Remove strategy": بيشيل المحفوظة (الافتراضي بيرجع).
  /// API: `DELETE /me/strategies/{id}` (أقرب شي بالـ backend، الربط مش متأكد منه).
  /// TODO(API): لسّا ما في endpoint واضح للفلتر (`/me/strategies` أو `/me/signal-plans`).
  Future<void> clear();
}

/// محفوظ على الجهاز لحد ما ينربط الحساب
final class LocalSignalProfileRepository implements SignalProfileRepository {
  const LocalSignalProfileRepository(this.prefs);

  static const storageKey = 'signal_profile';

  final SharedPreferences prefs;

  @override
  SignalProfile read() {
    final raw = prefs.getString(storageKey);
    if (raw == null) return SignalProfile.defaults;
    try {
      final json = Json.from(jsonDecode(raw));
      return json == null ? SignalProfile.defaults : SignalProfile.fromJson(json);
    } on FormatException {
      return SignalProfile.defaults;
    }
  }

  @override
  Future<void> save(SignalProfile profile) => prefs.setString(storageKey, jsonEncode(profile.toJson()));

  @override
  Future<void> clear() => prefs.remove(storageKey);
}

final signalProfileRepositoryProvider = Provider<SignalProfileRepository>(
  (ref) => apiSource(
    ref,
    ApiFeature.signalProfile,
    simulated: () => LocalSignalProfileRepository(ref.watch(sharedPreferencesProvider)),
  ),
);

/// الاستراتيجية المحفوظة - الـ sheet بتعدّل نسخة محلية وبتحفظ هون مرة وحدة.
///
/// مش autoDispose: بتضل طول عمر التطبيق، وكل يلي بيقراها (قائمة Signals،
/// البطاقة، Backtest) بيعمل watch فبيتحدّث فورًا مع الحفظ والإزالة.
class SignalProfileNotifier extends Notifier<SignalProfile> {
  @override
  SignalProfile build() => ref.watch(signalProfileRepositoryProvider).read();

  /// حفظ نفس الافتراضي = ما في استراتيجية خاصة (بينشال المحفوظ)
  Future<void> save(SignalProfile profile) async {
    if (!profile.isValid) throw ArgumentError.value(profile, 'profile', 'invalid signal profile');
    final repo = ref.read(signalProfileRepositoryProvider);
    await (profile == SignalProfile.defaults ? repo.clear() : repo.save(profile));
    state = profile;
  }

  /// "Remove strategy": بيرجّع الافتراضي، وبيرجّع المحذوفة لزر Undo ([save])
  Future<SignalProfile> remove() async {
    final previous = state;
    await ref.read(signalProfileRepositoryProvider).clear();
    state = SignalProfile.defaults;
    return previous;
  }
}

final signalProfileProvider = NotifierProvider<SignalProfileNotifier, SignalProfile>(SignalProfileNotifier.new);

/// في استراتيجية خاصة محفوظة؟ (البطاقة، زر "Remove strategy"، Backtest)
final hasCustomStrategyProvider = Provider<bool>((ref) => ref.watch(signalProfileProvider) != SignalProfile.defaults);
