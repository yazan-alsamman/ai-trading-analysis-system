import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';
import '../theme/theme_context.dart';

/// سطر ثابت "الإشارات لأغراض تعليمية وليست نصيحة استثمارية" (أيقونة + نص).
/// نفس الويدجت ونفس النص بكل مكان بيطلع فيه إشارة أو قراءة نموذج:
/// قائمة الإشارات، تفاصيل الإشارة، الـ Home، قراءة النموذج بشاشة السوق،
/// إشعارات الفرص، وأجوبة المساعد.
class NotAdviceNotice extends StatelessWidget {
  const NotAdviceNotice({super.key});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(top: 1),
          child: ExcludeSemantics(child: Icon(Icons.info_outline_rounded, size: AppSizes.iconSm, color: c.fg3)),
        ),
        const SizedBox(width: AppSpacing.xs),
        Expanded(
          child: Text(
            AppLocalizations.of(context)!.notAdviceNotice,
            style: context.textTheme.bodySmall!.copyWith(color: c.fg2),
          ),
        ),
      ],
    );
  }
}
