import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../markets/models/market_models.dart';

/// الأطر يلي توقّع النموذج بيشتغل عليها: **المكان الوحيد** للإعداد.
///
/// إطار مش بالقائمة = "No forecast right now" مع "Not available for this
/// timeframe" وبدون طلب. لو الـ backend الحقيقي حدّد أطر معيّنة (مثلًا النموذج
/// متدرّب على 1h بس)، منغيّر هالسطر وبس، بدون ما نلمس الواجهة.
const Set<Timeframe> forecastSupportedTimeframes = {
  Timeframe.m1,
  Timeframe.m15,
  Timeframe.h1,
  Timeframe.h4,
  Timeframe.d1,
};

/// نفس القائمة كـ provider (الـ ViewModel والشرح بيقروها من هون؛ الاختبارات
/// بتبدّلها لتجرّب إطار مش مدعوم)
final forecastSupportedTimeframesProvider = Provider<Set<Timeframe>>((ref) => forecastSupportedTimeframes);

/// أفق التوقّع على إطار: كم شمعة لقدّام بيرسم ([candles]) وكم شمعة بيضل صالح
/// ([validCandles]) من بداية الشمعة يلي انبنى عليها.
typedef ForecastHorizon = ({int candles, int validCandles});

/// الأطر القصيرة: دقائق لقدّام ونطاق ضيّق؛ 4h و 1D: أبعد ونطاق أعرض (النطاق
/// بيكبر مع تذبذب الشمعة). عدد الشموع صغير (≤ 15) فالرسم بيضل مقروء جنب الـ 80
/// شمعة الظاهرة. الصلاحية: 3 شموع (متل الإشارة)، و 1D يوم واحد.
ForecastHorizon forecastHorizon(Timeframe timeframe) => switch (timeframe) {
      Timeframe.m1 => (candles: 15, validCandles: 3),
      Timeframe.m15 => (candles: 12, validCandles: 3),
      Timeframe.h1 => (candles: 10, validCandles: 3),
      Timeframe.h4 => (candles: 8, validCandles: 3),
      Timeframe.d1 => (candles: 6, validCandles: 1),
    };

/// على إطار ما عليه إشارة للاستراتيجية، التوقّع بيلحق اتجاهها (أقوى إشارة،
/// نفس خلاصة الرأي) باحتمال أقل بهالقدر، وما بينزل تحت [forecastMinProbability].
const double forecastFollowPenalty = 0.08;
const double forecastMinProbability = 0.5;

/// موعد التحديث التلقائي الجاي: سكرة الشمعة الجاية على إطار الرسم. التوقّع
/// يلي بيلحق إشارة إطار تاني ([follows]) أو "ما في توقّع" بيتحدّث كمان مع سكرة
/// أقصر إطار للإشارات (15m)، لأنو أقوى إشارة ممكن تتغيّر وقتها.
/// هيك التحديث مربوط بسكرة الشموع، مش بالنبضات (على 1m: مرة بالدقيقة).
DateTime forecastRefreshAt(Timeframe timeframe, DateTime now, {required bool follows}) {
  DateTime next(Timeframe tf) => tf.bucketStart(now).add(tf.duration);
  final own = next(timeframe);
  if (!follows) return own;
  final signals = next(Timeframe.modelTimeframes.first);
  return signals.isBefore(own) ? signals : own;
}
