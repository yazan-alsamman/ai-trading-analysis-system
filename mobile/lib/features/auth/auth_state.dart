import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../models/user_model.dart';
import '../../providers/app_providers.dart';

/// حالة الجلسة: الـ route guard والتنقّل عند انتهاء الجلسة بيقرأوا من هون بس
sealed class AuthState {
  const AuthState();

  bool get isSignedIn => this is SignedIn;
}

final class SignedOut extends AuthState {
  const SignedOut();
}

@immutable
final class SignedIn extends AuthState {
  const SignedIn(this.user);

  final UserModel user;
}

// TODO(B02): المصدر لسّا AuthController القديم (mock) - بخطوة Auth بيتحوّل
// لـ Notifier على AuthRepository (Dio) واستعادة الجلسة من الـ token المحفوظ.
final authStateProvider = Provider<AuthState>((ref) {
  final user = ref.watch(authControllerProvider.select((c) => c.currentUser));
  return user == null ? const SignedOut() : SignedIn(user);
});

/// هل خلص الـ splash من قراءة الجلسة المحفوظة؟ قبلها الـ router ما بيطلع من
/// الـ splash (المسجّل دخوله ما بيشوف Welcome ولا لحظة)، بعدها بيقرّر: جلسة →
/// الرئيسية، بدونها → Welcome. بيصير true مرة وحدة بكل تشغيل.
class SessionRestoreNotifier extends Notifier<bool> {
  @override
  bool build() => false;

  void markRestored() => state = true;
}

final sessionRestoredProvider = NotifierProvider<SessionRestoreNotifier, bool>(SessionRestoreNotifier.new);
