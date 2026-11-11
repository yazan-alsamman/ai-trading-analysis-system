import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme/app_motion.dart';
import '../core/theme/app_theme.dart';
import '../core/theme/theme_mode_provider.dart';
import '../l10n/app_localizations.dart';
import '../providers/locale_provider.dart';
import 'router/app_router.dart';

// ═══════════════════════════════════════════════════════════
// Trading App - التطبيق الرئيسي
// ═══════════════════════════════════════════════════════════

class TradingApp extends ConsumerWidget {
  const TradingApp({super.key});
  
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // ملاحظة: ما في داعي لأي MultiProvider/ProviderScope هون - جذر
    // الـ Providers مضبوط مرة وحدة بـ main() (`runApp(ProviderScope(...))`)،
    // وكل الـ Providers المشتركة (auth / news / notifications / locale)
    // معرّفة بملف lib/providers/app_providers.dart (و
    // lib/providers/locale_provider.dart) وبتتفعّل تلقائيًا أول ما
    // شاشة تستخدمها.

    // الـ router بينبنى مرة وحدة (appRouterProvider): الـ auth guard وانتهاء
    // الجلسة (رجوع لـ Welcome ومسح الشجرة) جوّا الـ redirect تبعه.
    final router = ref.watch(appRouterProvider);

    // لغة التطبيق الحالية - أي تغيير عبر localeProvider.setLocale()
    // (من شاشة Profile) بيعيد بناء كامل الشجرة تلقائيًا بما فيها
    // اتجاه الواجهة (RTL/LTR)، لأنو Flutter بيحدد الـ Directionality
    // تلقائيًا حسب الـ locale المُمرّرة لـ MaterialApp تحت.
    final locale = ref.watch(localeProvider);
    final themeMode = ref.watch(themeModeProvider);
    final arabic = locale.languageCode == 'ar';

    // MaterialApp نفسه فوق الـ MediaQuery، فمنقرأ "تقليل الحركة" من
    // النظام مباشرة لنقرر إذا تبديل الثيم بيعمل cross-fade أو فوري.
    final reduceMotion = WidgetsBinding
        .instance.platformDispatcher.accessibilityFeatures.disableAnimations;

    return MaterialApp.router(
      // ═══════════════════════════════════════════════════════
      // App Configuration - إعدادات التطبيق
      // ═══════════════════════════════════════════════════════

      title: 'AI Trading Assistance',
      debugShowCheckedModeBanner: false,

      // ═══════════════════════════════════════════════════════
      // Localization - دعم اللغتين (عربي/إنجليزي)
      // ═══════════════════════════════════════════════════════
      //
      // locale: اللغة الحالية (محفوظة عبر localeProvider، راجع
      // lib/providers/locale_provider.dart).
      // Flutter بيضبط اتجاه الواجهة (RTL لما تكون 'ar'، LTR لما تكون
      // 'en') تلقائيًا حسب هاي القيمة - ما في داعي لأي Directionality
      // يدوي بأي شاشة.
      locale: locale,
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],

      // ═══════════════════════════════════════════════════════
      // Theme - الثيم
      // ═══════════════════════════════════════════════════════

      // الثيمين مبنيين من نفس الـ tokens (utils/theme/) - الخط العربي
      // وقواعد الـ tracking بتتبدّل حسب اللغة.
      theme: AppTheme.light(arabic: arabic),
      darkTheme: AppTheme.dark(arabic: arabic),
      themeMode: themeMode,
      themeAnimationDuration: reduceMotion ? Duration.zero : AppMotion.base,
      themeAnimationCurve: AppMotion.inOut,

      // أيقونات شريط الحالة/النظام عكس لون الثيم الحالي
      builder: (context, child) => AnnotatedRegion<SystemUiOverlayStyle>(
        value: AppTheme.overlayStyle(Theme.of(context).brightness),
        child: child!,
      ),

      // ═══════════════════════════════════════════════════════
      // Routing - نظام التنقل
      // ═══════════════════════════════════════════════════════
      //
      // go_router: جدول المسارات والـ shell بملف app/router/app_router.dart -
      // أول شاشة هي الـ splash، وبعدها Welcome (بدون جلسة) أو الرئيسية. أي
      // تنقّل لاحق بيصير عبر context.pushX() من app/router/app_navigator.dart.
      routerConfig: router,
    );
  }
}
