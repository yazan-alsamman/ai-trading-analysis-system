import 'package:flutter/material.dart';

import 'app_color_tokens.dart';

/// الطباعة - نفس هوية الويب، بمقاسات موبايل (النص الأساسي 16 بدل 14،
/// و12 هو الحد الأدنى لأي نص بالتطبيق)
///
/// - Instrument Serif: العناوين التحريرية بس (splash / auth / ترحيب Home)،
///   أبدًا جوّا لوحات البيانات.
/// - Inter: كل النصوص.
/// - JetBrains Mono: كل رقم مالي (سعر، نسبة، مبلغ، وقت) - أرقام بعرض
///   ثابت حتى ما "تنط" القيمة لما تتحدّث.
///
/// خطوط الويب ما فيها حروف عربية، فكل نمط إلو fallback عربي:
/// IBM Plex Sans Arabic للنصوص و Noto Naskh Arabic للعناوين التحريرية.
abstract final class AppFonts {
  static const String sans = 'Inter';
  static const String mono = 'JetBrainsMono';
  static const String display = 'InstrumentSerif';
  static const String sansArabic = 'IBMPlexSansArabic';
  static const String displayArabic = 'NotoNaskhArabic';

  static const List<String> sansFallback = [sansArabic];
  static const List<String> displayFallback = [displayArabic, sansArabic];
}

abstract final class AppTypography {
  /// Inter: cv11 (حرف a بطابق واحد) + ss01 (أرقام مفتوحة) - نفس الويب
  static const List<FontFeature> _interFeatures = [
    FontFeature('cv11'),
    FontFeature('ss01'),
  ];

  static const List<FontFeature> _numFeatures = [
    FontFeature.tabularFigures(),
    FontFeature.slashedZero(),
  ];

  static TextStyle _sans(double size, double height, FontWeight weight,
          Color color) =>
      TextStyle(
        fontFamily: AppFonts.sans,
        fontFamilyFallback: AppFonts.sansFallback,
        fontSize: size,
        height: height / size,
        fontWeight: weight,
        color: color,
        fontFeatures: _interFeatures,
      );

  /// العناوين التحريرية: الخط العربي (Naskh) محتاج سطر أعلى من الـ serif
  static TextStyle _display(double size, double height, Color color,
          {required bool arabic}) =>
      TextStyle(
        fontFamily: AppFonts.display,
        fontFamilyFallback: AppFonts.displayFallback,
        fontSize: size,
        height: (arabic ? height * 1.3 : height) / size,
        fontWeight: FontWeight.w400,
        letterSpacing: arabic ? 0 : size * -0.015,
        color: color,
      );

  static TextStyle _mono(double size, double height, FontWeight weight,
          Color color) =>
      TextStyle(
        fontFamily: AppFonts.mono,
        fontFamilyFallback: AppFonts.sansFallback,
        fontSize: size,
        height: height / size,
        fontWeight: weight,
        letterSpacing: size * -0.01,
        color: color,
        fontFeatures: _numFeatures,
      );

  /// سلّم Material 3 كامل (الشاشات بتقرأه عبر `context.textTheme`)
  static TextTheme textTheme(AppColorTokens c, {required bool arabic}) {
    return TextTheme(
      displayLarge: _display(40, 44, c.fg, arabic: arabic),
      displayMedium: _display(32, 38, c.fg, arabic: arabic),
      displaySmall: _display(26, 32, c.fg, arabic: arabic),
      headlineLarge: _sans(28, 36, FontWeight.w600, c.fg),
      headlineMedium: _sans(26, 34, FontWeight.w600, c.fg),
      headlineSmall: _sans(24, 32, FontWeight.w600, c.fg),
      titleLarge: _sans(20, 28, FontWeight.w600, c.fg),
      titleMedium: _sans(16, 24, FontWeight.w600, c.fg),
      titleSmall: _sans(14, 20, FontWeight.w600, c.fg),
      bodyLarge: _sans(16, 24, FontWeight.w400, c.fg),
      bodyMedium: _sans(14, 20, FontWeight.w400, c.fg2),
      bodySmall: _sans(12, 16, FontWeight.w400, c.fg3),
      labelLarge: _sans(14, 20, FontWeight.w600, c.fg),
      labelMedium: _sans(12, 16, FontWeight.w500, c.fg2),
      labelSmall: _sans(12, 16, FontWeight.w500, c.fg3),
    );
  }

  static AppTextTokens tokens(AppColorTokens c, {required bool arabic}) {
    return AppTextTokens(
      // الـ tracking والأحرف الكبيرة بيكسروا وصل الحروف العربية، فبالعربي
      // منلغيهن ومنستخدم الخط العربي العادي بدل الـ mono.
      eyebrow: arabic
          ? _sans(12, 16, FontWeight.w600, c.fg3)
          : TextStyle(
              fontFamily: AppFonts.mono,
              fontFamilyFallback: AppFonts.sansFallback,
              fontSize: 12,
              height: 16 / 12,
              fontWeight: FontWeight.w500,
              letterSpacing: 12 * 0.16,
              color: c.fg3,
            ),
      eyebrowUppercase: !arabic,
      displayMuted: _display(32, 38, c.fg2, arabic: arabic)
          .copyWith(fontStyle: arabic ? FontStyle.normal : FontStyle.italic),
      numHero: _mono(32, 36, FontWeight.w600, c.fg),
      numLarge: _mono(22, 28, FontWeight.w600, c.fg),
      num: _mono(16, 24, FontWeight.w500, c.fg),
      numSmall: _mono(13, 18, FontWeight.w500, c.fg2),
    );
  }
}

/// أنماط الهوية الإضافية يلي ما إلها مكان بسلّم Material
///
/// الاستخدام: `context.type.numHero`، `context.type.eyebrow`...
@immutable
class AppTextTokens extends ThemeExtension<AppTextTokens> {
  const AppTextTokens({
    required this.eyebrow,
    required this.eyebrowUppercase,
    required this.displayMuted,
    required this.numHero,
    required this.numLarge,
    required this.num,
    required this.numSmall,
  });

  /// `04 · RISK MANAGEMENT` - قبل الأقسام والعناوين
  final TextStyle eyebrow;

  /// false بالعربي (ما في أحرف كبيرة)
  final bool eyebrowUppercase;

  /// الجملة الثانية الخافتة بالعنوان التحريري ("...*to read the markets.*")
  final TextStyle displayMuted;

  /// الرقم البطل (إجمالي المحفظة، سعر الأداة بأعلى الشاشة)
  final TextStyle numHero;
  final TextStyle numLarge;

  /// كل سعر / نسبة / مبلغ عادي
  final TextStyle num;
  final TextStyle numSmall;

  @override
  AppTextTokens copyWith() => this;

  @override
  AppTextTokens lerp(ThemeExtension<AppTextTokens>? other, double t) {
    if (other is! AppTextTokens) return this;
    TextStyle l(TextStyle a, TextStyle b) => TextStyle.lerp(a, b, t)!;
    return AppTextTokens(
      eyebrow: l(eyebrow, other.eyebrow),
      eyebrowUppercase: t < 0.5 ? eyebrowUppercase : other.eyebrowUppercase,
      displayMuted: l(displayMuted, other.displayMuted),
      numHero: l(numHero, other.numHero),
      numLarge: l(numLarge, other.numLarge),
      num: l(num, other.num),
      numSmall: l(numSmall, other.numSmall),
    );
  }
}
