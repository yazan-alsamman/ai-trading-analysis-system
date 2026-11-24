import 'dart:io';

import '../../../core/data/low_data_mode.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_card.dart';
import '../../../l10n/app_localizations.dart';
import '../../../models/user_model.dart';

/// بطاقة الهوية أعلى البروفايل: صورة/حرف + الاسم + البريد + شارة الدور
///
/// الضغط عليها بيفتح تعديل البروفايل.
class ProfileIdentityCard extends StatelessWidget {
  const ProfileIdentityCard({
    super.key,
    required this.name,
    required this.email,
    required this.avatarPath,
    required this.role,
    required this.onTap,
  });

  final String name;
  final String email;
  final String? avatarPath;
  final UserRole role;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;

    return AppCard(
      onTap: onTap,
      semanticLabel: '$name, $email, ${roleLabel(l10n, role)}. ${l10n.editProfileHint}',
      child: ExcludeSemantics(
        child: Row(
          children: [
            ProfileAvatar(name: name, path: avatarPath),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    name,
                    style: text.titleMedium,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    email,
                    style: text.bodySmall!.copyWith(color: c.fg2),
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  RoleBadge(role: role),
                ],
              ),
            ),
            Icon(Icons.chevron_right_rounded, color: c.fg3, size: AppSizes.iconLg),
          ],
        ),
      ),
    );
  }
}

String roleLabel(AppLocalizations l10n, UserRole role) => switch (role) {
      UserRole.trader => l10n.roleTrader,
      UserRole.expert => l10n.roleExpert,
      UserRole.admin => l10n.roleAdmin,
    };

/// شارة الدور (نفس شارة الدور بمنشورات المجتمع على الويب)
class RoleBadge extends StatelessWidget {
  const RoleBadge({super.key, required this.role});

  final UserRole role;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return DecoratedBox(
      decoration: BoxDecoration(color: c.accentSoft, borderRadius: AppRadii.badge),
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.xs,
          vertical: AppSpacing.xxs / 2,
        ),
        child: Text(
          roleLabel(AppLocalizations.of(context)!, role),
          style: context.textTheme.labelSmall!.copyWith(color: c.accent),
        ),
      ),
    );
  }
}

/// صورة المستخدم، أو أول حرف من اسمه لما ما في صورة
class ProfileAvatar extends ConsumerWidget {
  const ProfileAvatar({super.key, required this.name, required this.path, this.size = 56});

  final String name;
  final String? path;
  final double size;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final initial = name.isEmpty ? '?' : name.characters.first.toUpperCase();
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: c.accentSoft,
        shape: BoxShape.circle,
        border: Border.all(color: c.accent.withValues(alpha: 0.35)),
        image: path == null
            ? null
            // فكّ الصورة على حجم الدائرة بس (H5b: أصغر كمان بالـ Low data mode)
            : DecorationImage(
                image: ResizeImage(
                  FileImage(File(path!)),
                  width: imageDecodeSize(size, MediaQuery.devicePixelRatioOf(context), ref.watch(lowDataImageScaleProvider)),
                ),
                fit: BoxFit.cover,
              ),
      ),
      alignment: Alignment.center,
      child: path == null
          ? Text(
              initial,
              style: (size >= 80 ? context.textTheme.displaySmall : context.textTheme.titleLarge)!
                  .copyWith(color: c.accent),
            )
          : null,
    );
  }
}
