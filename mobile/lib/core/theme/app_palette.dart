import 'package:flutter/painting.dart';

/// القيم الخام لهوية "Ink, Aurum and Violet" (نفس web/src/styles/tokens.css)
///
/// ⚠️ CRITICAL: هاد الملف هو المكان الوحيد المسموح فيه قيم hex.
/// الشاشات والـ widgets ما بتقرأ من هون أبدًا - بتقرأ الأسماء الدلالية
/// عبر `context.colors` (راجع app_color_tokens.dart).
///
/// كل زوج نص/خلفية تم قياسه (WCAG 2.x) على كل سطح بالثيمين ≥ 4.5:1،
/// وحدود الحقول (outline) ≥ 3:1 - التفاصيل بـ mobile/DESIGN_SPEC.md §3.6.
abstract final class DarkPalette {
  // ═══════════════════════════════════════════════════════════
  // Surfaces - الأسطح (ink مع لمسة بنفسجية خفيفة)، من الأبعد للأقرب
  // ═══════════════════════════════════════════════════════════

  static const Color canvas = Color(0xFF07070A);
  static const Color card = Color(0xFF0D0D12);
  static const Color raised = Color(0xFF13131A);
  static const Color sheet = Color(0xFF1A1922);
  static const Color dialog = Color(0xFF22212B);
  static const Color inset = Color(0xFF0A0A0E);
  static const Color pressed = Color(0xFF17171F);
  static const Color selected = Color(0xFF1C1B26);

  static const Color hairline = Color(0xFF1E1D28);
  static const Color lineStrong = Color(0xFF2F2E3D);
  static const Color outline = Color(0xFF706F80);

  // ═══════════════════════════════════════════════════════════
  // Text - عائلة رمادي-لافندر وحدة (التسلسل بالدرجة مش باللون)
  // ═══════════════════════════════════════════════════════════

  static const Color fg = Color(0xFFF2F1F6);
  static const Color fg2 = Color(0xFFB0AFBF);
  static const Color fg3 = Color(0xFF8F8EA0);
  static const Color fgDisabled = Color(0xFF4D4C5A);

  // ═══════════════════════════════════════════════════════════
  // Roles - كل لون إلو معنى واحد بس
  // ═══════════════════════════════════════════════════════════

  static const Color primaryAction = Color(0xFFF2F1F6);
  static const Color onPrimaryAction = Color(0xFF0A0A0E);

  static const Color accent = Color(0xFFE2BD72);
  static const Color onAccent = Color(0xFF17110A);

  static const Color up = Color(0xFF2FC68F);
  static const Color down = Color(0xFFFF6F77);
  static const Color forecast = Color(0xFFB9A0FF);
  static const Color onForecast = Color(0xFF160F2B);

  static const Color danger = Color(0xFFFF8A4C);
  static const Color onDanger = Color(0xFF1A0B03);
  static const Color warning = Color(0xFFF2A541);
  static const Color info = Color(0xFF6CBCFF);

  static const double softAlpha = 0.13;
  static const Color overlay = Color(0xB8030306);
  static const Color shadow = Color(0xFF000000);

  // ═══════════════════════════════════════════════════════════
  // Atmosphere + Chart
  // ═══════════════════════════════════════════════════════════

  static const Color atmosAurum = Color(0x17E2BD72);
  static const Color atmosViolet = Color(0x14B9A0FF);
  static const Color gridLine = Color(0x09F2F1F6);

  static const Color chartGrid = Color(0xFF121219);
  static const Color chartCrosshair = Color(0xFF6A6979);
  static const Color chartInd1 = Color(0xFF6CBCFF);
  static const Color chartInd2 = Color(0xFFD99A5B);
  static const Color chartInd3 = Color(0xFF8F8EA0);
  static const double chartZoneAlpha = 0.10;
  static const double chartVolumeAlpha = 0.22;
  static const double chartForecastRegionAlpha = 0.05;
}

/// الثيم الفاتح "paper" - مصمّم لحالو (مش عكس الداكن): درجات أعمق
/// وأقل تشبّعًا حتى يبقى كل لون ≥ 4.5:1 على الأبيض وعلى الخلفية الدافئة.
abstract final class LightPalette {
  static const Color canvas = Color(0xFFF4F3EF);
  static const Color card = Color(0xFFFFFFFF);
  static const Color raised = Color(0xFFFFFFFF);
  static const Color sheet = Color(0xFFFFFFFF);
  static const Color dialog = Color(0xFFFFFFFF);
  static const Color inset = Color(0xFFF8F7F4);
  static const Color pressed = Color(0xFFEFEEE9);
  static const Color selected = Color(0xFFF2EDE1);

  static const Color hairline = Color(0xFFE4E2DB);
  static const Color lineStrong = Color(0xFFCBC8BF);
  static const Color outline = Color(0xFF7A7884);

  static const Color fg = Color(0xFF141318);
  static const Color fg2 = Color(0xFF4A4853);
  static const Color fg3 = Color(0xFF5E5C67);
  static const Color fgDisabled = Color(0xFFA9A7B0);

  static const Color primaryAction = Color(0xFF141318);
  static const Color onPrimaryAction = Color(0xFFFFFFFF);

  static const Color accent = Color(0xFF7C540D);
  static const Color onAccent = Color(0xFFFFFFFF);

  static const Color up = Color(0xFF066B47);
  static const Color down = Color(0xFFB3262F);
  static const Color forecast = Color(0xFF6534C8);
  static const Color onForecast = Color(0xFFFFFFFF);

  static const Color danger = Color(0xFFA33C0B);
  static const Color onDanger = Color(0xFFFFFFFF);
  static const Color warning = Color(0xFF7F4700);
  static const Color info = Color(0xFF0B5A96);

  static const double softAlpha = 0.10;
  static const Color overlay = Color(0x66141318);
  static const Color shadow = Color(0x29141318);

  static const Color atmosAurum = Color(0x1FC4963C);
  static const Color atmosViolet = Color(0x0F6534C8);
  static const Color gridLine = Color(0x0B141318);

  static const Color chartGrid = Color(0xFFEFEEE9);
  static const Color chartCrosshair = Color(0xFF8B8995);
  static const Color chartInd1 = Color(0xFF1B6CA8);
  static const Color chartInd2 = Color(0xFFA8661C);
  static const Color chartInd3 = Color(0xFF6B6977);
  static const double chartZoneAlpha = 0.08;
  static const double chartVolumeAlpha = 0.17;
  static const double chartForecastRegionAlpha = 0.045;
}
