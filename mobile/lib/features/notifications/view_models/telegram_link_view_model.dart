import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/network_status.dart';
import '../data/notification_preferences_repository.dart';
import '../data/telegram_link_repository.dart';
import '../models/notification_preferences.dart';
import '../models/telegram_link.dart';

/// فك ربط صار (لزر Undo): الربط القديم + قناة Telegram كانت شغّالة؟
@immutable
final class TelegramDisconnect {
  const TelegramDisconnect({required this.link, required this.channelWasOn});

  final TelegramLinked link;
  final bool channelWasOn;
}

/// حالة ربط Telegram بتفضيلات الإشعارات (H4b).
/// - بدون ربط: قناة Telegram ما بتشتغل (المفتاح معطّل).
/// - فك الربط بيطفي القناة، والـ Undo بيرجّع الربط والقناة متل ما كانوا.
/// - بدون اتصال: [TelegramOfflineException] وما بينبعت شي.
class TelegramLinkViewModel extends AsyncNotifier<TelegramLinkStatus> {
  var _busy = false;

  TelegramLinkRepository get _repo => ref.read(telegramLinkRepositoryProvider);

  bool get _offline => ref.read(networkStatusProvider) == NetworkStatus.offline;

  @override
  Future<TelegramLinkStatus> build() => ref.watch(telegramLinkRepositoryProvider).status();

  Future<void> retry() async {
    state = const AsyncLoading<TelegramLinkStatus>();
    state = await AsyncValue.guard(_repo.status);
  }

  /// الكود انقبل: مربوط + قناة Telegram بتشتغل (هيدا قصد المستخدم من الربط)
  Future<void> linked(TelegramLinked link) async {
    state = AsyncData(link);
    await ref.read(notificationPreferencesProvider.notifier).setChannel(NotificationChannel.telegram, true);
  }

  /// null = ضغطة مكرّرة (طلب شغّال) أو مش مربوط
  Future<TelegramDisconnect?> disconnect() async {
    final link = state.valueOrNull;
    if (_busy || link is! TelegramLinked) return null;
    if (_offline) throw const TelegramOfflineException();
    _busy = true;
    try {
      final prefs = ref.read(notificationPreferencesProvider);
      final undo = TelegramDisconnect(link: link, channelWasOn: prefs.channels.contains(NotificationChannel.telegram));
      await _repo.unlink();
      state = const AsyncData(TelegramNotLinked());
      await ref.read(notificationPreferencesProvider.notifier).setChannel(NotificationChannel.telegram, false);
      return undo;
    } finally {
      _busy = false;
    }
  }

  /// Undo: نفس الربط + القناة متل ما كانت
  Future<void> undoDisconnect(TelegramDisconnect undo) async {
    if (_busy) return;
    if (_offline) throw const TelegramOfflineException();
    _busy = true;
    try {
      await _repo.restore(undo.link);
      state = AsyncData(undo.link);
      await ref
          .read(notificationPreferencesProvider.notifier)
          .setChannel(NotificationChannel.telegram, undo.channelWasOn);
    } finally {
      _busy = false;
    }
  }
}

final telegramLinkProvider =
    AsyncNotifierProvider<TelegramLinkViewModel, TelegramLinkStatus>(TelegramLinkViewModel.new);

/// قناة Telegram فعليًا شغّالة؟ (مفعّلة **و** مربوطة)
final telegramChannelActiveProvider = Provider<bool>((ref) {
  final on = ref.watch(notificationPreferencesProvider.select((p) => p.channels.contains(NotificationChannel.telegram)));
  return on && (ref.watch(telegramLinkProvider).valueOrNull?.isLinked ?? false);
});

// ── شيت الربط: كود لمرة وحدة ───────────────────────────────

enum TelegramCodeIssue {
  /// بدون اتصال: ما انبعت شي
  offline,

  /// الطلب فشل (Try again)
  failed,

  /// الكود انتهى: "Get a new code"
  expired,

  /// الخادم لسّا ما شاف الكود عند البوت
  notYet,
}

@immutable
final class TelegramCodeState {
  const TelegramCodeState({this.code, this.requesting = false, this.checking = false, this.issue, this.linked});

  final TelegramLinkCode? code;
  final bool requesting;
  final bool checking;
  final TelegramCodeIssue? issue;

  /// انربط (الشيت بيتسكّر)
  final TelegramLinked? linked;

  TelegramCodeState copyWith({bool? checking, TelegramCodeIssue? issue, bool clearIssue = false}) => TelegramCodeState(
        code: code,
        requesting: requesting,
        checking: checking ?? this.checking,
        issue: clearIssue ? null : (issue ?? this.issue),
        linked: linked,
      );
}

/// مدة انتظار "Check connection" قبل الفحص (المحاكاة: البوت بيستلم الكود).
/// TODO(API): مع الـ API = فاصل الـ polling.
final telegramCheckDelayProvider = Provider<Duration>((ref) => const Duration(milliseconds: 1500));

/// متحكّم الشيت (autoDispose): تسكير الشيت بيلغي أي فحص معلّق (ما بينبعت شي).
class TelegramCodeController extends AutoDisposeNotifier<TelegramCodeState> {
  Timer? _pending;
  var _disposed = false;
  var _generation = 0;

  TelegramLinkRepository get _repo => ref.read(telegramLinkRepositoryProvider);

  bool get _offline => ref.read(networkStatusProvider) == NetworkStatus.offline;

  DateTime _now() => ref.read(telegramClockProvider)().toUtc();

  @override
  TelegramCodeState build() {
    ref.onDispose(() {
      _disposed = true;
      _pending?.cancel();
    });
    return const TelegramCodeState();
  }

  /// كود جديد (أول فتح، "Get a new code"، Try again). الكود القديم بيروح من
  /// الحالة فورًا، فما بينعاد استعمالو.
  Future<void> requestCode() async {
    if (state.requesting || state.checking) return;
    if (_offline) {
      state = TelegramCodeState(code: state.code, issue: TelegramCodeIssue.offline);
      return;
    }
    final generation = ++_generation;
    state = const TelegramCodeState(requesting: true);
    try {
      final code = await _repo.requestCode();
      if (_disposed || generation != _generation) return;
      state = TelegramCodeState(code: code);
    } on TelegramOfflineException {
      if (!_disposed) state = const TelegramCodeState(issue: TelegramCodeIssue.offline);
    } catch (_) {
      if (!_disposed) state = const TelegramCodeState(issue: TelegramCodeIssue.failed);
    }
  }

  /// "Check connection": مرة وحدة حتى لو انضغط مرتين
  void check() {
    final code = state.code;
    if (code == null || state.checking || state.requesting) return;
    if (code.isExpiredAt(_now())) {
      state = state.copyWith(issue: TelegramCodeIssue.expired);
      return;
    }
    if (_offline) {
      state = state.copyWith(issue: TelegramCodeIssue.offline);
      return;
    }
    state = state.copyWith(checking: true, clearIssue: true);
    _pending = Timer(ref.read(telegramCheckDelayProvider), () => _runCheck(code));
  }

  Future<void> _runCheck(TelegramLinkCode code) async {
    _pending = null;
    if (_disposed) return;
    final link = ref.read(telegramLinkProvider.notifier);
    try {
      final result = await _repo.checkCode(code.code);
      if (result is TelegramLinked) {
        // الخادم ربط: حالة الربط بتتحدّث حتى لو الشيت تسكّر بنص الطلب
        await link.linked(result);
        if (!_disposed) state = TelegramCodeState(code: code, linked: result);
      } else if (!_disposed) {
        state = state.copyWith(checking: false, issue: TelegramCodeIssue.notYet);
      }
    } on TelegramCodeExpiredException {
      if (!_disposed) state = state.copyWith(checking: false, issue: TelegramCodeIssue.expired);
    } on TelegramOfflineException {
      if (!_disposed) state = state.copyWith(checking: false, issue: TelegramCodeIssue.offline);
    } catch (_) {
      if (!_disposed) state = state.copyWith(checking: false, issue: TelegramCodeIssue.failed);
    }
  }
}

final telegramCodeProvider =
    AutoDisposeNotifierProvider<TelegramCodeController, TelegramCodeState>(TelegramCodeController.new);
