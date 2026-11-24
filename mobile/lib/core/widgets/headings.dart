import 'package:flutter/material.dart';

import '../theme/theme_context.dart';

/// سطر صغير قبل الأقسام: `04 · RISK MANAGEMENT`
/// (mono بأحرف كبيرة بالإنجليزي، عادي بالعربي)
class Eyebrow extends StatelessWidget {
  const Eyebrow(this.text, {super.key, this.color});

  final String text;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final type = context.type;
    return Text(
      type.eyebrowUppercase ? text.toUpperCase() : text,
      style: color == null ? type.eyebrow : type.eyebrow.copyWith(color: color),
    );
  }
}

/// عنوان تحريري: eyebrow اختياري + عنوان serif + جملة ثانية خافتة مائلة
/// ("A clearer way *to read the markets.*") - التأكيد بالتخفيف مش بالزيادة.
///
/// للشاشات التحريرية بس (splash / auth / ترحيب Home) - أبدًا فوق بيانات كثيفة.
class SectionHeading extends StatelessWidget {
  const SectionHeading({
    super.key,
    required this.title,
    this.muted,
    this.eyebrow,
    this.size = SectionHeadingSize.medium,
  });

  final String title;

  /// الجملة الثانية الخافتة (اختيارية)
  final String? muted;
  final String? eyebrow;
  final SectionHeadingSize size;

  @override
  Widget build(BuildContext context) {
    final base = switch (size) {
      SectionHeadingSize.large => context.textTheme.displayLarge!,
      SectionHeadingSize.medium => context.textTheme.displayMedium!,
      SectionHeadingSize.small => context.textTheme.displaySmall!,
    };
    final mutedStyle = context.type.displayMuted.copyWith(
      fontSize: base.fontSize,
      height: base.height,
      letterSpacing: base.letterSpacing,
    );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (eyebrow != null) ...[
          Eyebrow(eyebrow!),
          const SizedBox(height: AppSpacing.xs),
        ],
        Semantics(
          header: true,
          child: Text.rich(
            TextSpan(children: [
              TextSpan(text: title),
              if (muted != null) TextSpan(text: ' $muted', style: mutedStyle),
            ]),
            style: base,
          ),
        ),
      ],
    );
  }
}

enum SectionHeadingSize { large, medium, small }
