import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../controllers/auth_controller.dart';
import '../features/auth/data/session_store.dart';
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
    sessionStore: ref.read(sessionStoreProvider),
  ),
);
