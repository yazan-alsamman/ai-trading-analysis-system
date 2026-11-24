import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../l10n/app_localizations.dart';
import '../data/analysis_methods_repository.dart';
import '../models/analysis_method.dart';

/// كتالوج الطرق بلغة الواجهة (null لسّا عم يتحمّل أو فشل)
List<AnalysisMethod>? watchAnalysisMethods(WidgetRef ref, BuildContext context) =>
    ref.watch(analysisMethodsProvider(Localizations.localeOf(context).languageCode)).valueOrNull;

/// اسم طريقة بلغة الواجهة (null لسّا الكتالوج ما وصل)
String? watchMethodName(WidgetRef ref, BuildContext context, String methodId) {
  for (final method in watchAnalysisMethods(ref, context) ?? const <AnalysisMethod>[]) {
    if (method.id == methodId) return method.name;
  }
  return null;
}

/// قائمة radio بطرق التحليل (اسم + جملة شرح لكل وحدة). نفس الويدجت بـ sheet
/// الاستراتيجية (الطريقة المحفوظة) وبـ "Request analysis" (تغيير لهالطلب بس).
/// كل صف ≥ 56 dp، والقارئ الصوتي بيسمع "الاسم. الشرح" + محدّد / مش محدّد.
class MethodPicker extends ConsumerWidget {
  const MethodPicker({super.key, required this.selectedId, required this.onSelected});

  final String selectedId;

  /// null = معطّل (مثلًا وقت الحفظ أو الطلب شغّال)
  final ValueChanged<String>? onSelected;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final language = Localizations.localeOf(context).languageCode;
    final methods = ref.watch(analysisMethodsProvider(language));

    return methods.when(
      loading: () => LoadingRegion(
        child: Column(
          children: [
            for (var i = 0; i < AnalysisMethod.knownIds.length; i++) ...[
              if (i > 0) const SizedBox(height: AppSpacing.xs),
              const Skeleton(height: _MethodTile.minHeight, radius: AppRadii.card),
            ],
          ],
        ),
      ),
      error: (_, __) => Semantics(
        liveRegion: true,
        container: true,
        child: Row(
          children: [
            Expanded(child: Text(l10n.strategyMethodsError, style: context.textTheme.bodyMedium)),
            TextButton(
              onPressed: () => ref.invalidate(analysisMethodsProvider(language)),
              style: TextButton.styleFrom(minimumSize: const Size(AppSizes.minTap, AppSizes.minTap)),
              child: Text(l10n.tryAgain),
            ),
          ],
        ),
      ),
      data: (list) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (final (i, method) in list.indexed) ...[
            if (i > 0) const SizedBox(height: AppSpacing.xs),
            _MethodTile(
              method: method,
              selected: method.id == selectedId,
              onTap: onSelected == null ? null : () => onSelected!(method.id),
            ),
          ],
        ],
      ),
    );
  }
}

class _MethodTile extends StatelessWidget {
  const _MethodTile({required this.method, required this.selected, required this.onTap});

  static const double minHeight = 56;

  final AnalysisMethod method;
  final bool selected;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;
    void tap() {
      if (selected) return;
      AppHaptics.selection();
      onTap?.call();
    }

    return Semantics(
      container: true,
      inMutuallyExclusiveGroup: true,
      checked: selected,
      enabled: onTap != null,
      label: '${method.name}. ${method.description}',
      onTap: onTap == null ? null : tap,
      excludeSemantics: true,
      child: Material(
        color: selected ? c.accentSoft : c.card,
        shape: RoundedRectangleBorder(
          borderRadius: AppRadii.card,
          // محدّد = حدّ ذهبي 1.5 (مش اللون لحالو)
          side: BorderSide(color: selected ? c.accent : c.hairline, width: selected ? 1.5 : 1),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap == null ? null : tap,
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: minHeight),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    selected ? Icons.radio_button_checked_rounded : Icons.radio_button_unchecked_rounded,
                    size: AppSizes.iconLg,
                    color: selected ? c.accent : c.fg3,
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(method.name, style: text.titleSmall),
                        const SizedBox(height: 2),
                        Text(method.description, style: text.bodySmall!.copyWith(color: c.fg2)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
