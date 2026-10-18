import 'package:flutter/material.dart';
import '../models/market_item_model.dart';
import '../views/widgets/market_picker_sheet.dart';
import 'mock_market_items.dart';
import 'routes/app_navigator.dart';

/// مفتاح الـ Navigator الرئيسي (الجذر) للتطبيق كله.
///
/// ليش لازم هالمفتاح؟ قبل كان كل زر بالـ navbar بيعتمد على
/// `Navigator.of(context)` المحلي لكل شاشة، وهاد كان بيسبب مشكلتين:
/// 1) بعض الشاشات كانت تستخدم `maybePop()` (بيرجع درجة وحدة بس) بدل
///    `popUntil(isFirst)` (بيرجع لجذر التطبيق)، فلو كنت غارق كذا شاشة
///    داخل بعضها، زر "Home" ما كان يرجّعك عالهوم فعليًا.
/// 2) بعض الأزرار (Markets مثلاً) كانت أصلًا غير مفعّلة إلا من داخل
///    HomeScreen نفسها.
///
/// باستخدام [appNavigatorKey] بدل `Navigator.of(context)` المحلي،
/// أي زر بالـ navbar - من أي شاشة وبأي عمق بشجرة التنقل - بيقدر
/// يتحكم بجذر التطبيق مباشرة، فبيشتغل فورًا بغض النظر وين كنت.
final GlobalKey<NavigatorState> appNavigatorKey = GlobalKey<NavigatorState>();

/// فهارس عناصر شريط التنقل السفلي - نفس ترتيب
/// [AppBottomNav.defaultItems] بالضبط.
abstract final class AppNavIndex {
  static const int home = 0;
  static const int markets = 1;
  static const int ai = 2;
  static const int news = 3;
  static const int profile = 4;
}

/// المعالج الموحّد لأي ضغطة على شريط التنقل السفلي، مشترك بين كل
/// شاشات التطبيق.
///
/// بغض النظر عن الشاشة الحالية أو قديش عميقة شجرة التنقل هلق، أول
/// خطوة دايمًا هي الرجوع لجذر التطبيق (HomeScreen) عبر
/// [appNavigatorKey]، وبعدها - إذا الزر المضغوط بده شاشة إضافية
/// (Markets / AI / News) - منفتحها فوق الـ Home مباشرة. هيك كل زر
/// "ياخد" فورًا من أي مكان، دون ما يحتاج المستخدم يرجع عالهوم يدويًا
/// قبل ما يضغط.
Future<void> handleGlobalBottomNavTap(int index) async {
  final navigator = appNavigatorKey.currentState;
  if (navigator == null) return;

  // الخطوة المشتركة الأولى لكل الأزرار: الرجوع لجذر التطبيق مهما كان
  // عمق شجرة التنقل الحالية.
  navigator.popUntil((route) => route.isFirst);

  switch (index) {
    case AppNavIndex.home:
      // وصلنا عالهوم بالسطر فوق - ما في شي إضافي مطلوب.
      return;

    case AppNavIndex.markets:
      final rootContext = navigator.context;
      final selected = await showModalBottomSheet<MarketItemModel>(
        context: rootContext,
        backgroundColor: Colors.transparent,
        isScrollControlled: true,
        builder: (_) => const MarketPickerSheet(items: kDefaultMarketItems),
      );
      if (selected != null) {
        await rootContext.pushTrade(selected);
      }
      return;

    case AppNavIndex.ai:
      await navigator.context.pushAiAssistant();
      return;

    case AppNavIndex.news:
      await navigator.context.pushMarketNews();
      return;

    case AppNavIndex.profile:
      await navigator.context.pushProfile();
      return;

    default:
      return;
  }
}
