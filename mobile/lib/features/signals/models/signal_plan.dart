import 'package:flutter/foundation.dart';

import '../../markets/models/market_models.dart';
import '../../risk/models/trade_sizing.dart';
import 'opportunity.dart';

/// خطة الإشارة بأرقام بتنقرا: منطقة الدخول، الهدف والوقف (منتصف منطقتهن)،
/// وبعدهن عن منتصف الدخول بالنقاط (pips)، والعائد : المخاطرة.
@immutable
final class SignalPlan {
  const SignalPlan({
    required this.entry,
    required this.target,
    required this.stop,
    required this.targetPips,
    required this.stopPips,
    required this.riskReward,
  });

  factory SignalPlan.of(Opportunity signal, Instrument instrument) {
    final pip = pipSize(instrument);
    final entry = signal.entryZone.mid;
    final target = signal.takeProfitZone.mid;
    final stop = signal.stopLossZone.mid;
    return SignalPlan(
      entry: signal.entryZone,
      target: target,
      stop: stop,
      targetPips: (target - entry).abs() / pip,
      stopPips: (stop - entry).abs() / pip,
      riskReward: signal.riskReward,
    );
  }

  final PriceZone entry;
  final double target;
  final double stop;

  /// بعد الهدف عن منتصف الدخول (نقاط)
  final double targetPips;

  /// بعد الوقف عن منتصف الدخول (نقاط)
  final double stopPips;
  final double riskReward;
}
