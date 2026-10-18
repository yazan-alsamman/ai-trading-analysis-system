import 'package:flutter/material.dart';
import '../../l10n/app_localizations.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_text_styles.dart';

/// حقل إدخال نصي مخصص يتماشى مع هوية التطبيق
/// 
/// ميزات:
/// - تصميم داكن احترافي
/// - دعم كلمات المرور مع إخفاء/إظهار
/// - أيقونات قابلة للتخصيص
/// - تحقق من الصحة
/// - رسائل خطأ واضحة
class CustomTextField extends StatefulWidget {
  const CustomTextField({
    super.key,
    required this.label,
    required this.hint,
    required this.controller,
    this.validator,
    this.isPassword = false,
    this.prefixIcon,
    this.keyboardType = TextInputType.text,
    this.enabled = true,
    this.maxLines = 1,
    this.onChanged,
  });
  
  // ═══════════════════════════════════════════════════════════
  // Properties - الخصائص
  // ═══════════════════════════════════════════════════════════
  
  /// التسمية فوق الحقل
  final String label;
  
  /// النص التوضيحي داخل الحقل
  final String hint;
  
  /// متحكم النص
  final TextEditingController controller;
  
  /// دالة التحقق من الصحة
  final String? Function(String?)? validator;
  
  /// هل الحقل لكلمة مرور؟
  final bool isPassword;
  
  /// أيقونة في البداية
  final IconData? prefixIcon;
  
  /// نوع لوحة المفاتيح
  final TextInputType keyboardType;
  
  /// هل الحقل مفعّل؟
  final bool enabled;
  
  /// عدد الأسطر
  final int maxLines;
  
  /// دالة تُستدعى عند تغيير النص
  final void Function(String)? onChanged;
  
  @override
  State<CustomTextField> createState() => _CustomTextFieldState();
}

class _CustomTextFieldState extends State<CustomTextField> {
  // ═══════════════════════════════════════════════════════════
  // State - الحالة
  // ═══════════════════════════════════════════════════════════
  
  /// إخفاء النص (لكلمات المرور)
  bool _obscureText = true;
  
  // ═══════════════════════════════════════════════════════════
  // Methods - الدوال
  // ═══════════════════════════════════════════════════════════
  
  /// تبديل إظهار/إخفاء كلمة المرور
  void _toggleObscure() {
    setState(() => _obscureText = !_obscureText);
  }
  
  // ═══════════════════════════════════════════════════════════
  // Build - البناء
  // ═══════════════════════════════════════════════════════════
  
  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // التسمية
        Text(
          widget.label,
          style: AppTextStyles.label,
        ),
        
        const SizedBox(height: 8),
        
        // الحقل
        TextFormField(
          controller: widget.controller,
          validator: widget.validator,
          obscureText: widget.isPassword && _obscureText,
          keyboardType: widget.keyboardType,
          enabled: widget.enabled,
          maxLines: widget.maxLines,
          onChanged: widget.onChanged,
          style: AppTextStyles.fieldText,
          decoration: InputDecoration(
            hintText: widget.hint,
            hintStyle: AppTextStyles.fieldHint,
            filled: true,
            fillColor: AppColors.bgMid,
            
            // أيقونة البداية
            prefixIcon: widget.prefixIcon != null
                ? Icon(
                    widget.prefixIcon,
                    color: AppColors.textHint,
                    size: 20,
                  )
                : null,
            
            // أيقونة النهاية (للإخفاء/الإظهار)
            suffixIcon: widget.isPassword
                ? IconButton(
                    onPressed: _toggleObscure,
                    icon: Icon(
                      _obscureText
                          ? Icons.visibility_off_outlined
                          : Icons.visibility_outlined,
                      color: AppColors.textHint,
                      size: 20,
                    ),
                    tooltip: _obscureText ? l10n.showPasswordTooltip : l10n.hidePasswordTooltip,
                  )
                : null,
            
            // المسافات الداخلية
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 18,
              vertical: 21,
            ),
            
            // الحدود
            border: _buildBorder(AppColors.fieldBorder),
            enabledBorder: _buildBorder(AppColors.fieldBorder),
            focusedBorder: _buildBorder(AppColors.fieldBorderFocus),
            errorBorder: _buildBorder(AppColors.error),
            focusedErrorBorder: _buildBorder(AppColors.error),
            disabledBorder: _buildBorder(AppColors.fieldBorder.withOpacity(0.5)),
            
            // نمط الخطأ
            errorStyle: AppTextStyles.error,
          ),
        ),
      ],
    );
  }
  
  // ═══════════════════════════════════════════════════════════
  // Helper Methods - دوال مساعدة
  // ═══════════════════════════════════════════════════════════
  
  /// بناء حدود الحقل
  OutlineInputBorder _buildBorder(Color color) {
    return OutlineInputBorder(
      borderRadius: BorderRadius.circular(30),
      borderSide: BorderSide(
        color: color,
        width: 2,
      ),
    );
  }
}
