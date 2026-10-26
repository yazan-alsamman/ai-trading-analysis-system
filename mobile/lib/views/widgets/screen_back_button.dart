import 'package:flutter/material.dart';

import '../../utils/app_colors.dart';

/// سهم رجوع علوي موحّد - بنفس ستايل وسلوك السهم المستخدم أصلًا بـ
/// [MarketNewsScreen] و[TradeScreen]، حتى ما نكرر نفس الكود بكل
/// شاشة بتحتاج زر رجوع بسيط بأعلى الصفحة.
///
/// نفس أيقونة `arrow_back_rounded` بكل اللغات (زي باقي أسهم الرجوع
/// بالتطبيق) - الـ [Row] وحده كافي يحط السهم بمكانه الصح (يمين
/// بالعربي RTL، يسار بالإنجليزي LTR)، بدون ما نغيّر شكل الأيقونة.
class ScreenBackButton extends StatelessWidget {
  const ScreenBackButton({super.key, this.onTap});

  /// دالة مخصصة عند الضغط - لو ما تم تمريرها، الافتراضي هو الرجوع
  /// خطوة وحدة بالـ Navigator المحلي (`maybePop`), بنفس نمط باقي
  /// شاشات التطبيق.
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(10, 6, 10, 0),
      child: Row(
        children: [
          InkWell(
            onTap: onTap ?? () => Navigator.of(context).maybePop(),
            borderRadius: BorderRadius.circular(14),
            child: const Padding(
              padding: EdgeInsets.all(12),
              child: Icon(
                Icons.arrow_back_rounded,
                color: AppColors.textPrimary,
                size: 22,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
