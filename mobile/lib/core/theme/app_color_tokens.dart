import 'package:flutter/material.dart';

import 'app_palette.dart';

/// الألوان الدلالية للتطبيق - بتتبدّل تلقائيًا بين الفاتح والداكن
///
/// الاستخدام: `context.colors.up`، `context.colors.card`...
///
/// قواعد المعنى (من DESIGN_SPEC.md §3.1):
/// - [accent] (ذهبي): الهوية، التحديد، الـ focus، الروابط. أبدًا مش اتجاه السوق.
/// - [primaryAction]: زر الإجراء الرئيسي الوحيد بالشاشة (لون معكوس).
/// - [up] / [down]: اتجاه السوق بس، ودايمًا مع إشارة (+/−) وسهم.
/// - [forecast] (بنفسجي): مخرجات نموذج الذكاء الاصطناعي بس.
/// - [demo] (سماوي): بيانات محاكاة. [warning] / [danger]: رسائل النظام
///   مع أيقونة وكلمة - و[danger] برتقالي عن قصد حتى ما ينفهم كهبوط سعر.
@immutable
class AppColorTokens extends ThemeExtension<AppColorTokens> {
  const AppColorTokens({
    required this.canvas,
    required this.card,
    required this.raised,
    required this.sheet,
    required this.dialog,
    required this.inset,
    required this.pressed,
    required this.selected,
    required this.hairline,
    required this.lineStrong,
    required this.outline,
    required this.fg,
    required this.fg2,
    required this.fg3,
    required this.fgDisabled,
    required this.primaryAction,
    required this.onPrimaryAction,
    required this.accent,
    required this.onAccent,
    required this.accentSoft,
    required this.up,
    required this.upSoft,
    required this.down,
    required this.downSoft,
    required this.forecast,
    required this.onForecast,
    required this.forecastSoft,
    required this.danger,
    required this.onDanger,
    required this.dangerSoft,
    required this.warning,
    required this.warningSoft,
    required this.info,
    required this.infoSoft,
    required this.demo,
    required this.demoSoft,
    required this.overlay,
    required this.atmosAurum,
    required this.atmosViolet,
    required this.gridLine,
    required this.chart,
  });

  // Surfaces
  final Color canvas;
  final Color card;
  final Color raised;
  final Color sheet;
  final Color dialog;
  final Color inset;
  final Color pressed;
  final Color selected;
  final Color hairline;
  final Color lineStrong;
  final Color outline;

  // Text
  final Color fg;
  final Color fg2;
  final Color fg3;
  final Color fgDisabled;

  // Roles
  final Color primaryAction;
  final Color onPrimaryAction;
  final Color accent;
  final Color onAccent;
  final Color accentSoft;
  final Color up;
  final Color upSoft;
  final Color down;
  final Color downSoft;
  final Color forecast;
  final Color onForecast;
  final Color forecastSoft;
  final Color danger;
  final Color onDanger;
  final Color dangerSoft;
  final Color warning;
  final Color warningSoft;
  final Color info;
  final Color infoSoft;
  final Color demo;
  final Color demoSoft;
  final Color overlay;

  // Atmosphere (splash / auth / home header بس - أبدًا ورا البيانات)
  final Color atmosAurum;
  final Color atmosViolet;
  final Color gridLine;

  final AppChartColors chart;

  /// لون الاتجاه حسب الإشارة - للأرقام يلي ممكن تكون موجبة أو سالبة
  Color direction(num value) => value >= 0 ? up : down;

  static final AppColorTokens dark = _build(
    canvas: DarkPalette.canvas,
    card: DarkPalette.card,
    raised: DarkPalette.raised,
    sheet: DarkPalette.sheet,
    dialog: DarkPalette.dialog,
    inset: DarkPalette.inset,
    pressed: DarkPalette.pressed,
    selected: DarkPalette.selected,
    hairline: DarkPalette.hairline,
    lineStrong: DarkPalette.lineStrong,
    outline: DarkPalette.outline,
    fg: DarkPalette.fg,
    fg2: DarkPalette.fg2,
    fg3: DarkPalette.fg3,
    fgDisabled: DarkPalette.fgDisabled,
    primaryAction: DarkPalette.primaryAction,
    onPrimaryAction: DarkPalette.onPrimaryAction,
    accent: DarkPalette.accent,
    onAccent: DarkPalette.onAccent,
    up: DarkPalette.up,
    down: DarkPalette.down,
    forecast: DarkPalette.forecast,
    onForecast: DarkPalette.onForecast,
    danger: DarkPalette.danger,
    onDanger: DarkPalette.onDanger,
    warning: DarkPalette.warning,
    info: DarkPalette.info,
    softAlpha: DarkPalette.softAlpha,
    overlay: DarkPalette.overlay,
    atmosAurum: DarkPalette.atmosAurum,
    atmosViolet: DarkPalette.atmosViolet,
    gridLine: DarkPalette.gridLine,
    chart: AppChartColors(
      grid: DarkPalette.chartGrid,
      crosshair: DarkPalette.chartCrosshair,
      indicator1: DarkPalette.chartInd1,
      indicator2: DarkPalette.chartInd2,
      indicator3: DarkPalette.chartInd3,
      zoneEntry: DarkPalette.accent.withValues(alpha: 0.12),
      zoneTarget: DarkPalette.up.withValues(alpha: DarkPalette.chartZoneAlpha),
      zoneStop: DarkPalette.down.withValues(alpha: DarkPalette.chartZoneAlpha),
      volumeUp: DarkPalette.up.withValues(alpha: DarkPalette.chartVolumeAlpha),
      volumeDown:
          DarkPalette.down.withValues(alpha: DarkPalette.chartVolumeAlpha),
      forecastRegion: DarkPalette.forecast
          .withValues(alpha: DarkPalette.chartForecastRegionAlpha),
    ),
  );

  static final AppColorTokens light = _build(
    canvas: LightPalette.canvas,
    card: LightPalette.card,
    raised: LightPalette.raised,
    sheet: LightPalette.sheet,
    dialog: LightPalette.dialog,
    inset: LightPalette.inset,
    pressed: LightPalette.pressed,
    selected: LightPalette.selected,
    hairline: LightPalette.hairline,
    lineStrong: LightPalette.lineStrong,
    outline: LightPalette.outline,
    fg: LightPalette.fg,
    fg2: LightPalette.fg2,
    fg3: LightPalette.fg3,
    fgDisabled: LightPalette.fgDisabled,
    primaryAction: LightPalette.primaryAction,
    onPrimaryAction: LightPalette.onPrimaryAction,
    accent: LightPalette.accent,
    onAccent: LightPalette.onAccent,
    up: LightPalette.up,
    down: LightPalette.down,
    forecast: LightPalette.forecast,
    onForecast: LightPalette.onForecast,
    danger: LightPalette.danger,
    onDanger: LightPalette.onDanger,
    warning: LightPalette.warning,
    info: LightPalette.info,
    softAlpha: LightPalette.softAlpha,
    overlay: LightPalette.overlay,
    atmosAurum: LightPalette.atmosAurum,
    atmosViolet: LightPalette.atmosViolet,
    gridLine: LightPalette.gridLine,
    chart: AppChartColors(
      grid: LightPalette.chartGrid,
      crosshair: LightPalette.chartCrosshair,
      indicator1: LightPalette.chartInd1,
      indicator2: LightPalette.chartInd2,
      indicator3: LightPalette.chartInd3,
      zoneEntry: LightPalette.accent.withValues(alpha: 0.10),
      zoneTarget: LightPalette.up.withValues(alpha: LightPalette.chartZoneAlpha),
      zoneStop: LightPalette.down.withValues(alpha: 0.07),
      volumeUp: LightPalette.up.withValues(alpha: LightPalette.chartVolumeAlpha),
      volumeDown:
          LightPalette.down.withValues(alpha: LightPalette.chartVolumeAlpha),
      forecastRegion: LightPalette.forecast
          .withValues(alpha: LightPalette.chartForecastRegionAlpha),
    ),
  );

  /// الخلفيات الناعمة (badges / zones) = نفس اللون بشفافية ثابتة
  static AppColorTokens _build({
    required Color canvas,
    required Color card,
    required Color raised,
    required Color sheet,
    required Color dialog,
    required Color inset,
    required Color pressed,
    required Color selected,
    required Color hairline,
    required Color lineStrong,
    required Color outline,
    required Color fg,
    required Color fg2,
    required Color fg3,
    required Color fgDisabled,
    required Color primaryAction,
    required Color onPrimaryAction,
    required Color accent,
    required Color onAccent,
    required Color up,
    required Color down,
    required Color forecast,
    required Color onForecast,
    required Color danger,
    required Color onDanger,
    required Color warning,
    required Color info,
    required double softAlpha,
    required Color overlay,
    required Color atmosAurum,
    required Color atmosViolet,
    required Color gridLine,
    required AppChartColors chart,
  }) {
    Color soft(Color c) => c.withValues(alpha: softAlpha);
    return AppColorTokens(
      canvas: canvas,
      card: card,
      raised: raised,
      sheet: sheet,
      dialog: dialog,
      inset: inset,
      pressed: pressed,
      selected: selected,
      hairline: hairline,
      lineStrong: lineStrong,
      outline: outline,
      fg: fg,
      fg2: fg2,
      fg3: fg3,
      fgDisabled: fgDisabled,
      primaryAction: primaryAction,
      onPrimaryAction: onPrimaryAction,
      accent: accent,
      onAccent: onAccent,
      accentSoft: soft(accent),
      up: up,
      upSoft: soft(up),
      down: down,
      downSoft: soft(down),
      forecast: forecast,
      onForecast: onForecast,
      forecastSoft: forecast.withValues(alpha: softAlpha + 0.01),
      danger: danger,
      onDanger: onDanger,
      dangerSoft: soft(danger),
      warning: warning,
      warningSoft: soft(warning),
      info: info,
      infoSoft: soft(info),
      demo: info,
      demoSoft: info.withValues(alpha: softAlpha - 0.02),
      overlay: overlay,
      atmosAurum: atmosAurum,
      atmosViolet: atmosViolet,
      gridLine: gridLine,
      chart: chart,
    );
  }

  @override
  AppColorTokens copyWith() => this;

  @override
  AppColorTokens lerp(ThemeExtension<AppColorTokens>? other, double t) {
    if (other is! AppColorTokens) return this;
    Color l(Color a, Color b) => Color.lerp(a, b, t)!;
    return AppColorTokens(
      canvas: l(canvas, other.canvas),
      card: l(card, other.card),
      raised: l(raised, other.raised),
      sheet: l(sheet, other.sheet),
      dialog: l(dialog, other.dialog),
      inset: l(inset, other.inset),
      pressed: l(pressed, other.pressed),
      selected: l(selected, other.selected),
      hairline: l(hairline, other.hairline),
      lineStrong: l(lineStrong, other.lineStrong),
      outline: l(outline, other.outline),
      fg: l(fg, other.fg),
      fg2: l(fg2, other.fg2),
      fg3: l(fg3, other.fg3),
      fgDisabled: l(fgDisabled, other.fgDisabled),
      primaryAction: l(primaryAction, other.primaryAction),
      onPrimaryAction: l(onPrimaryAction, other.onPrimaryAction),
      accent: l(accent, other.accent),
      onAccent: l(onAccent, other.onAccent),
      accentSoft: l(accentSoft, other.accentSoft),
      up: l(up, other.up),
      upSoft: l(upSoft, other.upSoft),
      down: l(down, other.down),
      downSoft: l(downSoft, other.downSoft),
      forecast: l(forecast, other.forecast),
      onForecast: l(onForecast, other.onForecast),
      forecastSoft: l(forecastSoft, other.forecastSoft),
      danger: l(danger, other.danger),
      onDanger: l(onDanger, other.onDanger),
      dangerSoft: l(dangerSoft, other.dangerSoft),
      warning: l(warning, other.warning),
      warningSoft: l(warningSoft, other.warningSoft),
      info: l(info, other.info),
      infoSoft: l(infoSoft, other.infoSoft),
      demo: l(demo, other.demo),
      demoSoft: l(demoSoft, other.demoSoft),
      overlay: l(overlay, other.overlay),
      atmosAurum: l(atmosAurum, other.atmosAurum),
      atmosViolet: l(atmosViolet, other.atmosViolet),
      gridLine: l(gridLine, other.gridLine),
      chart: chart.lerp(other.chart, t),
    );
  }
}

/// ألوان الرسوم البيانية. الشموع والحجم بـ up/down، المؤشرات أبدًا مش
/// up/down، والتوقّع بنفسجي متقطّع بعد خط NOW فوق منطقة بنفسجية خفيفة.
@immutable
class AppChartColors {
  const AppChartColors({
    required this.grid,
    required this.crosshair,
    required this.indicator1,
    required this.indicator2,
    required this.indicator3,
    required this.zoneEntry,
    required this.zoneTarget,
    required this.zoneStop,
    required this.volumeUp,
    required this.volumeDown,
    required this.forecastRegion,
  });

  final Color grid;
  final Color crosshair;
  final Color indicator1;
  final Color indicator2;
  final Color indicator3;
  final Color zoneEntry;
  final Color zoneTarget;
  final Color zoneStop;
  final Color volumeUp;
  final Color volumeDown;
  final Color forecastRegion;

  AppChartColors lerp(AppChartColors other, double t) {
    Color l(Color a, Color b) => Color.lerp(a, b, t)!;
    return AppChartColors(
      grid: l(grid, other.grid),
      crosshair: l(crosshair, other.crosshair),
      indicator1: l(indicator1, other.indicator1),
      indicator2: l(indicator2, other.indicator2),
      indicator3: l(indicator3, other.indicator3),
      zoneEntry: l(zoneEntry, other.zoneEntry),
      zoneTarget: l(zoneTarget, other.zoneTarget),
      zoneStop: l(zoneStop, other.zoneStop),
      volumeUp: l(volumeUp, other.volumeUp),
      volumeDown: l(volumeDown, other.volumeDown),
      forecastRegion: l(forecastRegion, other.forecastRegion),
    );
  }
}
