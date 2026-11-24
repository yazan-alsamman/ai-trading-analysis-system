import 'package:flutter/material.dart';

import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/brand_mark.dart';
import '../../../core/widgets/offline_banner.dart';
import '../../../core/widgets/page_header.dart';
import '../../../l10n/app_localizations.dart';
import 'auth_backdrop.dart';

/// الـ Hero المشترك بين Welcome و Log in و Create account: الشعار بيطير من
/// قلب الرسم بـ Welcome لراس الشاشة الجاية (ومع "تقليل الحركة" ما بيطير).
const Object kAuthBrandHeroTag = 'auth-brand-glyph';

/// الشعار كـ Hero (بيتعطّل الطيران مع "تقليل الحركة")
class AuthBrandHero extends StatelessWidget {
  const AuthBrandHero({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) => HeroMode(
        enabled: !context.reduceMotion,
        child: Hero(tag: kAuthBrandHeroTag, child: child),
      );
}

/// هيكل شاشات الدخول: خلفية الـ mesh، سهم رجوع لما في شاشة قبل، والمحتوى
/// بسكرول بعرض أقصى مريح للقراءة. الكيبورد بيدفع المحتوى لفوق بدل ما يغطّي
/// الحقول.
class AuthScaffold extends StatelessWidget {
  const AuthScaffold({super.key, required this.children, this.showBack = true});

  final List<Widget> children;
  final bool showBack;

  /// عرض المحتوى الأقصى على التابلت / الشاشات العريضة
  static const double maxContentWidth = 480;

  @override
  Widget build(BuildContext context) {
    final gutter = AppSpacing.gutter(context);
    final canPop = showBack && (ModalRoute.of(context)?.canPop ?? false);

    return Scaffold(
      bottomNavigationBar: const OfflineBanner(),
      body: AuthBackdrop(
        child: SafeArea(
          child: Column(
            children: [
              Padding(
                padding: EdgeInsetsDirectional.fromSTEB(gutter - AppSpacing.sm, AppSpacing.xs, gutter, 0),
                child: SizedBox(
                  height: AppSizes.minTap,
                  child: Align(
                    alignment: AlignmentDirectional.centerStart,
                    child: canPop ? const PageBackButton() : null,
                  ),
                ),
              ),
              Expanded(
                child: SingleChildScrollView(
                  keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
                  padding: EdgeInsets.fromLTRB(gutter, AppSpacing.xs, gutter, AppSpacing.xxl),
                  child: Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: maxContentWidth),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: children,
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// راس شاشة دخول: الشعار (أو أيقونة ببلاطة) بهالة ذهبية ناعمة بس - بدون حلقة ولا إطار، العنوان بلون واحد صافي (serif)،
/// وتحتو سطر شرح. [emphasis] بينضاف عريض بآخر السطر (البريد بشاشة الرمز).
class AuthHeader extends StatelessWidget {
  const AuthHeader({super.key, required this.title, this.subtitle, this.emphasis, this.icon});

  final String title;
  final String? subtitle;
  final String? emphasis;

  /// null = الشعار (Hero مع Welcome)
  final IconData? icon;

  static const double badgeSize = 52;

  /// امتداد الهالة = هامش الشاشة، فما بتطلع برّا الشاشة بالعرض
  static const double glowSpread = AppSpacing.md;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;

    final badge = icon == null
        ? const AuthBrandHero(child: BrandGlyph(size: badgeSize, glow: true, glowSpread: glowSpread))
        : ExcludeSemantics(
            child: Container(
              width: badgeSize,
              height: badgeSize,
              decoration: BoxDecoration(
                color: c.raised,
                // نفس زاوية بلاطة الشعار (9 من 32)
                borderRadius: BorderRadius.circular(badgeSize * 9 / 32),
              ),
              child: Icon(icon, size: AppSizes.iconLg, color: c.accent),
            ),
          );
    final glowing = icon == null ? badge : BrandGlow(spread: glowSpread, child: badge);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // مسافة فوق قد الهالة، حتى ما تنقصها حافة السكرول
        Padding(padding: const EdgeInsets.only(top: glowSpread - AppSpacing.xs), child: glowing),
        const SizedBox(height: AppSpacing.xl),
        Semantics(
          header: true,
          child: Text(title, style: text.displayMedium!.copyWith(color: c.fg)),
        ),
        if (subtitle != null) ...[
          const SizedBox(height: AppSpacing.xs),
          Text.rich(
            TextSpan(children: [
              TextSpan(text: subtitle),
              if (emphasis != null)
                TextSpan(text: ' $emphasis', style: TextStyle(color: c.fg, fontWeight: FontWeight.w600)),
            ]),
            style: text.bodyLarge!.copyWith(color: c.fg2),
          ),
        ],
      ],
    );
  }
}

/// لوح النموذج: سطح البطاقة فوق الخلفية بخط ذهبي رفيع بأعلاه (زخرفة)
class AuthPanel extends StatelessWidget {
  const AuthPanel({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: c.card.withValues(alpha: 0.94),
        borderRadius: AppRadii.heroCard,
        border: Border.all(color: c.hairline),
      ),
      child: Stack(
        children: [
          PositionedDirectional(
            top: 0,
            start: AppSpacing.xl,
            end: AppSpacing.xl,
            height: 1,
            child: ExcludeSemantics(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  gradient: LinearGradient(colors: [
                    c.accent.withValues(alpha: 0),
                    c.accent.withValues(alpha: 0.55),
                    c.accent.withValues(alpha: 0),
                  ]),
                ),
              ),
            ),
          ),
          Padding(padding: const EdgeInsets.all(AppSpacing.lg), child: child),
        ],
      ),
    );
  }
}

/// سطر التنبيه القصير: "للتحليل ودعم القرار فقط..." (أيقونة + نص)
class AuthDisclaimer extends StatelessWidget {
  const AuthDisclaimer({super.key});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(top: 1),
          child: Icon(Icons.shield_outlined, size: AppSizes.iconSm, color: c.fg3),
        ),
        const SizedBox(width: AppSpacing.xs),
        Flexible(
          child: Text(
            l10n.authDisclaimer,
            style: context.textTheme.bodySmall!.copyWith(color: c.fg2),
            textAlign: TextAlign.center,
          ),
        ),
      ],
    );
  }
}

/// رسالة فشل تحت الحقول (برتقالي danger، أيقونة + نص، بيعلنها القارئ الصوتي)
class AuthErrorBanner extends StatelessWidget {
  const AuthErrorBanner(this.message, {super.key});

  final String message;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Semantics(
      liveRegion: true,
      container: true,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: c.dangerSoft,
          borderRadius: AppRadii.card,
          border: Border.all(color: c.danger.withValues(alpha: 0.4)),
        ),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.sm),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.error_outline_rounded, size: AppSizes.iconMd, color: c.danger),
              const SizedBox(width: AppSpacing.xs),
              Expanded(child: Text(message, style: context.textTheme.bodyMedium!.copyWith(color: c.fg))),
            ],
          ),
        ),
      ),
    );
  }
}

/// سطر "عندك حساب؟ Log in" تحت الزر الرئيسي
class AuthSwitchRow extends StatelessWidget {
  const AuthSwitchRow({super.key, required this.question, required this.action, required this.onPressed});

  final String question;
  final String action;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      alignment: WrapAlignment.center,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        Text(question, style: context.textTheme.bodyMedium),
        TextButton(
          onPressed: onPressed,
          style: TextButton.styleFrom(minimumSize: const Size(AppSizes.minTap, AppSizes.minTap)),
          child: Text(action),
        ),
      ],
    );
  }
}
