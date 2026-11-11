import 'package:flutter/widgets.dart';

/// المسافات - شبكة 4dp (DESIGN_SPEC.md §5). ممنوع أرقام سحرية بالشاشات.
abstract final class AppSpacing {
  static const double xxs = 4;
  static const double xs = 8;
  static const double sm = 12;
  static const double md = 16;
  static const double lg = 20;
  static const double xl = 24;
  static const double xxl = 32;
  static const double xxxl = 40;
  static const double huge = 48;

  /// الهامش الجانبي للشاشة: 16، و20 على الشاشات ≥ 400dp
  static double gutter(BuildContext context) =>
      MediaQuery.sizeOf(context).width >= 400 ? lg : md;

  /// المسافة بين الأقسام الكبيرة بالشاشة
  static const double section = xl;
  static const double sectionLarge = xxl;
}

/// الزوايا: صغيرة وحادة على البيانات، أنعم على البطاقات التحريرية
abstract final class AppRadii {
  /// badges و tags
  static const double xs = 4;

  /// الحقول والبطاقات الكثيفة
  static const double md = 12;

  /// البطاقات التحريرية / البطل
  static const double lg = 16;

  /// أعلى الـ bottom sheet والـ dialogs (Material 3)
  static const double xl = 28;

  /// الكبسولة (pill): الأزرار الرئيسية، الـ segmented، الـ chips
  static const double pill = 999;

  static const BorderRadius badge = BorderRadius.all(Radius.circular(xs));
  static const BorderRadius field = BorderRadius.all(Radius.circular(md));
  static const BorderRadius card = BorderRadius.all(Radius.circular(md));
  static const BorderRadius heroCard = BorderRadius.all(Radius.circular(lg));
  static const BorderRadius dialog = BorderRadius.all(Radius.circular(xl));
  static const BorderRadius sheetTop =
      BorderRadius.vertical(top: Radius.circular(xl));
  static const BorderRadius pillAll = BorderRadius.all(Radius.circular(pill));
}

/// المقاسات الثابتة
abstract final class AppSizes {
  /// أصغر منطقة لمس (Android 48dp، أكبر من حد iOS 44pt)
  static const double minTap = 48;

  static const double iconSm = 16;
  static const double iconMd = 20;
  static const double iconLg = 24;

  /// ارتفاع الأزرار الرئيسية
  static const double buttonHeight = 52;
  static const double buttonHeightSm = 40;

  static const double hairline = 1;
}
