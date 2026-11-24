import 'package:flutter/material.dart';

import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/headings.dart';
import '../../../core/widgets/page_header.dart';
import '../../../l10n/app_localizations.dart';

/// الوثائق القانونية الموجودة فعلًا (نفس صفحات الويب). شروط الخدمة وسياسة
/// الخصوصية "قيد التحضير" بالويب، فما بينعرضوا لحد ما ينكتبوا.
enum LegalDocument { riskDisclosure, dataOnDevice }

/// صفحة قراءة لوثيقة: عنوان + مقدّمة + تاريخ آخر تحديث + أقسام مرقّمة
class LegalScreen extends StatelessWidget {
  const LegalScreen({super.key, required this.document});

  final LegalDocument document;

  static String titleOf(AppLocalizations l10n, LegalDocument document) => switch (document) {
        LegalDocument.riskDisclosure => l10n.riskDisclosure,
        LegalDocument.dataOnDevice => l10n.legalDataTitle,
      };

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final text = context.textTheme;
    final gutter = AppSpacing.gutter(context);

    final (String intro, List<(String, String)> parts) = switch (document) {
      LegalDocument.riskDisclosure => (
          l10n.legalRiskIntro,
          [
            (l10n.legalRisk1Title, l10n.legalRisk1Body),
            (l10n.legalRisk2Title, l10n.legalRisk2Body),
            (l10n.legalRisk3Title, l10n.legalRisk3Body),
            (l10n.legalRisk4Title, l10n.legalRisk4Body),
            (l10n.legalRisk5Title, l10n.legalRisk5Body),
            (l10n.legalRisk6Title, l10n.legalRisk6Body),
          ],
        ),
      LegalDocument.dataOnDevice => (
          l10n.legalDataIntro,
          [
            (l10n.legalData1Title, l10n.legalData1Body),
            (l10n.legalData2Title, l10n.legalData2Body),
            (l10n.legalData3Title, l10n.legalData3Body),
          ],
        ),
    };

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: ListView(
          padding: const EdgeInsets.only(bottom: AppSpacing.xxl),
          children: [
            PageHeader(title: titleOf(l10n, document), back: const PageBackButton()),
            Padding(
              padding: EdgeInsets.fromLTRB(gutter, AppSpacing.xs, gutter, 0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Eyebrow(l10n.legal),
                  const SizedBox(height: AppSpacing.xs),
                  Text(intro, style: text.bodyLarge),
                  const SizedBox(height: AppSpacing.xxs),
                  Text(l10n.legalUpdated, style: text.labelMedium),
                  for (final (title, body) in parts) ...[
                    const SizedBox(height: AppSpacing.xl),
                    Semantics(header: true, child: Text(title, style: text.titleMedium)),
                    const SizedBox(height: AppSpacing.xs),
                    Text(body, style: text.bodyMedium),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
