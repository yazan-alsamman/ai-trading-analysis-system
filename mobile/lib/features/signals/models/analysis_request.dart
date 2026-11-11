import 'package:flutter/foundation.dart';

import '../../markets/models/market_models.dart';
import 'analysis_method.dart';

/// مراحل طلب تحليل عند المصدر (بالترتيب)
enum AnalysisStage {
  /// انبعت وناطر دورو
  pending,

  /// الطريقة عم تحلّل الشمعة الأخيرة
  analyzing,
}

/// طلب تحليل أداة + إطار بطريقة وحدة ("Request analysis")
@immutable
final class AnalysisRequest {
  const AnalysisRequest({required this.symbol, required this.timeframe, this.methodId = AnalysisMethod.defaultId});

  final String symbol;
  final Timeframe timeframe;
  final String methodId;

  bool get isValid =>
      kProductSymbols.contains(symbol) &&
      Timeframe.modelTimeframes.contains(timeframe) &&
      AnalysisMethod.isKnown(methodId);

  /// جسم `POST /analysis-requests`
  Map<String, Object?> toJson() => {'symbol': symbol, 'timeframe': timeframe.apiValue, 'method_id': methodId};

  @override
  bool operator ==(Object other) =>
      other is AnalysisRequest && other.symbol == symbol && other.timeframe == timeframe && other.methodId == methodId;

  @override
  int get hashCode => Object.hash(symbol, timeframe, methodId);

  @override
  String toString() => 'AnalysisRequest($symbol, ${timeframe.apiValue}, $methodId)';
}
