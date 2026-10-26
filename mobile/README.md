# TradeX - Trading App

<div align="center">

![Flutter](https://img.shields.io/badge/Flutter-02569B?style=for-the-badge&logo=flutter&logoColor=white)
![Dart](https://img.shields.io/badge/Dart-0175C2?style=for-the-badge&logo=dart&logoColor=white)
![Riverpod](https://img.shields.io/badge/Riverpod-1B1B1F?style=for-the-badge&logo=flutter&logoColor=white)

**تطبيق احترافي للتداول مبني بـ Flutter باستخدام معمارية MVC**

</div>

---

## 📋 نظرة عامة

TradeX هو تطبيق تداول احترافي مبني بـ Flutter framework باستخدام معمارية MVC النظيفة. التطبيق يتميز بتصميم داكن أنيق وواجهات مستخدم سلسة مع التركيز على تجربة المستخدم.

## 🎨 الميزات الرئيسية

- ✨ **تصميم داكن احترافي** - واجهة مستخدم أنيقة مع تدرجات لونية جميلة
- 🏗️ **معمارية MVC نظيفة** - كود منظم وسهل الصيانة
- 🔐 **نظام مصادقة متكامل** - تسجيل دخول وإنشاء حسابات
- 🎯 **State Management** - إدارة الحالة باستخدام Riverpod
- 📱 **Responsive Design** - متجاوب مع جميع أحجام الشاشات
- 🌟 **Animated Background** - خلفيات متحركة جميلة
- 🔒 **Validation** - تحقق شامل من المدخلات

## 📁 بنية المشروع

```
lib/
├── controllers/          # متحكمات (Controllers)
│   └── auth_controller.dart
│
├── models/              # النماذج (Models)
│   └── user_model.dart
│
├── services/            # الخدمات (Services)
│   └── (سيتم إضافتها)
│
├── utils/               # الأدوات المساعدة
│   ├── app_colors.dart      # ألوان التطبيق
│   ├── app_text_styles.dart # أنماط النصوص
│   └── validators.dart      # دوال التحقق
│
├── views/               # الواجهات (Views)
│   ├── screens/         # الشاشات
│   │   └── registration_screen.dart
│   │
│   └── widgets/         # المكونات القابلة لإعادة الاستخدام
│       ├── custom_text_field.dart
│       ├── gradient_button.dart
│       ├── registration_background.dart
│       └── star_field_painter.dart
│
└── main.dart           # نقطة الدخول الرئيسية
```

## 🎯 معمارية MVC

### Model (النموذج)
- تمثيل البيانات والمنطق التجاري
- مستقلة عن الواجهة
- مثال: `UserModel`

### View (الواجهة)
- عرض البيانات للمستخدم
- التفاعل مع المستخدم
- لا تحتوي على منطق أعمال
- مثال: `RegistrationScreen`

### Controller (المتحكم)
- الوسيط بين Model و View
- إدارة حالة التطبيق
- معالجة أحداث المستخدم
- مثال: `AuthController`

## 🛠️ التقنيات المستخدمة

| التقنية | الاستخدام |
|---------|-----------|
| **Flutter 3.3+** | Framework الأساسي |
| **Dart 3.0+** | لغة البرمجة |
| **Riverpod** | إدارة الحالة |
| **Google Fonts** | الخطوط |
| **Flutter Animate** | الحركات |
| **Shimmer** | تأثيرات التحميل |

## 🚀 البدء

### المتطلبات
- Flutter SDK (3.3.0 أو أحدث)
- Dart SDK (3.0.0 أو أحدث)
- Android Studio / VS Code
- محاكي أو جهاز فعلي

### التثبيت

1. **استنساخ المشروع**
```bash
git clone https://github.com/your-username/trading_app.git
cd trading_app
```

2. **تثبيت الحزم**
```bash
flutter pub get
```

3. **تشغيل التطبيق**
```bash
flutter run
```

## 🎨 نظام الألوان

جميع الألوان مُدارة مركزياً في `app_colors.dart`:

```dart
// الخلفيات
AppColors.bgDeep        // #020B15
AppColors.bgMid         // #0A1E32
AppColors.bgSurface     // #0D2844

// التدرجات
AppColors.gradientStart // #D4FF5E
AppColors.gradientEnd   // #8588E0B1

// النصوص
AppColors.textPrimary   // #FFFFFF
AppColors.textSecondary // #B8C5D0
AppColors.textHint      // #5A7A92
```

## 📝 قواعد الكود النظيف

### 1. تسمية الملفات
- استخدم `snake_case` لجميع أسماء الملفات
- مثال: `custom_text_field.dart`

### 2. تسمية الكلاسات
- استخدم `PascalCase` للكلاسات
- مثال: `CustomTextField`

### 3. تسمية المتغيرات
- استخدم `camelCase` للمتغيرات والدوال
- مثال: `emailController`

### 4. التعليقات
- استخدم تعليقات توضيحية عربية وإنجليزية
- وثّق جميع الدوال العامة
- اشرح المنطق المعقد

### 5. فصل المسؤوليات
- لا تضع منطق أعمال في Views
- استخدم Controllers للمنطق
- استخدم Models للبيانات
- استخدم Services للـ API

## 🔐 التحقق من الصحة

جميع دوال التحقق في `validators.dart`:

```dart
// البريد الإلكتروني
Validators.email(value)

// كلمة المرور
Validators.password(value)

// تأكيد كلمة المرور
Validators.confirmPassword(value, original)
```

## 🎯 الشاشات

### 1. شاشة التسجيل (Registration Screen)
- إنشاء حساب جديد
- التحقق من المدخلات
- خلفية متحركة جميلة

### 2. شاشة تسجيل الدخول (قيد التطوير)
### 3. الشاشة الرئيسية (قيد التطوير)

## 🧩 المكونات القابلة لإعادة الاستخدام

### CustomTextField
```dart
CustomTextField(
  label: 'Email',
  hint: 'Enter your email',
  controller: emailController,
  validator: Validators.email,
  keyboardType: TextInputType.emailAddress,
)
```

### GradientButton
```dart
GradientButton(
  label: 'Create account',
  onPressed: () {},
  isLoading: false,
)
```

## 📊 إدارة الحالة

### استخدام Riverpod

```dart
// القراءة والاستماع للتغييرات (داخل ConsumerWidget / ConsumerState)
final isLoading = ref.watch(authControllerProvider).isLoading;

// القراءة مرة واحدة (بدون استماع)
final controller = ref.read(authControllerProvider);

// تنفيذ عملية
await controller.register(email: email, password: password);
```

كل الـ providers المشتركة (Auth / NewsRepository / NotificationsRepository)
معرّفة مركزيًا بملف `lib/providers/app_providers.dart`، والـ controllers
المحلية اللي بتُنشأ من جديد بكل فتحة شاشة (AI Chat / AI Chart Analyzer /
AI News Analyzer / Comments) معرّفة بملف `lib/providers/screen_providers.dart`
وبتنعمل override إلها محليًا جوا كل شاشة عبر `ProviderScope`.

## 🔄 تدفق البيانات

```
User Input (View)
    ↓
Controller (AuthController)
    ↓
Service (AuthService) → API
    ↓
Model (UserModel)
    ↓
Controller updates State
    ↓
View rebuilds
```

## 🐛 المعالجة للأخطاء

```dart
try {
  await controller.register(...);
  
  if (controller.status == AuthStatus.success) {
    // Success
  } else if (controller.errorMessage != null) {
    // Show error
  }
} catch (e) {
  // Handle exception
}
```

## 📦 الحزم المستخدمة

```yaml
dependencies:
  flutter_riverpod: ^2.6.1  # إدارة الحالة
  google_fonts: ^6.2.1      # الخطوط
  flutter_animate: ^4.5.0   # الحركات
  shimmer: ^3.0.0          # تأثيرات
```

## 🚧 قيد التطوير

- [ ] شاشة تسجيل الدخول
- [ ] الشاشة الرئيسية
- [ ] شاشة المحفظة
- [ ] شاشة التداول
- [ ] إعدادات المستخدم
- [ ] التكامل مع API حقيقي
- [ ] Local Storage
- [ ] Push Notifications

## 🤝 المساهمة

المساهمات مرحب بها! الرجاء:

1. Fork المشروع
2. إنشاء Branch جديد (`git checkout -b feature/AmazingFeature`)
3. Commit التغييرات (`git commit -m 'Add some AmazingFeature'`)
4. Push إلى Branch (`git push origin feature/AmazingFeature`)
5. فتح Pull Request

## 📄 الترخيص

هذا المشروع مرخص تحت MIT License

## 📧 التواصل

للأسئلة والاستفسارات: [your-email@example.com](mailto:your-email@example.com)

---

<div align="center">

**صُنع بـ ❤️ باستخدام Flutter**

[⭐ Star](https://github.com/your-username/trading_app) | [🐛 Report Bug](https://github.com/your-username/trading_app/issues) | [💡 Request Feature](https://github.com/your-username/trading_app/issues)

</div>
