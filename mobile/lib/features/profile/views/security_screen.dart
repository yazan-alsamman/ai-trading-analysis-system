import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_text_field.dart';
import '../../../core/widgets/page_header.dart';
import '../../../l10n/app_localizations.dart';
import '../../../providers/app_providers.dart';
import '../../../utils/validators.dart';

/// "Password & security" (من Profile): تغيير كلمة المرور.
///
/// خيارات البصمة والتحقق بخطوتين انشالت لأنها ما إلها تنفيذ - بترجع لما
/// تنبنى فعلًا. التغيير بيمر من AuthController (TODO(B02): الـ API).
class SecurityScreen extends ConsumerStatefulWidget {
  const SecurityScreen({super.key});

  @override
  ConsumerState<SecurityScreen> createState() => _SecurityScreenState();
}

class _SecurityScreenState extends ConsumerState<SecurityScreen> {
  final _formKey = GlobalKey<FormState>();
  final _current = TextEditingController();
  final _next = TextEditingController();
  final _confirm = TextEditingController();

  @override
  void dispose() {
    _current.dispose();
    _next.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final l10n = AppLocalizations.of(context)!;
    FocusScope.of(context).unfocus();
    if (!(_formKey.currentState?.validate() ?? false)) return;

    final controller = ref.read(authControllerProvider);
    final ok = await controller.changePassword(currentPassword: _current.text, newPassword: _next.text);
    if (!mounted) return;
    final messenger = ScaffoldMessenger.of(context)..hideCurrentSnackBar();
    if (ok) {
      _formKey.currentState?.reset();
      _current.clear();
      _next.clear();
      _confirm.clear();
      messenger.showSnackBar(SnackBar(content: Text(l10n.passwordUpdatedSuccessfully)));
    } else {
      messenger.showSnackBar(SnackBar(content: Text(controller.passwordError ?? l10n.couldNotUpdatePassword)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final busy = ref.watch(authControllerProvider.select((c) => c.isChangingPassword));
    final gutter = AppSpacing.gutter(context);

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: ListView(
          padding: const EdgeInsets.only(bottom: AppSpacing.xxl),
          children: [
            PageHeader(title: l10n.passwordAndSecurity, back: const PageBackButton()),
            Padding(
              padding: EdgeInsets.fromLTRB(gutter, AppSpacing.md, gutter, 0),
              child: AutofillGroup(
                child: Form(
                  key: _formKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(l10n.changePasswordIntro, style: context.textTheme.bodyMedium),
                      const SizedBox(height: AppSpacing.lg),
                      AppTextField(
                        label: l10n.currentPassword,
                        controller: _current,
                        enabled: !busy,
                        obscure: true,
                        textInputAction: TextInputAction.next,
                        autofillHints: const [AutofillHints.password],
                        validator: (v) => Validators.required(v, l10n, fieldName: l10n.currentPassword),
                      ),
                      const SizedBox(height: AppSpacing.md),
                      AppTextField(
                        label: l10n.newPassword,
                        controller: _next,
                        enabled: !busy,
                        obscure: true,
                        helper: l10n.passwordRequirementsHint,
                        textInputAction: TextInputAction.next,
                        autofillHints: const [AutofillHints.newPassword],
                        validator: (v) => Validators.password(v, l10n),
                      ),
                      const SizedBox(height: AppSpacing.md),
                      AppTextField(
                        label: l10n.confirmNewPassword,
                        controller: _confirm,
                        enabled: !busy,
                        obscure: true,
                        textInputAction: TextInputAction.done,
                        autofillHints: const [AutofillHints.newPassword],
                        validator: (v) => Validators.confirmPassword(v, _next.text, l10n),
                        onSubmitted: (_) => _submit(),
                      ),
                      const SizedBox(height: AppSpacing.xl),
                      AppButton(
                        label: l10n.updatePassword,
                        expand: true,
                        loading: busy,
                        onPressed: _submit,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
