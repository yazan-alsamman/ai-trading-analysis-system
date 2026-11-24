import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app_database_holder.dart';

/// قاعدة الكاش الوحيدة بالتطبيق: بتنفتح أول ما حدا يحتاجها، وبتتسكّر مع الـ
/// ProviderScope. الاختبارات: `appDatabaseProvider.overrideWith((ref) => ...memory())`.
final appDatabaseProvider = Provider<AppDatabaseHolder>((ref) {
  final holder = AppDatabaseHolder.file();
  ref.onDispose(holder.close);
  return holder;
});
