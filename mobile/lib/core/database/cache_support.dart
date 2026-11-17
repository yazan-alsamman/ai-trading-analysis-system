import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app_database.dart';

// ═══════════════════════════════════════════════════════════
// Cache support (H5b) - نفس نمط H5a (decorator فوق المصدر) لباقي الميزات
// ═══════════════════════════════════════════════════════════
//
// - [NoSavedDataException]: بدون اتصال وما في نسخة محفوظة (الشاشة بتبيّن حالة
//   الـ offline بسببها، وبترجع تحمّل لحالها لما يرجع الاتصال).
// - [SavedAtTracker]: لكل طلب انخدم من الكاش وقت حفظه ("Last updated")؛
//   انخدم من المصدر = بينشال (البيانات حيّة).
// - [BackgroundCacheWrites]: الكتابة بالخلفية وأي خطأ كاش بينبلع (الكاش ما
//   بيوقّف شاشة أبدًا)، متل `CachingMarketDataRepository`.

/// بدون اتصال وما في شي محفوظ لهالطلب
final class NoSavedDataException implements Exception {
  const NoSavedDataException();

  @override
  String toString() => 'NoSavedDataException';
}

/// مفتاح [CacheMeta] خاص بمستخدم (بينمسح مع تسجيل الخروج)
String userMetaKey(String owner, String key) => '$kUserMetaPrefix$owner:$key';

/// مفتاح طلب → وقت حفظ النسخة المعروضة (بس للي انخدم من الكاش)
class SavedAtTracker extends ValueNotifier<Map<String, DateTime>> {
  SavedAtTracker() : super(const {});

  DateTime? operator [](String key) => value[key];

  /// انخدموا من الكاش (نسخة محفوظة بـ [at])
  void served(Iterable<String> keys, DateTime at) {
    final next = {...value};
    var changed = false;
    for (final key in keys) {
      if (next[key] == at) continue;
      next[key] = at;
      changed = true;
    }
    if (changed) value = next;
  }

  /// انخدموا من المصدر (حيّين)
  void live(Iterable<String> keys) {
    if (!keys.any(value.containsKey)) return;
    value = {...value}..removeWhere((key, _) => keys.contains(key));
  }
}

/// provider بيقرأ وقت حفظ [key] من [tracker] وبيتحدّث لما يتغيّر
DateTime? watchSavedAt(Ref ref, SavedAtTracker? tracker, String key) {
  if (tracker == null) return null;
  void changed() => ref.invalidateSelf();
  tracker.addListener(changed);
  ref.onDispose(() => tracker.removeListener(changed));
  return tracker[key];
}

/// كتابات الكاش بالخلفية (ما منستناها) + قراءات ما بترمي
mixin BackgroundCacheWrites {
  final Set<Future<void>> _writes = {};

  String get cacheLabel;

  void writeInBackground(Future<void> Function() write) {
    late final Future<void> future;
    future = Future(write).catchError((Object error) {
      debugPrint('$cacheLabel: write failed: $error');
    }).whenComplete(() => _writes.remove(future));
    _writes.add(future);
  }

  /// بيستنّى كل الكتابات الحالية (الاختبارات + قبل المسح)
  Future<void> flushWrites() async {
    while (_writes.isNotEmpty) {
      await Future.wait(_writes.toList());
    }
  }

  Future<T?> readSafely<T>(Future<T?> Function() read) async {
    try {
      return await read();
    } catch (error) {
      debugPrint('$cacheLabel: read failed: $error');
      return null;
    }
  }
}
