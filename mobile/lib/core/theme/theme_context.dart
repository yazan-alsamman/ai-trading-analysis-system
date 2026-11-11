import 'package:flutter/material.dart';

import 'app_color_tokens.dart';
import 'app_typography.dart';

export 'app_color_tokens.dart';
export 'app_dimens.dart';
export 'app_motion.dart';
export 'app_typography.dart';

/// اختصارات للوصول للثيم من أي widget:
/// `context.colors.up`، `context.type.numHero`، `context.textTheme.titleMedium`
///
/// استيراد هاد الملف لحالو بيكفي - بيصدّر كل ملفات الـ tokens.
extension ThemeContext on BuildContext {
  AppColorTokens get colors => Theme.of(this).extension<AppColorTokens>()!;

  AppTextTokens get type => Theme.of(this).extension<AppTextTokens>()!;

  TextTheme get textTheme => Theme.of(this).textTheme;

  ColorScheme get colorScheme => Theme.of(this).colorScheme;

  bool get isDark => Theme.of(this).brightness == Brightness.dark;
}
