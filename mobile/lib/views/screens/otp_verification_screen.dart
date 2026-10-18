import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../controllers/auth_controller.dart';
import '../../l10n/app_localizations.dart';
import '../../providers/app_providers.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_text_styles.dart';
import '../../utils/routes/app_navigator.dart';
import '../widgets/gradient_button.dart';
import '../widgets/auth_background.dart';
import '../widgets/otp_input_widget.dart';

/// شاشة التحقق من رمز OTP
/// 
/// الدور المعماري: **View (واجهة)**
/// - عرض حقول إدخال OTP
/// - عرض مؤقت العد التنازلي
/// - السماح بإعادة إرسال الكود
/// - التحقق من الكود والمتابعة
class OtpVerificationScreen extends ConsumerStatefulWidget {
  const OtpVerificationScreen({
    super.key,
    required this.email,
  });
  
  /// البريد الإلكتروني المرسل إليه الكود
  final String email;
  
  @override
  ConsumerState<OtpVerificationScreen> createState() =>
      _OtpVerificationScreenState();
}

class _OtpVerificationScreenState
    extends ConsumerState<OtpVerificationScreen> {
  // ═══════════════════════════════════════════════════════════
  // State - الحالة
  // ═══════════════════════════════════════════════════════════
  
  /// مفتاح الـ OTP widget للتحكم به
  final GlobalKey<State<OtpInputWidget>> _otpKey = GlobalKey();
  
  /// الكود المدخل
  String _otpCode = '';
  
  /// وقت العد التنازلي (بالثواني)
  int _remainingSeconds = 60;
  
  /// Timer للعد التنازلي
  Timer? _timer;
  
  /// هل يمكن إعادة الإرسال؟
  bool get _canResend => _remainingSeconds == 0;
  
  // ═══════════════════════════════════════════════════════════
  // Lifecycle - دورة الحياة
  // ═══════════════════════════════════════════════════════════
  
  @override
  void initState() {
    super.initState();
    _startTimer();
  }
  
  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }
  
  // ═══════════════════════════════════════════════════════════
  // Timer Methods - دوال المؤقت
  // ═══════════════════════════════════════════════════════════
  
  /// بدء مؤقت العد التنازلي
  void _startTimer() {
    _remainingSeconds = 60;
    _timer?.cancel();
    
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_remainingSeconds > 0) {
        setState(() {
          _remainingSeconds--;
        });
      } else {
        timer.cancel();
      }
    });
  }
  
  /// تنسيق الوقت المتبقي
  String get _formattedTime {
    final minutes = _remainingSeconds ~/ 60;
    final seconds = _remainingSeconds % 60;
    return '${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
  }
  
  // ═══════════════════════════════════════════════════════════
  // Event Handlers - معالجات الأحداث
  // ═══════════════════════════════════════════════════════════
  
  /// معالج اكتمال إدخال OTP
  void _handleOtpCompleted(String code) {
    setState(() {
      _otpCode = code;
    });
  }
  
  /// معالج زر التحقق
  Future<void> _handleVerify() async {
    final l10n = AppLocalizations.of(context)!;

    if (_otpCode.length != 5) {
      _showErrorMessage(l10n.enterCompleteCode);
      return;
    }
    
    // إخفاء لوحة المفاتيح
    FocusScope.of(context).unfocus();
    
    // TODO: إرسال الكود للتحقق عبر API
    // محاكاة عملية التحقق
    await Future.delayed(const Duration(seconds: 2));
    
    // في حالة النجاح
    if (!mounted) return;
    
    _showSuccessMessage(l10n.emailVerifiedSuccessfully);
    
    // التنقل للشاشة الرئيسية
    context.pushHomeAndClearStack();
  }
  
  /// معالج إعادة إرسال الكود
  Future<void> _handleResendCode() async {
    final l10n = AppLocalizations.of(context)!;

    // TODO: إرسال طلب إعادة الإرسال عبر API
    
    // مسح الكود المدخل
    setState(() {
      _otpCode = '';
    });
    
    // إعادة تشغيل المؤقت
    _startTimer();
    
    _showInfoMessage(l10n.verificationCodeSent);
  }
  
  /// عرض رسالة نجاح
  void _showSuccessMessage(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: AppColors.success,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
        ),
      ),
    );
  }
  
  /// عرض رسالة خطأ
  void _showErrorMessage(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: AppColors.error,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
        ),
      ),
    );
  }
  
  /// عرض رسالة معلومات
  void _showInfoMessage(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: AppColors.accentCyan,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
        ),
      ),
    );
  }
  
  // ═══════════════════════════════════════════════════════════
  // Build Methods - دوال البناء
  // ═══════════════════════════════════════════════════════════
  
  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;

    return Scaffold(
      resizeToAvoidBottomInset: true,
      body: AuthBackground(
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 40),
            child: Column(
              children: [
                const SizedBox(height: 140),
                _buildLogoSection(),
                const SizedBox(height: 36),
                _buildHeadingSection(l10n),
                const SizedBox(height: 48),
                _buildOtpInput(),
                const SizedBox(height: 32),
                _buildTimer(l10n),
                const SizedBox(height: 32),
                _buildVerifyButton(l10n),
                const SizedBox(height: 24),
                _buildResendRow(l10n),
                const SizedBox(height: 32),
              ],
            ),
          ),
        ),
      ),
    );
  }
  
  /// بناء قسم الشعار
  Widget _buildLogoSection() {
    return Container(
      width: 120,
      height: 120,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: AppColors.brandGradient,
        boxShadow: [
          BoxShadow(
            color: AppColors.gradientEnd.withOpacity(0.45),
            blurRadius: 30,
            spreadRadius: 2,
          ),
        ],
      ),
      child: const Icon(
        Icons.trending_up_rounded,
        color: Color(0xFF1A2A1A),
        size: 66,
      ),
    );
  }
  
  /// بناء قسم العنوان
  Widget _buildHeadingSection(AppLocalizations l10n) {
    return Column(
      children: [
        Text(
          l10n.verifyEmail,
          style: AppTextStyles.heading1,
        ),
        const SizedBox(height: 12),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Text(
            l10n.enterCodeSent,
            style: AppTextStyles.subtitle,
            textAlign: TextAlign.center,
          ),
        ),
      ],
    );
  }
  
  /// بناء حقول OTP
  Widget _buildOtpInput() {
    return OtpInputWidget(
      key: _otpKey,
      length: 5,
      onCompleted: _handleOtpCompleted,
    );
  }
  
  /// بناء مؤقت العد التنازلي
  Widget _buildTimer(AppLocalizations l10n) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Text(
          _formattedTime,
          style: AppTextStyles.heading2.copyWith(
            color: _canResend 
                ? AppColors.error 
                : AppColors.accentCyan,
          ),
        ),
        const SizedBox(width: 8),
        Text(
          l10n.second,
          style: AppTextStyles.bodySmall,
        ),
      ],
    );
  }
  
  /// بناء زر التحقق
  Widget _buildVerifyButton(AppLocalizations l10n) {
    final isLoading = ref.watch(authControllerProvider).isLoading;
    
    return GradientButton(
      label: l10n.verify,
      isLoading: isLoading,
      onPressed: isLoading ? null : _handleVerify,
    );
  }
  
  /// بناء صف إعادة الإرسال
  Widget _buildResendRow(AppLocalizations l10n) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Text(
          l10n.didntReceiveCode,
          style: AppTextStyles.bodySmall,
        ),
        GestureDetector(
          onTap: _handleResendCode,
          child: Text(
            l10n.resendCode,
            style: AppTextStyles.link,
          ),
        ),
      ],
    );
  }
}
