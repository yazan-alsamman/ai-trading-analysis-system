import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../view_models/push_permission_view_model.dart';

/// بيشغّل تسجيل token الجهاز ([pushRegistrationProvider]) طول ما الـ shell
/// (المستخدم داخل) موجود: token معلّق بينبعت لما يرجع الاتصال أو بالتشغيل الجاي.
class PushRegistrationScope extends ConsumerWidget {
  const PushRegistrationScope({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.watch(pushRegistrationProvider);
    return child;
  }
}
