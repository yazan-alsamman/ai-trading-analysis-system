import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../controllers/auth_controller.dart';
import '../../../core/data/network_status.dart';
import '../../../providers/app_providers.dart';

/// حالة نموذج الدخول / إنشاء الحساب
@immutable
final class AuthFormState {
  const AuthFormState({this.submitting = false, this.failed = false, this.offline = false});

  final bool submitting;

  /// آخر محاولة فشلت (الشاشة بتعرض رسالة تحت الحقول)
  final bool failed;

  /// الفشل لأنو الجهاز بدون اتصال (ما انبعت طلب أصلًا)
  final bool offline;
}

/// ViewModel شاشتي Log in و Create account: إرسال واحد بنفس الوقت (ضغطة
/// مزدوجة ما بتبعت طلبين)، والنتيجة true/false للشاشة لتقرّر وين تروح.
///
/// TODO(B02): المصدر لسّا AuthController القديم (mock) - بيتبدّل بـ AuthRepository (Dio).
class AuthFormViewModel extends AutoDisposeNotifier<AuthFormState> {
  @override
  AuthFormState build() => const AuthFormState();

  Future<bool> login({required String email, required String password}) =>
      _submit((auth) => auth.login(email: email, password: password));

  Future<bool> register({
    required String fullName,
    required String email,
    required String password,
  }) =>
      _submit((auth) => auth.register(fullName: fullName, email: email, password: password));

  /// المستخدم عدّل الحقول بعد فشل: منخفي الرسالة
  void clearFailure() {
    if (state.failed) state = const AuthFormState();
  }

  Future<bool> _submit(Future<void> Function(AuthController auth) action) async {
    if (state.submitting) return false;
    if (ref.read(networkStatusProvider) == NetworkStatus.offline) {
      state = const AuthFormState(failed: true, offline: true);
      return false;
    }
    state = const AuthFormState(submitting: true);
    final auth = ref.read(authControllerProvider);
    try {
      await action(auth);
    } catch (_) {
      // الفشل بيوصل تحت كحالة failure
    }
    final ok = auth.status == AuthStatus.success;
    if (!ok) auth.clearError();
    state = AuthFormState(failed: !ok);
    return ok;
  }
}

final authFormViewModelProvider = AutoDisposeNotifierProvider<AuthFormViewModel, AuthFormState>(AuthFormViewModel.new);

// ── OTP ───────────────────────────────────────────────────

enum OtpStep { entering, verifying, verified }

@immutable
final class OtpState {
  const OtpState({this.step = OtpStep.entering, this.resendIn = OtpViewModel.resendCooldown});

  final OtpStep step;

  /// كم ثانية باقي لحد ما يصير "Resend code" متاح
  final int resendIn;

  OtpState copyWith({OtpStep? step, int? resendIn}) =>
      OtpState(step: step ?? this.step, resendIn: resendIn ?? this.resendIn);
}

/// ViewModel التحقق من البريد: الإرسال، العدّاد، وإعادة الإرسال.
///
/// TODO(B02): محاكاة - أي 5 أرقام بتمشي لحد ما ينربط خادم الحسابات (السؤال
/// المفتوح عن الـ OTP عند صاحب الـ backend).
class OtpViewModel extends AutoDisposeNotifier<OtpState> {
  static const int codeLength = 5;
  static const int resendCooldown = 60;

  /// تأخير الشبكة المحاكى
  static const Duration latency = Duration(milliseconds: 900);

  @override
  OtpState build() => const OtpState();

  /// ثانية مرّت (الشاشة بتنادي هاد من مؤقتها)
  void tick() {
    if (state.resendIn > 0) state = state.copyWith(resendIn: state.resendIn - 1);
  }

  bool get canResend => state.resendIn == 0 && state.step == OtpStep.entering;

  Future<void> resend() async {
    if (!canResend) return;
    state = state.copyWith(resendIn: resendCooldown);
  }

  /// false = الرمز ناقص أو في تحقق جاري
  Future<bool> verify(String code) async {
    if (state.step != OtpStep.entering || !isComplete(code)) return false;
    state = state.copyWith(step: OtpStep.verifying);
    await Future<void>.delayed(latency);
    // البريد تأكّد: هون الحساب الجديد بيصير جلسة محفوظة (مش عند Create account)
    await ref.read(authControllerProvider).persistSession();
    state = state.copyWith(step: OtpStep.verified);
    return true;
  }

  static bool isComplete(String code) => RegExp('^\\d{$codeLength}\$').hasMatch(code);
}

final otpViewModelProvider = AutoDisposeNotifierProvider<OtpViewModel, OtpState>(OtpViewModel.new);
