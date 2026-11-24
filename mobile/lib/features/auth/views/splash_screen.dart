import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/brand_mark.dart';
import '../../../l10n/app_localizations.dart';
import '../../../providers/app_providers.dart';
import '../auth_state.dart';

/// شاشة الإطلاق القصيرة: الشعار بينبني (الشموع، بعدين خط النموذج)، وبنفس
/// الوقت منقرأ الجلسة المحفوظة (`AuthController.restoreSession`). بعد
/// [displayDuration] وقراءة الجلسة (الاتنين) منعلّم إنو الجلسة انقرأت
/// (`sessionRestoredProvider`)، والـ redirect تبع الـ router بيقرّر: جلسة →
/// الرئيسية، بدونها → Welcome. مع "تقليل الحركة" الشعار بيطلع كامل فورًا.
///
/// TODO(B02): مع الـ API، الاستعادة بتجيب البروفايل بالـ token المحفوظ.
class SplashScreen extends ConsumerStatefulWidget {
  const SplashScreen({super.key});

  static const Duration displayDuration = Duration(milliseconds: 1300);

  static const double glyphSize = 96;

  @override
  ConsumerState<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends ConsumerState<SplashScreen> {
  @override
  void initState() {
    super.initState();
    Future.wait<Object?>([
      Future<void>.delayed(SplashScreen.displayDuration),
      ref.read(authControllerProvider).restoreSession(),
    ]).then((_) {
      // الـ redirect بيبدّل الشجرة كلها، فزر الرجوع ما بيرجّع للـ splash أبدًا
      if (mounted) ref.read(sessionRestoredProvider.notifier).markRestored();
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final glyph = context.reduceMotion
        ? const BrandGlyph(size: SplashScreen.glyphSize, glow: true)
        : TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: 1),
            duration: AppMotion.emphasis,
            curve: AppMotion.out,
            builder: (context, progress, _) => BrandGlyph(size: SplashScreen.glyphSize, progress: progress, glow: true),
          );

    return Scaffold(
      backgroundColor: context.colors.canvas,
      body: Center(
        child: Semantics(label: l10n.appName, child: glyph),
      ),
    );
  }
}
