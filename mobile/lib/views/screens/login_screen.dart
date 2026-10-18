import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../controllers/auth_controller.dart';
import '../../l10n/app_localizations.dart';
import '../../providers/app_providers.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_text_styles.dart';
import '../../utils/routes/app_navigator.dart';
import '../../utils/validators.dart';
import '../widgets/custom_text_field.dart';
import '../widgets/gradient_button.dart';
import '../widgets/auth_background.dart';

/// شاشة تسجيل الدخول - Sign In
/// 
/// الدور المعماري: **View (واجهة)**
/// - قراءة الحالة من [AuthController] عبر [ref.watch]
/// - إرسال الأوامر عبر [ref.read]
/// - لا منطق أعمال هنا - فقط عرض وتفاعل
/// - جميع التحققات في [Validators]
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});
  
  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
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
  
  // ═══════════════════════════════════════════════════════════
  // Lifecycle Methods - دوال دورة الحياة
  // ═══════════════════════════════════════════════════════════
  
  @override
  void initState() {
    super.initState();
    _emailController = TextEditingController();
    _passwordController = TextEditingController();
  }
  
  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }
  
  // ═══════════════════════════════════════════════════════════
  // Event Handlers - معالجات الأحداث
  // ═══════════════════════════════════════════════════════════
  
  /// معالج زر تسجيل الدخول
  Future<void> _handleSignIn() async {
    // التحقق من صحة الحقول
    if (!(_formKey.currentState?.validate() ?? false)) {
      return;
    }
    
    // إخفاء لوحة المفاتيح
    FocusScope.of(context).unfocus();
    
    // إرسال طلب تسجيل الدخول للمتحكم
    await ref.read(authControllerProvider).login(
          email: _emailController.text.trim(),
          password: _passwordController.text,
        );
    
    // التحقق من النتيجة
    if (!mounted) return;
    _handleAuthResult();
  }
  
  /// معالجة نتيجة عملية تسجيل الدخول
  void _handleAuthResult() {
    final controller = ref.read(authControllerProvider);
    
    if (controller.status == AuthStatus.success) {
      // الانتقال للشاشة الرئيسية
      context.pushHomeAndClearStack();
    } else if (controller.errorMessage != null) {
      _showErrorMessage(controller.errorMessage!);
      controller.clearError();
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
  
  /// معالج الضغط على "Sign up"
  void _handleSignUpTapped() {
    // العودة لشاشة التسجيل
    Navigator.of(context).pop();
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
                  _buildSignInButton(l10n),
                  const SizedBox(height: 24),
                  _buildSignUpRow(l10n),
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
          l10n.welcomeBack,
          style: AppTextStyles.heading1,
        ),
        const SizedBox(height: 2),
        Text(
          l10n.signInToContinue,
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
          prefixIcon: Icons.key_outlined,
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
      ],
    );
  }
  
  /// بناء زر تسجيل الدخول
  Widget _buildSignInButton(AppLocalizations l10n) {
    final isLoading = ref.watch(authControllerProvider).isLoading;
    
    return GradientButton(
      label: l10n.signIn,
      isLoading: isLoading,
      onPressed: isLoading ? null : _handleSignIn,
    );
  }
  
  /// بناء صف التسجيل
  Widget _buildSignUpRow(AppLocalizations l10n) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Text(
          l10n.noAccountQuestion,
          style: AppTextStyles.bodySmall,
        ),
        GestureDetector(
          onTap: _handleSignUpTapped,
          child: Text(
            l10n.signUp,
            style: AppTextStyles.link,
          ),
        ),
      ],
    );
  }
}
