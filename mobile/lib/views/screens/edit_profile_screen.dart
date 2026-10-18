import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../controllers/auth_controller.dart';
import '../../l10n/app_localizations.dart';
import '../../providers/app_providers.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_text_styles.dart';
import '../../utils/validators.dart';
import '../widgets/auth_background.dart';
import '../widgets/custom_text_field.dart';
import '../widgets/gradient_button.dart';

/// شاشة "Account Settings" - تعديل بيانات البروفايل (الاسم المعروض،
/// البريد الإلكتروني، صورة البروفايل)
///
/// الدور المعماري: **View (واجهة)**
/// - كل التعديلات تمر عبر [AuthController.updateProfile] و
///   [AuthController.pickAvatar] - الشاشة لا تحتفظ بأي منطق أعمال
///
/// تُفتح من "Account Settings" بـ [ProfileScreen]، وكمان من الضغط
/// على رأس البروفايل مباشرة (الصورة + الاسم).
class EditProfileScreen extends ConsumerStatefulWidget {
  const EditProfileScreen({super.key});

  @override
  ConsumerState<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends ConsumerState<EditProfileScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _nameController;
  late final TextEditingController _emailController;

  @override
  void initState() {
    super.initState();
    final user = ref.read(authControllerProvider).currentUser;
    _nameController = TextEditingController(text: user?.displayName ?? '');
    _emailController = TextEditingController(text: user?.email ?? '');
  }

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    super.dispose();
  }

  // ═══════════════════════════════════════════════════════════
  // Event Handlers - معالجات الأحداث
  // ═══════════════════════════════════════════════════════════

  /// حفظ التعديلات: تحقق من صحة النموذج ثم تمرير القيم لـ
  /// [AuthController.updateProfile]
  Future<void> _handleSave() async {
    final l10n = AppLocalizations.of(context)!;
    FocusScope.of(context).unfocus();
    if (!(_formKey.currentState?.validate() ?? false)) return;

    final controller = ref.read(authControllerProvider);
    final success = await controller.updateProfile(
      displayName: _nameController.text.trim(),
      email: _emailController.text.trim(),
    );

    if (!mounted) return;

    if (success) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(l10n.profileUpdatedSuccessfully),
          backgroundColor: AppColors.bgSurface,
          behavior: SnackBarBehavior.floating,
        ),
      );
      Navigator.of(context).maybePop();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(controller.profileError ?? l10n.couldNotSaveChanges),
          backgroundColor: AppColors.error,
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  /// فتح ورقة سفلية لاختيار مصدر صورة البروفايل (كاميرا / معرض /
  /// إزالة الصورة الحالية)
  Future<void> _handleChangeAvatar() async {
    final l10n = AppLocalizations.of(context)!;
    final controller = ref.read(authControllerProvider);
    final hasAvatar = controller.currentUser?.avatarUrl != null;

    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: AppColors.bgSurface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (sheetContext) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 8),
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: AppColors.fieldBorder,
                borderRadius: BorderRadius.circular(4),
              ),
            ),
            const SizedBox(height: 16),
            ListTile(
              leading: const Icon(Icons.photo_camera_outlined,
                  color: AppColors.accentCyan),
              title: Text(l10n.takeAPhoto, style: AppTextStyles.bodyMedium),
              onTap: () {
                Navigator.of(sheetContext).pop();
                controller.pickAvatar(source: ImageSource.camera);
              },
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_outlined,
                  color: AppColors.accentCyan),
              title: Text(l10n.chooseFromGallery, style: AppTextStyles.bodyMedium),
              onTap: () {
                Navigator.of(sheetContext).pop();
                controller.pickAvatar(source: ImageSource.gallery);
              },
            ),
            if (hasAvatar)
              ListTile(
                leading: const Icon(Icons.delete_outline_rounded,
                    color: AppColors.error),
                title: Text(
                  l10n.removeCurrentPhoto,
                  style: AppTextStyles.bodyMedium.copyWith(color: AppColors.error),
                ),
                onTap: () {
                  Navigator.of(sheetContext).pop();
                  controller.removeAvatar();
                },
              ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════
  // Build Methods - دوال البناء
  // ═══════════════════════════════════════════════════════════

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final isSaving = ref.watch(authControllerProvider).isSavingProfile;

    return Scaffold(
      body: AuthBackground(
        child: SafeArea(
          bottom: false,
          child: Column(
            children: [
              _buildTopBar(l10n),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
                  child: Form(
                    key: _formKey,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const SizedBox(height: 12),
                        _buildAvatarPicker(l10n),
                        const SizedBox(height: 32),
                        CustomTextField(
                          label: l10n.displayName,
                          hint: l10n.enterYourName,
                          controller: _nameController,
                          prefixIcon: Icons.person_outline_rounded,
                          validator: (value) =>
                              Validators.required(value, l10n, fieldName: l10n.name),
                        ),
                        const SizedBox(height: 20),
                        CustomTextField(
                          label: l10n.email,
                          hint: l10n.enterYourEmail,
                          controller: _emailController,
                          prefixIcon: Icons.email_outlined,
                          keyboardType: TextInputType.emailAddress,
                          validator: (value) => Validators.email(value, l10n),
                        ),
                        const SizedBox(height: 36),
                        GradientButton(
                          label: l10n.saveChanges,
                          isLoading: isSaving,
                          onPressed: isSaving ? null : _handleSave,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// شريط علوي: سهم رجوع + عنوان الشاشة (نفس نمط باقي الشاشات
  /// الفرعية مثل [NotificationsScreen])
  Widget _buildTopBar(AppLocalizations l10n) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(10, 6, 20, 0),
      child: Row(
        children: [
          InkWell(
            onTap: () => Navigator.of(context).maybePop(),
            borderRadius: BorderRadius.circular(14),
            child: const Padding(
              padding: EdgeInsets.all(12),
              child: Icon(
                Icons.arrow_back_rounded,
                color: AppColors.textPrimary,
                size: 22,
              ),
            ),
          ),
          const SizedBox(width: 4),
          Text(l10n.accountSettings, style: AppTextStyles.heading2),
        ],
      ),
    );
  }

  /// دائرة صورة البروفايل مع زر تعديل صغير فوقها
  Widget _buildAvatarPicker(AppLocalizations l10n) {
    final user = ref.watch(authControllerProvider).currentUser;
    final displayName = user?.displayName?.trim().isNotEmpty == true
        ? user!.displayName!
        : l10n.trader;
    final initial = displayName.isNotEmpty ? displayName[0].toUpperCase() : 'T';
    final avatarPath = user?.avatarUrl;

    return Center(
      child: Stack(
        children: [
          Container(
            width: 96,
            height: 96,
            decoration: BoxDecoration(
              color: AppColors.accentGreen,
              shape: BoxShape.circle,
              image: avatarPath != null
                  ? DecorationImage(
                      image: FileImage(File(avatarPath)),
                      fit: BoxFit.cover,
                    )
                  : null,
              border: Border.all(color: AppColors.fieldBorder, width: 2),
            ),
            child: avatarPath == null
                ? Center(
                    child: Text(
                      initial,
                      style: AppTextStyles.heading1.copyWith(
                        color: AppColors.buttonText,
                      ),
                    ),
                  )
                : null,
          ),
          Positioned(
            right: 0,
            bottom: 0,
            child: InkWell(
              onTap: _handleChangeAvatar,
              borderRadius: BorderRadius.circular(20),
              child: Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: AppColors.accentCyan,
                  shape: BoxShape.circle,
                  border: Border.all(color: AppColors.bgDeep, width: 3),
                ),
                child: const Icon(
                  Icons.camera_alt_rounded,
                  size: 16,
                  color: AppColors.buttonText,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
