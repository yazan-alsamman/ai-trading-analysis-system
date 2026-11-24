import '../../l10n/app_localizations.dart';

/// تنسيق الأرقام المشترك (نسب، مبالغ، ساعة) - نفس صيغ `web/src/lib/format.ts`
///
/// الأرقام دايمًا بأرقام لاتينية وبخط mono (حتى بالعربي)، متل الويب.
abstract final class Formatters {
  /// احتمال/نسبة من 0..1 لـ "72%" (أو "57.4%" مع [decimals])
  static String percent(double ratio, {int decimals = 0}) =>
      '${(ratio * 100).toStringAsFixed(decimals)}%';

  /// رقم عادي بعدد خانات ثابت ("0.231")
  static String number(double value, int decimals) => value.toStringAsFixed(decimals);

  /// نسبة مكتوبة بالمية أصلًا (1 → "1%"، 1.5 → "1.5%") بدون أصفار زايدة
  static String plainPercent(double value) => '${trimZeros(value.toStringAsFixed(2))}%';

  /// رقم مع فواصل الآلاف: 38461.5 → "38,461.5" (بـ [decimals] خانات، بدون أصفار زايدة)
  static String grouped(double value, {int decimals = 0}) {
    final parts = trimZeros(value.abs().toStringAsFixed(decimals)).split('.');
    final whole = parts.first.replaceAllMapped(_thousands, (_) => ',');
    return '${value < 0 ? '−' : ''}$whole${parts.length > 1 ? '.${parts.last}' : ''}';
  }

  /// "1.50" → "1.5"، "2.00" → "2"
  static String trimZeros(String fixed) =>
      fixed.contains('.') ? fixed.replaceFirst(_trailingZeros, '') : fixed;

  // مترجمة مرة وحدة (كانت تنبني مع كل رقم بكل صف)
  static final RegExp _thousands = RegExp(r'\B(?=(\d{3})+(?!\d))');
  static final RegExp _trailingZeros = RegExp(r'\.?0+$');

  /// مبلغ مع رمز العملة وفواصل الآلاف: "USD 1,250.00"
  static String money(double amount, String currency) {
    final fixed = amount.abs().toStringAsFixed(2);
    final parts = fixed.split('.');
    final whole = parts.first.replaceAllMapped(_thousands, (_) => ',');
    return '${amount < 0 ? '−' : ''}$currency $whole.${parts.last}';
  }

  /// ساعة بصيغة 24 ساعة: "14:05"
  static String clock(DateTime time) =>
      '${time.hour.toString().padLeft(2, '0')}:${time.minute.toString().padLeft(2, '0')}';
}

/// وقت نسبي قصير: "Just now" / "12m ago" / "3h ago" / "2d ago" (حسب اللغة)
String relativeTime(AppLocalizations l10n, DateTime time, DateTime now) {
  final diff = now.difference(time);
  if (diff.inMinutes < 1) return l10n.justNow;
  if (diff.inHours < 1) return l10n.minutesAgo(diff.inMinutes);
  if (diff.inDays < 1) return l10n.hoursAgo(diff.inHours);
  return l10n.daysAgo(diff.inDays);
}
