import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';

/// الحركة: قصيرة وهادفة (150-400ms، أبدًا أكتر)
///
/// قواعد ثابتة (DESIGN_SPEC.md §7 + قرار 2026-10-20):
/// - الأسعار الحيّة بتتحدّث فورًا بدون أي حركة أو وميض.
/// - الإجماليات ونتائج التحليل بس بتعمل tween عند التحميل/التحديث.
/// - الرسم البياني بينرسم مرة وحدة (عند التحميل أو تغيير الإطار الزمني).
/// - لما المستخدم يفعّل "تقليل الحركة" كل شي بيوصل لحالته النهائية فورًا
///   - استخدم [MotionContext.motion] بدل `Duration` مباشرة.
abstract final class AppMotion {
  // ═══════════════════════════════════════════════════════════
  // Durations
  // ═══════════════════════════════════════════════════════════

  /// ضغط، toggle، chip
  static const Duration fast = Duration(milliseconds: 150);

  /// fade-through بين التبويبات، إضافة عنصر لقائمة
  static const Duration base = Duration(milliseconds: 200);

  /// bottom sheets، dialogs
  static const Duration medium = Duration(milliseconds: 250);

  /// الانتقال بين الشاشات
  static const Duration page = Duration(milliseconds: 300);

  /// الحد الأقصى: Hero، رسم الشارت، tween الأرقام
  static const Duration emphasis = Duration(milliseconds: 400);

  /// دورة نقاط "المساعد عم يكتب" - الحلقة الوحيدة المسموحة (نفس الويب 1100ms)
  static const Duration typingLoop = Duration(milliseconds: 1100);

  // ═══════════════════════════════════════════════════════════
  // Curves - نفس منحنيات الويب. ممنوع linear.
  // ═══════════════════════════════════════════════════════════

  /// أي شي داخل: بداية سريعة واستقرار طويل
  static const Curve out = Cubic(0.22, 1, 0.36, 1);

  /// أي شي طالع
  static const Curve exit = Cubic(0.55, 0, 1, 0.45);

  /// حركة من مكان لمكان على الشاشة
  static const Curve inOut = Cubic(0.65, 0, 0.35, 1);

  /// تجاوز خفيف - لتأكيد التحديد بس (chip / like / segment)
  static const Curve spring = Cubic(0.34, 1.4, 0.64, 1);

  // ═══════════════════════════════════════════════════════════
  // Stagger - للقوائم عند أول ظهور بس، وأول [staggerMaxItems] عناصر
  // ═══════════════════════════════════════════════════════════

  static const Duration staggerStep = Duration(milliseconds: 40);
  static const int staggerMaxItems = 8;

  /// مسافة "الطلوع" للعنصر الداخل
  static const double rise = 10;

  /// تأخير العنصر رقم [index] بالقائمة، أو null إذا ما لازم يتحرّك
  static Duration? staggerDelay(int index) => index < staggerMaxItems
      ? staggerStep * index
      : null;
}

extension MotionContext on BuildContext {
  /// true لما المستخدم مفعّل "إزالة الحركة" من إعدادات الجهاز
  bool get reduceMotion => MediaQuery.maybeDisableAnimationsOf(this) ?? false;

  /// المدة الفعلية: صفر لما الحركة مقلّلة
  Duration motion(Duration duration) =>
      reduceMotion ? Duration.zero : duration;
}

/// اهتزازات خفيفة على الإجراءات المهمة بس
abstract final class AppHaptics {
  /// تبويب، segment، chip، crosshair بيلقط شمعة
  static Future<void> selection() => HapticFeedback.selectionClick();

  /// تفعيل pull-to-refresh، ضغطة مطوّلة
  static Future<void> light() => HapticFeedback.lightImpact();

  /// تأكيد الإجراء الرئيسي
  static Future<void> confirm() => HapticFeedback.mediumImpact();
}
