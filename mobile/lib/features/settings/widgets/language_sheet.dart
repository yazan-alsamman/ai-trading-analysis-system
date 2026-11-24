import 'package:flutter/material.dart';

import '../../../core/theme/theme_context.dart';
import '../../../l10n/app_localizations.dart';

/// Bottom sheet اختيار اللغة - بيرجع رمز اللغة المختارة (أو null لو انسكّر)
///
/// أسماء اللغات مكتوبة بلغتها نفسها (English / العربية) حتى يلاقيها
/// المستخدم مهما كانت لغة الواجهة الحالية.
Future<String?> showLanguageSheet(BuildContext context, {required String current}) {
  return showModalBottomSheet<String>(
    useRootNavigator: true,
    context: context,
    sheetAnimationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
    showDragHandle: true,
    builder: (context) => _LanguageSheet(current: current),
  );
}

class _LanguageSheet extends StatelessWidget {
  const _LanguageSheet({required this.current});

  final String current;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final text = context.textTheme;
    final c = context.colors;
    final gutter = AppSpacing.gutter(context);

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.only(bottom: AppSpacing.md),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: EdgeInsets.symmetric(horizontal: gutter),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Semantics(
                    header: true,
                    child: Text(l10n.language, style: text.titleLarge),
                  ),
                  const SizedBox(height: AppSpacing.xxs),
                  Text(
                    l10n.chooseAppLanguage,
                    style: text.bodyMedium!.copyWith(color: c.fg2),
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            for (final (code, name) in const [('en', 'English'), ('ar', 'العربية')])
              _LanguageOption(
                name: name,
                selected: code == current,
                onTap: () => Navigator.of(context).pop(code),
              ),
          ],
        ),
      ),
    );
  }
}

class _LanguageOption extends StatelessWidget {
  const _LanguageOption({
    required this.name,
    required this.selected,
    required this.onTap,
  });

  final String name;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Semantics(
      inMutuallyExclusiveGroup: true,
      checked: selected,
      child: ListTile(
        contentPadding: EdgeInsets.symmetric(horizontal: AppSpacing.gutter(context)),
        minTileHeight: 56,
        title: Text(
          name,
          style: context.textTheme.titleMedium!.copyWith(
            color: selected ? c.fg : c.fg2,
          ),
        ),
        trailing: selected ? Icon(Icons.check_rounded, color: c.accent, size: AppSizes.iconLg) : null,
        onTap: onTap,
      ),
    );
  }
}
