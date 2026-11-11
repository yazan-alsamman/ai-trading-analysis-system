import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'app_color_tokens.dart';
import 'app_dimens.dart';
import 'app_motion.dart';
import 'app_palette.dart';
import 'app_typography.dart';

/// بناء الثيمين (Material 3) من الـ tokens
///
/// كل مكوّن Material (أزرار، حقول، sheets، شريط التنقل...) متظبّط هون
/// مرة وحدة، فالشاشات بتورث الشكل الصح بدون أي ستايل يدوي.
///
/// أسطح الداكن بتعلى بالدرجة (سلّم من 5 درجات، بدون ظلال)، والفاتح
/// بطاقات بيضا مع خط رفيع. الـ surfaceTint ملغى حتى تضل الأسطح محايدة.
abstract final class AppTheme {
  static ThemeData light({bool arabic = false}) =>
      _build(Brightness.light, AppColorTokens.light, AppColorTokens.dark,
          arabic: arabic);

  static ThemeData dark({bool arabic = false}) =>
      _build(Brightness.dark, AppColorTokens.dark, AppColorTokens.light,
          arabic: arabic);

  /// شريط الحالة وشريط النظام شفافين، والأيقونات عكس لون الثيم
  static SystemUiOverlayStyle overlayStyle(Brightness brightness) {
    final icons =
        brightness == Brightness.dark ? Brightness.light : Brightness.dark;
    return SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: icons,
      statusBarBrightness: brightness,
      systemStatusBarContrastEnforced: false,
      systemNavigationBarColor: Colors.transparent,
      systemNavigationBarIconBrightness: icons,
      systemNavigationBarContrastEnforced: false,
      systemNavigationBarDividerColor: Colors.transparent,
    );
  }

  static ThemeData _build(
    Brightness brightness,
    AppColorTokens c,
    AppColorTokens inverse, {
    required bool arabic,
  }) {
    final isDark = brightness == Brightness.dark;
    final shadow = isDark ? DarkPalette.shadow : LightPalette.shadow;
    final text = AppTypography.textTheme(c, arabic: arabic);
    final type = AppTypography.tokens(c, arabic: arabic);

    final scheme = ColorScheme(
      brightness: brightness,
      // الذهبي = الهوية والتحديد (مؤشر التنقل، switches، focus، progress)
      primary: c.accent,
      onPrimary: c.onAccent,
      primaryContainer: Color.alphaBlend(c.accentSoft, c.card),
      onPrimaryContainer: c.accent,
      secondary: c.fg2,
      onSecondary: c.canvas,
      secondaryContainer: c.selected,
      onSecondaryContainer: c.fg,
      // البنفسجي = مخرجات النموذج بس
      tertiary: c.forecast,
      onTertiary: c.onForecast,
      tertiaryContainer: Color.alphaBlend(c.forecastSoft, c.card),
      onTertiaryContainer: c.forecast,
      error: c.danger,
      onError: c.onDanger,
      errorContainer: Color.alphaBlend(c.dangerSoft, c.card),
      onErrorContainer: c.danger,
      surface: c.canvas,
      onSurface: c.fg,
      onSurfaceVariant: c.fg2,
      surfaceContainerLowest: isDark ? c.inset : c.card,
      surfaceContainerLow: c.card,
      surfaceContainer: c.raised,
      surfaceContainerHigh: c.sheet,
      surfaceContainerHighest: isDark ? c.dialog : c.pressed,
      outline: c.outline,
      outlineVariant: c.hairline,
      shadow: shadow,
      scrim: c.overlay,
      // الزر الرئيسي = محايد معكوس (نفس الويب)، وكمان الـ SnackBar
      inverseSurface: c.primaryAction,
      onInverseSurface: c.onPrimaryAction,
      inversePrimary: inverse.accent,
      surfaceTint: Colors.transparent,
    );

    const pill = WidgetStatePropertyAll<OutlinedBorder>(StadiumBorder());
    final buttonText = WidgetStatePropertyAll(text.labelLarge!.copyWith(
      fontSize: 16,
      height: 1.25,
    ));
    const buttonSize = WidgetStatePropertyAll(
      Size(64, AppSizes.buttonHeight),
    );
    const buttonPadding = WidgetStatePropertyAll(
      EdgeInsets.symmetric(horizontal: AppSpacing.xl),
    );

    final primaryButton = ButtonStyle(
      backgroundColor: WidgetStateProperty.resolveWith((s) =>
          s.contains(WidgetState.disabled) ? c.pressed : c.primaryAction),
      foregroundColor: WidgetStateProperty.resolveWith((s) =>
          s.contains(WidgetState.disabled) ? c.fgDisabled : c.onPrimaryAction),
      overlayColor: WidgetStatePropertyAll(
        c.onPrimaryAction.withValues(alpha: 0.08),
      ),
      elevation: const WidgetStatePropertyAll(0),
      shape: pill,
      textStyle: buttonText,
      minimumSize: buttonSize,
      padding: buttonPadding,
    );

    OutlineInputBorder field(Color color, [double width = 1]) =>
        OutlineInputBorder(
          borderRadius: AppRadii.field,
          borderSide: BorderSide(color: color, width: width),
        );

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      scaffoldBackgroundColor: c.canvas,
      canvasColor: c.canvas,
      fontFamily: AppFonts.sans,
      fontFamilyFallback: AppFonts.sansFallback,
      textTheme: text,
      primaryTextTheme: text,
      extensions: [c, type],
      materialTapTargetSize: MaterialTapTargetSize.padded,
      visualDensity: VisualDensity.standard,
      splashFactory: InkRipple.splashFactory,
      highlightColor: Colors.transparent,
      splashColor: c.fg.withValues(alpha: 0.06),
      hoverColor: Colors.transparent,
      focusColor: c.accentSoft,
      dividerColor: c.hairline,
      disabledColor: c.fgDisabled,
      iconTheme: IconThemeData(color: c.fg2, size: AppSizes.iconLg),
      pageTransitionsTheme: const PageTransitionsTheme(
        builders: {
          TargetPlatform.android:
              _MotionAwareTransitions(FadeForwardsPageTransitionsBuilder()),
          TargetPlatform.iOS:
              _MotionAwareTransitions(CupertinoPageTransitionsBuilder()),
          TargetPlatform.macOS:
              _MotionAwareTransitions(CupertinoPageTransitionsBuilder()),
        },
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: c.canvas,
        foregroundColor: c.fg,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        titleTextStyle: text.titleLarge,
        iconTheme: IconThemeData(color: c.fg, size: AppSizes.iconLg),
        actionsIconTheme: IconThemeData(color: c.fg, size: AppSizes.iconLg),
        systemOverlayStyle: overlayStyle(brightness),
      ),
      cardTheme: CardThemeData(
        color: c.card,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        margin: EdgeInsets.zero,
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(
          borderRadius: AppRadii.card,
          side: BorderSide(color: c.hairline),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(style: primaryButton),
      // الشاشات القديمة بتستخدم ElevatedButton - بياخد نفس شكل الزر الرئيسي
      elevatedButtonTheme: ElevatedButtonThemeData(style: primaryButton),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: ButtonStyle(
          foregroundColor: WidgetStateProperty.resolveWith((s) =>
              s.contains(WidgetState.disabled) ? c.fgDisabled : c.fg),
          overlayColor: WidgetStatePropertyAll(c.fg.withValues(alpha: 0.06)),
          side: WidgetStateProperty.resolveWith((s) => BorderSide(
                color: s.contains(WidgetState.disabled)
                    ? c.hairline
                    : c.lineStrong,
              )),
          shape: pill,
          textStyle: buttonText,
          minimumSize: buttonSize,
          padding: buttonPadding,
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: ButtonStyle(
          foregroundColor: WidgetStateProperty.resolveWith((s) =>
              s.contains(WidgetState.disabled) ? c.fgDisabled : c.accent),
          overlayColor: WidgetStatePropertyAll(c.accentSoft),
          shape: pill,
          textStyle: WidgetStatePropertyAll(text.labelLarge),
          minimumSize: const WidgetStatePropertyAll(
            Size(AppSizes.minTap, AppSizes.minTap),
          ),
        ),
      ),
      iconButtonTheme: IconButtonThemeData(
        style: ButtonStyle(
          foregroundColor: WidgetStatePropertyAll(c.fg),
          overlayColor: WidgetStatePropertyAll(c.fg.withValues(alpha: 0.08)),
          minimumSize: const WidgetStatePropertyAll(
            Size(AppSizes.minTap, AppSizes.minTap),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: c.inset,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.md,
        ),
        border: field(c.outline),
        enabledBorder: field(c.outline),
        focusedBorder: field(c.accent, 2),
        errorBorder: field(c.danger),
        focusedErrorBorder: field(c.danger, 2),
        disabledBorder: field(c.hairline),
        labelStyle: text.bodyMedium,
        floatingLabelStyle: text.bodySmall!.copyWith(color: c.accent),
        hintStyle: text.bodyLarge!.copyWith(color: c.fg3),
        helperStyle: text.bodySmall,
        errorStyle: text.bodySmall!.copyWith(color: c.danger),
        prefixIconColor: c.fg3,
        suffixIconColor: c.fg3,
      ),
      textSelectionTheme: TextSelectionThemeData(
        cursorColor: c.accent,
        selectionColor: c.accentSoft,
        selectionHandleColor: c.accent,
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: c.raised,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        height: 72,
        indicatorColor: c.accentSoft,
        indicatorShape: const StadiumBorder(),
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        iconTheme: WidgetStateProperty.resolveWith((s) => IconThemeData(
              size: AppSizes.iconLg,
              color: s.contains(WidgetState.selected) ? c.accent : c.fg2,
            )),
        labelTextStyle: WidgetStateProperty.resolveWith((s) =>
            text.labelMedium!.copyWith(
              color: s.contains(WidgetState.selected) ? c.fg : c.fg2,
              fontWeight: s.contains(WidgetState.selected)
                  ? FontWeight.w600
                  : FontWeight.w500,
            )),
      ),
      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: c.sheet,
        modalBackgroundColor: c.sheet,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        modalElevation: 0,
        modalBarrierColor: c.overlay,
        shape: const RoundedRectangleBorder(borderRadius: AppRadii.sheetTop),
        showDragHandle: true,
        dragHandleColor: c.lineStrong,
        clipBehavior: Clip.antiAlias,
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: c.dialog,
        surfaceTintColor: Colors.transparent,
        elevation: isDark ? 0 : 6,
        shadowColor: shadow,
        barrierColor: c.overlay,
        shape: const RoundedRectangleBorder(borderRadius: AppRadii.dialog),
        titleTextStyle: text.titleLarge,
        contentTextStyle: text.bodyMedium,
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: c.primaryAction,
        contentTextStyle:
            text.bodyMedium!.copyWith(color: c.onPrimaryAction),
        actionTextColor: inverse.accent,
        behavior: SnackBarBehavior.floating,
        elevation: 0,
        shape: const RoundedRectangleBorder(borderRadius: AppRadii.card),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: c.card,
        selectedColor: c.accentSoft,
        disabledColor: c.pressed,
        // المحدّد: إطار ذهبي أعرض (مش بس تظليل خفيف - تباين الحالة ≥ 3:1)
        side: WidgetStateBorderSide.resolveWith((s) => s.contains(WidgetState.selected)
            ? BorderSide(color: c.accent, width: 1.5)
            : BorderSide(color: c.hairline)),
        shape: const StadiumBorder(),
        labelStyle: text.labelMedium!.copyWith(color: c.fg),
        secondaryLabelStyle: text.labelMedium!.copyWith(color: c.accent),
        checkmarkColor: c.accent,
        iconTheme: IconThemeData(color: c.fg2, size: AppSizes.iconSm),
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xs),
        showCheckmark: false,
      ),
      segmentedButtonTheme: SegmentedButtonThemeData(
        style: ButtonStyle(
          backgroundColor: WidgetStateProperty.resolveWith((s) =>
              s.contains(WidgetState.selected) ? c.accentSoft : c.card),
          foregroundColor: WidgetStateProperty.resolveWith((s) =>
              s.contains(WidgetState.selected) ? c.accent : c.fg2),
          side: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected)
              ? BorderSide(color: c.accent, width: 1.5)
              : BorderSide(color: c.lineStrong)),
          shape: pill,
          textStyle: WidgetStatePropertyAll(text.labelLarge),
          minimumSize: const WidgetStatePropertyAll(
            Size(AppSizes.minTap, AppSizes.minTap),
          ),
        ),
      ),
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith((s) =>
            s.contains(WidgetState.selected) ? c.onAccent : c.fg2),
        trackColor: WidgetStateProperty.resolveWith((s) =>
            s.contains(WidgetState.selected) ? c.accent : c.inset),
        trackOutlineColor: WidgetStateProperty.resolveWith((s) =>
            s.contains(WidgetState.selected) ? c.accent : c.outline),
      ),
      checkboxTheme: CheckboxThemeData(
        fillColor: WidgetStateProperty.resolveWith((s) =>
            s.contains(WidgetState.selected) ? c.accent : Colors.transparent),
        checkColor: WidgetStatePropertyAll(c.onAccent),
        side: BorderSide(color: c.outline, width: 1.5),
        shape: const RoundedRectangleBorder(borderRadius: AppRadii.badge),
      ),
      radioTheme: RadioThemeData(
        fillColor: WidgetStateProperty.resolveWith((s) =>
            s.contains(WidgetState.selected) ? c.accent : c.outline),
      ),
      sliderTheme: SliderThemeData(
        activeTrackColor: c.accent,
        inactiveTrackColor: c.lineStrong,
        thumbColor: c.accent,
        overlayColor: c.accentSoft,
        valueIndicatorColor: c.primaryAction,
        valueIndicatorTextStyle:
            type.numSmall.copyWith(color: c.onPrimaryAction),
      ),
      progressIndicatorTheme: ProgressIndicatorThemeData(
        color: c.accent,
        linearTrackColor: c.hairline,
        circularTrackColor: Colors.transparent,
        refreshBackgroundColor: c.raised,
      ),
      listTileTheme: ListTileThemeData(
        iconColor: c.fg2,
        textColor: c.fg,
        titleTextStyle: text.bodyLarge,
        subtitleTextStyle: text.bodyMedium,
        leadingAndTrailingTextStyle: text.bodyMedium,
        minVerticalPadding: AppSpacing.sm,
        minTileHeight: 56,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: AppSpacing.md),
        shape: const RoundedRectangleBorder(borderRadius: AppRadii.card),
      ),
      expansionTileTheme: ExpansionTileThemeData(
        iconColor: c.fg2,
        collapsedIconColor: c.fg2,
        textColor: c.fg,
        collapsedTextColor: c.fg,
        shape: const Border(),
        collapsedShape: const Border(),
      ),
      dividerTheme: DividerThemeData(
        color: c.hairline,
        thickness: AppSizes.hairline,
        space: AppSizes.hairline,
      ),
      tabBarTheme: TabBarThemeData(
        labelColor: c.fg,
        unselectedLabelColor: c.fg2,
        labelStyle: text.titleSmall,
        unselectedLabelStyle: text.titleSmall!.copyWith(
          fontWeight: FontWeight.w500,
        ),
        indicatorColor: c.accent,
        indicatorSize: TabBarIndicatorSize.label,
        dividerColor: c.hairline,
        overlayColor: WidgetStatePropertyAll(c.fg.withValues(alpha: 0.06)),
      ),
      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: c.primaryAction,
          borderRadius: AppRadii.badge,
        ),
        textStyle: text.bodySmall!.copyWith(color: c.onPrimaryAction),
      ),
      popupMenuTheme: PopupMenuThemeData(
        color: c.sheet,
        surfaceTintColor: Colors.transparent,
        elevation: isDark ? 0 : 4,
        shape: RoundedRectangleBorder(
          borderRadius: AppRadii.card,
          side: BorderSide(color: c.hairline),
        ),
        textStyle: text.bodyLarge,
      ),
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: c.primaryAction,
        foregroundColor: c.onPrimaryAction,
        elevation: 0,
        focusElevation: 0,
        hoverElevation: 0,
        highlightElevation: 0,
        shape: const StadiumBorder(),
      ),
      badgeTheme: BadgeThemeData(
        backgroundColor: c.accent,
        textColor: c.onAccent,
        textStyle: type.numSmall.copyWith(fontSize: 12, height: 1),
      ),
      scrollbarTheme: ScrollbarThemeData(
        thumbColor: WidgetStatePropertyAll(c.lineStrong),
        radius: const Radius.circular(AppRadii.pill),
      ),
    );
  }
}

/// انتقال الشاشات: الافتراضي حسب المنصة (يحافظ على سحب-للرجوع بـ iOS)،
/// ولما الحركة مقلّلة بيصير fade بسيط بدل الانزلاق.
class _MotionAwareTransitions extends PageTransitionsBuilder {
  const _MotionAwareTransitions(this._delegate);

  final PageTransitionsBuilder _delegate;

  @override
  Widget buildTransitions<T>(
    PageRoute<T> route,
    BuildContext context,
    Animation<double> animation,
    Animation<double> secondaryAnimation,
    Widget child,
  ) {
    if (context.reduceMotion) {
      return FadeTransition(opacity: animation, child: child);
    }
    return _delegate.buildTransitions(
      route,
      context,
      animation,
      secondaryAnimation,
      child,
    );
  }
}
