import 'package:flutter/foundation.dart';

import '../../../core/widgets/direction_badge.dart';
import '../../markets/models/market_models.dart';

/// نقطة من توقّع النموذج: الوقت، السعر المتوقّع، وحدود النطاق (low / high)
@immutable
final class ForecastPoint {
  const ForecastPoint({required this.time, required this.expected, required this.low, required this.high});

  final DateTime time;
  final double expected;
  final double low;
  final double high;

  ForecastPoint shifted(double by) =>
      ForecastPoint(time: time, expected: expected + by, low: low + by, high: high + by);

  @override
  bool operator ==(Object other) =>
      other is ForecastPoint &&
      other.time == time &&
      other.expected == expected &&
      other.low == low &&
      other.high == high;

  @override
  int get hashCode => Object.hash(time, expected, low, high);
}

/// كلمة الاحتمال (الشرح والقارئ الصوتي): "high probability"، احتمال وليس وعد
enum ForecastLikelihood {
  high,
  moderate,
  low;

  static ForecastLikelihood of(double probability) => probability >= 0.7
      ? high
      : probability >= 0.6
          ? moderate
          : low;
}

/// توقّع النموذج لأداة + إطار: المسار المتوقّع بعد آخر شمعة على [Timeframe]
/// الرسم، مع نطاق (low / high)، الاتجاه والاحتمال.
///
/// مبني من نفس إشارة الاستراتيجية المحفوظة ([signalId]، نفس الطريقة [methodId]):
/// نفس الاتجاه ونفس الاحتمال، والمسار بيخلص عند هدف الخطة ([target]). على إطار
/// ما عليه إشارة، بيلحق اتجاه أقوى إشارة ([basisTimeframe]) باحتمال أقل.
/// الـ [points] بعد [anchorTime] (وقت آخر شمعة وقت الطلب) بخطوة شمعة وحدة.
@immutable
final class ForecastPath {
  const ForecastPath({
    required this.symbol,
    required this.timeframe,
    required this.methodId,
    required this.signalId,
    required this.basisTimeframe,
    required this.direction,
    required this.probability,
    required this.anchorTime,
    required this.anchorPrice,
    required this.target,
    required this.generatedAt,
    required this.validUntil,
    required this.points,
  });

  final String symbol;
  final Timeframe timeframe;
  final String methodId;

  /// الإشارة يلي التوقّع مبني عليها (`SYMBOL-tf-bucket@method`)
  final String signalId;

  /// إطار الإشارة [signalId]: نفس [timeframe] لما الاستراتيجية إلها إشارة عليه؛
  /// غيرو (مثلًا 1h على رسم 1m) لما التوقّع بيلحق اتجاه أقوى إشارة ([follows])
  final Timeframe basisTimeframe;

  /// بيلحق إشارة إطار تاني (ما في خطة على إطار الرسم): نفس الاتجاه، احتمال أقل
  bool get follows => basisTimeframe != timeframe;
  final SignalDirection direction;

  /// نفس احتمال الإشارة (0..1)، أو أقل منو لما [follows]
  final double probability;

  /// آخر شمعة وقت الطلب (بدايتها) وسعرها (منتصف منطقة الدخول)
  final DateTime anchorTime;
  final double anchorPrice;

  /// منتصف منطقة الهدف بالخطة (آخر نقطة بالمسار)
  final double target;
  final DateTime generatedAt;

  /// صلاحية متناسبة مع الإطار (نفس صلاحية الإشارة لما في خطة): بعدها
  /// التوقّع "Outdated" وما بينرسم لحد التحديث الجاي
  final DateTime validUntil;

  /// النقاط الجاية بالترتيب (أول وحدة بعد [anchorTime] بشمعة)
  final List<ForecastPoint> points;

  ForecastLikelihood get likelihood => ForecastLikelihood.of(probability);

  /// السعر المتوقّع بآخر المسار
  double get expectedLevel => points.isEmpty ? anchorPrice : points.last.expected;

  DateTime get endTime => points.isEmpty ? anchorTime : points.last.time;

  bool isOutdated(DateTime now) => !now.isBefore(validUntil);

  /// المسار من آخر شمعة على الرسم ([lastTime] / [lastClose]) مع وصول النبضات:
  ///
  /// - أول نقطة = آخر شمعة نفسها (الخط بيبلّش من السعر الحي، بلا فجوة).
  /// - النقاط يلي صار وقتها ≤ [lastTime] (شمعة جديدة فتحت) بتنشال.
  /// - الفرق بين السعر الحي والمتوقّع بهاللحظة بيتوزّع ويتلاشى لآخر المسار،
  ///   فالمسار بيضل يخلص عند [target] (ما بيتغيّر رأي النموذج مع كل نبضة).
  /// حتمية وبدون طلب: نفس المدخلات = نفس النقاط.
  List<ForecastPoint> followFrom(DateTime lastTime, double lastClose) {
    var reference = anchorPrice;
    final ahead = <ForecastPoint>[];
    for (final p in points) {
      if (p.time.isAfter(lastTime)) {
        ahead.add(p);
      } else {
        reference = p.expected;
      }
    }
    if (ahead.isEmpty) return const [];
    final delta = lastClose - reference;
    final n = ahead.length;
    return [
      ForecastPoint(time: lastTime, expected: lastClose, low: lastClose, high: lastClose),
      for (var i = 0; i < n; i++) ahead[i].shifted(delta * (1 - (i + 1) / n)),
    ];
  }
}
