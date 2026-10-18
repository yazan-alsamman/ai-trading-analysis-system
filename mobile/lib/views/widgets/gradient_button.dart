import 'package:flutter/material.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_text_styles.dart';

/// زر بتدرج لوني يتماشى مع العلامة التجارية
/// 
/// ميزات:
/// - عرض كامل
/// - تدرج لوني من ألوان العلامة التجارية
/// - يعرض مؤشر تحميل عند الحاجة
/// - ظلال جميلة
class GradientButton extends StatelessWidget {
  const GradientButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.isLoading = false,
  });
  
  // ═══════════════════════════════════════════════════════════
  // Properties - الخصائص
  // ═══════════════════════════════════════════════════════════
  
  /// نص الزر
  final String label;
  
  /// دالة تُستدعى عند الضغط
  final VoidCallback? onPressed;
  
  /// هل الزر في حالة تحميل؟
  final bool isLoading;
  
  // ═══════════════════════════════════════════════════════════
  // Build - البناء
  // ═══════════════════════════════════════════════════════════
  
  @override
  Widget build(BuildContext context) {
    // تحديد التدرج بناءً على حالة الزر
    final gradient = onPressed != null
        ? AppColors.brandGradient
        : const LinearGradient(
            colors: [
              Color(0xFF5EFFB4),
              Color(0x8588E0B1),
            ],
          );
    
    return SizedBox(
      width: double.infinity,
      height: 56,
      child: DecoratedBox(
        decoration: BoxDecoration(
          gradient: gradient,
          borderRadius: BorderRadius.circular(30),
          boxShadow: [
            BoxShadow(
              color: AppColors.gradientEnd.withOpacity(0.25),
              blurRadius: 16,
              offset: const Offset(0, 6),
            ),
          ],
        ),
        child: ElevatedButton(
          onPressed: isLoading ? null : onPressed,
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.transparent,
            shadowColor: Colors.transparent,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(30),
            ),
          ),
          child: _buildChild(),
        ),
      ),
    );
  }
  
  // ═══════════════════════════════════════════════════════════
  // Helper Methods - دوال مساعدة
  // ═══════════════════════════════════════════════════════════
  
  /// بناء محتوى الزر
  Widget _buildChild() {
    if (isLoading) {
      return const SizedBox(
        width: 22,
        height: 22,
        child: CircularProgressIndicator(
          strokeWidth: 2.5,
          valueColor: AlwaysStoppedAnimation(AppColors.bgDeep),
        ),
      );
    }
    
    return Text(
      label,
      style: AppTextStyles.button,
    );
  }
}
