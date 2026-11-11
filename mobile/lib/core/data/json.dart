/// قراءة آمنة لـ JSON جاي من الـ API (أو المصدر المحاكى)
///
/// ولا دالة هون بترمي استثناء: الحقل الناقص أو بنوع غلط بيرجع null، والـ
/// mapper (DTO → domain) هو يلي بيقرر إذا العنصر صالح أو بينتشال.
extension type const Json(Map<String, Object?> raw) {
  /// من أي قيمة (Map أو غيرها) - غير الـ Map بيرجع null
  static Json? from(Object? value) {
    if (value is Map<String, Object?>) return Json(value);
    if (value is Map) {
      return Json({for (final e in value.entries) '${e.key}': e.value});
    }
    return null;
  }

  String? string(String key) {
    final v = raw[key];
    if (v is String) return v;
    if (v is num || v is bool) return '$v';
    return null;
  }

  double? number(String key) {
    final v = raw[key];
    final d = switch (v) {
      num() => v.toDouble(),
      String() => double.tryParse(v),
      _ => null,
    };
    return d == null || d.isNaN || d.isInfinite ? null : d;
  }

  int? integer(String key) {
    final v = raw[key];
    return switch (v) {
      int() => v,
      double() when v.isFinite && v == v.roundToDouble() => v.toInt(),
      String() => int.tryParse(v),
      _ => null,
    };
  }

  bool? boolean(String key) {
    final v = raw[key];
    return switch (v) {
      bool() => v,
      'true' => true,
      'false' => false,
      _ => null,
    };
  }

  /// ISO 8601 أو unix seconds → UTC
  DateTime? dateTime(String key) {
    final v = raw[key];
    if (v is String) return DateTime.tryParse(v)?.toUtc();
    if (v is num && v.isFinite) {
      return DateTime.fromMillisecondsSinceEpoch((v * 1000).round(), isUtc: true);
    }
    return null;
  }

  /// unix milliseconds → UTC (حقول `generatedAt` / `validUntil` بعقد الويب)
  DateTime? epochMillis(String key) {
    final v = raw[key];
    if (v is num && v.isFinite) {
      return DateTime.fromMillisecondsSinceEpoch(v.round(), isUtc: true);
    }
    return v is String ? DateTime.tryParse(v)?.toUtc() : null;
  }

  Json? object(String key) => Json.from(raw[key]);

  /// قائمة عناصر - أي عنصر مش Map بينتشال بهدوء
  List<Json> objects(String key) {
    final v = raw[key];
    if (v is! List) return const [];
    return [
      for (final item in v)
        if (Json.from(item) case final json?) json,
    ];
  }
}

/// بيحوّل قائمة بالـ [mapper] وبيشيل العناصر يلي ما انقرت (null)
List<T> mapValid<S, T extends Object>(Iterable<S> items, T? Function(S) mapper) => [
      for (final item in items)
        if (mapper(item) case final T value) value,
    ];
