import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/json.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';
import '../models/analysis_method.dart';

/// كتالوج طرق التحليل - بيتبدّل بتنفيذ API.
abstract interface class AnalysisMethodsRepository {
  /// بيانات محاكاة؟ ("Simulated")
  bool get isSimulated;

  /// كل الطرق (الفنية: MA Crossover، RSI Reversal) بلغة [language] ('en' / 'ar')، بالترتيب يلي بينعرض فيه.
  /// API: `GET /analysis-methods?language=` → `[{id, name, description, kind: technical}]` (النموذج مش بالقائمة: هو دايمًا شغّال).
  /// TODO(API): الـ endpoint مش موجود بالـ backend لسّا.
  Future<List<AnalysisMethod>> list({String language = 'en'});
}

/// شكل الـ API لطريقة → domain (null لو ناقصة، نوعها غلط، أو معرّفها مش معروف
/// للمحرّك)
AnalysisMethod? analysisMethodFromJson(Json json) {
  final id = json.string('id');
  final name = json.string('name')?.trim();
  final description = json.string('description')?.trim();
  final kind = switch (json.string('kind')) {
    'technical' => AnalysisMethodKind.technical,
    // 'ai' (النموذج كخيار) ما عاد طريقة: بينشال
    _ => null,
  };
  if (!AnalysisMethod.isKnown(id) || name == null || name.isEmpty || description == null || kind == null) return null;
  return AnalysisMethod(id: id!, name: name, description: description, kind: kind);
}

List<AnalysisMethod> analysisMethodsFromJson(Object? body) => body is List
    ? mapValid(
        body,
        (Object? item) => switch (Json.from(item)) {
              final json? => analysisMethodFromJson(json),
              null => null,
            })
    : const [];

/// كتالوج محاكى ثابت (EN / AR)
final class SimulatedAnalysisMethodsRepository implements AnalysisMethodsRepository {
  const SimulatedAnalysisMethodsRepository({this.latency = Duration.zero});

  final Duration latency;

  static const Map<String, Map<String, (String, String)>> _text = {
    'en': {
      AnalysisMethod.maCrossoverId: (
        'MA Crossover',
        'Follows the trend when the 10-period average crosses the 30-period average.',
      ),
      AnalysisMethod.rsiReversalId: (
        'RSI Reversal',
        'Looks for a turn when RSI (14) shows the price has moved too far, too fast.',
      ),
    },
    'ar': {
      AnalysisMethod.maCrossoverId: (
        'تقاطع المتوسطات',
        'يتبع الاتجاه عندما يتقاطع متوسط 10 فترات مع متوسط 30 فترة.',
      ),
      AnalysisMethod.rsiReversalId: (
        'انعكاس RSI',
        'يبحث عن انعكاس عندما يُظهر مؤشر RSI (14) أن السعر تحرّك أكثر مما ينبغي وبسرعة.',
      ),
    },
  };

  /// نفس شكل جواب الـ API
  List<Map<String, Object?>> listJson(String language) {
    final text = _text[language] ?? _text['en']!;
    return [
      for (final id in AnalysisMethod.knownIds)
        {
          'id': id,
          'name': text[id]!.$1,
          'description': text[id]!.$2,
          'kind': 'technical',
        },
    ];
  }

  @override
  bool get isSimulated => true;

  @override
  Future<List<AnalysisMethod>> list({String language = 'en'}) async {
    if (latency > Duration.zero) await Future<void>.delayed(latency);
    return analysisMethodsFromJson(listJson(language));
  }
}

final analysisMethodsRepositoryProvider = Provider<AnalysisMethodsRepository>(
  (ref) => apiSource(
    ref,
    // الكتالوج جزء من Signals (نفس المفتاح)
    ApiFeature.signals,
    simulated: () => const SimulatedAnalysisMethodsRepository(),
  ),
);

/// الكتالوج بلغة معيّنة (للـ A3b)
final analysisMethodsProvider = FutureProvider.autoDispose.family<List<AnalysisMethod>, String>(
  (ref, language) => ref.watch(analysisMethodsRepositoryProvider).list(language: language),
);
