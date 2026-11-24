import 'package:flutter/material.dart';

/// تسمية جزء بشريط مقسّم (`ButtonSegment.label`): دايمًا سطر واحد.
///
/// الأجزاء بعرض متساوي؛ لما الكلمة ما بتساع (خط كبير، عربي أطول) بتصغر
/// لتساع بدل ما تلتف لسطرين أو تنقص بـ "…". الارتفاع بيضل ≥ 48 dp من الثيم.
class SegmentLabel extends StatelessWidget {
  const SegmentLabel(this.text, {super.key});

  final String text;

  @override
  Widget build(BuildContext context) => FittedBox(
        fit: BoxFit.scaleDown,
        child: Text(text, maxLines: 1, softWrap: false, textAlign: TextAlign.center),
      );
}
