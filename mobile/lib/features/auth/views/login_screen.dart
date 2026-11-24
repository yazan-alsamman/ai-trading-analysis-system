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

/// Log in: البريد + كلمة المرور بس، بلوح فوق خلفية الـ mesh. كلمة المرور
/// بتنفحص بنفس قاعدة Create account قبل ما ينبعت أي طلب. الفشل بيطلع
/// رسالة تحت الحقول (مش snackbar بيختفي)، والحقول بتضل معبّاية. تحت: سطر
/// التنبيه القصير (تحليل ودعم قرار، مش نصيحة مالية، مش وسيط).
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _submitted = false;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  void _edited(String _) => ref.read(authFormViewModelProvider.notifier).clearFailure();

  Future<void> _submit() async {
    setState(() => _submitted = true);
    if (!(_formKey.currentState?.validate() ?? false)) return;
    FocusScope.of(context).unfocus();
    final ok = await ref.read(authFormViewModelProvider.notifier).login(
          email: _email.text.trim(),
          password: _password.text,
        );
    if (ok && mounted) {
      TextInput.finishAutofillContext();
      context.pushHomeAndClearStack();
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final form = ref.watch(authFormViewModelProvider);

    return AuthScaffold(
      children: [
        AuthHeader(title: l10n.loginTitle, subtitle: l10n.loginSubtitle),
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
                        textInputAction: TextInputAction.done,
                        autofillHints: const [AutofillHints.password],
                        // نفس قاعدة Create account (Validators.password، مصدر واحد):
                        // رسالة وحدة تحت الحقل بالشرط الناقص، بدون قائمة الشروط
                        validator: (v) => Validators.password(v, l10n),
                        onChanged: _edited,
                        onSubmitted: (_) => _submit(),
                      ),
                    ],
                  ),
                ),
              ),
              if (form.failed) ...[
                const SizedBox(height: AppSpacing.md),
                AuthErrorBanner(form.offline ? l10n.authOffline : l10n.loginFailed),
              ],
              const SizedBox(height: AppSpacing.xl),
              AppButton(
                label: l10n.logIn,
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
          question: l10n.noAccount,
          action: l10n.createAccountAction,
          onPressed: () => context.pushRegistration(replace: true),
        ),
        const SizedBox(height: AppSpacing.lg),
        const AuthDisclaimer(),
      ],
    );
  }
}
