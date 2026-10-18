// اختبار أساسي (Smoke Test) للتأكد إنو التطبيق بيبلش ويرسم أول شاشة
// بدون أي استثناء (Exception).
//
// ⚠️ ملاحظة: هاد الملف كان أصلًا القالب الافتراضي يلي بينزل مع أي
// مشروع Flutter جديد (`flutter create`) - بيختبر تطبيق عداد وهمي
// (`MyApp` مع زر "+") مالوش أي علاقة فعلية بتطبيق TradeX. تم استبداله
// هون باختبار حقيقي على [TradingApp] (الكلاس الفعلي بملف main.dart).

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/main.dart';

void main() {
  testWidgets('TradeX app builds and shows the splash/auth flow',
      (WidgetTester tester) async {
    // نفس طريقة تشغيل التطبيق الحقيقية بـ main.dart: TradingApp لازم
    // تكون ملفوفة بـ ProviderScope حتى تقدر تقرأ الـ Providers
    // المشتركة (auth / locale / news / notifications).
    await tester.pumpWidget(const ProviderScope(child: TradingApp()));

    // فريم واحد بس لبناء أول شجرة (شاشة Splash).
    await tester.pump();

    // ⚠️ SplashScreen فيها Future.delayed(1300ms) بتنقل تلقائيًا لشاشة
    // التسجيل + انيميشن fadeIn/scale (300ms). لازم نـ"نقدّم" الوقت
    // الوهمي (Fake Clock) يدويًا حتى تنفّذ هالمؤقتات وتخلص قبل ما
    // ينتهي الاختبار - وإلا Flutter Test بيرمي خطأ "Timer is still
    // pending" (بالضبط الخطأ يلي طلع قبل ما نضيف هالسطرين).
    await tester.pump(const Duration(milliseconds: 1400)); // مؤقت الانتقال
    await tester.pump(const Duration(milliseconds: 400)); // انيميشن الدخول

    // التأكد إنو الشجرة بنت نفسها بنجاح بدون رمي أي استثناء - كافي
    // كـ Smoke Test أساسي بدون الاعتماد على نص ثابت معيّن (يلي ممكن
    // يتغيّر حسب اللغة الحالية أو حالة تسجيل الدخول المحفوظة).
    expect(tester.takeException(), isNull);
  });
}
