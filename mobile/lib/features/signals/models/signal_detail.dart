import 'package:flutter/foundation.dart';

import '../../../core/widgets/direction_badge.dart';
import '../../markets/models/market_models.dart';
import 'opportunity.dart';
import 'signal_plan.dart';
import 'signal_rationale.dart';

/// كل شي بتعرضه شاشة تفاصيل إشارة: الأداة، الاتجاه والاحتمال، الخطة (دخول /
/// هدف / وقف + البعد بالنقاط + العائد : المخاطرة)، الأسباب، والصلاحية.
@immutable
final class SignalDetail {
  const SignalDetail({
    required this.signal,
    required this.instrument,
    required this.plan,
    required this.rationale,
    required this.expired,
  });

  /// [siblings] = رأي النموذج على باقي أطر نفس الأداة (null = ما وصل، فسبب
  /// الاتفاق بيغيب)
  factory SignalDetail.of(
    Opportunity signal, {
    required Instrument instrument,
    required List<Opportunity>? siblings,
    required DateTime now,
  }) =>
      SignalDetail(
        signal: signal,
        instrument: instrument,
        plan: SignalPlan.of(signal, instrument),
        rationale: buildSignalRationale(signal, siblings: siblings, now: now),
        expired: signal.isStale(now),
      );

  final Opportunity signal;
  final Instrument instrument;
  final SignalPlan plan;
  final List<SignalReason> rationale;

  /// أقوى [kTopReasons] أسباب (كل واحد مع [SignalReason.influence])
  List<SignalReason> get topReasons => rationale.take(kTopReasons).toList();

  /// الباقي بعدهن بنفس الترتيب
  List<SignalReason> get otherReasons => rationale.skip(kTopReasons).toList();

  /// الطريقة يلي طلّعت الإشارة ("strategy used")
  String get methodId => signal.methodId;

  /// نتيجة محايدة لطلب تحليل: "No clear setup right now" + [rationale]
  bool get isNoClearSetup => !signal.isDetected;

  /// صلاحيتها خلصت: المستويات قديمة، بتنعرض للمرجع بس (مش رأي حالي)
  final bool expired;

  String get symbol => signal.symbol;
  SignalDirection get direction => signal.direction;
  double get probability => signal.probability;
  DateTime get validUntil => signal.validUntil;

  SignalDetail markExpired() => expired
      ? this
      : SignalDetail(signal: signal, instrument: instrument, plan: plan, rationale: rationale, expired: true);
}
