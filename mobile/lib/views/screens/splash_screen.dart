import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../../utils/app_colors.dart';
import '../../utils/routes/app_navigator.dart';

// ═══════════════════════════════════════════════════════════
// Splash Screen - شاشة البداية
// ═══════════════════════════════════════════════════════════

/// أول شاشة تظهر لما التطبيق يفتح - خلفية بلون قريب من التطبيق
/// الأساسي (أفتح شوي من AppColors.bgDeep) وبس سهم الشعار (نفس أيقونة
/// [RegistrationScreen]، بدون الدائرة المتدرّجة) بلون فسفوري متوهج
/// بنص الشاشة.
///
/// بعد مدة قصيرة، بتنتقل تلقائيًا لشاشة التسجيل.
///
/// TODO: لما نربط الـ API الحقيقي ونفعّل auto-login (راجع
/// [AuthController.hasStoredSession])، هون هو المكان الصح لعمل
/// الفحص: لو في جلسة محفوظة سابقًا روح على الـ Home مباشرة (تخطي
/// شاشة التسجيل)، وإلا روح على شاشة التسجيل زي هلق بالضبط.
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  /// مدة ظهور شاشة البداية قبل الانتقال التلقائي
  static const _displayDuration = Duration(milliseconds: 1300);

  @override
  void initState() {
    super.initState();
    _navigateAfterDelay();
  }

  Future<void> _navigateAfterDelay() async {
    await Future.delayed(_displayDuration);
    if (!mounted) return;

    // pushNamedAndRemoveUntil (لا Push عادي) حتى شاشة السبلاش تنمسح
    // من شجرة التنقل بالكامل - زر الرجوع ما لازم يقدر يرجّع المستخدم
    // إلها أبدًا
    context.pushRegistrationAndClearStack();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      // لون أفتح شوي من AppColors.bgDeep الافتراضي - بس لهاي الشاشة،
      // ما لمسنا AppColors.bgDeep نفسها حتى ما نأثر على باقي التطبيق
      backgroundColor: const Color(0xFF071624),
      body: Center(
        child: Icon(
              Icons.trending_up_rounded,
              size: 130,
              color: AppColors.accentGreen,
              shadows: [
                Shadow(
                  color: AppColors.accentGreen.withOpacity(0.7),
                  blurRadius: 48,
                ),
              ],
            )
            .animate()
            .fadeIn(duration: 300.ms, curve: Curves.easeOut)
            .scale(
              begin: const Offset(0.7, 0.7),
              end: const Offset(1, 1),
              duration: 300.ms,
              curve: Curves.easeOutBack,
            ),
      ),
    );
  }
}
