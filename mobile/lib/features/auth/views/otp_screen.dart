import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/router/app_navigator.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_illustration.dart';
import '../../../core/widgets/source_tag.dart';
import '../../../l10n/app_localizations.dart';
import '../view_models/auth_view_models.dart';
import '../widgets/auth_scaffold.dart';

/// التحقق من البريد بعد إنشاء الحساب: رمز من 5 أرقام بحقل واحد (بيقبل
/// اللصق والتعبئة التلقائية من الرسائل)، عدّاد "إعادة الإرسال"، وبعد النجاح
/// خطوة تأكيد واضحة (علامة صح بتنرسم + "البريد متحقَّق منه") قبل الدخول.
class OtpVerificationScreen extends ConsumerStatefulWidget {
  const OtpVerificationScreen({super.key, required this.email});

  final String email;

  @override
  ConsumerState<OtpVerificationScreen> createState() => _OtpVerificationScreenState();
}

class _OtpVerificationScreenState extends ConsumerState<OtpVerificationScreen> {
  final _code = TextEditingController();
  final _focus = FocusNode();
  Timer? _timer;
  bool _showIncomplete = false;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) => ref.read(otpViewModelProvider.notifier).tick());
  }

  @override
  void dispose() {
    _timer?.cancel();
    _code.dispose();
    _focus.dispose();
    super.dispose();
  }

  Future<void> _verify() async {
    if (!OtpViewModel.isComplete(_code.text)) {
      setState(() => _showIncomplete = true);
      _focus.requestFocus();
      return;
    }
    FocusScope.of(context).unfocus();
    await ref.read(otpViewModelProvider.notifier).verify(_code.text);
  }

  Future<void> _resend() async {
    final l10n = AppLocalizations.of(context)!;
    await ref.read(otpViewModelProvider.notifier).resend();
    _code.clear();
    if (!mounted) return;
    setState(() => _showIncomplete = false);
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(l10n.otpResent)));
  }

  @override
  Widget build(BuildContext context) {
    final otp = ref.watch(otpViewModelProvider);
    final verified = otp.step == OtpStep.verified;

    return PopScope(
      // بعد التحقق ما في رجوع لشاشة الرمز - بس "Continue"
      canPop: !verified,
      child: AuthScaffold(
        showBack: !verified,
        children: [
          AnimatedSwitcher(
            duration: context.motion(AppMotion.medium),
            switchInCurve: AppMotion.out,
            switchOutCurve: AppMotion.exit,
            child: verified ? _Verified(key: const ValueKey('verified'), email: widget.email) : _entry(context, otp),
          ),
        ],
      ),
    );
  }

  Widget _entry(BuildContext context, OtpState otp) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final verifying = otp.step == OtpStep.verifying;
    final seconds = otp.resendIn;
    final time = '0:${seconds.toString().padLeft(2, '0')}';

    return Column(
      key: const ValueKey('entry'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        AuthHeader(
          icon: Icons.mark_email_unread_outlined,
          title: l10n.otpTitle,
          subtitle: l10n.otpBody,
          emphasis: widget.email,
        ),
        const SizedBox(height: AppSpacing.xl),
        AuthPanel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _CodeField(
                controller: _code,
                focusNode: _focus,
                enabled: !verifying,
                error: _showIncomplete && !OtpViewModel.isComplete(_code.text),
                onChanged: (value) {
                  setState(() {});
                  if (OtpViewModel.isComplete(value)) _verify();
                },
              ),
              if (_showIncomplete && !OtpViewModel.isComplete(_code.text)) ...[
                const SizedBox(height: AppSpacing.xs),
                Semantics(
                  liveRegion: true,
                  child: Text(l10n.otpIncomplete, style: context.textTheme.bodySmall!.copyWith(color: c.danger)),
                ),
              ],
              const SizedBox(height: AppSpacing.md),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SourceTag(SourceKind.demo),
                  const SizedBox(width: AppSpacing.xs),
                  Expanded(child: Text(l10n.otpSimulated, style: context.textTheme.bodySmall)),
                ],
              ),
              const SizedBox(height: AppSpacing.xl),
              AppButton(label: l10n.otpVerify, expand: true, loading: verifying, onPressed: _verify),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.sm),
        Center(
          child: seconds > 0
              ? Padding(
                  padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
                  child: Text(
                    l10n.otpResendIn(time),
                    style: context.textTheme.bodyMedium,
                  ),
                )
              : TextButton(
                  onPressed: verifying ? null : _resend,
                  style: TextButton.styleFrom(minimumSize: const Size(AppSizes.minTap, AppSizes.minTap)),
                  child: Text(l10n.otpResend),
                ),
        ),
      ],
    );
  }
}

/// حقل الرمز: TextField حقيقي (شفاف) فوق 5 مربعات مرسومة - القارئ الصوتي
/// واللصق والتعبئة التلقائية بيشتغلوا عالحقل نفسه
class _CodeField extends StatelessWidget {
  const _CodeField({
    required this.controller,
    required this.focusNode,
    required this.enabled,
    required this.error,
    required this.onChanged,
  });

  final TextEditingController controller;
  final FocusNode focusNode;
  final bool enabled;
  final bool error;
  final ValueChanged<String> onChanged;

  static const double _boxHeight = 64;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final code = controller.text;

    return SizedBox(
      height: _boxHeight,
      child: Stack(
        children: [
          ExcludeSemantics(
            child: Directionality(
              // الأرقام دايمًا من اليسار لليمين
              textDirection: TextDirection.ltr,
              child: ListenableBuilder(
                listenable: focusNode,
                builder: (context, _) => Row(
                  children: [
                    for (var i = 0; i < OtpViewModel.codeLength; i++) ...[
                      if (i > 0) const SizedBox(width: AppSpacing.xs),
                      Expanded(
                        child: _Box(
                          digit: i < code.length ? code[i] : null,
                          active: focusNode.hasFocus && i == code.length.clamp(0, OtpViewModel.codeLength - 1),
                          error: error,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),
          Positioned.fill(
            child: Opacity(
              opacity: 0,
              // الحقل مخفي بصريًا بس لازم يضل بشجرة القارئ (وإلا ما في طريقة تدخّل الرمز)
              alwaysIncludeSemantics: true,
              child: TextField(
                controller: controller,
                focusNode: focusNode,
                enabled: enabled,
                autofocus: true,
                keyboardType: TextInputType.number,
                textInputAction: TextInputAction.done,
                autofillHints: const [AutofillHints.oneTimeCode],
                inputFormatters: [
                  FilteringTextInputFormatter.digitsOnly,
                  LengthLimitingTextInputFormatter(OtpViewModel.codeLength),
                ],
                showCursor: false,
                enableInteractiveSelection: true,
                decoration: InputDecoration(
                  labelText: l10n.otpLabel,
                  counterText: '',
                  border: InputBorder.none,
                ),
                style: TextStyle(color: c.fg),
                onChanged: onChanged,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Box extends StatelessWidget {
  const _Box({required this.digit, required this.active, required this.error});

  final String? digit;
  final bool active;
  final bool error;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final border = error ? c.danger : (active ? c.accent : c.outline);
    return AnimatedContainer(
      duration: context.motion(AppMotion.fast),
      curve: AppMotion.out,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: c.inset,
        borderRadius: AppRadii.field,
        border: Border.all(color: border, width: active || error ? 2 : 1),
      ),
      child: Text(digit ?? '', style: context.type.numLarge),
    );
  }
}

/// بعد التحقق: خطوة نجاح واضحة - علامة صح بتنرسم، العنوان، سطر "البريد
/// متحقَّق منه" بالبريد نفسه، و"Continue" للرئيسية
class _Verified extends StatelessWidget {
  const _Verified({super.key, required this.email});

  final String email;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final c = context.colors;
    final text = context.textTheme;
    return Semantics(
      liveRegion: true,
      container: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const SizedBox(height: AppSpacing.xxl),
          const Center(child: SuccessIllustration(size: 144)),
          const SizedBox(height: AppSpacing.xl),
          Semantics(
            header: true,
            child: Text(
              l10n.otpDoneTitle,
              style: text.displayMedium!.copyWith(color: c.fg),
              textAlign: TextAlign.center,
            ),
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            l10n.otpDoneBody,
            style: text.bodyLarge!.copyWith(color: c.fg2),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: AppSpacing.xl),
          AuthPanel(
            child: Row(
              children: [
                Icon(Icons.verified_outlined, size: AppSizes.iconLg, color: c.accent),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(l10n.otpVerifiedRow, style: text.titleSmall),
                      Text(
                        email,
                        style: text.bodyMedium!.copyWith(color: c.fg2),
                        textDirection: TextDirection.ltr,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.xxl),
          AppButton(
            label: l10n.otpContinue,
            trailingIcon: Icons.arrow_forward_rounded,
            expand: true,
            onPressed: context.pushHomeAndClearStack,
          ),
        ],
      ),
    );
  }
}
