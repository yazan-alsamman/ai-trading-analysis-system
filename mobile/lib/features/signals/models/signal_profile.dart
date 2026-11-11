import 'package:flutter/foundation.dart';

import '../../../core/data/json.dart';
import '../../../core/widgets/direction_badge.dart';
import '../../markets/models/market_models.dart';
import 'analysis_method.dart';

/// "Strategy" (الاستراتيجية): طريقة التحليل ([methodId]) + فلتر المستخدم المحفوظ
/// (نفس `SignalProfile` بالويب). الطريقة بتقرر كيف الإشارات بتنبني (النموذج دايمًا شغّال)، والفلتر
/// بيقرر شو بينعرض منها بس.
@immutable
final class SignalProfile {
  const SignalProfile({
    required this.symbols,
    required this.timeframes,
    required this.directions,
    required this.minProbability,
    required this.minRiskReward,
    required this.requireRiskFit,
    this.methodId = AnalysisMethod.defaultId,
  });

  /// طريقة التحليل ([AnalysisMethod.knownIds])؛ الافتراضي MA Crossover
  final String methodId;

  final Set<String> symbols;
  final Set<Timeframe> timeframes;

  /// long و/أو short (المحايد مش إشارة)
  final Set<SignalDirection> directions;

  /// أقل احتمال (0..0.9)، 0 = أي
  final double minProbability;

  /// أقل عائد : مخاطرة، 0 = أي
  final double minRiskReward;

  /// بس الإشارات يلي بتناسب رأس المال والحدود
  final bool requireRiskFit;

  /// الافتراضي (بدون استراتيجية خاصة): MA Crossover + كل الأدوات، وباقي القيم متل الويب
  static final SignalProfile defaults = SignalProfile(
    symbols: kProductSymbols.toSet(),
    timeframes: Timeframe.modelTimeframes.toSet(),
    directions: const {SignalDirection.long, SignalDirection.short},
    minProbability: 0.6,
    minRiskReward: 1.5,
    requireRiskFit: true,
  );

  static const double maxMinProbability = 0.9;
  static const double maxMinRiskReward = 3;

  bool get isValid =>
      AnalysisMethod.isKnown(methodId) &&
      symbols.isNotEmpty &&
      symbols.every(kProductSymbols.contains) &&
      timeframes.isNotEmpty &&
      timeframes.every(Timeframe.modelTimeframes.contains) &&
      directions.isNotEmpty &&
      !directions.contains(SignalDirection.neutral) &&
      minProbability >= 0 &&
      minProbability <= maxMinProbability &&
      minRiskReward >= 0 &&
      minRiskReward <= maxMinRiskReward;

  SignalProfile copyWith({
    Set<String>? symbols,
    Set<Timeframe>? timeframes,
    Set<SignalDirection>? directions,
    double? minProbability,
    double? minRiskReward,
    bool? requireRiskFit,
    String? methodId,
  }) =>
      SignalProfile(
        symbols: symbols ?? this.symbols,
        timeframes: timeframes ?? this.timeframes,
        directions: directions ?? this.directions,
        minProbability: minProbability ?? this.minProbability,
        minRiskReward: minRiskReward ?? this.minRiskReward,
        requireRiskFit: requireRiskFit ?? this.requireRiskFit,
        methodId: methodId ?? this.methodId,
      );

  Map<String, Object?> toJson() => {
        'method_id': methodId,
        'symbols': symbols.toList(),
        'timeframes': [for (final tf in timeframes) tf.apiValue],
        'directions': [for (final d in directions) d.name],
        'min_probability': minProbability,
        'min_risk_reward': minRiskReward,
        'require_risk_fit': requireRiskFit,
      };

  /// محفوظ تالف → الافتراضي. ترحيل (A3c): `method_id` ناقص (قبل A3)، أو
  /// `ai_model` (قبل A3c)، أو أي طريقة مش معروفة = الطريقة الافتراضية مع نفس
  /// الفلاتر؛ `method_id` مش نص = تالف.
  static SignalProfile fromJson(Json json) {
    final rawMethod = json.raw['method_id'];
    if (rawMethod != null && rawMethod is! String) return defaults;
    List<Object?> list(String key) => switch (json.raw[key]) { final List<Object?> l => l, _ => const [] };
    final parsed = SignalProfile(
      symbols: {
        for (final s in list('symbols'))
          if (s is String) s
      },
      timeframes: {
        for (final t in list('timeframes'))
          if (Timeframe.fromApi('$t') case final tf?) tf
      },
      directions: {
        for (final d in list('directions'))
          if (d == 'long') SignalDirection.long else if (d == 'short') SignalDirection.short,
      },
      minProbability: json.number('min_probability') ?? -1,
      minRiskReward: json.number('min_risk_reward') ?? -1,
      requireRiskFit: json.boolean('require_risk_fit') ?? defaults.requireRiskFit,
      methodId: AnalysisMethod.isKnown(rawMethod as String?) ? rawMethod! : AnalysisMethod.defaultId,
    );
    return parsed.isValid ? parsed : defaults;
  }

  @override
  bool operator ==(Object other) =>
      other is SignalProfile &&
      other.methodId == methodId &&
      setEquals(other.symbols, symbols) &&
      setEquals(other.timeframes, timeframes) &&
      setEquals(other.directions, directions) &&
      other.minProbability == minProbability &&
      other.minRiskReward == minRiskReward &&
      other.requireRiskFit == requireRiskFit;

  @override
  int get hashCode => Object.hash(
        methodId,
        Object.hashAllUnordered(symbols),
        Object.hashAllUnordered(timeframes),
        Object.hashAllUnordered(directions),
        minProbability,
        minRiskReward,
        requireRiskFit,
      );
}
