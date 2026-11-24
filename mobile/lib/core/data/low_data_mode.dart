import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../app/shell/shell_tab.dart';
import '../network/connectivity_source.dart';
import '../storage/preferences_provider.dart';
import 'network_status.dart';

// ═══════════════════════════════════════════════════════════
// Low data mode (H5b، ميزة 17)
// ═══════════════════════════════════════════════════════════
//
// إعداد بـ Settings (مطفي بالافتراضي، بينحفظ). شغّال:
// - الأسعار بتتحدّث مرة كل [kLowDataQuoteInterval] (مش مع كل نبضة)
// - ما في حركة للرسم (ولا sparkline)
// - الصور بتنفك بحجم أصغر ([lowDataImageScaleProvider])
// - التبويبات المخفية ما بتتحدّث لحالها ([reloadWhenBackOnline])
// - شموع الرسم أقل (نافذة أصغر) والتوقّع بيتحدّث بس عند سكرة شمعته
// ما في شي بيختفي بدون ما نقول: شارة "Low data mode" بالـ Home وشاشة السوق.
// الاقتراح (بيانات جوال أو اتصال بطيء) banner بينسكّر، وما بيشغّل الوضع أبدًا لحالو.

const String kLowDataModeKey = 'low_data_mode';
const String kLowDataSuggestionDismissedKey = 'low_data_suggestion_dismissed';

/// تحديث سعر واحد كل 5 ثواني بالـ Low data mode
const Duration kLowDataQuoteInterval = Duration(seconds: 5);

/// نسبة حجم فك الصور بالـ Low data mode
const double kLowDataImageScale = 0.5;

/// طلب API أبطأ من هيك = "بطيء"؛ [kSlowSamples] طلبات بطيئة ورا بعض = اتصال بطيء
const Duration kSlowRequest = Duration(milliseconds: 2500);
const int kSlowSamples = 3;

/// التخزين، أو null إذا مش متاح (container بدون SharedPreferences = الوضع مطفي)
SharedPreferences? _prefs(Ref ref) {
  try {
    return ref.watch(sharedPreferencesProvider);
  } on Object {
    return null;
  }
}

class LowDataModeNotifier extends Notifier<bool> {
  @override
  bool build() => _prefs(ref)?.getBool(kLowDataModeKey) ?? false;

  /// بينحفظ؛ الإطفاء بيرجّع السلوك العادي فورًا (كل شي بيقرأ هالـ provider)
  Future<void> set(bool on) async {
    if (state == on) return;
    state = on;
    await _prefs(ref)?.setBool(kLowDataModeKey, on);
  }
}

final lowDataModeProvider = NotifierProvider<LowDataModeNotifier, bool>(LowDataModeNotifier.new);

/// أقل مدة بين تحديثين للأسعار على الشاشة (صفر = كل نبضة)
final quoteUpdateIntervalProvider = Provider<Duration>(
  (ref) => ref.watch(lowDataModeProvider) ? kLowDataQuoteInterval : Duration.zero,
);

/// مضاعف حجم فك الصور (1 = عادي)
final lowDataImageScaleProvider = Provider<double>((ref) => ref.watch(lowDataModeProvider) ? kLowDataImageScale : 1);

/// حجم فك صورة بالبكسل لعرض [logical] بكثافة [devicePixelRatio] (أصغر بالـ Low data mode)
int imageDecodeSize(double logical, double devicePixelRatio, double scale) =>
    (logical * devicePixelRatio * scale).round().clamp(1, 1 << 14);

// ── التبويب الظاهر ──────────────────────────────────────────

/// تبويب الـ shell الظاهر هلق (الـ AppShell بيحدّثه)
final currentShellTabProvider = StateProvider<ShellTab>((ref) => ShellTab.home);

/// رجع الاتصال → [reload] إذا [needed]. بالـ Low data mode والتبويب [tab]
/// مخفي: بيستنّى لحد ما التبويب يبيّن (أو الوضع ينطفي) بدل ما يحمّل بالخلفية.
void reloadWhenBackOnline(
  Ref ref, {
  required ShellTab tab,
  required bool Function() needed,
  required void Function() reload,
}) {
  var pending = false;
  bool visible() => ref.read(currentShellTabProvider) == tab;

  void runIfPending() {
    if (!pending || ref.read(networkStatusProvider) != NetworkStatus.online) return;
    if (ref.read(lowDataModeProvider) && !visible()) return;
    pending = false;
    reload();
  }

  ref.listen<NetworkStatus>(networkStatusProvider, (previous, next) {
    if (next != NetworkStatus.online || !needed()) return;
    pending = true;
    runIfPending();
  });
  ref.listen<ShellTab>(currentShellTabProvider, (_, __) => runIfPending());
  ref.listen<bool>(lowDataModeProvider, (_, __) => runIfPending());
}

// ── اقتراح الوضع ───────────────────────────────────────────

/// ليش منقترح الوضع
enum LowDataReason { mobileData, slowConnection }

/// الجهاز على بيانات الجوال (من مصدر الاتصال إذا بيعرف؛ غير هيك false)
class MobileDataNotifier extends Notifier<bool> {
  @override
  bool build() {
    final source = ref.watch(connectivitySourceProvider);
    if (source is! ConnectionTypeSource) return false;
    final typed = source as ConnectionTypeSource;
    var changed = false;
    final sub = typed.mobileDataChanges().listen(
      (mobile) {
        changed = true;
        state = mobile;
      },
      onError: (Object error) => debugPrint('MobileData: stream failed: $error'),
    );
    ref.onDispose(sub.cancel);
    unawaited(typed.isMobileData().then((mobile) {
      if (!changed) state = mobile;
    }, onError: (Object error) => debugPrint('MobileData: check failed: $error')));
    return false;
  }
}

final mobileDataProvider = NotifierProvider<MobileDataNotifier, bool>(MobileDataNotifier.new);

/// اتصال بطيء: آخر [kSlowSamples] طلبات API كلها أبطأ من [kSlowRequest]
/// (`LatencyInterceptor` بيسجّل كل طلب)
class SlowConnectionNotifier extends Notifier<bool> {
  final List<Duration> _samples = [];

  @override
  bool build() => false;

  void record(Duration elapsed) {
    _samples.add(elapsed);
    if (_samples.length > kSlowSamples) _samples.removeAt(0);
    final slow = _samples.length == kSlowSamples && _samples.every((d) => d >= kSlowRequest);
    if (slow != state) state = slow;
  }
}

final slowConnectionProvider = NotifierProvider<SlowConnectionNotifier, bool>(SlowConnectionNotifier.new);

/// المستخدم سكّر الاقتراح (بينحفظ: ما منرجع نلحّ)
class LowDataSuggestionDismissedNotifier extends Notifier<bool> {
  @override
  bool build() => _prefs(ref)?.getBool(kLowDataSuggestionDismissedKey) ?? false;

  Future<void> dismiss() async {
    state = true;
    await _prefs(ref)?.setBool(kLowDataSuggestionDismissedKey, true);
  }
}

final lowDataSuggestionDismissedProvider =
    NotifierProvider<LowDataSuggestionDismissedNotifier, bool>(LowDataSuggestionDismissedNotifier.new);

/// null = ما في اقتراح (الوضع شغّال، بدون اتصال، انسكّر، أو الاتصال منيح)
final lowDataSuggestionProvider = Provider<LowDataReason?>((ref) {
  if (ref.watch(lowDataModeProvider)) return null;
  if (ref.watch(networkStatusProvider) == NetworkStatus.offline) return null;
  if (ref.watch(lowDataSuggestionDismissedProvider)) return null;
  if (ref.watch(slowConnectionProvider)) return LowDataReason.slowConnection;
  if (ref.watch(mobileDataProvider)) return LowDataReason.mobileData;
  return null;
});
