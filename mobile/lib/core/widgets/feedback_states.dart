import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';
import '../theme/theme_context.dart';
import 'app_button.dart';
import 'app_illustration.dart';

/// مكان محجوز أثناء التحميل. ثابت عن قصد (بدون نبض) - القاعدة إنو
/// الحلقة المتحرّكة الوحيدة بالتطبيق هي نقاط "المساعد عم يكتب".
class Skeleton extends StatelessWidget {
  const Skeleton({
    super.key,
    this.width,
    this.height = AppSpacing.md,
    this.radius = AppRadii.badge,
  });

  final double? width;
  final double height;
  final BorderRadius radius;

  @override
  Widget build(BuildContext context) {
    return ExcludeSemantics(
      child: Container(
        width: width,
        height: height,
        decoration: BoxDecoration(
          color: context.colors.pressed,
          borderRadius: radius,
        ),
      ),
    );
  }
}

/// مجموعة هياكل تحميل: القارئ الصوتي بيسمع "Loading…" مرة وحدة بدل صمت
/// (الـ [Skeleton] نفسه مخفي عن القارئ)
class LoadingRegion extends StatelessWidget {
  const LoadingRegion({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      liveRegion: true,
      label: AppLocalizations.of(context)!.loading,
      child: child,
    );
  }
}

/// حالة فاضية: شرح + الخطوة الجاية
///
/// مع [illustrated]: الأيقونة جوّا [AppIllustration] (للفراغ الأساسي بالشاشة).
class EmptyState extends StatelessWidget {
  const EmptyState({
    super.key,
    required this.icon,
    required this.title,
    this.message,
    this.actionLabel,
    this.onAction,
    this.illustrated = false,
  });

  final IconData icon;
  final String title;
  final String? message;
  final String? actionLabel;
  final VoidCallback? onAction;
  final bool illustrated;

  @override
  Widget build(BuildContext context) {
    return _StateLayout(
      icon: icon,
      illustration: illustrated ? AppIllustration(icon: icon) : null,
      iconColor: context.colors.fg3,
      title: title,
      message: message,
      action: actionLabel == null ? null : AppButton.secondary(label: actionLabel!, onPressed: onAction),
    );
  }
}

/// حالة خطأ: أيقونة + كلمة (برتقالي danger، مش أحمر) + "حاول مجددًا"
class ErrorState extends StatelessWidget {
  const ErrorState({super.key, this.title, this.message, this.onRetry});

  final String? title;
  final String? message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return _StateLayout(
      icon: Icons.error_outline_rounded,
      iconColor: context.colors.danger,
      title: title ?? l10n.somethingWentWrong,
      message: message,
      action: onRetry == null
          ? null
          : AppButton.secondary(
              label: l10n.tryAgain,
              icon: Icons.refresh_rounded,
              onPressed: onRetry,
            ),
    );
  }
}

class _StateLayout extends StatelessWidget {
  const _StateLayout({
    required this.icon,
    required this.iconColor,
    required this.title,
    this.message,
    this.action,
    this.illustration,
  });

  final IconData icon;
  final Widget? illustration;
  final Color iconColor;
  final String title;
  final String? message;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    // live region: الحالة (فاضي / خطأ / بدون اتصال) بتنقرأ لما تطلع بدل التحميل
    return Semantics(
      container: true,
      liveRegion: true,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            illustration ?? Icon(icon, size: AppSpacing.xxxl, color: iconColor),
            const SizedBox(height: AppSpacing.md),
            Semantics(
              header: true,
              child: Text(
                title,
                style: context.textTheme.titleMedium,
                textAlign: TextAlign.center,
              ),
            ),
            if (message != null) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(
                message!,
                style: context.textTheme.bodyMedium,
                textAlign: TextAlign.center,
              ),
            ],
            if (action != null) ...[
              const SizedBox(height: AppSpacing.lg),
              action!,
            ],
          ],
        ),
      ),
    );
  }
}
