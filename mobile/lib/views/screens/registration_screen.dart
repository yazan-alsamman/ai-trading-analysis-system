import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../controllers/auth_controller.dart';
import '../../l10n/app_localizations.dart';
import '../../providers/app_providers.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_text_styles.dart';
import '../../utils/validators.dart';
import '../../utils/routes/app_navigator.dart';
import '../widgets/custom_text_field.dart';
import '../widgets/gradient_button.dart';
import '../widgets/auth_background.dart';

/// شاشة التسجيل - أول شاشة يراها المستخدم
/// 
/// الدور المعماري: **View (واجهة)**
/// - قراءة الحالة من [AuthController] عبر [ref.watch]
/// - إرسال الأوامر عبر [ref.read]
/// - لا منطق أعمال هنا - فقط عرض وتفاعل
/// - جميع التحققات في [Validators]
class RegistrationScreen extends ConsumerStatefulWidget {
  const RegistrationScreen({super.key});
  
  @override
  ConsumerState<RegistrationScreen> createState() =>
      _RegistrationScreenState();
}

class _RegistrationScreenState extends ConsumerState<RegistrationScreen> {
  // ═══════════════════════════════════════════════════════════
  // Form State - حالة النموذج
  // ═══════════════════════════════════════════════════════════
  
  /// مفتاح النموذج للتحقق من الصحة
  final _formKey = GlobalKey<FormState>();
  
  // ═══════════════════════════════════════════════════════════
  // Text Controllers - متحكمات النصوص
  // ═══════════════════════════════════════════════════════════
  
  late final TextEditingController _emailController;
  late final TextEditingController _passwordController;
  late final TextEditingController _confirmController;
  
  // ═══════════════════════════════════════════════════════════
  // Lifecycle Methods - دوال دورة الحياة
  // ═══════════════════════════════════════════════════════════
  
  @override
  void initState() {
    super.initState();
    _emailController = TextEditingController();
    _passwordController = TextEditingController();
    _confirmController = TextEditingController();
  }
  
  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _confirmController.dispose();
    super.dispose();
  }
  
  // ═══════════════════════════════════════════════════════════
  // Event Handlers - معالجات الأحداث
  // ═══════════════════════════════════════════════════════════
  
  /// معالج زر إنشاء الحساب
  Future<void> _handleCreateAccount() async {
    // التحقق من صحة الحقول
    if (!(_formKey.currentState?.validate() ?? false)) {
      return;
    }
    
    // إخفاء لوحة المفاتيح
    FocusScope.of(context).unfocus();
    
    // إرسال طلب التسجيل للمتحكم
    await ref.read(authControllerProvider).register(
          email: _emailController.text.trim(),
          password: _passwordController.text,
        );
    
    // التحقق من النتيجة
    if (!mounted) return;
    _handleAuthResult();
  }
  
  /// معالجة نتيجة عملية التسجيل
  void _handleAuthResult() {
    final controller = ref.read(authControllerProvider);
    
    if (controller.status == AuthStatus.success) {
      // الانتقال لشاشة التحقق من OTP
      context.pushOtpVerification(email: _emailController.text.trim());
    } else if (controller.errorMessage != null) {
      _showErrorMessage(controller.errorMessage!);
    }
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
  
  /// معالج الضغط على "تسجيل دخول"
  void _handleSignInTapped() {
    // التنقل إلى شاشة تسجيل الدخول
    context.pushLogin();
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
            padding: const EdgeInsets.symmetric(horizontal: 65),
            child: Form(
              key: _formKey,
              child: Column(
                children: [
                  const SizedBox(height: 140),
                  _buildLogoSection(),
                  const SizedBox(height: 36),
                  _buildHeadingSection(l10n),
                  const SizedBox(height: 32),
                  _buildFieldsSection(l10n),
                  const SizedBox(height: 32),
                  _buildCreateButton(l10n),
                  const SizedBox(height: 24),
                  _buildSignInRow(l10n),
                  const SizedBox(height: 32),
                ],
              ),
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
          l10n.createAccount,
          style: AppTextStyles.heading1,
        ),
        const SizedBox(height: 2),
        Text(
          l10n.joinTraders,
          style: AppTextStyles.subtitle,
        ),
      ],
    );
  }
  
  /// بناء قسم الحقول
  Widget _buildFieldsSection(AppLocalizations l10n) {
    return Column(
      children: [
        CustomTextField(
          label: l10n.email,
          hint: l10n.email,
          controller: _emailController,
          keyboardType: TextInputType.emailAddress,
          validator: (value) => Validators.email(value, l10n),
        ),
        const SizedBox(height: 20),
        CustomTextField(
          label: l10n.password,
          hint: l10n.password,
          controller: _passwordController,
          isPassword: true,
          validator: (value) => Validators.password(value, l10n),
        ),
        const SizedBox(height: 8),
        Align(
          alignment: Alignment.centerLeft,
          child: Text(
            l10n.passwordRequirementsHint,
            style: AppTextStyles.labelSmall.copyWith(
              color: AppColors.textHint,
            ),
          ),
        ),
        const SizedBox(height: 12),
        CustomTextField(
          label: l10n.confirmPassword,
          hint: '••••••••••••••',
          controller: _confirmController,
          isPassword: true,
          prefixIcon: Icons.key_outlined,
          validator: (value) => Validators.confirmPassword(
            value,
            _passwordController.text,
            l10n,
          ),
        ),
      ],
    );
  }
  
  /// بناء زر إنشاء الحساب
  Widget _buildCreateButton(AppLocalizations l10n) {
    final isLoading = ref.watch(authControllerProvider).isLoading;
    
    return GradientButton(
      label: l10n.createAccountButton,
      isLoading: isLoading,
      onPressed: isLoading ? null : _handleCreateAccount,
    );
  }
  
  /// بناء صف تسجيل الدخول
  Widget _buildSignInRow(AppLocalizations l10n) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Text(
          l10n.alreadyHaveAccount,
          style: AppTextStyles.bodySmall,
        ),
        GestureDetector(
          onTap: _handleSignInTapped,
          child: Text(
            l10n.signIn,
            style: AppTextStyles.link,
          ),
        ),
      ],
    );
  }
}
