import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app/app.dart';
import 'core/storage/preferences_provider.dart';

// ═══════════════════════════════════════════════════════════
// Main Entry Point - نقطة الدخول الرئيسية
// ═══════════════════════════════════════════════════════════

Future<void> main() async {
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
  //
  // لون أيقونات الشريطين (فاتح/غامق) صار يتبع الثيم الحالي - بينضبط
  // بـ [TradingApp] تحت عبر AnnotatedRegion (AppTheme.overlayStyle).
  SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);

  _registerFontLicenses();

  // اختيار الثيم (فاتح/داكن/نظام) بينقرأ قبل أول فريم حتى ما يطلع
  // التطبيق بالثيم الغلط للحظة (راجع core/theme/theme_mode_provider.dart).
  final prefs = await SharedPreferences.getInstance();


  // ProviderScope هو جذر أي تطبيق Riverpod - بيحمل كل الـ Providers
  // (معادل [MultiProvider] بمرحلة Provider، بس بدون داعي نعدد فيه كل
  // Provider يدويًا: كل Provider معرّف بملف lib/providers/app_providers.dart
  // وبيتفعّل تلقائيًا أول ما شاشة تستخدمه عبر ref.watch/ref.read).
  runApp(ProviderScope(
    overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
    child: const TradingApp(),
  ));
}

/// الخطوط مضمّنة بالتطبيق برخصة OFL - لازم رخصها تبيّن بصفحة التراخيص
void _registerFontLicenses() {
  const fonts = {
    'Inter': 'assets/fonts/inter/OFL.txt',
    'JetBrains Mono': 'assets/fonts/jetbrains_mono/OFL.txt',
    'Instrument Serif': 'assets/fonts/instrument_serif/OFL.txt',
    'IBM Plex Sans Arabic': 'assets/fonts/ibm_plex_sans_arabic/OFL.txt',
    'Noto Naskh Arabic': 'assets/fonts/noto_naskh_arabic/OFL.txt',
  };
  LicenseRegistry.addLicense(() async* {
    for (final entry in fonts.entries) {
      final text = await rootBundle.loadString(entry.value);
      yield LicenseEntryWithLineBreaks([entry.key], text);
    }
  });
}
