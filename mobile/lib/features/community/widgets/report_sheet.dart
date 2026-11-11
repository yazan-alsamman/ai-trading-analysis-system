import 'package:flutter/material.dart';

import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../l10n/app_localizations.dart';
import '../models/post.dart';

/// "Report post" بـ bottom sheet: سبب واحد من 4 (صفوف كاملة 48dp+)، و"Send
/// report" معطّل لحد ما تختار. بيرجّع السبب أو null لو تسكّر.
Future<ReportReason?> showReportSheet(BuildContext context) {
  AppHaptics.light();
  return showModalBottomSheet<ReportReason>(
    useRootNavigator: true,
    context: context,
    sheetAnimationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
    isScrollControlled: true,
    useSafeArea: true,
    showDragHandle: true,
    builder: (context) => const _ReportSheet(),
  );
}

class _ReportSheet extends StatefulWidget {
  const _ReportSheet();

  @override
  State<_ReportSheet> createState() => _ReportSheetState();
}

class _ReportSheetState extends State<_ReportSheet> {
  ReportReason? _reason;

  static String _label(AppLocalizations l10n, ReportReason reason) => switch (reason) {
        ReportReason.spam => l10n.reportSpam,
        ReportReason.misleading => l10n.reportMisleading,
        ReportReason.abusive => l10n.reportAbusive,
        ReportReason.other => l10n.reportOther,
      };

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final text = context.textTheme;
    final gutter = AppSpacing.gutter(context);

    return SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(gutter, 0, gutter, AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Semantics(header: true, child: Text(l10n.reportTitle, style: text.titleLarge)),
          const SizedBox(height: AppSpacing.xxs),
          Text(l10n.reportBody, style: text.bodyMedium),
          const SizedBox(height: AppSpacing.sm),
          RadioGroup<ReportReason>(
            groupValue: _reason,
            onChanged: (value) {
              AppHaptics.selection();
              setState(() => _reason = value);
            },
            child: Column(
              children: [
                for (final reason in ReportReason.values)
                  RadioListTile<ReportReason>(
                    value: reason,
                    contentPadding: EdgeInsets.zero,
                    title: Text(_label(l10n, reason)),
                  ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          AppButton(
            label: l10n.reportSend,
            icon: Icons.flag_outlined,
            expand: true,
            onPressed: _reason == null ? null : () => Navigator.of(context).pop(_reason),
          ),
        ],
      ),
    );
  }
}
