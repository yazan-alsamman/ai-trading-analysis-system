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
  
  /// التحقق من صحة كلمة المرور - نفس قاعدة الـ backend بالضبط
  /// (backend/app/schemas/user.py) حتى نفس الحساب يشتغل عالويب والموبايل:
  /// - 8 لـ 128 حرف
  /// - حرف واحد على الأقل
  /// - رقم واحد على الأقل
  static String? password(String? value, AppLocalizations l10n) {
    if (value == null || value.isEmpty) {
      return l10n.passwordRequired;
    }
    if (value.length < passwordMinLength) {
      return l10n.passwordMinChars;
    }
    if (value.length > passwordMaxLength) {
      return l10n.passwordMaxChars;
    }
    if (!hasLetter(value)) {
      return l10n.passwordNeedsLetter;
    }
    if (!hasDigit(value)) {
      return l10n.passwordNeedsNumber;
    }
    return null;
  }

  static const int passwordMinLength = 8;
  static const int passwordMaxLength = 128;

  static bool hasLetter(String value) => value.contains(RegExp(r'[A-Za-z]'));

  static bool hasDigit(String value) => value.contains(RegExp(r'[0-9]'));

  /// الاسم الكامل بشاشة إنشاء الحساب: 2 لـ 60 حرف (نفس الويب)
  static String? fullName(String? value, AppLocalizations l10n) {
    final trimmed = value?.trim() ?? '';
    if (trimmed.length < 2) return l10n.fullNameRequired;
    if (trimmed.length > 60) return l10n.fullNameTooLong;
    return null;
  }

  
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
}
