import 'package:flutter/material.dart';

import '../../../core/theme/theme_context.dart';
import '../../../l10n/app_localizations.dart';

/// شرط التنبيه - نفس `AlertCondition` بالـ backend
enum AlertCondition {
  above('above'),
  below('below'),
  crossesAbove('crosses_above'),
  crossesBelow('crosses_below'),
  changePct('change_pct');

  const AlertCondition(this.apiValue);

  final String apiValue;

  static AlertCondition? fromApi(String? value) {
    for (final c in values) {
      if (c.apiValue == value) return c;
    }
    return null;
  }

  bool get isRising => this == above || this == crossesAbove;
}

/// حالة التنبيه المحفوظة (H4a). الانتقالات المسموحة بس:
/// Active ⇄ Paused، Active → Triggered، Active / Paused → Expired.
/// Triggered و Expired نهائيين (سجل): "Set again" بينشئ تنبيه جديد.
enum AlertStatus {
  active('active'),
  paused('paused'),
  triggered('triggered'),
  expired('expired');

  const AlertStatus(this.apiValue);

  final String apiValue;

  static AlertStatus? fromApi(String? value) {
    for (final s in values) {
      if (s.apiValue == value) return s;
    }
    return null;
  }

  /// بقسم "History" (مش "Active")
  bool get isHistory => this == triggered || this == expired;

  Set<AlertStatus> get next => switch (this) {
        active => const {paused, triggered, expired},
        paused => const {active, expired},
        triggered || expired => const {},
      };

  bool canMoveTo(AlertStatus to) => next.contains(to);
}

/// المدة قبل ما ينتهي التنبيه لحاله (اختيارية بشاشة "Set alert")
enum AlertExpiry {
  none(null),
  day(Duration(days: 1)),
  week(Duration(days: 7)),
  // شهر = 30 يوم (ثابت، بدون حساب أطوال الأشهر)
  month(Duration(days: 30));

  const AlertExpiry(this.duration);

  final Duration? duration;

  DateTime? from(DateTime now) => duration == null ? null : now.add(duration!);

  String label(AppLocalizations l10n) => switch (this) {
        none => l10n.alertExpiryNone,
        day => l10n.alertExpiryDay,
        week => l10n.alertExpiryWeek,
        month => l10n.alertExpiryMonth,
      };
}

/// تنبيه سعر (immutable) - حقول `PriceAlertRead` بالـ backend + الحالة (H4a)
@immutable
final class PriceAlert {
  const PriceAlert({
    required this.id,
    required this.symbol,
    required this.condition,
    required this.value,
    required this.status,
    required this.createdAt,
    this.note,
    this.expiresAt,
    this.lastTriggeredAt,
    this.triggeredPrice,
    this.armed = true,
  });

  final String id;
  final String symbol;
  final AlertCondition condition;

  /// السعر الهدف (أو نسبة مئوية لـ change_pct)
  final double value;
  final AlertStatus status;
  final String? note;
  final DateTime createdAt;

  /// null = ما بينتهي
  final DateTime? expiresAt;

  /// وقت ما اشتغل والسعر يلي وصله (Triggered بس)
  final DateTime? lastTriggeredAt;
  final double? triggeredPrice;

  /// false = "Set again" والسعر كان أصلًا ورا المستوى: لازم السعر يرجع لجهة
  /// البداية أول، وبعدين بيشتغل عالعبور الجاي (ما بيشتغل فورًا مرة تانية)
  final bool armed;

  bool get isActive => status == AlertStatus.active;

  AlertState get state => AlertState.of(this);

  /// السعر وصل المستوى أو تجاوزه (بالاتجاه المطلوب)
  bool crossedBy(double price) => condition.isRising ? price >= value : price <= value;

  /// انتهت مدته (لسّا مش بالسجل)
  bool isDue(DateTime now) => !status.isHistory && expiresAt != null && !now.isBefore(expiresAt!);

  /// هالسعر بيغيّر شي؟ (فحص سريع قبل ما نسأل الـ repository عن النسخة المحفوظة)
  bool reactsTo(double price) => isActive && (armed ? crossedBy(price) : !crossedBy(price));

  /// وقت آخر حدث بالسجل (للترتيب: الأحدث أول)
  DateTime get historyTime => switch (status) {
        AlertStatus.triggered => lastTriggeredAt ?? createdAt,
        AlertStatus.expired => expiresAt ?? createdAt,
        _ => createdAt,
      };

  /// الانتقال لـ [to] إذا مسموح، وإلا null (ما في تغيير)
  PriceAlert? moveTo(AlertStatus to, {DateTime? at, double? price}) {
    if (!status.canMoveTo(to)) return null;
    return _copy(
      status: to,
      lastTriggeredAt: to == AlertStatus.triggered ? at : lastTriggeredAt,
      triggeredPrice: to == AlertStatus.triggered ? price : triggeredPrice,
    );
  }

  PriceAlert copyWith({bool? isActive, bool? armed}) => _copy(
        status: isActive == null ? status : (isActive ? AlertStatus.active : AlertStatus.paused),
        armed: armed,
      );

  PriceAlert _copy({AlertStatus? status, DateTime? lastTriggeredAt, double? triggeredPrice, bool? armed}) => PriceAlert(
        id: id,
        symbol: symbol,
        condition: condition,
        value: value,
        status: status ?? this.status,
        createdAt: createdAt,
        note: note,
        expiresAt: expiresAt,
        lastTriggeredAt: lastTriggeredAt ?? this.lastTriggeredAt,
        triggeredPrice: triggeredPrice ?? this.triggeredPrice,
        armed: armed ?? this.armed,
      );

  @override
  bool operator ==(Object other) =>
      other is PriceAlert &&
      other.id == id &&
      other.symbol == symbol &&
      other.condition == condition &&
      other.value == value &&
      other.status == status &&
      other.note == note &&
      other.createdAt == createdAt &&
      other.expiresAt == expiresAt &&
      other.lastTriggeredAt == lastTriggeredAt &&
      other.triggeredPrice == triggeredPrice &&
      other.armed == armed;

  @override
  int get hashCode =>
      Object.hash(id, symbol, condition, value, status, note, createdAt, expiresAt, lastTriggeredAt, triggeredPrice, armed);
}

/// القسمين بالقائمة: "Active" (نشطة + موقوفة، الأحدث إنشاءً أول) و "History"
/// (اشتغلت + انتهت، الأحدث حدثًا أول)
({List<PriceAlert> active, List<PriceAlert> history}) splitAlerts(Iterable<PriceAlert> alerts) {
  final active = [for (final a in alerts) if (!a.status.isHistory) a]
    ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
  final history = [for (final a in alerts) if (a.status.isHistory) a]
    ..sort((a, b) => b.historyTime.compareTo(a.historyTime));
  return (active: active, history: history);
}

/// شو بيقدر المستخدم يعمل بالتنبيه بحالته الحالية
enum AlertAction { pause, resume, setAgain, delete }

/// حالة التنبيه للعرض (State pattern): كل حالة بتعرف تسميتها وأيقونتها ولونها
/// وشو مسموح فيها - الـ widgets بتسأل الحالة بدل ما تفحص حقول.
sealed class AlertState {
  const AlertState();

  factory AlertState.of(PriceAlert alert) => switch (alert.status) {
        AlertStatus.active => const AlertActive(),
        AlertStatus.paused => const AlertPaused(),
        AlertStatus.triggered => AlertTriggered(alert.lastTriggeredAt, alert.triggeredPrice),
        AlertStatus.expired => AlertExpired(alert.expiresAt),
      };

  /// التسمية (والقارئ الصوتي بيقولها): "Active" / "Triggered at 1.09012" / "Expired".
  /// [format] = تنسيق السعر بدقة الأداة.
  String label(AppLocalizations l10n, String Function(double) format);
  IconData get icon;
  Color color(AppColorTokens c);
  Set<AlertAction> get actions;

  /// الوقت يلي بينعرض جنب التسمية (اشتغل / انتهى / بينتهي)، null = ما في
  DateTime? time(PriceAlert alert);
}

final class AlertActive extends AlertState {
  const AlertActive();

  @override
  String label(AppLocalizations l10n, String Function(double) format) => l10n.alertActive;
  @override
  IconData get icon => Icons.notifications_active_outlined;
  @override
  Color color(AppColorTokens c) => c.accent;
  @override
  Set<AlertAction> get actions => const {AlertAction.pause, AlertAction.delete};
  @override
  DateTime? time(PriceAlert alert) => alert.expiresAt;
}

final class AlertPaused extends AlertState {
  const AlertPaused();

  @override
  String label(AppLocalizations l10n, String Function(double) format) => l10n.alertPaused;
  @override
  IconData get icon => Icons.notifications_paused_outlined;
  @override
  Color color(AppColorTokens c) => c.fg3;
  @override
  Set<AlertAction> get actions => const {AlertAction.resume, AlertAction.delete};
  @override
  DateTime? time(PriceAlert alert) => alert.expiresAt;
}

final class AlertTriggered extends AlertState {
  const AlertTriggered(this.at, this.price);

  final DateTime? at;
  final double? price;

  @override
  String label(AppLocalizations l10n, String Function(double) format) =>
      price == null ? l10n.alertTriggered : l10n.alertTriggeredAt(format(price!));
  @override
  IconData get icon => Icons.task_alt_rounded;
  @override
  Color color(AppColorTokens c) => c.fg2;
  @override
  Set<AlertAction> get actions => const {AlertAction.setAgain, AlertAction.delete};
  @override
  DateTime? time(PriceAlert alert) => at;
}

final class AlertExpired extends AlertState {
  const AlertExpired(this.at);

  final DateTime? at;

  @override
  String label(AppLocalizations l10n, String Function(double) format) => l10n.alertExpired;
  @override
  IconData get icon => Icons.timer_off_outlined;
  @override
  Color color(AppColorTokens c) => c.fg3;
  @override
  Set<AlertAction> get actions => const {AlertAction.delete};
  @override
  DateTime? time(PriceAlert alert) => at;
}

/// بيانات تنبيه جديد قبل ما ينحفظ (من شاشة "Set alert" أو "Set again")
@immutable
final class AlertDraft {
  const AlertDraft({
    required this.symbol,
    required this.condition,
    required this.value,
    this.note,
    this.expiresAt,
    this.armed = true,
  });

  final String symbol;
  final AlertCondition condition;
  final double value;
  final String? note;
  final DateTime? expiresAt;
  final bool armed;

  /// الشرط بيتحدّد لحاله من موقع الهدف بالنسبة للسعر الحالي
  static AlertCondition conditionFor({required double target, required double current}) =>
      target >= current ? AlertCondition.crossesAbove : AlertCondition.crossesBelow;

  /// "Set again": نفس المستوى والاتجاه والملاحظة ونفس طول المدة (من [now]).
  /// إذا السعر الحالي [current] أصلًا ورا المستوى (أو مش معروف) بيستنّى عبور
  /// جديد بدل ما يشتغل فورًا.
  factory AlertDraft.again(PriceAlert alert, {required DateTime now, double? current}) {
    final expiry = alert.expiresAt?.difference(alert.createdAt);
    return AlertDraft(
      symbol: alert.symbol,
      condition: alert.condition,
      value: alert.value,
      note: alert.note,
      expiresAt: expiry == null || expiry <= Duration.zero ? null : now.add(expiry),
      armed: current != null && !alert.crossedBy(current),
    );
  }
}

/// أخطاء التحقق من سعر التنبيه
enum AlertValueError { empty, invalid, notPositive, equalsCurrent }

/// بيتحقق من نص السعر - null = صالح
AlertValueError? validateAlertValue(String text, {required double current, required int precision}) {
  final trimmed = text.trim().replaceAll(',', '.');
  if (trimmed.isEmpty) return AlertValueError.empty;
  final value = double.tryParse(trimmed);
  if (value == null || value.isNaN || value.isInfinite) return AlertValueError.invalid;
  if (value <= 0) return AlertValueError.notPositive;
  final rounded = double.parse(value.toStringAsFixed(precision));
  if (rounded == double.parse(current.toStringAsFixed(precision))) {
    return AlertValueError.equalsCurrent;
  }
  return null;
}
