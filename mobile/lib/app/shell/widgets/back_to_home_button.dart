import 'package:flutter/material.dart';

import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/page_header.dart';
import '../../../l10n/app_localizations.dart';
import '../../router/app_navigator.dart';

/// سهم "رجوع للرئيسية" بأعلى التبويبات (Signals / Assistant /
/// Community / Profile)
///
/// بيختار تبويب Home (نفس زر الرجوع بالنظام). السهم بينقلب تلقائيًا
/// بالعربي (RTL)، وإلو tooltip ووصف للقارئ الصوتي، ومساحة ضغط 48×48.
class BackToHomeButton extends StatelessWidget {
  const BackToHomeButton({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return IconButton(
      onPressed: () {
        AppHaptics.selection();
        context.goToTab(ShellTab.home);
      },
      tooltip: l10n.backToHome,
      constraints: const BoxConstraints(
        minWidth: AppSizes.minTap,
        minHeight: AppSizes.minTap,
      ),
      icon: Icon(
        Icons.arrow_back_rounded,
        color: context.colors.fg,
        size: AppSizes.iconLg,
      ),
    );
  }
}

/// رأس تبويب: سهم الرجوع للرئيسية + العنوان بنفس الصف ([PageHeader])
class TabHeader extends StatelessWidget {
  const TabHeader({super.key, required this.title, this.actions = const [], this.icon});

  final String title;
  final List<Widget> actions;
  final IconData? icon;

  @override
  Widget build(BuildContext context) =>
      PageHeader(title: title, back: const BackToHomeButton(), actions: actions, icon: icon);
}
