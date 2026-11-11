import 'package:flutter/foundation.dart';
import 'package:image_picker/image_picker.dart';
import '../core/network/token_store.dart';
import '../features/auth/data/session_store.dart';
import '../models/user_model.dart';

// ═══════════════════════════════════════════════════════════
// Auth Status Enum - حالات المصادقة
// ═══════════════════════════════════════════════════════════

/// حالات عملية المصادقة
enum AuthStatus {
  /// الحالة الأولية - لم يتم البدء بعد
  idle,
  
  /// جاري التحميل - في انتظار الاستجابة
  loading,
  
  /// نجحت العملية
  success,
  
  /// فشلت العملية
  failure,
}

// ═══════════════════════════════════════════════════════════
// Auth Controller - متحكم المصادقة
// ═══════════════════════════════════════════════════════════

/// متحكم إدارة حالة المصادقة
/// 
/// مسؤوليات هذا الكلاس:
/// - إدارة حالة المصادقة (تسجيل دخول، تسجيل، خروج)
/// - التواصل مع طبقة الخدمات (Services)
/// - إشعار الواجهة بالتغييرات
/// 
/// ⚠️ IMPORTANT: الواجهة (View) لا تتواصل مع الخدمات مباشرة
/// يجب أن تمر جميع العمليات عبر هذا المتحكم
final class AuthController extends ChangeNotifier {
  AuthController({ImagePicker? picker, SessionStore? sessionStore})
      : _picker = picker ?? ImagePicker(),
        _sessionStore = sessionStore;

  /// أداة اختيار الصور (لصورة البروفايل) - نفس نمط
  /// [AiChartAnalyzerController]، الواجهة ما بتلمسها مباشرة
  final ImagePicker _picker;

  /// الجلسة المحفوظة على الجهاز (G3: الـ token بالتخزين الآمن + أقل بيانات
  /// للمستخدم) - null = بالذاكرة بس (بدون حفظ)
  final SessionStore? _sessionStore;

  /// الجلسة الحالية محفوظة؟ (بعد Log in / التحقق من البريد / الاستعادة)
  bool _sessionSaved = false;

  // ═══════════════════════════════════════════════════════════
  // Private State - الحالة الخاصة
  // ═══════════════════════════════════════════════════════════
  
  /// حالة المصادقة الحالية
  AuthStatus _status = AuthStatus.idle;
  
  /// المستخدم الحالي المسجل
  UserModel? _currentUser;
  
  /// رسالة الخطأ في حالة الفشل
  String? _errorMessage;

  /// حالة تحميل منفصلة لتعديل بيانات البروفايل (اسم/بريد/صورة) -
  /// مفصولة عمدًا عن [_status] حتى ما تأثر على [isAuthenticated] أو
  /// تتصادم مع حالة تسجيل الدخول/الخروج
  bool _isSavingProfile = false;

  /// رسالة خطأ خاصة بتعديل البروفايل
  String? _profileError;

  /// حالة تحميل منفصلة لتغيير كلمة المرور
  bool _isChangingPassword = false;

  /// رسالة خطأ خاصة بتغيير كلمة المرور
  String? _passwordError;
  
  // ═══════════════════════════════════════════════════════════
  // Public Getters - القيم العامة (للقراءة فقط)
  // ═══════════════════════════════════════════════════════════
  
  /// الحصول على حالة المصادقة الحالية
  AuthStatus get status => _status;
  
  /// الحصول على المستخدم الحالي
  UserModel? get currentUser => _currentUser;
  
  /// الحصول على رسالة الخطأ
  String? get errorMessage => _errorMessage;
  
  /// التحقق من وجود عملية تحميل جارية
  bool get isLoading => _status == AuthStatus.loading;
  
  /// التحقق من تسجيل دخول المستخدم
  bool get isAuthenticated => _currentUser != null && _status == AuthStatus.success;

  /// هل في عملية حفظ بيانات بروفايل جارية؟
  bool get isSavingProfile => _isSavingProfile;

  /// رسالة خطأ تعديل البروفايل الحالية (إن وجدت)
  String? get profileError => _profileError;

  /// هل في عملية تغيير كلمة مرور جارية؟
  bool get isChangingPassword => _isChangingPassword;

  /// رسالة خطأ تغيير كلمة المرور الحالية (إن وجدت)
  String? get passwordError => _passwordError;
  
  // ═══════════════════════════════════════════════════════════
  // Public Actions - العمليات العامة
  // ═══════════════════════════════════════════════════════════
  
  /// تسجيل مستخدم جديد
  /// 
  /// Parameters:
  /// - [fullName]: الاسم الكامل (بيصير الاسم المعروض)
  /// - [email]: البريد الإلكتروني
  /// - [password]: كلمة المرور
  /// 
  /// في حالة النجاح: [status] = [AuthStatus.success] و [currentUser] يتم تعيينه
  /// في حالة الفشل: [status] = [AuthStatus.failure] و [errorMessage] يتم تعيينه
  Future<void> register({
    required String fullName,
    required String email,
    required String password,
  }) async {
    _setLoading();
    
    try {
      // TODO: استبدال هذا بـ API call حقيقي عبر AuthService
      await Future.delayed(const Duration(seconds: 2));
      
      // محاكاة إنشاء مستخدم جديد
      _currentUser = UserModel(
        id: 'uid_${DateTime.now().millisecondsSinceEpoch}',
        email: email,
        displayName: fullName,
        createdAt: DateTime.now(),
        // حساب الـ mock = متداول دايمًا؛ الدور بينحفظ مع الجلسة وبيرجع بعد الإقلاع
        role: UserRole.trader,
      );

      // الحساب الجديد داخل بالذاكرة بس: الجلسة ما بتنحفظ قبل التحقق من
      // البريد (OtpViewModel → [persistSession]). سكّر التطبيق بنص التسجيل
      // = الإقلاع الجاي على Welcome.
      _setStatus(AuthStatus.success);
    } catch (error) {
      _setError(_parseError(error));
    }
  }
  
  /// تسجيل دخول مستخدم موجود
  /// 
  /// Parameters:
  /// - [email]: البريد الإلكتروني
  /// - [password]: كلمة المرور
  Future<void> login({
    required String email,
    required String password,
  }) async {
    _setLoading();
    
    try {
      // TODO: استبدال هذا بـ API call حقيقي عبر AuthService
      await Future.delayed(const Duration(seconds: 2));
      
      // محاكاة تسجيل دخول
      _currentUser = UserModel(
        id: 'uid_mock',
        email: email,
        // تسجيل دخول الـ mock = متداول دايمًا (SessionStore بيحفظ الدور، restoreSession بيرجّعه)
        role: UserRole.trader,
      );

      // TODO: لما نربط الـ API الحقيقي، الـ token رح يجي من استجابة
      // السيرفر مباشرة (مثلاً response['token']) بدل التوليد الوهمي
      await persistSession();

      _setStatus(AuthStatus.success);
    } catch (error) {
      _setError(_parseError(error));
    }
  }
  
  /// تسجيل خروج المستخدم الحالي
  Future<void> logout() async {
    _setLoading();
    
    try {
      // TODO: استبدال هذا بـ API call حقيقي عبر AuthService
      await Future.delayed(const Duration(seconds: 1));

      await endSession();
    } catch (error) {
      _setError(_parseError(error));
    }
  }

  /// نهاية الجلسة (الطريق الوحيد من "داخل" لـ "طالع"): بيمسح الجلسة المحفوظة،
  /// بعدين بيطلّع المستخدم - والـ router بيرجع لـ Welcome ويمسح الشجرة.
  /// تسجيل الخروج بيستخدمها، والـ AuthInterceptor كمان لما الـ refresh ينرفض (E1).
  Future<void> endSession() async {
    try {
      await _sessionStore?.clear();
    } catch (error) {
      debugPrint('AuthController: could not clear the saved session: $error');
    } finally {
      _sessionSaved = false;
      _currentUser = null;
      _setStatus(AuthStatus.idle);
    }
  }

  /// يحفظ الجلسة الحالية على الجهاز (الإقلاع الجاي بيفتح على الرئيسية):
  /// بعد Log in، وبعد التحقق من البريد لحساب جديد (مش قبل). فشل الحفظ ما
  /// بيوقف الدخول - الجلسة بتضل بالذاكرة بس. [tokens] = استجابة `/auth/login`
  /// لما الـ API الحقيقي مفعّل للـ auth (E1: SessionStore.realApi).
  Future<void> persistSession({TokenPair? tokens}) async {
    final user = _currentUser;
    if (user == null || _sessionStore == null) return;
    try {
      await _sessionStore.save(user, tokens: tokens);
      _sessionSaved = true;
    } catch (error) {
      debugPrint('AuthController: could not save the session: $error');
    }
  }

  /// الـ splash: بيقرأ الجلسة المحفوظة؛ إذا موجودة المستخدم بيرجع داخل
  /// (true)، غير هيك بيضل طالع (false). أي خطأ بالتخزين = ما في جلسة.
  Future<bool> restoreSession() async {
    if (_currentUser != null) return true;
    final store = _sessionStore;
    if (store == null) return false;
    try {
      final user = await store.read();
      if (user == null) return false;
      _currentUser = user;
      _sessionSaved = true;
      _setStatus(AuthStatus.success);
      return true;
    } catch (error) {
      debugPrint('AuthController: could not read the saved session: $error');
      return false;
    }
  }
  
  /// مسح الخطأ السابق
  /// 
  /// يستخدم لإعادة تعيين حالة الواجهة
  void clearError() {
    _errorMessage = null;
    if (_status == AuthStatus.failure) {
      _setStatus(AuthStatus.idle);
    }
  }

  // ═══════════════════════════════════════════════════════════
  // Profile Editing - تعديل بيانات البروفايل
  // ═══════════════════════════════════════════════════════════

  /// تعديل الاسم المعروض و/أو البريد الإلكتروني للمستخدم الحالي
  ///
  /// يرجع `true` بحالة النجاح و`false` بحالة الفشل (راجع
  /// [profileError] للتفاصيل). القيم null بتُترك كما هي (بدون تعديل).
  Future<bool> updateProfile({String? displayName, String? email}) async {
    if (_currentUser == null) return false;

    _isSavingProfile = true;
    _profileError = null;
    notifyListeners();

    try {
      // TODO: استبدال هذا بـ API call حقيقي عبر AuthService
      await Future.delayed(const Duration(milliseconds: 900));

      _currentUser = _currentUser!.copyWith(
        displayName: displayName,
        email: email,
      );
      // الجلسة المحفوظة بتاخد الاسم/البريد الجديد (الإقلاع الجاي بيعرضهن)
      if (_sessionSaved) await persistSession();

      _isSavingProfile = false;
      notifyListeners();
      return true;
    } catch (error) {
      _profileError = _parseError(error);
      _isSavingProfile = false;
      notifyListeners();
      return false;
    }
  }

  /// اختيار صورة بروفايل جديدة من المعرض أو الكاميرا وتعيينها مباشرة
  /// للمستخدم الحالي
  Future<void> pickAvatar({required ImageSource source}) async {
    if (_currentUser == null) return;

    try {
      final picked = await _picker.pickImage(source: source, maxWidth: 512, maxHeight: 512, imageQuality: 85);
      if (picked == null) return; // المستخدم لغى الاختيار

      _currentUser = _currentUser!.copyWith(avatarUrl: picked.path);
      notifyListeners();
    } catch (error) {
      _profileError = 'Could not open the image. Please try again.';
      notifyListeners();
    }
  }

  /// إزالة صورة البروفايل الحالية والرجوع للأيقونة الافتراضية (الحرف
  /// الأول من الاسم)
  void removeAvatar() {
    if (_currentUser?.avatarUrl == null) return;
    _currentUser = UserModel(
      id: _currentUser!.id,
      email: _currentUser!.email,
      displayName: _currentUser!.displayName,
      avatarUrl: null,
      createdAt: _currentUser!.createdAt,
      role: _currentUser!.role,
    );
    notifyListeners();
  }


  // ═══════════════════════════════════════════════════════════
  // Password Management - إدارة كلمة المرور
  // ═══════════════════════════════════════════════════════════

  /// تغيير كلمة مرور المستخدم الحالي
  ///
  /// Parameters:
  /// - [currentPassword]: كلمة المرور الحالية (للتحقق)
  /// - [newPassword]: كلمة المرور الجديدة
  ///
  /// يرجع `true` بحالة النجاح و`false` بحالة الفشل (راجع
  /// [passwordError] للتفاصيل)
  Future<bool> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    _isChangingPassword = true;
    _passwordError = null;
    notifyListeners();

    try {
      // TODO: استبدال هذا بـ API call حقيقي عبر AuthService، واللي
      // بيتحقق فعليًا من currentPassword قبل تعيين الجديدة
      await Future.delayed(const Duration(milliseconds: 900));

      _isChangingPassword = false;
      notifyListeners();
      return true;
    } catch (error) {
      _passwordError = _parseError(error);
      _isChangingPassword = false;
      notifyListeners();
      return false;
    }
  }

  
  // ═══════════════════════════════════════════════════════════
  // Private Helper Methods - دوال مساعدة خاصة
  // ═══════════════════════════════════════════════════════════
  
  /// تعيين حالة التحميل
  void _setLoading() {
    _errorMessage = null;
    _setStatus(AuthStatus.loading);
  }
  
  /// تعيين حالة الخطأ
  void _setError(String message) {
    _errorMessage = message;
    _setStatus(AuthStatus.failure);
  }
  
  /// تعيين الحالة وإشعار المستمعين
  void _setStatus(AuthStatus newStatus) {
    _status = newStatus;
    notifyListeners();
  }
  
  /// تحويل الخطأ إلى رسالة مفهومة
  String _parseError(dynamic error) {
    // TODO: تحسين معالجة الأخطاء بناءً على نوع الخطأ
    if (error.toString().contains('network')) {
      return 'Network error. Please check your connection';
    }
    return 'An error occurred. Please try again';
  }
}
