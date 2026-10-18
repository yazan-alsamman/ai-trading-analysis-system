import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../utils/app_colors.dart';

/// مكون إدخال OTP المخصص
/// 
/// يعرض 5 حقول منفصلة لإدخال رمز التحقق
/// مع auto-focus تلقائي بين الحقول
class OtpInputWidget extends StatefulWidget {
  const OtpInputWidget({
    super.key,
    required this.onCompleted,
    this.length = 5,
  });
  
  /// عدد خانات OTP
  final int length;
  
  /// دالة تُستدعى عند اكتمال الإدخال
  final void Function(String code) onCompleted;
  
  @override
  State<OtpInputWidget> createState() => _OtpInputWidgetState();
}

class _OtpInputWidgetState extends State<OtpInputWidget> {
  // ═══════════════════════════════════════════════════════════
  // State - الحالة
  // ═══════════════════════════════════════════════════════════
  
  /// Controllers لكل حقل
  late final List<TextEditingController> _controllers;
  
  /// Focus nodes لكل حقل
  late final List<FocusNode> _focusNodes;
  
  /// الحقل النشط حالياً
  int _currentIndex = 0;
  
  // ═══════════════════════════════════════════════════════════
  // Lifecycle - دورة الحياة
  // ═══════════════════════════════════════════════════════════
  
  @override
  void initState() {
    super.initState();
    
    // إنشاء controllers و focus nodes
    _controllers = List.generate(
      widget.length,
      (_) => TextEditingController(),
    );
    
    _focusNodes = List.generate(
      widget.length,
      (_) => FocusNode(),
    );
    
    // تفعيل أول حقل
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_focusNodes.isNotEmpty) {
        _focusNodes[0].requestFocus();
      }
    });
  }
  
  @override
  void dispose() {
    // تنظيف الموارد
    for (var controller in _controllers) {
      controller.dispose();
    }
    for (var node in _focusNodes) {
      node.dispose();
    }
    super.dispose();
  }
  
  // ═══════════════════════════════════════════════════════════
  // Methods - الدوال
  // ═══════════════════════════════════════════════════════════
  
  /// الانتقال للحقل التالي
  void _nextField(int index) {
    if (index < widget.length - 1) {
      _currentIndex = index + 1;
      _focusNodes[_currentIndex].requestFocus();
    } else {
      // آخر حقل - إخفاء لوحة المفاتيح والتحقق
      _focusNodes[index].unfocus();
      _checkCompletion();
    }
  }
  
  /// الرجوع للحقل السابق
  void _previousField(int index) {
    if (index > 0) {
      _currentIndex = index - 1;
      _controllers[_currentIndex].clear();
      _focusNodes[_currentIndex].requestFocus();
    }
  }
  
  /// التحقق من اكتمال الكود
  void _checkCompletion() {
    final code = _controllers.map((c) => c.text).join();
    if (code.length == widget.length) {
      widget.onCompleted(code);
    }
  }
  
  /// مسح جميع الحقول
  void clear() {
    for (var controller in _controllers) {
      controller.clear();
    }
    _currentIndex = 0;
    if (_focusNodes.isNotEmpty) {
      _focusNodes[0].requestFocus();
    }
  }
  
  // ═══════════════════════════════════════════════════════════
  // Build - البناء
  // ═══════════════════════════════════════════════════════════
  
  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: List.generate(
        widget.length,
        (index) => _buildOtpField(index),
      ),
    );
  }
  
  /// بناء حقل OTP واحد
  Widget _buildOtpField(int index) {
    return SizedBox(
      width: 56,
      height: 64,
      child: TextField(
        controller: _controllers[index],
        focusNode: _focusNodes[index],
        textAlign: TextAlign.center,
        style: const TextStyle(
          fontSize: 24,
          fontWeight: FontWeight.w600,
          color: AppColors.textPrimary,
        ),
        keyboardType: TextInputType.number,
        maxLength: 1,
        
        // السماح بالأرقام فقط
        inputFormatters: [
          FilteringTextInputFormatter.digitsOnly,
        ],
        
        decoration: InputDecoration(
          counterText: '',
          filled: true,
          fillColor: AppColors.bgMid,
          contentPadding: EdgeInsets.zero,
          
          // الحدود
          border: _buildBorder(AppColors.fieldBorder),
          enabledBorder: _buildBorder(AppColors.fieldBorder),
          focusedBorder: _buildBorder(AppColors.fieldBorderFocus),
          errorBorder: _buildBorder(AppColors.error),
        ),
        
        onChanged: (value) {
          if (value.isNotEmpty) {
            // الانتقال للحقل التالي
            _nextField(index);
          } else if (value.isEmpty && index > 0) {
            // إذا تم المسح، الرجوع للحقل السابق
            _previousField(index);
          }
        },
      ),
    );
  }
  
  /// بناء حدود الحقل
  OutlineInputBorder _buildBorder(Color color) {
    return OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: BorderSide(
        color: color,
        width: 2,
      ),
    );
  }
}
