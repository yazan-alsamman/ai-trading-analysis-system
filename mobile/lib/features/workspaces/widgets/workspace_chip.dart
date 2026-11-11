import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../l10n/app_localizations.dart';
import '../view_models/workspaces_view_model.dart';
import 'workspaces_sheet.dart';

/// chip المساحة الفعّالة فوق قائمة المتابعة بالـ Home - المدخل الوحيد لمساحات العمل.
///
/// الاسم ما بينقص أبدًا: بيلتف لسطر تاني والـ chip بيطول (≥ 48dp).
class WorkspaceChip extends ConsumerWidget {
  const WorkspaceChip({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final active = ref.watch(activeWorkspaceProvider).valueOrNull;

    if (active == null) {
      return const SizedBox(
        height: AppSizes.minTap,
        child: Align(
          alignment: AlignmentDirectional.centerStart,
          child: Skeleton(width: AppSpacing.huge * 3, height: AppSpacing.xl, radius: AppRadii.pillAll),
        ),
      );
    }

    final name = workspaceDisplayName(l10n, active);
    final count = l10n.workspaceInstrumentCount(active.symbols.length);
    return Semantics(
      button: true,
      label: l10n.workspaceChipLabel(name, count),
      hint: l10n.workspaceChipHint,
      onTap: () => showWorkspacesSheet(context),
      excludeSemantics: true,
      child: Material(
        color: c.raised,
        shape: StadiumBorder(side: BorderSide(color: c.hairline)),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: () => showWorkspacesSheet(context),
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: AppSizes.minTap),
            child: Padding(
              padding: const EdgeInsetsDirectional.fromSTEB(AppSpacing.sm, AppSpacing.xs, AppSpacing.xs, AppSpacing.xs),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.layers_outlined, size: AppSizes.iconMd, color: c.accent),
                  const SizedBox(width: AppSpacing.xs),
                  Flexible(
                    child: Text.rich(
                      TextSpan(children: [
                        TextSpan(text: name, style: context.textTheme.labelLarge!.copyWith(color: c.fg)),
                        TextSpan(text: ' · $count', style: context.textTheme.bodySmall!.copyWith(color: c.fg2)),
                      ]),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.xxs),
                  Icon(Icons.expand_more_rounded, size: AppSizes.iconMd, color: c.fg2),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
