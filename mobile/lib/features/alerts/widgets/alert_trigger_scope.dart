import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../view_models/alert_trigger.dart';

/// بيشغّل فاحص التنبيهات ([alertTriggerProvider]) طول ما الـ shell (المستخدم
/// داخل) موجود، وبيوقفه لما يطلع.
class AlertTriggerScope extends ConsumerWidget {
  const AlertTriggerScope({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.watch(alertTriggerProvider);
    return child;
  }
}
