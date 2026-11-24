import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/router/app_navigator.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_text_field.dart';
import '../../../l10n/app_localizations.dart';
import '../../../utils/validators.dart';
import '../view_models/auth_view_models.dart';
import '../widgets/auth_scaffold.dart';
import '../widgets/password_checks.dart';

/// Create account: الحقول المطلوبة بس (الاسم، البريد، كلمة المرور + تأكيدها)
/// بلوح فوق خلفية الـ mesh، ومربّع "مش نصيحة مالية" إلزامي (هو نفسه التنبيه،
/// فما في سطر تنبيه تاني تحت). شروط كلمة المرور بتبيّن وأنت عم تكتب
/// (نفس قاعدة الـ backend)، والأخطاء تحت كل حقل بعد أول محاولة.
class RegistrationScreen extends ConsumerStatefulWidget {
  const RegistrationScreen({super.key});

  @override
  ConsumerState<RegistrationScreen> createState() => _RegistrationScreenState();
}

class _RegistrationScreenState extends ConsumerState<RegistrationScreen> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _confirm = TextEditingController();
  bool _acknowledged = false;
  bool _submitted = false;

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _password.dispose();
    _confirm.dispose();
    super.dispose();
  }

  void _edited([String? _]) => ref.read(authFormViewModelProvider.notifier).clearFailure();

  Future<void> _submit() async {
    setState(() => _submitted = true);
    final valid = _formKey.currentState?.validate() ?? false;
    if (!valid || !_acknowledged) return;
    FocusScope.of(context).unfocus();
    final email = _email.text.trim();
    final ok = await ref.read(authFormViewModelProvider.notifier).register(
          fullName: _name.text.trim(),
          email: email,
          password: _password.text,
        );
    if (ok && mounted) {
      TextInput.finishAutofillContext();
      context.pushOtpVerification(email: email);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final form = ref.watch(authFormViewModelProvider);

    return AuthScaffold(
      children: [
        AuthHeader(title: l10n.registerTitle, subtitle: l10n.registerSubtitle),
        const SizedBox(height: AppSpacing.xl),
        AuthPanel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Form(
                key: _formKey,
                autovalidateMode: _submitted ? AutovalidateMode.onUserInteraction : AutovalidateMode.disabled,
                child: AutofillGroup(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      AppTextField(
                        label: l10n.fullName,
                        controller: _name,
                        enabled: !form.submitting,
                        prefixIcon: Icons.person_outline_rounded,
                        textInputAction: TextInputAction.next,
                        textCapitalization: TextCapitalization.words,
                        autofillHints: const [AutofillHints.name],
                        validator: (v) => Validators.fullName(v, l10n),
                        onChanged: _edited,
                      ),
                      const SizedBox(height: AppSpacing.md),
                      AppTextField(
                        label: l10n.email,
                        controller: _email,
                        enabled: !form.submitting,
                        prefixIcon: Icons.mail_outline_rounded,
                        keyboardType: TextInputType.emailAddress,
                        textInputAction: TextInputAction.next,
                        autofillHints: const [AutofillHints.email],
                        validator: (v) => Validators.email(v, l10n),
                        onChanged: _edited,
                      ),
                      const SizedBox(height: AppSpacing.md),
                      AppTextField(
                        label: l10n.password,
                        controller: _password,
                        enabled: !form.submitting,
                        prefixIcon: Icons.lock_outline_rounded,
                        obscure: true,
                        textInputAction: TextInputAction.next,
                        autofillHints: const [AutofillHints.newPassword],
                        validator: (v) => Validators.password(v, l10n),
                        onChanged: (v) {
                          setState(() {});
                          _edited();
                        },
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      PasswordChecks(password: _password.text),
                      const SizedBox(height: AppSpacing.md),
                      AppTextField(
                        label: l10n.confirmPasswordLabel,
                        controller: _confirm,
                        enabled: !form.submitting,
                        prefixIcon: Icons.lock_outline_rounded,
                        obscure: true,
                        textInputAction: TextInputAction.done,
                        autofillHints: const [AutofillHints.newPassword],
                        validator: (v) => Validators.confirmPassword(v, _password.text, l10n),
                        onChanged: _edited,
                        onSubmitted: (_) => _submit(),
                      ),
                      const SizedBox(height: AppSpacing.md),
                      _AdviceCheckbox(
                        value: _acknowledged,
                        showError: _submitted && !_acknowledged,
                        onChanged: form.submitting ? null : (v) => setState(() => _acknowledged = v),
                      ),
                    ],
                  ),
                ),
              ),
              if (form.failed) ...[
                const SizedBox(height: AppSpacing.md),
                AuthErrorBanner(form.offline ? l10n.authOffline : l10n.registerFailed),
              ],
              const SizedBox(height: AppSpacing.xl),
              AppButton(
                label: l10n.createAccountAction,
                trailingIcon: Icons.arrow_forward_rounded,
                expand: true,
                loading: form.submitting,
                onPressed: _submit,
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.sm),
        AuthSwitchRow(
          question: l10n.haveAccount,
          action: l10n.logIn,
          onPressed: () => context.pushLogin(replace: true),
        ),
      ],
    );
  }
}

/// "أفهم إنو التطبيق ما بيعطي نصيحة مالية" - الصف كلو بيبدّل، والخطأ تحتو
class _AdviceCheckbox extends StatelessWidget {
  const _AdviceCheckbox({required this.value, required this.showError, required this.onChanged});

  final bool value;
  final bool showError;
  final ValueChanged<bool>? onChanged;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        MergeSemantics(
          child: InkWell(
            borderRadius: AppRadii.card,
            onTap: onChanged == null
                ? null
                : () {
                    AppHaptics.selection();
                    onChanged!(!value);
                  },
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: AppSpacing.xxs),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Checkbox(
                    value: value,
                    isError: showError,
                    onChanged: onChanged == null ? null : (v) => onChanged!(v ?? false),
                  ),
                  const SizedBox(width: AppSpacing.xxs),
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.only(top: AppSpacing.sm),
                      child: Text(l10n.registerAdviceAck, style: context.textTheme.bodyMedium!.copyWith(color: c.fg)),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        if (showError)
          Padding(
            padding: const EdgeInsetsDirectional.only(start: AppSpacing.sm),
            child: Semantics(
              liveRegion: true,
              child: Text(
                l10n.registerAdviceRequired,
                style: context.textTheme.bodySmall!.copyWith(color: c.danger),
              ),
            ),
          ),
      ],
    );
  }
}
