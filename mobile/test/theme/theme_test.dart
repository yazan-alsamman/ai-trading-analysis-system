// اختبارات أساس الـ design system: حفظ الثيم، تباين الألوان (WCAG)،
// قواعد الاتجاه، وتقليل الحركة.

import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:trading_app/core/storage/preferences_provider.dart';
import 'package:trading_app/l10n/app_localizations.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/core/theme/app_theme.dart';
import 'package:trading_app/core/theme/theme_context.dart';
import 'package:trading_app/dev/design_system_screen.dart';
import 'package:trading_app/core/widgets/direction_text.dart';
import 'package:trading_app/core/widgets/motion.dart';

double _contrast(Color a, Color b) {
  final la = a.computeLuminance();
  final lb = b.computeLuminance();
  return (math.max(la, lb) + 0.05) / (math.min(la, lb) + 0.05);
}

Widget _host(Widget child, {ThemeData? theme, bool reduceMotion = false}) {
  return MaterialApp(
    theme: theme ?? AppTheme.dark(),
    localizationsDelegates: const [AppLocalizations.delegate],
    supportedLocales: AppLocalizations.supportedLocales,
    home: MediaQuery(
      data: MediaQueryData(disableAnimations: reduceMotion),
      child: Scaffold(body: child),
    ),
  );
}

void main() {
  group('ThemeModeNotifier', () {
    test('defaults to system and persists the choice', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      expect(container.read(themeModeProvider), ThemeMode.system);
      await container.read(themeModeProvider.notifier).setThemeMode(ThemeMode.dark);
      expect(container.read(themeModeProvider), ThemeMode.dark);
      expect(prefs.getString(themeModeStorageKey), 'dark');
    });

    test('restores a saved choice and ignores unknown values', () async {
      Future<ThemeMode> readWith(String saved) async {
        SharedPreferences.setMockInitialValues({themeModeStorageKey: saved});
        final prefs = await SharedPreferences.getInstance();
        final container = ProviderContainer(
          overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
        );
        addTearDown(container.dispose);
        return container.read(themeModeProvider);
      }

      expect(await readWith('light'), ThemeMode.light);
      expect(await readWith('sepia'), ThemeMode.system);
    });
  });

  group('Colour tokens meet WCAG AA', () {
    for (final entry in {
      'dark': AppColorTokens.dark,
      'light': AppColorTokens.light,
    }.entries) {
      final c = entry.value;
      final surfaces = {
        'canvas': c.canvas,
        'card': c.card,
        'raised': c.raised,
        'sheet': c.sheet,
        'dialog': c.dialog,
        'inset': c.inset,
        'selected': c.selected,
      };
      final text = {
        'fg': c.fg,
        'fg2': c.fg2,
        'fg3': c.fg3,
        'accent': c.accent,
        'up': c.up,
        'down': c.down,
        'forecast': c.forecast,
        'danger': c.danger,
        'warning': c.warning,
        'info': c.info,
      };

      test('${entry.key}: every text tone ≥ 4.5:1 on every surface', () {
        for (final t in text.entries) {
          for (final s in surfaces.entries) {
            expect(
              _contrast(t.value, s.value),
              greaterThanOrEqualTo(4.5),
              reason: '${t.key} on ${s.key}',
            );
          }
        }
      });

      test('${entry.key}: input outline ≥ 3:1 on every surface', () {
        for (final s in surfaces.entries) {
          expect(_contrast(c.outline, s.value), greaterThanOrEqualTo(3.0),
              reason: 'outline on ${s.key}');
        }
      });

      test('${entry.key}: on-colour labels ≥ 4.5:1', () {
        expect(_contrast(c.onPrimaryAction, c.primaryAction), greaterThanOrEqualTo(4.5));
        expect(_contrast(c.onAccent, c.accent), greaterThanOrEqualTo(4.5));
        expect(_contrast(c.onDanger, c.danger), greaterThanOrEqualTo(4.5));
        expect(_contrast(c.onForecast, c.forecast), greaterThanOrEqualTo(4.5));
      });

      test('${entry.key}: tone text on its own soft badge ≥ 4.5:1', () {
        final pairs = {
          'accent': (c.accent, c.accentSoft),
          'up': (c.up, c.upSoft),
          'down': (c.down, c.downSoft),
          'forecast': (c.forecast, c.forecastSoft),
          'danger': (c.danger, c.dangerSoft),
          'warning': (c.warning, c.warningSoft),
          'demo': (c.demo, c.demoSoft),
        };
        for (final p in pairs.entries) {
          final badge = Color.alphaBlend(p.value.$2, c.card);
          expect(_contrast(p.value.$1, badge), greaterThanOrEqualTo(4.5),
              reason: p.key);
        }
      });
    }
  });

  group('Themes', () {
    test('both themes expose the token extensions', () {
      for (final theme in [AppTheme.light(), AppTheme.dark(arabic: true)]) {
        expect(theme.extension<AppColorTokens>(), isNotNull);
        expect(theme.extension<AppTextTokens>(), isNotNull);
        expect(theme.colorScheme.surfaceTint, Colors.transparent);
      }
    });

    test('Arabic switches off tracking and uppercase in eyebrows', () {
      final ar = AppTheme.dark(arabic: true).extension<AppTextTokens>()!;
      final en = AppTheme.dark().extension<AppTextTokens>()!;
      expect(ar.eyebrowUppercase, isFalse);
      expect(en.eyebrowUppercase, isTrue);
      expect(ar.eyebrow.letterSpacing ?? 0, 0);
    });

    test('no text style goes below the 12px floor', () {
      final t = AppTheme.light().textTheme;
      for (final s in [
        t.displayLarge, t.displayMedium, t.displaySmall, t.headlineSmall,
        t.titleLarge, t.titleMedium, t.titleSmall, t.bodyLarge, t.bodyMedium,
        t.bodySmall, t.labelLarge, t.labelMedium, t.labelSmall,
      ]) {
        expect(s!.fontSize, greaterThanOrEqualTo(12));
      }
    });
  });

  group('DirectionText', () {
    testWidgets('shows sign + arrow and announces the direction', (tester) async {
      await tester.pumpWidget(_host(const DirectionText(value: -0.96)));
      expect(find.text('−0.96%'), findsOneWidget);
      expect(find.byIcon(Icons.arrow_downward_rounded), findsOneWidget);
      expect(find.bySemanticsLabel('Down 0.96%'), findsOneWidget);
    });

    testWidgets('a value that rounds to zero is neutral', (tester) async {
      await tester.pumpWidget(_host(const DirectionText(value: 0.001)));
      expect(find.text('0.00%'), findsOneWidget);
      expect(find.byType(Icon), findsNothing);
    });
  });

  group('Reduced motion', () {
    testWidgets('FadeRise renders the final state immediately', (tester) async {
      await tester.pumpWidget(_host(
        const FadeRise(index: 2, child: Text('row')),
        reduceMotion: true,
      ));
      expect(find.text('row'), findsOneWidget);
      expect(find.byType(Animate), findsNothing);
    });

    testWidgets('FadeRise animates when motion is allowed', (tester) async {
      await tester.pumpWidget(_host(const FadeRise(child: Text('row'))));
      expect(find.byType(Animate), findsOneWidget);
      await tester.pumpAndSettle();
    });

    testWidgets('AnimatedNumber shows the final value without tweening',
        (tester) async {
      await tester.pumpWidget(_host(
        AnimatedNumber(value: 42, format: (v) => v.toStringAsFixed(0)),
        reduceMotion: true,
      ));
      expect(find.text('42'), findsOneWidget);
    });
  });

  group('Design system gallery', () {
    for (final theme in {'light': AppTheme.light(), 'dark': AppTheme.dark()}.entries) {
      testWidgets('renders in ${theme.key} without layout errors', (tester) async {
        SharedPreferences.setMockInitialValues({});
        final prefs = await SharedPreferences.getInstance();
        await tester.binding.setSurfaceSize(const Size(375, 812));
        addTearDown(() => tester.binding.setSurfaceSize(null));

        await tester.pumpWidget(ProviderScope(
          overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
          child: MaterialApp(
            theme: theme.value,
            localizationsDelegates: const [AppLocalizations.delegate],
            supportedLocales: AppLocalizations.supportedLocales,
            home: const DesignSystemScreen(),
          ),
        ));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);

        await tester.drag(find.byType(ListView), const Offset(0, -6000));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
      });
    }
  });
}
