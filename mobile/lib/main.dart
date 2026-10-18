import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'l10n/app_localizations.dart';
import 'providers/locale_provider.dart';
import 'utils/app_colors.dart';
import 'utils/app_navigation.dart';
import 'utils/app_text_styles.dart';
import 'utils/routes/app_routes.dart';

// ═══════════════════════════════════════════════════════════
// Main Entry Point - نقطة الدخول الرئيسية
// ═══════════════════════════════════════════════════════════

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  
  // ضبط اتجاه الشاشة - عمودي فقط
  SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
  ]);
  
  // ضبط شريط الحالة وشريط التنقل السفلي (النظام)
  //
  // ⚠️ IMPORTANT (السبب الحقيقي للخط الأبيض): بدءًا من أندرويد 15
  // (targetSdk 35)، أندرويد بيفرض وضع edge-to-edge بشكل إجباري
  // وبيتجاهل تمامًا systemNavigationBarColor و
  // systemNavigationBarDividerColor - صارت deprecated no-op. يعني
  // مهما حددنا فيهن لون، أندرويد رح يرسم شريط النظام بلونه الافتراضي
  // (شفاف/فاتح) فوق تطبيقنا، وهيك يطلع خط أبيض رفيع بغض النظر شو
  // اللون المحدد.
  //
  // الحل: منخلي شريط النظام شفاف بالكامل (Colors.transparent) ومنفعّل
  // edge-to-edge صراحة، وهيك تطبيقنا نفسه هو يلي بيرسم لونه الحقيقي
  // تحت شريط النظام (AppBottomNav بملف app_bottom_nav.dart أصلاً
  // مبني صح لهيك: خلفيته الملوّنة بتغطي كامل عرض/طول الـ Container،
  // و[SafeArea] جواته بس بتحط padding للمحتوى (الأيقونات) مش
  // بتقص الخلفية - فلما شريط النظام يصير شفاف، خلفية الـ navbar
  // بتظهر كاملة تحته بدون أي فجوة).
  SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
      systemStatusBarContrastEnforced: false,
      systemNavigationBarColor: Colors.transparent,
      systemNavigationBarIconBrightness: Brightness.light,
      systemNavigationBarContrastEnforced: false,
      systemNavigationBarDividerColor: Colors.transparent,
    ),
  );
  
  // ProviderScope هو جذر أي تطبيق Riverpod - بيحمل كل الـ Providers
  // (معادل [MultiProvider] بمرحلة Provider، بس بدون داعي نعدد فيه كل
  // Provider يدويًا: كل Provider معرّف بملف lib/providers/app_providers.dart
  // وبيتفعّل تلقائيًا أول ما شاشة تستخدمه عبر ref.watch/ref.read).
  runApp(const ProviderScope(child: TradingApp()));
}

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

    // لغة التطبيق الحالية - أي تغيير عبر localeProvider.setLocale()
    // (من شاشة Profile) بيعيد بناء كامل الشجرة تلقائيًا بما فيها
    // اتجاه الواجهة (RTL/LTR)، لأنو Flutter بيحدد الـ Directionality
    // تلقائيًا حسب الـ locale المُمرّرة لـ MaterialApp تحت.
    final locale = ref.watch(localeProvider);

    return MaterialApp(
      // ═══════════════════════════════════════════════════════
      // App Configuration - إعدادات التطبيق
      // ═══════════════════════════════════════════════════════

      title: 'TradeX',
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

      // مفتاح الـ Navigator الرئيسي - بيسمح لشريط التنقل السفلي
      // (AppBottomNav) إنو يتحكم بالتنقّل من أي شاشة مباشرة، بدل
      // ما يعتمد على الـ context المحلي لكل شاشة على حدة.
      // التفاصيل بملف utils/app_navigation.dart.
      navigatorKey: appNavigatorKey,

      // ═══════════════════════════════════════════════════════
      // Theme - الثيم
      // ═══════════════════════════════════════════════════════

      theme: _buildAppTheme(),

      // ═══════════════════════════════════════════════════════
      // Routing - نظام التنقل
      // ═══════════════════════════════════════════════════════
      //
      // كل أسماء المسارات ومنطق بناء الشاشات مركزي بملف
      // utils/routes/app_routes.dart - أول شاشة يشوفها المستخدم
      // هي شاشة التسجيل (AppRoutes.registration)، وأي تنقّل لاحق
      // بصير عبر context.pushX() من utils/routes/app_navigator.dart
      // (راجع أي شاشة، مثلاً login_screen.dart، لأمثلة الاستخدام).

      initialRoute: AppRoutes.splash,
      onGenerateRoute: AppRoutes.onGenerateRoute,
    );
  }
  
  // ═══════════════════════════════════════════════════════════
  // Theme Builder - بناء الثيم
  // ═══════════════════════════════════════════════════════════
  
  /// بناء ثيم التطبيق الكامل
  ThemeData _buildAppTheme() {
    return ThemeData.dark().copyWith(
      // ══════════════════════════════════════════════════════
      // Colors - الألوان
      // ══════════════════════════════════════════════════════
      
      scaffoldBackgroundColor: AppColors.bgDeep,
      primaryColor: AppColors.accentGreen,
      colorScheme: const ColorScheme.dark(
        primary: AppColors.accentGreen,
        secondary: AppColors.accentCyan,
        surface: AppColors.bgSurface,
        background: AppColors.bgDeep,
        error: AppColors.error,
      ),
      
      // ══════════════════════════════════════════════════════
      // Typography - الطباعة
      // ══════════════════════════════════════════════════════
      
      textTheme: const TextTheme(
        displayLarge: AppTextStyles.heading1,
        displayMedium: AppTextStyles.heading2,
        displaySmall: AppTextStyles.heading3,
        bodyLarge: AppTextStyles.bodyLarge,
        bodyMedium: AppTextStyles.bodyMedium,
        bodySmall: AppTextStyles.bodySmall,
        labelLarge: AppTextStyles.button,
        labelMedium: AppTextStyles.label,
        labelSmall: AppTextStyles.labelSmall,
      ),
      
      // ══════════════════════════════════════════════════════
      // App Bar Theme - ثيم شريط التطبيق
      // ══════════════════════════════════════════════════════
      
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        titleTextStyle: AppTextStyles.heading2,
        iconTheme: IconThemeData(color: AppColors.textPrimary),
        systemOverlayStyle: SystemUiOverlayStyle(
          statusBarColor: Colors.transparent,
          statusBarIconBrightness: Brightness.light,
        ),
      ),
      
      // ══════════════════════════════════════════════════════
      // Card Theme - ثيم الكروت
      // ══════════════════════════════════════════════════════
      
        cardTheme: CardThemeData(
        color: AppColors.bgSurface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
      ),
      
      // ══════════════════════════════════════════════════════
      // Elevated Button Theme - ثيم الأزرار المرفوعة
      // ══════════════════════════════════════════════════════
      
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.accentGreen,
          foregroundColor: AppColors.buttonText,
          textStyle: AppTextStyles.button,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(30),
          ),
          padding: const EdgeInsets.symmetric(
            horizontal: 32,
            vertical: 16,
          ),
        ),
      ),
      
      // ══════════════════════════════════════════════════════
      // Text Button Theme - ثيم الأزرار النصية
      // ══════════════════════════════════════════════════════
      
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: AppColors.textLink,
          textStyle: AppTextStyles.link,
        ),
      ),
      
      // ══════════════════════════════════════════════════════
      // Input Decoration Theme - ثيم حقول الإدخال
      // ══════════════════════════════════════════════════════
      
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.bgMid,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 18,
          vertical: 21,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(30),
          borderSide: const BorderSide(
            color: AppColors.fieldBorder,
            width: 2,
          ),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(30),
          borderSide: const BorderSide(
            color: AppColors.fieldBorder,
            width: 2,
          ),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(30),
          borderSide: const BorderSide(
            color: AppColors.fieldBorderFocus,
            width: 2,
          ),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(30),
          borderSide: const BorderSide(
            color: AppColors.error,
            width: 2,
          ),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(30),
          borderSide: const BorderSide(
            color: AppColors.error,
            width: 2,
          ),
        ),
        hintStyle: AppTextStyles.fieldHint,
        labelStyle: AppTextStyles.label,
        errorStyle: AppTextStyles.error,
      ),
      
      // ══════════════════════════════════════════════════════
      // Icon Theme - ثيم الأيقونات
      // ══════════════════════════════════════════════════════
      
      iconTheme: const IconThemeData(
        color: AppColors.textSecondary,
        size: 24,
      ),
      
      // ══════════════════════════════════════════════════════
      // Divider Theme - ثيم الفواصل
      // ══════════════════════════════════════════════════════
      
      dividerTheme: const DividerThemeData(
        color: AppColors.fieldBorder,
        thickness: 1,
        space: 1,
      ),
    );
  }
}
