import 'package:flutter/material.dart';

import '../theme/theme_context.dart';
import 'headings.dart';

/// مجموعة إعدادات: عنوان صغير (eyebrow) + بطاقة وحدة فيها الصفوف مفصولة
/// بخطوط رفيعة - نمط القوائم المجمّعة المعتاد على الموبايل.
class SettingsGroup extends StatelessWidget {
  const SettingsGroup({super.key, this.title, required this.children});

  final String? title;
  final List<Widget> children;

  /// بداية نص الصف (تحت العنوان): لمحتوى إضافي تحت صف بنفس المحاذاة
  static const double textIndent = _SettingsTileLayout.textIndent;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (title != null)
          Padding(
            padding: const EdgeInsetsDirectional.only(
              start: AppSpacing.xxs,
              bottom: AppSpacing.xs,
            ),
            child: Semantics(header: true, child: Eyebrow(title!)),
          ),
        Material(
          color: c.card,
          shape: RoundedRectangleBorder(
            borderRadius: AppRadii.card,
            side: BorderSide(color: c.hairline),
          ),
          clipBehavior: Clip.antiAlias,
          child: Column(
            children: [
              for (var i = 0; i < children.length; i++) ...[
                if (i > 0)
                  Divider(
                    height: 1,
                    thickness: 1,
                    indent: _SettingsTileLayout.textIndent,
                    color: c.hairline,
                  ),
                children[i],
              ],
            ],
          ),
        ),
      ],
    );
  }
}

abstract final class _SettingsTileLayout {
  static const double iconBox = 36;

  /// بداية النص (padding + أيقونة + فراغ) - الخط الفاصل بيبلش من هون
  static const double textIndent = AppSpacing.md + iconBox + AppSpacing.md;
}

/// صف واحد بمجموعة إعدادات: أيقونة + عنوان + وصف + (سهم أو [trailing])
///
/// بدون [onTap] الصف بيصير معلومة بس (بدون سهم ولا ripple).
class SettingsTile extends StatelessWidget {
  const SettingsTile({
    super.key,
    required this.icon,
    required this.title,
    this.subtitle,
    this.onTap,
    this.trailing,
    this.iconColor,
    this.titleColor,
  });

  final IconData icon;
  final String title;
  final String? subtitle;
  final VoidCallback? onTap;
  final Widget? trailing;
  final Color? iconColor;
  final Color? titleColor;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;

    final trailingWidget = trailing ??
        (onTap != null
            ? Icon(Icons.chevron_right_rounded, color: c.fg3, size: AppSizes.iconLg)
            : null);

    final row = ConstrainedBox(
      constraints: const BoxConstraints(minHeight: 64),
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.sm,
        ),
        child: Row(
          children: [
            Container(
              width: _SettingsTileLayout.iconBox,
              height: _SettingsTileLayout.iconBox,
              decoration: BoxDecoration(
                color: c.inset,
                borderRadius: AppRadii.field,
                border: Border.all(color: c.hairline),
              ),
              child: Icon(icon, size: AppSizes.iconMd, color: iconColor ?? c.fg2),
            ),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(title, style: text.titleSmall!.copyWith(color: titleColor ?? c.fg)),
                  if (subtitle != null) ...[
                    const SizedBox(height: 2),
                    Text(subtitle!, style: text.bodySmall!.copyWith(color: c.fg2)),
                  ],
                ],
              ),
            ),
            if (trailingWidget != null) ...[
              const SizedBox(width: AppSpacing.sm),
              trailingWidget,
            ],
          ],
        ),
      ),
    );

    if (onTap == null) return Semantics(container: true, child: row);
    return Semantics(container: true, button: true, child: InkWell(onTap: onTap, child: row));
  }
}

/// صف بمفتاح تشغيل: الضغط على الصف كلو بيبدّل، والقارئ الصوتي بيسمع
/// العنوان + الوصف + الحالة (مفعّل/مطفي) كعنصر واحد.
class SettingsSwitchTile extends StatelessWidget {
  const SettingsSwitchTile({
    super.key,
    required this.icon,
    required this.title,
    this.subtitle,
    required this.value,
    required this.onChanged,
  });

  final IconData icon;
  final String title;
  final String? subtitle;
  final bool value;

  /// null = معطّل
  final ValueChanged<bool>? onChanged;

  @override
  Widget build(BuildContext context) {
    return MergeSemantics(
      child: SettingsTile(
        icon: icon,
        title: title,
        subtitle: subtitle,
        onTap: onChanged == null
            ? null
            : () {
                AppHaptics.selection();
                onChanged!(!value);
              },
        trailing: Switch(value: value, onChanged: onChanged),
      ),
    );
  }
}

