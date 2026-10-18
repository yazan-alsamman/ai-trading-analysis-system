import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../controllers/auth_controller.dart';
import '../controllers/news_repository.dart';
import '../controllers/notifications_repository.dart';
import '../services/secure_storage_service.dart';

// ═══════════════════════════════════════════════════════════
// App Providers - متحكمات/مصادر مشتركة لكل التطبيق (Root-level)
// ═══════════════════════════════════════════════════════════
//
// معادل [MultiProvider] القديم بملف main.dart (مرحلة Provider). كل
// Provider هون بيبقى حي طول عمر التطبيق (ما إلها autoDispose)، بنفس
// سلوك الـ ChangeNotifierProvider الجذرية القديمة.
//
// الاستخدام من داخل الشاشات:
// - قراءة + استماع للتغييرات: `ref.watch(authControllerProvider)`
// - قراءة مرة وحدة (بدون استماع)، عادة لتنفيذ أمر: `ref.read(authControllerProvider)`
//   (بيرجع الـ Notifier نفسه، فينفع تنادي عليه الدوال مباشرة، بنفس
//   شكل `context.read<AuthController>()` بمرحلة Provider)

/// خدمة التخزين الآمن - instance واحدة مشتركة (ما في داعي لأكتر من
/// وحدة، ولا هي ChangeNotifier أصلاً - بس Provider عادي)
final secureStorageServiceProvider = Provider<SecureStorageService>(
  (ref) => SecureStorageService(),
);

/// متحكم المصادقة - تسجيل دخول / تسجيل / خروج / تعديل بروفايل / كلمة مرور
final authControllerProvider = ChangeNotifierProvider<AuthController>(
  (ref) => AuthController(
    secureStorage: ref.read(secureStorageServiceProvider),
  ),
);

/// المصدر الوحيد لأخبار السوق - مشترك بين Home / Market News / AI News
/// Analyzer / Discussion، حتى عدد التعليقات يبقى نفسه بكل مكان يظهر فيه
final newsRepositoryProvider = ChangeNotifierProvider<NewsRepository>(
  (ref) => NewsRepository(),
);

/// المصدر الوحيد لإشعارات التطبيق - مشترك بين Home وشاشة الإشعارات
final notificationsRepositoryProvider =
    ChangeNotifierProvider<NotificationsRepository>(
  (ref) => NotificationsRepository(),
);

// TODO: إضافة متحكمات أخرى هنا
// مثال:
// final tradingControllerProvider = ChangeNotifierProvider<TradingController>(
//   (ref) => TradingController(),
// );
