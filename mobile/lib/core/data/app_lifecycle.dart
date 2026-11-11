import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

// ═══════════════════════════════════════════════════════════
// App Lifecycle - التطبيق بالواجهة ولا بالخلفية
// ═══════════════════════════════════════════════════════════
//
// النبضات الحيّة بتوقف لما التطبيق يروح عالخلفية (بطارية + CPU)، وبترجع
// لما يرجع. "inactive" (ستارة الإشعارات، تبديل التطبيقات) بيضل فعّال حتى
// ما نعيد الاشتراك على كل سحبة ستارة.

class AppActiveNotifier extends Notifier<bool> {
  @override
  bool build() {
    final listener = AppLifecycleListener(
      onStateChange: (s) => state = s == AppLifecycleState.resumed || s == AppLifecycleState.inactive,
    );
    ref.onDispose(listener.dispose);
    return true;
  }
}

final appActiveProvider = NotifierProvider<AppActiveNotifier, bool>(AppActiveNotifier.new);
