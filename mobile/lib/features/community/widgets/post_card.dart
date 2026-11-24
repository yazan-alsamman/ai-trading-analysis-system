import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/clock.dart';
import '../../../core/format/formatters.dart';
import '../../../core/theme/theme_context.dart';
import '../../../l10n/app_localizations.dart';
import '../models/post.dart';

/// بطاقة منشور (نفس الشكل لكل الكتّاب): الكاتب (صورة بالحرف الأول + الاسم)
/// والوقت، النص كامل، شارة الأداة (بتفتح شاشتها)، وتحت: إعجاب وتعليقات. قائمة "خيارات": الحذف لمنشورك،
/// والبلاغ لمنشورات غيرك.
class PostCard extends ConsumerWidget {
  const PostCard({
    super.key,
    required this.post,
    required this.onLike,
    required this.onComments,
    this.onSymbol,
    this.onDelete,
    this.onReport,
  });

  final Post post;
  final VoidCallback onLike;
  final VoidCallback onComments;
  final ValueChanged<String>? onSymbol;

  /// null = مش منشورك
  final VoidCallback? onDelete;

  /// null = منشورك (ما بتبلّغ عن حالك)
  final VoidCallback? onReport;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final text = context.textTheme;
    final l10n = AppLocalizations.of(context)!;
    final now = ref.watch(clockProvider).valueOrNull ?? DateTime.now();
    final author = post.isOwn ? l10n.commentAuthorYou : post.authorName;

    return Semantics(
      container: true,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: c.card,
          borderRadius: AppRadii.card,
          border: Border.all(color: c.hairline),
        ),
        child: Padding(
          // البداية xxs: أزرار الإعجاب والتعليق إلها padding داخلي sm، فأيقوناتها
          // بتصفّ مع الصورة (xxs + sm = md)
          padding: const EdgeInsetsDirectional.fromSTEB(AppSpacing.xxs, AppSpacing.md, AppSpacing.xs, AppSpacing.xxs),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsetsDirectional.only(start: AppSpacing.sm),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _Avatar(name: author, own: post.isOwn),
                        const SizedBox(width: AppSpacing.sm),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(author, style: text.titleSmall),
                              const SizedBox(height: 2),
                              Text(relativeTime(l10n, post.createdAt, now), style: text.bodySmall),
                            ],
                          ),
                        ),
                        if (onDelete != null || onReport != null)
                          PopupMenuButton<VoidCallback>(
                            useRootNavigator: true,
                            tooltip: l10n.postOptions,
                            icon: Icon(Icons.more_vert_rounded, color: c.fg3),
                            onSelected: (action) => action(),
                            itemBuilder: (context) => [
                              if (onDelete case final delete?)
                                PopupMenuItem(
                                  value: delete,
                                  child: Row(
                                    children: [
                                      Icon(Icons.delete_outline_rounded, size: AppSizes.iconMd, color: c.danger),
                                      const SizedBox(width: AppSpacing.sm),
                                      Flexible(child: Text(l10n.postDelete)),
                                    ],
                                  ),
                                ),
                              if (onReport case final report?)
                                PopupMenuItem(
                                  value: report,
                                  // بلّغت قبل: البند بيضل ظاهر بس معطّل ("Reported")
                                  enabled: !post.reportedByMe,
                                  child: Row(
                                    children: [
                                      Icon(
                                        post.reportedByMe ? Icons.flag_rounded : Icons.flag_outlined,
                                        size: AppSizes.iconMd,
                                        color: c.fg2,
                                      ),
                                      const SizedBox(width: AppSpacing.sm),
                                      Flexible(child: Text(post.reportedByMe ? l10n.postReported : l10n.postReport)),
                                    ],
                                  ),
                                ),
                            ],
                          )
                        else
                          const SizedBox(width: AppSpacing.xs),
                      ],
                    ),
                    Padding(
                      padding: const EdgeInsetsDirectional.only(top: AppSpacing.sm, end: AppSpacing.xs),
                      child: Text(post.body, style: text.bodyMedium!.copyWith(color: c.fg)),
                    ),
                    if (post.symbol case final symbol?)
                      Padding(
                        padding: const EdgeInsets.only(top: AppSpacing.xxs),
                        child: _SymbolChip(symbol: symbol, onTap: onSymbol == null ? null : () => onSymbol!(symbol)),
                      ),
                  ],
                ),
              ),
              Row(
                children: [
                  _LikeButton(liked: post.likedByMe, count: post.likesCount, onPressed: onLike),
                  _ActionButton(
                    icon: Icons.mode_comment_outlined,
                    count: post.commentsCount,
                    semanticLabel: l10n.commentsTitle('${post.commentsCount}'),
                    onPressed: onComments,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Avatar extends StatelessWidget {
  const _Avatar({required this.name, required this.own});

  final String name;
  final bool own;

  static const double size = 40;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return ExcludeSemantics(
      child: Container(
        width: size,
        height: size,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: own ? c.accentSoft : c.inset,
          border: Border.all(color: c.hairline),
        ),
        child: Text(
          name.characters.first.toUpperCase(),
          style: context.textTheme.labelLarge!.copyWith(color: own ? c.accent : c.fg2),
        ),
      ),
    );
  }
}

/// شارة الأداة: بتفتح شاشة الأداة (منطقة لمس 48)
class _SymbolChip extends StatelessWidget {
  const _SymbolChip({required this.symbol, this.onTap});

  final String symbol;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    return Semantics(
      button: onTap != null,
      label: l10n.postOpenInstrument(symbol),
      onTap: onTap,
      excludeSemantics: true,
      child: InkWell(
        onTap: onTap,
        borderRadius: AppRadii.card,
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: AppSizes.minTap),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              DecoratedBox(
                decoration: BoxDecoration(
                  color: c.inset,
                  borderRadius: AppRadii.badge,
                  border: Border.all(color: c.lineStrong),
                ),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xs, vertical: AppSpacing.xxs),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.candlestick_chart_outlined, size: AppSizes.iconSm, color: c.accent),
                      const SizedBox(width: AppSpacing.xxs),
                      Text(symbol,
                          style: context.type.numSmall.copyWith(color: c.fg), textDirection: TextDirection.ltr),
                    ],
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

/// إعجاب: قلب (ذهبي لما معجب) + العدد. القارئ الصوتي بيسمع "إعجاب، 24" مع
/// حالة التبديل. تأكيد خفيف بالتكبير (spring) - بدون حركة مع "تقليل الحركة".
class _LikeButton extends StatelessWidget {
  const _LikeButton({required this.liked, required this.count, required this.onPressed});

  final bool liked;
  final int count;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final icon = AnimatedSwitcher(
      duration: context.motion(AppMotion.fast),
      switchInCurve: AppMotion.spring,
      transitionBuilder: (child, animation) => ScaleTransition(scale: animation, child: child),
      child: Icon(
        liked ? Icons.favorite_rounded : Icons.favorite_border_rounded,
        key: ValueKey(liked),
        size: AppSizes.iconMd,
        color: liked ? c.accent : c.fg2,
      ),
    );
    return _ActionButton(
      iconWidget: icon,
      count: count,
      semanticLabel: l10n.postLikes('$count'),
      toggled: liked,
      onPressed: () {
        AppHaptics.selection();
        onPressed();
      },
    );
  }
}

class _ActionButton extends StatelessWidget {
  const _ActionButton({
    this.icon,
    this.iconWidget,
    required this.count,
    required this.semanticLabel,
    required this.onPressed,
    this.toggled,
  });

  final IconData? icon;
  final Widget? iconWidget;
  final int count;
  final String semanticLabel;
  final VoidCallback onPressed;
  final bool? toggled;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Semantics(
      button: true,
      toggled: toggled,
      label: semanticLabel,
      onTap: onPressed,
      excludeSemantics: true,
      child: InkWell(
        onTap: onPressed,
        borderRadius: AppRadii.pillAll,
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: AppSizes.minTap, minWidth: AppSizes.minTap),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                iconWidget ?? Icon(icon, size: AppSizes.iconMd, color: c.fg2),
                const SizedBox(width: AppSpacing.xs),
                Text('$count', style: context.type.numSmall.copyWith(color: c.fg2)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
