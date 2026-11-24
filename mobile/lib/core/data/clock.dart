import 'package:flutter_riverpod/flutter_riverpod.dart';

/// الساعة الحالية، بتتحدّث كل دقيقة (سطر حالة الجلسات بالـ Home)
///
/// كل شي بيعرض وقت بيقرأ من هون مش من `DateTime.now()` مباشرة - هيك
/// الاختبارات بتثبّت الوقت: `clockProvider.overrideWith((ref) => Stream.value(t))`.
final clockProvider = StreamProvider.autoDispose<DateTime>((ref) async* {
  yield DateTime.now();
  yield* Stream.periodic(const Duration(minutes: 1), (_) => DateTime.now());
});
