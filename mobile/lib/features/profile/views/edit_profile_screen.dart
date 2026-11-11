import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_text_field.dart';
import '../../../core/widgets/page_header.dart';
import '../../../l10n/app_localizations.dart';
import '../../../providers/app_providers.dart';
import '../../../utils/validators.dart';
import '../widgets/profile_identity_card.dart';

/// تعديل البروفايل (من بطاقة الهوية): الصورة، الاسم المعروض، البريد.
///
/// الحفظ بيمر من AuthController (TODO(B02): بيصير AuthRepository مع الـ API).
/// لو في تعديلات مش محفوظة، الرجوع بيسأل قبل ما يتجاهلها.
class EditProfileScreen extends ConsumerStatefulWidget {
  const EditProfileScreen({super.key});

  @override
  ConsumerState<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends ConsumerState<EditProfileScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _name;
  late final TextEditingController _email;
  late final String _initialName;
  late final String _initialEmail;
  bool _dirty = false;

  @override
  void initState() {
    super.initState();
    final user = ref.read(authControllerProvider).currentUser;
    _initialName = user?.displayName ?? '';
    _initialEmail = user?.email ?? '';
    _name = TextEditingController(text: _initialName)..addListener(_onEdited);
    _email = TextEditingController(text: _initialEmail)..addListener(_onEdited);
  }

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    super.dispose();
  }

  void _onEdited() {
    // كل تعديل بيعيد الرسم (حرف الصورة بيتبع الاسم المكتوب)
    setState(() {
      _dirty = _name.text.trim() != _initialName.trim() || _email.text.trim() != _initialEmail.trim();
    });
  }

  Future<void> _save() async {
    final l10n = AppLocalizations.of(context)!;
    FocusScope.of(context).unfocus();
    if (!(_formKey.currentState?.validate() ?? false)) return;

    final controller = ref.read(authControllerProvider);
    final ok = await controller.updateProfile(displayName: _name.text.trim(), email: _email.text.trim());
    if (!mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    if (ok) {
      setState(() => _dirty = false);
      messenger.showSnackBar(SnackBar(content: Text(l10n.profileUpdatedSuccessfully)));
      // pop مش maybePop: الـ PopScope لسّا ما انعاد بناؤه بعد الحفظ، وكان رح يسأل "تجاهل؟"
      Navigator.of(context).pop();
    } else {
      messenger.showSnackBar(SnackBar(content: Text(controller.profileError ?? l10n.couldNotSaveChanges)));
    }
  }

  Future<void> _changePhoto() async {
    final l10n = AppLocalizations.of(context)!;
    final controller = ref.read(authControllerProvider);
    final hasPhoto = controller.currentUser?.avatarUrl != null;
    final c = context.colors;

    final action = await showModalBottomSheet<_PhotoAction>(
      useRootNavigator: true,
      context: context,
      sheetAnimationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              minTileHeight: 56,
              leading: const Icon(Icons.photo_camera_outlined),
              title: Text(l10n.takeAPhoto),
              onTap: () => Navigator.of(sheetContext).pop(_PhotoAction.camera),
            ),
            ListTile(
              minTileHeight: 56,
              leading: const Icon(Icons.photo_library_outlined),
              title: Text(l10n.chooseFromGallery),
              onTap: () => Navigator.of(sheetContext).pop(_PhotoAction.gallery),
            ),
            if (hasPhoto)
              ListTile(
                minTileHeight: 56,
                leading: Icon(Icons.delete_outline_rounded, color: c.danger),
                title: Text(
                  l10n.removeCurrentPhoto,
                  style: context.textTheme.bodyLarge!.copyWith(color: c.danger),
                ),
                onTap: () => Navigator.of(sheetContext).pop(_PhotoAction.remove),
              ),
            const SizedBox(height: AppSpacing.xs),
          ],
        ),
      ),
    );
    switch (action) {
      case _PhotoAction.camera:
        await controller.pickAvatar(source: ImageSource.camera);
      case _PhotoAction.gallery:
        await controller.pickAvatar(source: ImageSource.gallery);
      case _PhotoAction.remove:
        controller.removeAvatar();
      case null:
        break;
    }
  }

  Future<bool> _confirmDiscard() async {
    final l10n = AppLocalizations.of(context)!;
    final discard = await showDialog<bool>(
      context: context,
      animationStyle: context.reduceMotion ? AnimationStyle.noAnimation : null,
      builder: (dialogContext) => AlertDialog(
        title: Text(l10n.discardChangesTitle),
        content: Text(l10n.discardChangesBody),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: Text(l10n.keepEditing),
          ),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: Text(l10n.discard),
          ),
        ],
      ),
    );
    return discard ?? false;
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final auth = ref.watch(authControllerProvider);
    final user = auth.currentUser;
    final saving = auth.isSavingProfile;
    final gutter = AppSpacing.gutter(context);
    final name = _name.text.trim().isEmpty ? l10n.trader : _name.text.trim();

    return PopScope(
      canPop: !_dirty || saving,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop) return;
        if (await _confirmDiscard() && context.mounted) {
          setState(() => _dirty = false);
          Navigator.of(context).pop();
        }
      },
      child: Scaffold(
        body: SafeArea(
          bottom: false,
          child: ListView(
            padding: const EdgeInsets.only(bottom: AppSpacing.xxl),
            children: [
              PageHeader(title: l10n.editProfileHint, back: const PageBackButton()),
              Padding(
                padding: EdgeInsets.fromLTRB(gutter, AppSpacing.md, gutter, 0),
                child: Form(
                  key: _formKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Center(
                        child: ExcludeSemantics(
                          child: ProfileAvatar(name: name, path: user?.avatarUrl, size: 96),
                        ),
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      Center(
                        child: AppButton.ghost(
                          label: l10n.changePhoto,
                          icon: Icons.photo_camera_outlined,
                          compact: true,
                          onPressed: saving ? null : _changePhoto,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.lg),
                      AppTextField(
                        label: l10n.displayName,
                        hint: l10n.enterYourName,
                        controller: _name,
                        enabled: !saving,
                        prefixIcon: Icons.person_outline_rounded,
                        textInputAction: TextInputAction.next,
                        autofillHints: const [AutofillHints.name],
                        validator: (v) => Validators.required(v, l10n, fieldName: l10n.name),
                      ),
                      const SizedBox(height: AppSpacing.md),
                      AppTextField(
                        label: l10n.email,
                        hint: l10n.enterYourEmail,
                        controller: _email,
                        enabled: !saving,
                        prefixIcon: Icons.mail_outline_rounded,
                        keyboardType: TextInputType.emailAddress,
                        textInputAction: TextInputAction.done,
                        autofillHints: const [AutofillHints.email],
                        validator: (v) => Validators.email(v, l10n),
                        onSubmitted: (_) => _save(),
                      ),
                      const SizedBox(height: AppSpacing.xl),
                      AppButton(
                        label: l10n.saveChanges,
                        expand: true,
                        loading: saving,
                        onPressed: _dirty ? _save : null,
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

enum _PhotoAction { camera, gallery, remove }
