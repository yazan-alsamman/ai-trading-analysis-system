// H4a: أزرار Undo / Redo الظاهرة برأس Workspaces (نفس تاريخ الأوامر):
// tooltip + اسم للقارئ الصوتي + 48 dp، معطّلة لما ما في شي، redo بعد undo
// للإنشاء والتعديل والحذف، وأمر جديد بيمسح الـ redo. Undo تبع الـ snackbar باقي.

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:trading_app/core/storage/preferences_provider.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/features/home/views/home_screen.dart';
import 'package:trading_app/features/workspaces/data/workspaces_repository.dart';
import 'package:trading_app/features/workspaces/models/workspace.dart';
import 'package:trading_app/features/workspaces/view_models/workspaces_view_model.dart';
import 'package:trading_app/features/workspaces/widgets/workspace_chip.dart';
import 'package:trading_app/features/workspaces/widgets/workspaces_sheet.dart';

import '../../helpers/test_app.dart';

const gold = Workspace(id: 'ws_gold', name: 'Gold', symbols: ['XAU/USD']);
const majors = Workspace(id: 'ws_majors', name: 'Majors', symbols: ['EUR/USD', 'GBP/USD', 'USD/JPY']);

Map<String, Object> stored(List<Workspace> list, {String? active}) => {
      LocalWorkspacesRepository.storageKey: jsonEncode([for (final w in list) w.toJson()]),
      if (active != null) LocalWorkspacesRepository.activeKey: active,
    };

Finder inSheet(Finder finder) => find.descendant(of: find.byType(WorkspacesSheet), matching: finder);

Finder historyButton(IconData icon) => inSheet(find.widgetWithIcon(IconButton, icon));

bool enabled(WidgetTester tester, IconData icon) => tester.widget<IconButton>(historyButton(icon)).onPressed != null;

Future<void> pumpSheet(WidgetTester tester, {Map<String, Object> prefs = const {}, String locale = 'en', String theme = 'light'}) async {
  usePhoneSize(tester, height: 1400);
  await tester.pumpWidget(await testScope(
    const TestApp(home: HomeScreen()),
    locale: locale,
    prefs: {themeModeStorageKey: theme, ...prefs},
  ));
  await tester.pumpAndSettle();
  await tester.tap(find.byType(WorkspaceChip));
  await tester.pumpAndSettle();
}

Future<void> tapInSheet(WidgetTester tester, Finder finder) async {
  await tester.scrollUntilVisible(finder, 200, scrollable: inSheet(find.byType(Scrollable)).first);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

Future<void> tapHistory(WidgetTester tester, IconData icon) async {
  await tester.tap(historyButton(icon));
  await tester.pumpAndSettle();
}

List<Workspace> custom(WidgetTester tester) => ProviderScope.containerOf(tester.element(find.byType(HomeScreen)))
    .read(workspacesViewModelProvider)
    .requireValue
    .custom;

Future<void> backToList(WidgetTester tester) async {
  await tester.tap(find.byTooltip('Back to workspaces'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('both start disabled; tooltips, screen-reader names, 48 dp', (tester) async {
    final handle = tester.ensureSemantics();
    await pumpSheet(tester);
    expect(enabled(tester, Icons.undo_rounded), isFalse);
    expect(enabled(tester, Icons.redo_rounded), isFalse);
    expect(inSheet(find.byTooltip('Undo')), findsOneWidget);
    expect(inSheet(find.byTooltip('Redo')), findsOneWidget);
    expect(
      tester.getSemantics(find.bySemanticsLabel('Undo last workspace change')),
      isSemantics(isButton: true, hasEnabledState: true, isEnabled: false),
    );
    expect(
      tester.getSemantics(find.bySemanticsLabel('Redo last workspace change')),
      isSemantics(isButton: true, hasEnabledState: true, isEnabled: false),
    );
    for (final icon in [Icons.undo_rounded, Icons.redo_rounded]) {
      final size = tester.getSize(historyButton(icon));
      expect(size.width, greaterThanOrEqualTo(48));
      expect(size.height, greaterThanOrEqualTo(48));
    }
    handle.dispose();
  });

  testWidgets('create → Undo → Redo; a new action clears Redo', (tester) async {
    final handle = tester.ensureSemantics();
    await pumpSheet(tester);
    await tapInSheet(tester, inSheet(find.text('New workspace')));
    await tester.enterText(inSheet(find.byType(TextField)), 'Gold only');
    await tapInSheet(tester, find.byKey(const ValueKey('ws-symbol-XAU/USD')));
    await tapInSheet(tester, inSheet(find.text('Save')));
    await backToList(tester);
    expect(custom(tester), hasLength(1));
    expect(enabled(tester, Icons.undo_rounded), isTrue);
    expect(enabled(tester, Icons.redo_rounded), isFalse);
    expect(
      tester.getSemantics(find.bySemanticsLabel('Undo last workspace change')),
      isSemantics(isButton: true, isEnabled: true, hasTapAction: true),
    );

    await tapHistory(tester, Icons.undo_rounded);
    expect(custom(tester), isEmpty);
    expect(inSheet(find.text('Gold only')), findsNothing);
    expect(enabled(tester, Icons.undo_rounded), isFalse);
    expect(enabled(tester, Icons.redo_rounded), isTrue);

    await tapHistory(tester, Icons.redo_rounded);
    expect(custom(tester).single.name, 'Gold only');
    expect(inSheet(find.text('Gold only')), findsOneWidget);
    expect(enabled(tester, Icons.redo_rounded), isFalse);

    // undo ثم أمر جديد: الـ redo بينمسح
    await tapHistory(tester, Icons.undo_rounded);
    expect(enabled(tester, Icons.redo_rounded), isTrue);
    await tapInSheet(tester, inSheet(find.text('New workspace')));
    await tester.enterText(inSheet(find.byType(TextField)), 'Euro');
    await tapInSheet(tester, find.byKey(const ValueKey('ws-symbol-EUR/USD')));
    await tapInSheet(tester, inSheet(find.text('Save')));
    await backToList(tester);
    expect(enabled(tester, Icons.redo_rounded), isFalse);
    expect(enabled(tester, Icons.undo_rounded), isTrue);
    expect(custom(tester).map((w) => w.name), ['Euro']);
    handle.dispose();
  });

  testWidgets('edit → Undo restores the old version → Redo applies the edit again', (tester) async {
    await pumpSheet(tester, prefs: stored([majors], active: majors.id));
    await tester.tap(inSheet(find.byTooltip('Edit Majors')));
    await tester.pumpAndSettle();
    await tapInSheet(tester, find.byKey(const ValueKey('ws-symbol-USD/JPY')));
    await tapInSheet(tester, inSheet(find.text('Save')));
    expect(find.text('Changes saved'), findsOneWidget, reason: 'the snackbar Undo stays');
    await backToList(tester);
    expect(custom(tester).single.symbols, ['EUR/USD', 'GBP/USD']);

    await tapHistory(tester, Icons.undo_rounded);
    expect(custom(tester).single.symbols, majors.symbols);
    expect(find.text('Changes saved'), findsNothing, reason: 'its stale Undo is hidden');
    await tapHistory(tester, Icons.redo_rounded);
    expect(custom(tester).single.symbols, ['EUR/USD', 'GBP/USD']);
    expect(enabled(tester, Icons.redo_rounded), isFalse);
  });

  testWidgets('delete → Undo brings it back (still active) → Redo deletes it again', (tester) async {
    await pumpSheet(tester, prefs: stored([gold, majors], active: gold.id));
    await tester.tap(inSheet(find.byTooltip('Edit Gold')));
    await tester.pumpAndSettle();
    await tapInSheet(tester, inSheet(find.text('Delete workspace')));
    expect(custom(tester).map((w) => w.id), [majors.id]);

    await tapHistory(tester, Icons.undo_rounded);
    expect(custom(tester).map((w) => w.id), [gold.id, majors.id]);
    final container = ProviderScope.containerOf(tester.element(find.byType(HomeScreen)));
    expect(container.read(workspacesViewModelProvider).requireValue.activeId, gold.id);

    await tapHistory(tester, Icons.redo_rounded);
    expect(custom(tester).map((w) => w.id), [majors.id]);
    expect(container.read(workspacesViewModelProvider).requireValue.activeId, Workspace.defaultId);
  });

  test('view model: redo after undo for create / edit / delete; a new command clears redo', () async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    final c = ProviderContainer(overrides: [sharedPreferencesProvider.overrideWithValue(prefs)]);
    addTearDown(c.dispose);
    c.listen(workspacesViewModelProvider, (_, __) {});
    await c.read(workspacesViewModelProvider.future);
    final vm = c.read(workspacesViewModelProvider.notifier);
    List<Workspace> list() => c.read(workspacesViewModelProvider).requireValue.custom;

    final created = await vm.create(name: 'Gold', symbols: const ['XAU/USD']);
    final id = created.workspace.id;
    await vm.edit(id, name: 'Gold 2', symbols: const ['XAU/USD', 'EUR/USD']);
    await vm.delete(id);
    expect(list(), isEmpty);

    expect(await vm.undo(), isTrue); // delete
    expect(list().single.name, 'Gold 2');
    expect(await vm.undo(), isTrue); // edit
    expect(list().single.name, 'Gold');
    expect(await vm.undo(), isTrue); // create
    expect(list(), isEmpty);
    expect(vm.canUndo, isFalse);

    expect(await vm.redo(), isTrue);
    expect(list().single.name, 'Gold');
    expect(await vm.redo(), isTrue);
    expect(list().single.name, 'Gold 2');
    expect(await vm.redo(), isTrue);
    expect(list(), isEmpty);
    expect(vm.canRedo, isFalse);

    await vm.undo();
    expect(vm.canRedo, isTrue);
    await vm.create(name: 'Euro', symbols: const ['EUR/USD']);
    expect(vm.canRedo, isFalse);
    expect(await vm.redo(), isFalse);

    // المخزّن نفسه (بعد إعادة التشغيل)
    final reopened = await LocalWorkspacesRepository(prefs).list();
    expect(reopened.map((w) => w.name).toSet(), {'Gold 2', 'Euro'});
  });

  for (final (locale, theme) in [('en', 'light'), ('ar', 'dark')]) {
    testWidgets('largest font ($locale, $theme): header buttons on their own row, title not broken', (tester) async {
      useLargeText(tester);
      await pumpSheet(tester, locale: locale, theme: theme, prefs: stored([gold]));
      expect(tester.takeException(), isNull);
      final title = inSheet(find.text(locale == 'en' ? 'Workspaces' : 'مساحات العمل'));
      final undo = historyButton(Icons.undo_rounded);
      expect(tester.getTopLeft(undo).dy, lessThan(tester.getTopLeft(title).dy), reason: 'buttons above the title');
      final paragraph = tester.renderObject<RenderParagraph>(
        find.descendant(of: title, matching: find.byType(RichText)).first,
      );
      expect(paragraph.didExceedMaxLines, isFalse);
      if (locale == 'en') {
        // كلمة وحدة: بسطر واحد (ما انكسرت بنصها)
        expect(tester.getSize(title).height, lessThan(2 * 22 * 2 * 1.6));
      }
      for (final icon in [Icons.undo_rounded, Icons.redo_rounded, Icons.close_rounded]) {
        final size = tester.getSize(inSheet(find.widgetWithIcon(IconButton, icon)));
        expect(size.width, greaterThanOrEqualTo(48));
        expect(size.height, greaterThanOrEqualTo(48));
      }
    });
  }
}
