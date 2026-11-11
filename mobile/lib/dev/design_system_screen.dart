import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme/theme_mode_provider.dart';
import '../core/theme/theme_context.dart';
import '../core/widgets/app_button.dart';
import '../core/widgets/app_card.dart';
import '../core/widgets/app_text_field.dart';
import '../core/widgets/atmosphere.dart';
import '../core/widgets/brand_mark.dart';
import '../core/widgets/direction_text.dart';
import '../core/widgets/feedback_states.dart';
import '../core/widgets/headings.dart';
import '../core/widgets/motion.dart';
import '../core/widgets/source_tag.dart';

/// معرض الـ design system - أداة تطوير بس (debug)، مش جزء من التطبيق
///
/// بيعرض كل الـ tokens والمكوّنات المشتركة بالثيم الحالي حتى نتأكد منها
/// على المحاكي قبل ما نبلّش نعيد تصميم الشاشات. التبديل بين الفاتح
/// والداكن هون حقيقي (محفوظ)، فبيختبر الـ persistence كمان.
///
/// بيفتح بـ: `flutter run --dart-define=DESIGN_GALLERY=true`
class DesignSystemScreen extends ConsumerStatefulWidget {
  const DesignSystemScreen({super.key});

  @override
  ConsumerState<DesignSystemScreen> createState() => _DesignSystemScreenState();
}

class _DesignSystemScreenState extends ConsumerState<DesignSystemScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _glyph = AnimationController(
    vsync: this,
    duration: AppMotion.emphasis,
    value: 1,
  );
  double _total = 12480.55;
  int _replay = 0;
  bool _switch = true;
  int _segment = 0;
  final Set<String> _chips = {'Gold'};

  @override
  void dispose() {
    _glyph.dispose();
    super.dispose();
  }

  void _replayGlyph() {
    if (context.reduceMotion) {
      _glyph.value = 1;
      return;
    }
    _glyph.forward(from: 0);
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final t = context.textTheme;
    final gutter = AppSpacing.gutter(context);
    final mode = ref.watch(themeModeProvider);

    Widget section(String eyebrow, List<Widget> children) => Padding(
          padding: EdgeInsets.fromLTRB(gutter, AppSpacing.xl, gutter, 0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Eyebrow(eyebrow),
              const SizedBox(height: AppSpacing.sm),
              ...children,
            ],
          ),
        );

    Widget gap() => const SizedBox(height: AppSpacing.sm);

    return Scaffold(
      appBar: AppBar(title: const Text('Design system')),
      body: ListView(
        padding: const EdgeInsets.only(bottom: AppSpacing.huge),
        children: [
          // ── Theme ─────────────────────────────────────────
          section('00 · Theme', [
            SegmentedButton<ThemeMode>(
              segments: const [
                ButtonSegment(
                  value: ThemeMode.light,
                  icon: Icon(Icons.light_mode_outlined),
                  label: Text('Light'),
                ),
                ButtonSegment(
                  value: ThemeMode.dark,
                  icon: Icon(Icons.dark_mode_outlined),
                  label: Text('Dark'),
                ),
                ButtonSegment(
                  value: ThemeMode.system,
                  icon: Icon(Icons.phone_android_outlined),
                  label: Text('System'),
                ),
              ],
              selected: {mode},
              showSelectedIcon: false,
              onSelectionChanged: (s) {
                AppHaptics.selection();
                ref.read(themeModeProvider.notifier).setThemeMode(s.first);
              },
            ),
            gap(),
            Text(
              'Reduce motion: ${context.reduceMotion ? 'ON' : 'off'}  ·  '
              'Text scale: ${MediaQuery.textScalerOf(context).scale(1).toStringAsFixed(2)}×',
              style: t.bodySmall,
            ),
          ]),

          // ── Brand + atmosphere ────────────────────────────
          Padding(
            padding: EdgeInsets.fromLTRB(gutter, AppSpacing.xl, gutter, 0),
            child: ClipRRect(
              borderRadius: AppRadii.heroCard,
              child: Atmosphere(
                child: Padding(
                  padding: const EdgeInsets.all(AppSpacing.xl),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          GestureDetector(
                            onTap: _replayGlyph,
                            child: AnimatedBuilder(
                              animation: _glyph,
                              builder: (_, __) =>
                                  BrandGlyph(size: 56, progress: _glyph.value),
                            ),
                          ),
                          const SizedBox(width: AppSpacing.md),
                          const Expanded(child: BrandMark(glyphSize: 32)),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.xl),
                      const SectionHeading(
                        eyebrow: '01 · Research',
                        title: 'A clearer way',
                        muted: 'to read the markets.',
                      ),
                      const SizedBox(height: AppSpacing.sm),
                      Text('طريقة أوضح لقراءة الأسواق',
                          style: t.displaySmall),
                      gap(),
                      Text('Tap the glyph to replay its build (400ms).',
                          style: t.bodySmall),
                    ],
                  ),
                ),
              ),
            ),
          ),

          // ── Colour ────────────────────────────────────────
          section('02 · Colour', [
            _Swatches(entries: {
              'canvas': c.canvas,
              'card': c.card,
              'raised': c.raised,
              'sheet': c.sheet,
              'dialog': c.dialog,
              'inset': c.inset,
              'selected': c.selected,
              'outline': c.outline,
            }),
            gap(),
            _Swatches(entries: {
              'accent': c.accent,
              'primary': c.primaryAction,
              'up': c.up,
              'down': c.down,
              'forecast': c.forecast,
              'danger': c.danger,
              'warning': c.warning,
              'demo': c.demo,
            }),
          ]),

          // ── Type ──────────────────────────────────────────
          section('03 · Type', [
            Text('Display 40 serif', style: t.displayLarge),
            Text('Headline 24', style: t.headlineSmall),
            Text('Title 20 · app bar', style: t.titleLarge),
            Text('Title 16 · card title', style: t.titleMedium),
            Text('Body 16 — the base size on mobile.', style: t.bodyLarge),
            Text('Body 14 — secondary text in fg-2.', style: t.bodyMedium),
            Text('Body 12 — metadata in fg-3, the floor.', style: t.bodySmall),
            Text('نص عربي بخط IBM Plex Sans Arabic كبديل تلقائي', style: t.bodyLarge),
            gap(),
            Text('Numbers (JetBrains Mono, tabular, slashed zero)',
                style: t.labelMedium),
            Text('2,045.30  1.08760  0.00%', style: context.type.num),
          ]),

          // ── Numbers + direction ───────────────────────────
          section('04 · Numbers', [
            AppCard(
              highlight: true,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                          child: Text('Total (tweens on refresh)',
                              style: t.bodyMedium)),
                      const SourceTag(SourceKind.demo),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  AnimatedNumber(
                    value: _total,
                    format: (v) => '\$${v.toStringAsFixed(2)}',
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  const Wrap(
                    spacing: AppSpacing.md,
                    children: [
                      DirectionText(value: 1.24),
                      DirectionText(value: -0.96),
                      DirectionText(value: 0),
                    ],
                  ),
                ],
              ),
            ),
            gap(),
            AppButton.secondary(
              label: 'Refresh total',
              icon: Icons.refresh_rounded,
              onPressed: () => setState(() => _total += 312.4),
            ),
          ]),

          // ── Provenance ────────────────────────────────────
          section('05 · Source tags', [
            Wrap(
              spacing: AppSpacing.xs,
              runSpacing: AppSpacing.xs,
              children: [
                for (final k in SourceKind.values) SourceTag(k),
              ],
            ),
          ]),

          // ── Buttons ───────────────────────────────────────
          section('06 · Buttons', [
            AppButton(label: 'Primary action', onPressed: () {}, expand: true),
            gap(),
            Row(
              children: [
                Expanded(
                  child: AppButton.secondary(label: 'Secondary', onPressed: () {}),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(child: AppButton.ghost(label: 'Ghost', onPressed: () {})),
              ],
            ),
            gap(),
            Row(
              children: [
                Expanded(
                  child: AppButton(label: 'Loading', onPressed: () {}, loading: true),
                ),
                const SizedBox(width: AppSpacing.sm),
                const Expanded(child: AppButton(label: 'Disabled', onPressed: null)),
              ],
            ),
          ]),

          // ── Inputs + controls ─────────────────────────────
          section('07 · Inputs', [
            const AppTextField(
              label: 'Email',
              hint: 'name@example.com',
              prefixIcon: Icons.mail_outline_rounded,
              keyboardType: TextInputType.emailAddress,
              autofillHints: [AutofillHints.email],
            ),
            gap(),
            const AppTextField(
              label: 'Password',
              obscure: true,
              autofillHints: [AutofillHints.password],
            ),
            gap(),
            const AppTextField(
              label: 'With error',
              errorText: 'Enter a valid email address',
            ),
            gap(),
            Wrap(
              spacing: AppSpacing.xs,
              children: [
                for (final label in ['Gold', 'FX', 'Indices'])
                  FilterChip(
                    label: Text(label),
                    selected: _chips.contains(label),
                    onSelected: (on) {
                      AppHaptics.selection();
                      setState(() => on ? _chips.add(label) : _chips.remove(label));
                    },
                  ),
              ],
            ),
            gap(),
            SegmentedButton<int>(
              segments: const [
                ButtonSegment(value: 0, label: Text('1H')),
                ButtonSegment(value: 1, label: Text('4H')),
                ButtonSegment(value: 2, label: Text('1D')),
              ],
              selected: {_segment},
              showSelectedIcon: false,
              onSelectionChanged: (s) {
                AppHaptics.selection();
                setState(() => _segment = s.first);
              },
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Price alerts'),
              subtitle: const Text('Switch with a 48dp row'),
              value: _switch,
              onChanged: (v) => setState(() => _switch = v),
            ),
          ]),

          // ── Surfaces + overlays ───────────────────────────
          section('08 · Cards, sheet, dialog, snackbar', [
            AppCard(
              onTap: () {},
              onLongPress: () => _showSheet(context),
              semanticLabel: 'Sample card',
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('XAU/USD', style: t.titleMedium),
                        Text('Tap: ripple · long-press: sheet + haptic',
                            style: t.bodySmall),
                      ],
                    ),
                  ),
                  Text('2,045.30', style: context.type.num),
                ],
              ),
            ),
            gap(),
            Wrap(
              spacing: AppSpacing.xs,
              runSpacing: AppSpacing.xs,
              children: [
                AppButton.secondary(
                  label: 'Sheet',
                  compact: true,
                  onPressed: () => _showSheet(context),
                ),
                AppButton.secondary(
                  label: 'Dialog',
                  compact: true,
                  onPressed: () => showDialog<void>(
                    context: context,
                    builder: (_) => AlertDialog(
                      title: const Text('Dialog'),
                      content: const Text('Elevated dialog surface with scrim.'),
                      actions: [
                        TextButton(
                          onPressed: () => Navigator.pop(context),
                          child: const Text('Close'),
                        ),
                      ],
                    ),
                  ),
                ),
                AppButton.secondary(
                  label: 'Snackbar',
                  compact: true,
                  onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: const Text('Removed from watchlist'),
                      action: SnackBarAction(label: 'Undo', onPressed: () {}),
                    ),
                  ),
                ),
              ],
            ),
          ]),

          // ── States ────────────────────────────────────────
          section('09 · States', [
            const Row(
              children: [
                Skeleton(width: 48, height: 48, radius: AppRadii.card),
                SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Skeleton(width: 140),
                      SizedBox(height: AppSpacing.xs),
                      Skeleton(width: 90, height: AppSpacing.sm),
                    ],
                  ),
                ),
              ],
            ),
            const AppCard(
              child: EmptyState(
                icon: Icons.inbox_outlined,
                title: 'Nothing here yet',
                message: 'Saved analyses will appear here.',
              ),
            ),
            gap(),
            AppCard(child: ErrorState(onRetry: () {})),
          ]),

          // ── Motion ────────────────────────────────────────
          section('10 · Motion (stagger, first 8 only)', [
            AppButton.ghost(
              label: 'Replay list entrance',
              icon: Icons.replay_rounded,
              onPressed: () => setState(() => _replay++),
            ),
            KeyedSubtree(
              key: ValueKey(_replay),
              child: Column(
                children: [
                  for (var i = 0; i < 10; i++)
                    FadeRise(
                      index: i,
                      child: ListTile(
                        contentPadding: EdgeInsets.zero,
                        title: Text('Row ${i + 1}'),
                        subtitle: Text(i < AppMotion.staggerMaxItems
                            ? 'Animated (delay ${i * 40}ms)'
                            : 'Static (past the stagger cap)'),
                      ),
                    ),
                ],
              ),
            ),
          ]),

          // ── Haptics ───────────────────────────────────────
          section('11 · Haptics', [
            const Wrap(
              spacing: AppSpacing.xs,
              children: [
                AppButton.secondary(
                    label: 'Selection', compact: true, onPressed: AppHaptics.selection),
                AppButton.secondary(
                    label: 'Light', compact: true, onPressed: AppHaptics.light),
                AppButton.secondary(
                    label: 'Confirm', compact: true, onPressed: AppHaptics.confirm),
              ],
            ),
          ]),
        ],
      ),
    );
  }

  void _showSheet(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      builder: (context) => Padding(
        padding: EdgeInsets.fromLTRB(
          AppSpacing.gutter(context),
          0,
          AppSpacing.gutter(context),
          AppSpacing.xl,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Quick actions', style: context.textTheme.titleLarge),
            const SizedBox(height: AppSpacing.xs),
            ListTile(
              leading: const Icon(Icons.auto_awesome_outlined),
              title: const Text('Analyze with AI'),
              onTap: () => Navigator.pop(context),
            ),
            ListTile(
              leading: const Icon(Icons.notifications_none_rounded),
              title: const Text('Set an alert'),
              onTap: () => Navigator.pop(context),
            ),
          ],
        ),
      ),
    );
  }
}

class _Swatches extends StatelessWidget {
  const _Swatches({required this.entries});

  final Map<String, Color> entries;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: AppSpacing.xs,
      runSpacing: AppSpacing.xs,
      children: [
        for (final e in entries.entries)
          SizedBox(
            width: 72,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  height: 40,
                  decoration: BoxDecoration(
                    color: e.value,
                    borderRadius: AppRadii.badge,
                    border: Border.all(color: context.colors.hairline),
                  ),
                ),
                const SizedBox(height: AppSpacing.xxs),
                Text(e.key, style: context.textTheme.bodySmall),
              ],
            ),
          ),
      ],
    );
  }
}
