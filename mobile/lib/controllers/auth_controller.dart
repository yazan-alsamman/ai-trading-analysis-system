import 'package:flutter/foundation.dart';
import 'package:image_picker/image_picker.dart';
import '../models/user_model.dart';
import '../services/secure_storage_service.dart';

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
  AuthController({ImagePicker? picker, SecureStorageService? secureStorage})
      : _picker = picker ?? ImagePicker(),
        _secureStorage = secureStorage ?? SecureStorageService();

  /// أداة اختيار الصور (لصورة البروفايل) - نفس نمط
  /// [AiChartAnalyzerController]، الواجهة ما بتلمسها مباشرة
  final ImagePicker _picker;

  /// خدمة التخزين الآمن - لحفظ/قراءة/حذف auth token بعد
  /// تسجيل الدخول/التسجيل/الخروج
  final SecureStorageService _secureStorage;

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
  /// - [email]: البريد الإلكتروني
  /// - [password]: كلمة المرور
  /// 
  /// في حالة النجاح: [status] = [AuthStatus.success] و [currentUser] يتم تعيينه
  /// في حالة الفشل: [status] = [AuthStatus.failure] و [errorMessage] يتم تعيينه
  Future<void> register({
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
        createdAt: DateTime.now(),
      );

      // TODO: لما نربط الـ API الحقيقي، الـ token رح يجي من استجابة
      // السيرفر مباشرة (مثلاً response['token']) بدل التوليد الوهمي هون
      await _secureStorage.saveToken('mock_token_${_currentUser!.id}');

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
      );

      // TODO: لما نربط الـ API الحقيقي، الـ token رح يجي من استجابة
      // السيرفر مباشرة (مثلاً response['token']) بدل التوليد الوهمي هون
      await _secureStorage.saveToken('mock_token_${_currentUser!.id}');

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

      await _secureStorage.deleteToken();
      _currentUser = null;
      _setStatus(AuthStatus.idle);
    } catch (error) {
      _setError(_parseError(error));
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

  /// هل في auth token محفوظ من جلسة سابقة؟
  ///
  /// حالياً بس بتتحقق من وجود الـ token (بدون استرجاع بيانات
  /// المستخدم، لأنه هاد يحتاج نداء API حقيقي لجلب بروفايله).
  ///
  /// TODO: لما نربط الـ API الحقيقي، نستخدمها بشاشة البداية (splash/
  /// initial route) لعمل auto-login: إذا رجعت true، ننادي endpoint
  /// يرجع بيانات المستخدم عبر الـ token المحفوظ ونعبي [_currentUser]
  /// بدل ما نودي المستخدم لشاشة تسجيل الدخول من جديد
  Future<bool> hasStoredSession() async {
    final token = await _secureStorage.readToken();
    return token != null;
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
      final picked = await _picker.pickImage(source: source, imageQuality: 85);
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
    );
    notifyListeners();
  }

  /// مسح خطأ تعديل البروفايل
  void clearProfileError() {
    _profileError = null;
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

  /// مسح خطأ تغيير كلمة المرور
  void clearPasswordError() {
    _passwordError = null;
    notifyListeners();
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
