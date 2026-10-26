import 'package:flutter/material.dart';

/// مركز إدارة الألوان للتطبيق بالكامل
/// جميع الألوان مستخرجة من تصميم الواجهة الأصلي
/// 
/// ⚠️ CRITICAL: لا تستخدم قيم hex مباشرة خارج هذا الملف
abstract final class AppColors {
  // ═══════════════════════════════════════════════════════════
  // Background Colors - الخلفيات
  // ═══════════════════════════════════════════════════════════
  
  /// أغمق خلفية - خلفية التطبيق الرئيسية
  static const Color bgDeep = Color(0xFF020B15);
  
  /// خلفية متوسطة - للحقول والكروت
  static const Color bgMid = Color(0xFF0A1E32);
  
  /// خلفية سطحية - للعناصر المرفوعة
  static const Color bgSurface = Color(0xFF0D2844);
  
  // ═══════════════════════════════════════════════════════════
  // Brand Gradient - التدرج اللوني للعلامة التجارية
  // ═══════════════════════════════════════════════════════════
  
  /// بداية التدرج - أصفر-أخضر فاتح
  static const Color gradientStart = Color(0xFFD4FF5E);
  
  /// نهاية التدرج - أخضر سماوي
  static const Color gradientEnd = Color(0x8588E0B1);
  
  /// منتصف التدرج - أخضر فاتح
  static const Color gradientMid = Color(0xFF5EFFB4);
  
  // ═══════════════════════════════════════════════════════════
  // Accent Colors - الألوان التمييزية
  // ═══════════════════════════════════════════════════════════
  
  /// سماوي فاتح - للعناصر التفاعلية
  static const Color accentCyan = Color(0xFF4DD4E8);
  
  /// أزرق داكن - للعناصر الثانوية
  static const Color accentBlue = Color(0xFF1A5A8F);
  
  /// أخضر توهج - للعناصر المميزة
  static const Color accentGreen = Color(0xFF6BFFB8);
  
  // ═══════════════════════════════════════════════════════════
  // Text Colors - ألوان النصوص
  // ═══════════════════════════════════════════════════════════
  
  /// نص رئيسي - أبيض نقي
  static const Color textPrimary = Color(0xFFFFFFFF);
  
  /// نص ثانوي - رمادي فاتح
  static const Color textSecondary = Color(0xFFB8C5D0);
  
  /// نص توضيحي - رمادي-أزرق للـ placeholder
  static const Color textHint = Color(0xFF5A7A92);
  
  /// نص الروابط - أخضر توهج
  static const Color textLink = Color(0xFF6BFFB8);
  
  // ═══════════════════════════════════════════════════════════
  // Field Colors - ألوان حقول الإدخال
  // ═══════════════════════════════════════════════════════════
  
  /// خلفية الحقل
  static const Color fieldFill = Color(0xFF0D2539);
  
  /// حدود الحقل العادية
  static const Color fieldBorder = Color(0xFF2A5A7A);
  
  /// حدود الحقل عند التركيز
  static const Color fieldBorderFocus = Color(0xFF5EFFB4);
  
  // ═══════════════════════════════════════════════════════════
  // Button Colors - ألوان الأزرار
  // ═══════════════════════════════════════════════════════════
  
  /// خلفية الزر الرئيسي
  static const Color buttonBg = Color(0xFF6BFFB8);
  
  /// نص الزر
  static const Color buttonText = Color(0xFF051A28);
  
  // ═══════════════════════════════════════════════════════════
  // Status Colors - ألوان الحالات
  // ═══════════════════════════════════════════════════════════
  
  /// لون الخطأ
  static const Color error = Color(0xFFFF4757);
  
  /// لون النجاح
  static const Color success = Color(0xFF6BFFB8);
  
  // ═══════════════════════════════════════════════════════════
  // Trading Colors - ألوان التداول (شراء/بيع)
  // ═══════════════════════════════════════════════════════════
  
  /// أخضر زر الشراء (Buy) - أخضر مسطح مختلف عن أخضر العلامة التجارية
  static const Color buyGreen = Color(0xFF4ADE80);
  
  /// أحمر زر البيع (Sell) - نفس لون الخطأ لثبات الهوية اللونية
  static const Color sellRed = error;
  
  // ═══════════════════════════════════════════════════════════
  // Star/Particle Colors - ألوان النجوم والجزيئات
  // ═══════════════════════════════════════════════════════════
  
  /// نجمة مضيئة - أصفر-أخضر فاتح
  static const Color starBright = Color(0xFFB8FF6E);
  
  /// نجمة خافتة - أزرق سماوي
  static const Color starDim = Color(0xFF2B8AC4);
  
  /// نجمة سماوية - أخضر سماوي
  static const Color starTeal = Color(0xFF5EFFB4);
  
  // ═══════════════════════════════════════════════════════════
  // Chart Colors - ألوان الرسوم البيانية
  // ═══════════════════════════════════════════════════════════
  
  /// خط شارت أزرق
  static const Color chartLineBlue = Color(0xFF3B9DD4);
  
  /// خط شارت سماوي
  static const Color chartLineTeal = Color(0xFF4DD4C8);
  
  /// ظل علامة الدولار
  static const Color dollarShadow = Color(0xFF0D3A58);
  
  // ═══════════════════════════════════════════════════════════
  // Gradient Helpers - مساعدات التدرجات
  // ═══════════════════════════════════════════════════════════
  
  /// تدرج العلامة التجارية
  static const LinearGradient brandGradient = LinearGradient(
    colors: [gradientStart, gradientEnd],
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
  );
  
  /// تدرج الخلفية
  static const LinearGradient backgroundGradient = LinearGradient(
    colors: [bgDeep, Color(0xFF0A1C2E), bgMid],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
}
