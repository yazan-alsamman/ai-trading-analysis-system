import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../features/alerts/data/alerts_repository.dart';
import '../../features/auth/auth_state.dart';
import '../../features/community/data/expert_subscriptions_repository.dart';
import '../../features/notifications/data/notifications_repository.dart';
import '../../features/notifications/data/telegram_link_repository.dart';
import '../../features/signals/data/signal_profile_repository.dart';
import '../../features/workspaces/data/workspaces_repository.dart';
import '../storage/preferences_provider.dart';
import 'database_providers.dart';

/// H5b: صاحب الصفوف الخاصة بمستخدم بالكاش (معرّف الحساب الداخل، `''` = ما
/// في حدا داخل = ما في حفظ ولا قراءة لشي خاص). الـ decorators بيعيدوا البناء
/// لما يتغيّر، فحساب تاني ما بيشوف ولا صف من الأول.
final cacheOwnerProvider = Provider<String>((ref) {
  try {
    return switch (ref.watch(authStateProvider)) {
      SignedIn(:final user) => user.id,
      SignedOut() => '',
    };
  } on Object {
    // container بدون جلسة (اختبارات بدون تخزين) = ما في حدا داخل
    return '';
  }
});

/// H5c: بيمسح الصفوف الخاصة بالمستخدم (قائمة Signals والمطلوبة، الإشعارات).
/// `TradingApp` بيبقيه شغّال.
/// - طلع (تسجيل خروج أو نهاية الجلسة): كل الصفوف الخاصة.
/// - حساب داخل (أول قراءة بعد الإقلاع، دخول بعد خروج، أو حساب تاني بدون
///   خروج نظيف): كل صف مش إلو.
/// - `''` بأول الإقلاع (الجلسة لسّا عم تنقرأ) ما بيمسح شي.
final userCacheGuardProvider = Provider<void>((ref) {
  ref.listen<String>(
    cacheOwnerProvider,
    (previous, next) {
      // قبل ما الـ providers (يلي بتراقب الحساب) تنبنى من جديد: متزامن
      scopeAccountPrefs(ref, previous: previous, next: next);
      if (next.isNotEmpty) {
        unawaited(clearUserCache(ref, keep: next));
      } else if (previous != null && previous.isNotEmpty) {
        unawaited(clearUserCache(ref));
      }
    },
    fireImmediately: true,
  );
});

/// H5d: بيانات محلية لكل حساب (الجهاز بيحتفظ بنسخة الحساب الداخل بس؛ مع
/// الـ API بترجع من الخادم): الاستراتيجية، مساحات العمل، التنبيهات وإشعاراتها،
/// اشتراكات الخبراء، ربط Telegram. حدّ المساعد اليومي أصلًا بمفتاح المستخدم.
/// الإعدادات (الثيم، اللغة، حدود المخاطرة، تفضيلات الإشعارات، Low data) للجهاز.
const List<String> kAccountPrefsKeys = [
  LocalSignalProfileRepository.storageKey,
  LocalWorkspacesRepository.storageKey,
  LocalWorkspacesRepository.activeKey,
  LocalAlertsRepository.storageKey,
  SimulatedNotificationsRepository.alertsStorageKey,
  LocalExpertSubscriptionsRepository.storageKey,
  SimulatedTelegramLinkRepository.storageKey,
];

/// لمين البيانات المحلية بـ [kAccountPrefsKeys]
const String kAccountPrefsOwnerKey = 'account_prefs_owner';

/// خروج = بتنمسح؛ دخول حساب تاني غير صاحبها = بتنمسح؛ ما إلها صاحب (قبل H5d)
/// = بتصير للحساب الداخل. متزامن (ذاكرة SharedPreferences بتتحدّث فورًا).
void scopeAccountPrefs(Ref ref, {required String? previous, required String next}) {
  final SharedPreferences prefs;
  try {
    prefs = ref.read(sharedPreferencesProvider);
  } on Object {
    return;
  }
  void clear() {
    for (final key in kAccountPrefsKeys) {
      unawaited(prefs.remove(key));
    }
  }

  if (next.isEmpty) {
    if (previous == null || previous.isEmpty) return;
    clear();
    unawaited(prefs.remove(kAccountPrefsOwnerKey));
    return;
  }
  final owner = prefs.getString(kAccountPrefsOwnerKey);
  if (owner != null && owner != next) clear();
  if (owner != next) unawaited(prefs.setString(kAccountPrefsOwnerKey, next));
}

/// بيمسح الصفوف الخاصة بالمستخدمين (غير [keep]) - خطأ كاش بينبلع: القراءة
/// أصلًا بمعرّف الحساب
Future<void> clearUserCache(Ref ref, {String? keep}) async {
  try {
    await ref.read(appDatabaseProvider).run((db) => db.clearUserRows(keep: keep));
  } catch (error) {
    debugPrint('UserCacheGuard: clear failed: $error');
  }
}

/// H5c: الحساب لسّا [owner]؟ (كتابة متأخرة: جواب وصل بعد الخروج ما بينحفظ)
bool Function() ownerStillCurrent(Ref ref, String owner) => () {
      try {
        return ref.read(cacheOwnerProvider) == owner;
      } on Object {
        return false;
      }
    };
