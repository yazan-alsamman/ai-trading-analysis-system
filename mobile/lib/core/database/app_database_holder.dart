import 'dart:async';
import 'dart:io';

import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

import 'app_database.dart';

// ═══════════════════════════════════════════════════════════
// AppDatabaseHolder - فتح كسول + إصلاح ذاتي للكاش
// ═══════════════════════════════════════════════════════════
//
// - بينفتح أول مرة حدا بيحتاجه ([run])، مش وقت الإقلاع.
// - SQLite بـ isolate بالخلفية ([NativeDatabase.createInBackground]) فالكتابة
//   والتقليم ما بيوقّفوا الواجهة.
// - ملف مضروب / مش قاعدة بيانات / فحص فشل → بيتسكّر، بينمسح، وبينعمل من
//   جديد (مرة وحدة لكل عملية). إذا حتى هيك ما زبط → الكاش بيتعطّل لهالجلسة
//   ([CacheUnavailableException]) والتطبيق بيكمل بدونه. ما في crash أبدًا.
// - [close] من الـ provider (onDispose).

/// الكاش مش متاح هالجلسة (حتى بعد إعادة البناء)
final class CacheUnavailableException implements Exception {
  const CacheUnavailableException(this.cause);

  final Object cause;

  @override
  String toString() => 'CacheUnavailableException($cause)';
}

/// فحص السلامة رجّع شي غير "ok"
final class CorruptDatabaseException implements Exception {
  const CorruptDatabaseException(this.detail);

  final String detail;

  @override
  String toString() => 'CorruptDatabaseException($detail)';
}

/// SQLITE_CORRUPT (11) و SQLITE_NOTADB (26) - كمان لما الخطأ جاي من isolate الخلفية
bool isCorruptionError(Object error) {
  if (error is CorruptDatabaseException) return true;
  if (error is SqliteException) {
    final code = error.resultCode & 0xff;
    return code == 11 || code == 26;
  }
  // من isolate الخلفية الخطأ بيوصل ملفوف (DriftRemoteException) بنصّه الأصلي
  final text = '$error'.toLowerCase();
  return text.contains('malformed') || text.contains('not a database');
}

class AppDatabaseHolder {
  AppDatabaseHolder({required this.open, this.deleteStorage});

  /// ملف حقيقي بمجلد دعم التطبيق (SQLite بالخلفية)
  factory AppDatabaseHolder.file({String fileName = 'app_cache.sqlite'}) {
    Future<File> file() async {
      final dir = await getApplicationSupportDirectory();
      return File('${dir.path}${Platform.pathSeparator}$fileName');
    }

    return AppDatabaseHolder(
      open: () => AppDatabase(LazyDatabase(() async => NativeDatabase.createInBackground(await file()))),
      deleteStorage: () async {
        final f = await file();
        for (final suffix in const ['', '-wal', '-shm', '-journal']) {
          final part = File('${f.path}$suffix');
          if (await part.exists()) await part.delete();
        }
      },
    );
  }

  /// بالذاكرة (الاختبارات) - "المسح" = قاعدة جديدة فاضية
  factory AppDatabaseHolder.memory() => AppDatabaseHolder(open: () => AppDatabase(NativeDatabase.memory()));

  final AppDatabase Function() open;

  /// بيمسح الملفات قبل إعادة البناء (null = بالذاكرة، ما في شي ينمسح)
  final Future<void> Function()? deleteStorage;

  Future<AppDatabase>? _ready;
  bool _closed = false;
  bool _broken = false;

  /// كم مرة انعادت القاعدة من جديد بسبب ملف مضروب (للاختبارات والـ logs)
  int recoveries = 0;

  /// بيفتح القاعدة (إذا لسّا) وبينفّذ [action]؛ ملف مضروب → إعادة بناء ومحاولة وحدة كمان
  Future<T> run<T>(Future<T> Function(AppDatabase db) action) async {
    if (_closed) throw const CacheUnavailableException('closed');
    if (_broken) throw const CacheUnavailableException('disabled for this session');
    try {
      return await action(await (_ready ??= _openChecked()));
    } catch (error) {
      if (!isCorruptionError(error)) rethrow;
      debugPrint('AppDatabase: corrupted cache ($error), recreating');
      try {
        await _recreate();
        return await action(await _ready!);
      } catch (second) {
        _broken = true;
        await _closeCurrent();
        throw CacheUnavailableException(second);
      }
    }
  }

  Future<AppDatabase> _openChecked() async {
    final db = open();
    try {
      // أول استعلام بيفتح الملف وبيشغّل الترحيلات؛ quick_check بيلقط الصفحات المضروبة
      final rows = await db.customSelect('PRAGMA quick_check(1)').get();
      final result = rows.isEmpty ? '' : '${rows.first.data.values.first}';
      if (result != 'ok') throw CorruptDatabaseException(result);
      return db;
    } catch (_) {
      await _safeClose(db);
      _ready = null;
      rethrow;
    }
  }

  Future<void> _recreate() async {
    recoveries++;
    await _closeCurrent();
    await deleteStorage?.call();
    _ready = _openChecked();
    await _ready;
  }

  Future<void> _closeCurrent() async {
    final current = _ready;
    _ready = null;
    if (current == null) return;
    try {
      await _safeClose(await current);
    } catch (_) {
      // فتح فشل أصلًا - ما في شي ينسكّر
    }
  }

  static Future<void> _safeClose(AppDatabase db) async {
    try {
      await db.close();
    } catch (error) {
      debugPrint('AppDatabase: close failed: $error');
    }
  }

  Future<void> close() async {
    if (_closed) return;
    _closed = true;
    await _closeCurrent();
  }
}
