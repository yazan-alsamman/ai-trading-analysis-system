import 'package:flutter/widgets.dart';

/// مفتاح الـ Navigator الجذر (تبع الـ GoRouter): شاشات الدخول، محادثة الخبير،
/// Backtest، وكل الـ sheets والـ dialogs بتنفتح عليه - فوق الـ shell وشريطه.
final GlobalKey<NavigatorState> appNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'root');
