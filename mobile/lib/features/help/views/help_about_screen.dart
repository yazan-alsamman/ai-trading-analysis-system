import 'package:flutter/material.dart';

import '../../../app/router/app_navigator.dart';
import '../../../core/app_info.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/brand_mark.dart';
import '../../../core/widgets/headings.dart';
import '../../../core/widgets/page_header.dart';
import '../../../core/widgets/settings_group.dart';
import '../../../l10n/app_localizations.dart';
import 'legal_screen.dart';

/// "Help & about" (من Profile): عن التطبيق باختصار + "ما بيتداول أبدًا"،
/// أسئلة شائعة، الوثائق القانونية، تراخيص الطرف الثالث، والنسخة.
class HelpAboutScreen extends StatelessWidget {
  const HelpAboutScreen({super.key});

  void _openLicenses(BuildContext context, AppLocalizations l10n) => showLicensePage(
        context: context,
        applicationName: l10n.appName,
        applicationVersion: l10n.versionLine(AppInfo.version, AppInfo.build),
        applicationIcon: const Padding(
          padding: EdgeInsets.all(AppSpacing.xs),
          child: BrandGlyph(size: 48),
        ),
      );

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final text = context.textTheme;
    final c = context.colors;
    final gutter = AppSpacing.gutter(context);

    final faqs = [
      (l10n.faqModelReadQ, l10n.faqModelReadA),
      (l10n.faqSimulatedQ, l10n.faqSimulatedA),
      (l10n.faqAccuracyQ, l10n.faqAccuracyA),
      (l10n.faqStrategyQ, l10n.faqStrategyA),
    ];

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: ListView(
          padding: const EdgeInsets.only(bottom: AppSpacing.xxl),
          children: [
            PageHeader(title: l10n.helpAndAbout, back: const PageBackButton()),
            Padding(
              padding: EdgeInsets.fromLTRB(gutter, AppSpacing.xs, gutter, 0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Align(alignment: AlignmentDirectional.centerStart, child: BrandMark()),
                  const SizedBox(height: AppSpacing.md),
                  Text(l10n.aboutShort, style: text.bodyLarge),
                  const SizedBox(height: AppSpacing.lg),
                  AppCard(
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(Icons.block_rounded, color: c.accent, size: AppSizes.iconLg),
                        const SizedBox(width: AppSpacing.sm),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Semantics(
                                header: true,
                                child: Text(l10n.neverTradesTitle, style: text.titleMedium),
                              ),
                              const SizedBox(height: AppSpacing.xxs),
                              Text(l10n.neverTradesBody, style: text.bodyMedium),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: AppSpacing.xl),
                  _FaqGroup(title: l10n.frequentlyAskedQuestions, items: faqs),
                  const SizedBox(height: AppSpacing.xl),
                  SettingsGroup(
                    title: l10n.legal,
                    children: [
                      for (final (doc, icon) in const [
                        (LegalDocument.riskDisclosure, Icons.gpp_maybe_outlined),
                        (LegalDocument.dataOnDevice, Icons.phone_android_rounded),
                      ])
                        SettingsTile(
                          icon: icon,
                          title: LegalScreen.titleOf(l10n, doc),
                          onTap: () => context.pushLegal(doc),
                        ),
                      SettingsTile(
                        icon: Icons.article_outlined,
                        title: l10n.thirdPartyNotices,
                        subtitle: l10n.thirdPartyNoticesSubtitle,
                        onTap: () => _openLicenses(context, l10n),
                      ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.xl),
                  Text(
                    l10n.versionLine(AppInfo.version, AppInfo.build),
                    style: context.type.numSmall,
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// أسئلة شائعة: كل سؤال بينفتح بمكانه (الجواب قصير، ما بيستاهل شاشة)
class _FaqGroup extends StatelessWidget {
  const _FaqGroup({required this.title, required this.items});

  final String title;
  final List<(String, String)> items;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsetsDirectional.only(start: AppSpacing.xxs, bottom: AppSpacing.xs),
          child: Semantics(header: true, child: Eyebrow(title)),
        ),
        Material(
          color: c.card,
          shape: RoundedRectangleBorder(borderRadius: AppRadii.card, side: BorderSide(color: c.hairline)),
          clipBehavior: Clip.antiAlias,
          child: Column(
            children: [
              for (final (i, (question, answer)) in items.indexed) ...[
                if (i > 0) Divider(height: 1, thickness: 1, color: c.hairline),
                ExpansionTile(
                  shape: const Border(),
                  collapsedShape: const Border(),
                  minTileHeight: 56,
                  tilePadding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
                  childrenPadding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.md),
                  expandedCrossAxisAlignment: CrossAxisAlignment.start,
                  iconColor: c.fg2,
                  collapsedIconColor: c.fg3,
                  expansionAnimationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
                  title: Text(question, style: text.titleSmall),
                  children: [Text(answer, style: text.bodyMedium)],
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }
}
