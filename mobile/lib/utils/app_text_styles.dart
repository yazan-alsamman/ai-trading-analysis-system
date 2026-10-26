import 'package:flutter/material.dart';
import 'app_colors.dart';

/// مركز إدارة أنماط النصوص في التطبيق
/// 
/// جميع الشاشات يجب أن تستورد الأنماط من هنا فقط
/// لا تقم بإنشاء TextStyle مباشرة في الشاشات
abstract final class AppTextStyles {
  // ═══════════════════════════════════════════════════════════
  // Font Family
  // ═══════════════════════════════════════════════════════════
  
  static const String _fontFamily = 'SF Pro Display';
  
  // ═══════════════════════════════════════════════════════════
  // Heading Styles - أنماط العناوين
  // ═══════════════════════════════════════════════════════════
  
  /// عنوان رئيسي كبير (H1)
  static const TextStyle heading1 = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 28,
    fontWeight: FontWeight.w700,
    color: AppColors.textPrimary,
    height: 1.2,
    letterSpacing: -0.5,
  );
  
  /// عنوان فرعي (H2)
  static const TextStyle heading2 = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 22,
    fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
    height: 1.3,
  );
  
  /// عنوان صغير (H3)
  static const TextStyle heading3 = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 18,
    fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
    height: 1.4,
  );
  
  // ═══════════════════════════════════════════════════════════
  // Body Styles - أنماط النصوص العادية
  // ═══════════════════════════════════════════════════════════
  
  /// نص عادي كبير
  static const TextStyle bodyLarge = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 16,
    fontWeight: FontWeight.w400,
    color: AppColors.textPrimary,
    height: 1.5,
  );
  
  /// نص عادي متوسط
  static const TextStyle bodyMedium = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 15,
    fontWeight: FontWeight.w400,
    color: AppColors.textPrimary,
    height: 1.5,
  );
  
  /// نص عادي صغير
  static const TextStyle bodySmall = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 13,
    fontWeight: FontWeight.w400,
    color: AppColors.textSecondary,
    height: 1.4,
  );
  
  // ═══════════════════════════════════════════════════════════
  // Subtitle Styles - أنماط النصوص الفرعية
  // ═══════════════════════════════════════════════════════════
  
  /// نص فرعي
  static const TextStyle subtitle = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 15,
    fontWeight: FontWeight.w400,
    color: AppColors.textSecondary,
    height: 1.4,
  );
  
  // ═══════════════════════════════════════════════════════════
  // Label Styles - أنماط التسميات
  // ═══════════════════════════════════════════════════════════
  
  /// تسمية عادية
  static const TextStyle label = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 13,
    fontWeight: FontWeight.w500,
    color: AppColors.textSecondary,
    letterSpacing: 0.3,
  );
  
  /// تسمية صغيرة
  static const TextStyle labelSmall = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 13,
    fontWeight: FontWeight.w500,
    color: AppColors.textSecondary,
    letterSpacing: 0.5,
  );
  
  // ═══════════════════════════════════════════════════════════
  // Field Styles - أنماط حقول الإدخال
  // ═══════════════════════════════════════════════════════════
  
  /// نص الحقل
  static const TextStyle fieldText = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 15,
    fontWeight: FontWeight.w400,
    color: AppColors.textPrimary,
  );
  
  /// نص توضيحي في الحقل
  static const TextStyle fieldHint = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 15,
    fontWeight: FontWeight.w400,
    color: AppColors.textHint,
  );
  
  // ═══════════════════════════════════════════════════════════
  // Button Styles - أنماط الأزرار
  // ═══════════════════════════════════════════════════════════
  
  /// نص الزر
  static const TextStyle button = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 16,
    fontWeight: FontWeight.w700,
    color: AppColors.buttonText,
    letterSpacing: 0.5,
  );
  
  /// نص زر صغير
  static const TextStyle buttonSmall = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 14,
    fontWeight: FontWeight.w600,
    color: AppColors.buttonText,
    letterSpacing: 0.3,
  );
  
  // ═══════════════════════════════════════════════════════════
  // Link Styles - أنماط الروابط
  // ═══════════════════════════════════════════════════════════
  
  /// رابط
  static const TextStyle link = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 13,
    fontWeight: FontWeight.w600,
    color: AppColors.textLink,
  );
  
  /// رابط صغير
  static const TextStyle linkSmall = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 11,
    fontWeight: FontWeight.w600,
    color: AppColors.textLink,
  );
  
  // ═══════════════════════════════════════════════════════════
  // Special Styles - أنماط خاصة
  // ═══════════════════════════════════════════════════════════
  
  /// نص الأخطاء
  static const TextStyle error = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 11,
    fontWeight: FontWeight.w400,
    color: AppColors.error,
    height: 1.3,
  );
  
  /// نص النجاح
  static const TextStyle success = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 13,
    fontWeight: FontWeight.w500,
    color: AppColors.success,
  );
}
