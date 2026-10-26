import '../l10n/app_localizations.dart';

/// دوال التحقق من صحة المدخلات
/// 
/// جميع دوال التحقق نقية تقريبًا (Pure) - بتاخد [AppLocalizations]
/// كباراميتر أول حتى ترجع رسالة الخطأ باللغة الحالية للتطبيق، بدل ما
/// تعتمد على BuildContext مباشرة (يخليها أسهل بالاختبار والاستخدام).
/// ترجع null عندما تكون القيمة صحيحة، وترجع رسالة خطأ عندما تكون خاطئة
abstract final class Validators {
  // ═══════════════════════════════════════════════════════════
  // Email Validation - التحقق من البريد الإلكتروني
  // ═══════════════════════════════════════════════════════════
  
  /// التحقق من صحة البريد الإلكتروني
  /// 
  /// يستخدم نمط (Regular Expression) شامل مطابق لمعيار HTML5 لحقول
  /// البريد الإلكتروني - بيرفض الأشكال الشائعة الخاطئة متل نقطتين
  /// متتاليتين، أو بريد بدون نطاق صحيح، أو بدون @ أصلاً
  static String? email(String? value, AppLocalizations l10n) {
    if (value == null || value.trim().isEmpty) {
      return l10n.emailRequired;
    }

    final trimmed = value.trim();

    final emailRegex = RegExp(
      r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
      r'@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?'
      r'(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$',
    );

    if (!emailRegex.hasMatch(trimmed)) {
      return l10n.enterValidEmail;
    }

    return null;
  }
  
  // ═══════════════════════════════════════════════════════════
  // Password Validation - التحقق من كلمة المرور
  // ═══════════════════════════════════════════════════════════
  
  /// التحقق من صحة كلمة المرور
  /// 
  /// الشروط:
  /// - الحد الأدنى 8 أحرف
  /// - حرف كبير واحد على الأقل (A-Z)
  /// - حرف صغير واحد على الأقل (a-z)
  /// - رقم واحد على الأقل (0-9)
  /// - رمز خاص واحد على الأقل (!@#$%^&*...)
  static String? password(String? value, AppLocalizations l10n) {
    if (value == null || value.isEmpty) {
      return l10n.passwordRequired;
    }
    
    if (value.length < 8) {
      return l10n.passwordMinChars;
    }
    
    if (!value.contains(RegExp(r'[A-Z]'))) {
      return l10n.passwordNeedsUppercase;
    }

    if (!value.contains(RegExp(r'[a-z]'))) {
      return l10n.passwordNeedsLowercase;
    }
    
    if (!value.contains(RegExp(r'[0-9]'))) {
      return l10n.passwordNeedsNumber;
    }

    if (!value.contains(RegExp(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]/~`]'))) {
      return l10n.passwordNeedsSymbol;
    }
    
    return null;
  }

  /// نص وصفي موجز بشروط كلمة المرور - للعرض تحت الحقل بشاشات
  /// التسجيل/تغيير كلمة المرور، حتى تكون الشروط واضحة للمستخدم قبل
  /// ما يحاول يرسل النموذج
  static String passwordRequirementsHint(AppLocalizations l10n) =>
      l10n.passwordRequirementsHint;
  
  // ═══════════════════════════════════════════════════════════
  // Confirm Password Validation - التحقق من تطابق كلمات المرور
  // ═══════════════════════════════════════════════════════════
  
  /// التحقق من تطابق كلمة المرور مع التأكيد
  static String? confirmPassword(
    String? value,
    String original,
    AppLocalizations l10n,
  ) {
    if (value == null || value.isEmpty) {
      return l10n.pleaseConfirmPassword;
    }
    
    if (value != original) {
      return l10n.passwordsDoNotMatch;
    }
    
    return null;
  }
  
  // ═══════════════════════════════════════════════════════════
  // General Validation - التحقق العام
  // ═══════════════════════════════════════════════════════════
  
  /// التحقق من أن الحقل غير فارغ
  static String? required(
    String? value,
    AppLocalizations l10n, {
    String? fieldName,
  }) {
    if (value == null || value.trim().isEmpty) {
      return fieldName != null
          ? l10n.fieldRequired(fieldName)
          : l10n.thisFieldRequired;
    }
    return null;
  }
  
  /// التحقق من الحد الأدنى للطول
  static String? minLength(
    String? value,
    int min,
    AppLocalizations l10n, {
    String? fieldName,
  }) {
    if (value == null || value.isEmpty) {
      return fieldName != null
          ? l10n.fieldRequired(fieldName)
          : l10n.thisFieldRequired;
    }
    
    if (value.length < min) {
      return l10n.fieldMinLength(fieldName ?? l10n.thisFieldRequired, min);
    }
    
    return null;
  }
  
  /// التحقق من الحد الأقصى للطول
  static String? maxLength(
    String? value,
    int max,
    AppLocalizations l10n, {
    String? fieldName,
  }) {
    if (value != null && value.length > max) {
      return l10n.fieldMaxLength(fieldName ?? l10n.thisFieldRequired, max);
    }
    return null;
  }
}
