import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/data/low_data_mode.dart';
import '../../core/theme/theme_context.dart';
import '../../core/widgets/offline_banner.dart';
import '../../l10n/app_localizations.dart';
import 'shell_tab.dart';

/// الهيكل الرئيسي بعد تسجيل الدخول: 5 تبويبات + شريط "غير متصل"
///
/// - كل تبويب فرع بـ `StatefulShellRoute.indexedStack` (app_router.dart): إلو
///   navigator، بيحتفظ بحالته وسكروله لما تتنقل بينهم، وبينبنى أول مرة بس لما
///   تفتحه (lazy). التبويب المخفي بيوقف الـ tickers (TickerMode من go_router).
/// - تبديل التبويب: fade سريع (200ms) - فوري لما الحركة مقلّلة.
/// - زر الرجوع بأندرويد: شاشة فرعية → بترجع لتبويبها؛ من جذر أي تبويب غير
///   Home → Home أولًا؛ من جذر Home → بيطلع من التطبيق.
/// - الشاشات الفرعية (Market، تفاصيل إشارة، Insights...) جوّا تبويبها والشريط
///   ظاهر؛ الدخول ومحادثة الخبير وBacktest فوق الـ shell بدون شريط.
class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> with SingleTickerProviderStateMixin {
  late final AnimationController _fade = AnimationController(
    vsync: this,
    duration: AppMotion.base,
    value: 1,
  );

  int get _current => widget.navigationShell.currentIndex;

  @override
  void initState() {
    super.initState();
    _publishTab();
  }

  @override
  void didUpdateWidget(AppShell oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.navigationShell.currentIndex != _current) {
      _onTabChanged();
      _publishTab();
    }
  }

  /// H5b: التبويب الظاهر (الـ Low data mode ما بيحدّث المخفي) - بعد الإطار،
  /// لأنو تعديل provider أثناء البناء ممنوع
  void _publishTab() {
    final tab = ShellTab.values[_current];
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) ref.read(currentShellTabProvider.notifier).state = tab;
    });
  }

  @override
  void dispose() {
    _fade.dispose();
    super.dispose();
  }

  void _onTabChanged() {
    if (context.reduceMotion) {
      _fade.value = 1;
    } else {
      _fade.forward(from: 0);
    }
  }

  void _select(int index) {
    if (index == _current) return;
    AppHaptics.selection();
    widget.navigationShell.goBranch(index);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;

    return PopScope(
      canPop: _current == ShellTab.home.index,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) widget.navigationShell.goBranch(ShellTab.home.index);
      },
      child: Scaffold(
        body: FadeTransition(
          opacity: CurvedAnimation(parent: _fade, curve: AppMotion.out),
          child: widget.navigationShell,
        ),
        bottomNavigationBar: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const OfflineBanner(),
            NavigationBar(
              selectedIndex: _current,
              onDestinationSelected: _select,
              destinations: [
                NavigationDestination(
                  icon: const Icon(Icons.home_outlined),
                  selectedIcon: const Icon(Icons.home_rounded),
                  label: l10n.navHome,
                ),
                NavigationDestination(
                  icon: const Icon(Icons.insights_outlined),
                  selectedIcon: const Icon(Icons.insights_rounded),
                  label: l10n.navSignals,
                ),
                NavigationDestination(
                  // راس روبوت = المساعد (مبني بـ Material، بدون صور)
                  icon: const Icon(Icons.smart_toy_outlined),
                  selectedIcon: const Icon(Icons.smart_toy),
                  label: l10n.navAssistant,
                ),
                NavigationDestination(
                  icon: const Icon(Icons.forum_outlined),
                  selectedIcon: const Icon(Icons.forum_rounded),
                  label: l10n.navCommunity,
                ),
                NavigationDestination(
                  icon: const Icon(Icons.person_outline_rounded),
                  selectedIcon: const Icon(Icons.person_rounded),
                  label: l10n.navProfile,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
