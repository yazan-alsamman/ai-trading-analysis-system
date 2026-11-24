import 'package:flutter/material.dart';

import '../theme/theme_context.dart';

/// رأس الصفحة: سهم الرجوع + العنوان (serif) بنفس الصف، بالنص عموديًا
///
/// بالعربي بينعكس تلقائيًا (السهم يمين والعنوان جنبه). العنوان بيلتف لسطر
/// تاني بالخط الكبير بدل ما يطلع برا الشاشة. [back] هو زر الرجوع:
/// `BackToHomeButton` بالتبويبات، و[PageBackButton] بصفحات التفاصيل.
class PageHeader extends StatelessWidget {
  const PageHeader({super.key, required this.title, required this.back, this.actions = const [], this.icon});

  final String title;
  final Widget back;

  /// أيقونة زخرفية قبل العنوان (راس الروبوت بتبويب Assistant مثلًا)
  final IconData? icon;

  /// أزرار أيقونة بآخر الصف (48×48 كل وحدة)
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) {
    final gutter = AppSpacing.gutter(context);
    return Padding(
      // السهم بيوقف عند حافة الـ gutter بصريًا (الأيقونة جوا مربع 48)
      padding: EdgeInsetsDirectional.fromSTEB(
        gutter - AppSpacing.sm,
        AppSpacing.xs,
        actions.isEmpty ? gutter : gutter - AppSpacing.sm,
        AppSpacing.xs,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          back,
          const SizedBox(width: AppSpacing.xxs),
          if (icon != null) ...[
            ExcludeSemantics(child: Icon(icon, size: AppSizes.iconLg, color: context.colors.fg2)),
            const SizedBox(width: AppSpacing.xs),
          ],
          Expanded(
            child: Semantics(
              header: true,
              child: Text(title, style: context.textTheme.displaySmall),
            ),
          ),
          ...actions,
        ],
      ),
    );
  }
}

/// سهم رجوع لصفحات التفاصيل (Markets، Plans...) - بيرجع للشاشة يلي قبل
///
/// نفس [BackButton] تبع Flutter (tooltip مترجم، 48×48، بينعكس بالـ RTL)
/// بلون الهوية.
class PageBackButton extends StatelessWidget {
  const PageBackButton({super.key});

  @override
  Widget build(BuildContext context) {
    return BackButton(
      color: context.colors.fg,
      style: IconButton.styleFrom(
        minimumSize: const Size.square(AppSizes.minTap),
      ),
    );
  }
}
