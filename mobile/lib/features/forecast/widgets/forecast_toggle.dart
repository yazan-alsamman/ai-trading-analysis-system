import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/theme_context.dart';
import '../../../l10n/app_localizations.dart';
import '../../markets/view_models/market_view_model.dart';
import '../view_models/forecast_view_model.dart';

/// مفتاح "Forecast" بشريط أدوات الرسم (مكانه الوحيد: مش بـ sheet المؤشرات،
/// لأنو مخرجات نموذج مش مؤشر محسوب من الأسعار).
///
/// أيقونة النموذج (بنفسجي) + كلمة، ≥ 48 dp. أثناء التحميل: معطّل مع مؤشّر صغير
/// (ثابت مع تقليل الحركة) والقارئ الصوتي بيقول "Forecast, loading".
class ForecastToggle extends ConsumerWidget {
  const ForecastToggle({super.key, required this.symbol});

  final String symbol;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final on = ref.watch(marketViewModelProvider(symbol).select((s) => s.showForecast));
    final loading = ref.watch(forecastViewModelProvider(symbol).select((s) => s is ForecastLoading));

    final Widget avatar = loading
        ? SizedBox.square(
            dimension: AppSizes.iconSm,
            child: context.reduceMotion
                ? Icon(Icons.hourglass_top_rounded, size: AppSizes.iconSm, color: c.forecast)
                : CircularProgressIndicator(strokeWidth: 2, color: c.forecast),
          )
        : Icon(Icons.auto_awesome_rounded, size: AppSizes.iconSm, color: c.forecast);

    return FilterChip(
      key: const ValueKey('forecast-toggle'),
      avatar: avatar,
      label: Text(
        l10n.forecastToggle,
        semanticsLabel: loading ? l10n.forecastToggleLoading : l10n.forecastToggle,
      ),
      selected: on,
      showCheckmark: false,
      materialTapTargetSize: MaterialTapTargetSize.padded,
      onSelected: loading
          ? null
          : (_) {
              AppHaptics.selection();
              ref.read(marketViewModelProvider(symbol).notifier).toggleForecast();
            },
    );
  }
}
