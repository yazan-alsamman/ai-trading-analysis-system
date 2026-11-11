// اختبارات مساحات العمل (D4): الـ Commands (تنفيذ / تراجع / إعادة)، التخزين
// والبيانات التالفة، قواعد الـ ViewModel (التحقق، حذف الفعّالة، الضغط
// السريع، dispose)، والـ sheet من الـ Home (تبديل، إنشاء "Saved"، تعديل وحذف
// مع Undo، عربي + خط كبير + داكن).

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:trading_app/core/storage/preferences_provider.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/features/home/views/home_screen.dart';
import 'package:trading_app/features/home/widgets/watchlist_row.dart';
import 'package:trading_app/features/markets/models/market_models.dart';
import 'package:trading_app/features/workspaces/data/workspaces_repository.dart';
import 'package:trading_app/features/workspaces/models/workspace.dart';
import 'package:trading_app/features/workspaces/view_models/workspace_commands.dart';
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

/// مستودع بالذاكرة؛ [hold] بيعلّق الكتابة لحد ما يكمل الـ Completer
final class MemoryRepo implements WorkspacesRepository {
  MemoryRepo([List<Workspace> initial = const [], this.active]) : items = [...initial];

  final List<Workspace> items;
  String? active;
  Completer<void>? hold;
  bool failList = false;

  @override
  Future<List<Workspace>> list() async {
    if (failList) throw StateError('read failed');
    return [...items];
  }

  @override
  Future<void> create(Workspace workspace, {int? at}) async {
    await hold?.future;
    items.insert((at ?? items.length).clamp(0, items.length), workspace);
  }

  @override
  Future<void> update(Workspace workspace) async {
    await hold?.future;
    final i = items.indexWhere((w) => w.id == workspace.id);
    items[i] = workspace;
  }

  @override
  Future<void> delete(String id) async {
    await hold?.future;
    items.removeWhere((w) => w.id == id);
  }

  @override
  Future<String?> readActiveId() async => active;

  @override
  Future<void> saveActiveId(String id) async => active = id;
}

Future<SharedPreferences> prefsWith(Map<String, Object> values) async {
  SharedPreferences.setMockInitialValues(values);
  return SharedPreferences.getInstance();
}

ProviderContainer containerFor(SharedPreferences prefs, {WorkspacesRepository? repo}) {
  final container = ProviderContainer(overrides: [
    sharedPreferencesProvider.overrideWithValue(prefs),
    if (repo != null) workspacesRepositoryProvider.overrideWithValue(repo),
  ]);
  addTearDown(container.dispose);
  return container;
}

Future<void> pumpHome(
  WidgetTester tester, {
  Map<String, Object> prefs = const {},
  String locale = 'en',
  String theme = 'light',
  double height = 1400,
}) async {
  usePhoneSize(tester, height: height);
  await tester.pumpWidget(await testScope(
    const TestApp(home: HomeScreen()),
    locale: locale,
    prefs: {themeModeStorageKey: theme, ...prefs},
  ));
  await tester.pumpAndSettle();
}

Finder inSheet(Finder finder) => find.descendant(of: find.byType(WorkspacesSheet), matching: finder);

Future<void> openSheet(WidgetTester tester) async {
  await tester.tap(find.byType(WorkspaceChip));
  await tester.pumpAndSettle();
  expect(find.byType(WorkspacesSheet), findsOneWidget);
}

Future<void> tapInSheet(WidgetTester tester, Finder finder) async {
  await tester.scrollUntilVisible(
    finder,
    200,
    scrollable: inSheet(find.byType(Scrollable)).first,
  );
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

Finder symbolBox(String symbol) => find.byKey(ValueKey('ws-symbol-$symbol'));

void main() {
  group('commands', () {
    test('create: execute adds and activates; undo removes and restores the old active; redo again', () async {
      final repo = MemoryRepo([majors], majors.id);
      final start = WorkspacesState(custom: const [majors], activeId: majors.id);
      final command = CreateWorkspaceCommand(gold, previousActiveId: majors.id);

      final done = await command.execute(start, repo);
      expect(done.custom, [majors, gold]);
      expect(done.activeId, gold.id);
      expect(repo.items, [majors, gold]);
      expect(repo.active, gold.id);

      final undone = await command.undo(done, repo);
      expect(undone, start);
      expect(repo.items, [majors]);
      expect(repo.active, majors.id);

      final redone = await command.execute(undone, repo);
      expect(redone, done);
    });

    test('update: execute writes the new value, undo the old one', () async {
      final repo = MemoryRepo([gold]);
      final after = gold.copyWith(name: 'Gold + euro', symbols: ['EUR/USD', 'XAU/USD']);
      final command = UpdateWorkspaceCommand(before: gold, after: after);
      const start = WorkspacesState(custom: [gold]);

      final done = await command.execute(start, repo);
      expect(done.custom.single, after);
      expect(repo.items.single, after);
      final undone = await command.undo(done, repo);
      expect(undone.custom.single, gold);
      expect(repo.items.single, gold);
    });

    test('delete the active one: falls back to the default; undo restores position and active', () async {
      final repo = MemoryRepo([gold, majors], gold.id);
      final start = WorkspacesState(custom: const [gold, majors], activeId: gold.id);
      const command = DeleteWorkspaceCommand(gold, index: 0, wasActive: true);

      final done = await command.execute(start, repo);
      expect(done.custom, [majors]);
      expect(done.activeId, Workspace.defaultId);
      expect(repo.active, Workspace.defaultId);

      final undone = await command.undo(done, repo);
      expect(undone.custom, [gold, majors]);
      expect(undone.activeId, gold.id);
      expect(repo.items, [gold, majors]);
      expect(repo.active, gold.id);
    });

    test('history: a new command clears redo; the oldest drop past the limit', () {
      final history = WorkspaceHistory(limit: 2);
      const a = DeleteWorkspaceCommand(gold, index: 0, wasActive: false);
      const b = DeleteWorkspaceCommand(majors, index: 0, wasActive: false);
      const c = CreateWorkspaceCommand(gold, previousActiveId: Workspace.defaultId);
      history
        ..push(a)
        ..push(b);
      history.movedToRedo();
      expect(history.canRedo, isTrue);
      expect(history.lastUndone, same(b));
      history.push(c);
      expect(history.canRedo, isFalse);
      history.push(b);
      expect(history.lastDone, same(b));
      history.movedToRedo();
      history.movedToRedo();
      expect(history.canUndo, isFalse, reason: 'a was dropped (limit 2)');
    });
  });

  group('repository', () {
    test('persists create / update / delete / active across instances', () async {
      final prefs = await prefsWith({});
      final repo = LocalWorkspacesRepository(prefs);
      expect(await repo.list(), isEmpty);
      expect(await repo.readActiveId(), isNull);

      await repo.create(gold);
      await repo.create(majors, at: 0);
      await repo.saveActiveId(gold.id);
      await repo.update(gold.copyWith(name: 'Metals'));
      final again = LocalWorkspacesRepository(prefs);
      expect((await again.list()).map((w) => w.name), ['Majors', 'Metals']);
      expect(await again.readActiveId(), gold.id);

      await again.delete(majors.id);
      expect((await LocalWorkspacesRepository(prefs).list()).map((w) => w.id), [gold.id]);
    });

    for (final (label, raw) in [
      ('broken JSON', '{not json'),
      ('not a list', '{"id":"x"}'),
      ('a number', '42'),
    ]) {
      test('corrupted storage ($label) → no custom workspaces', () async {
        final prefs = await prefsWith({LocalWorkspacesRepository.storageKey: raw});
        expect(await LocalWorkspacesRepository(prefs).list(), isEmpty);
      });
    }

    test('invalid items are dropped; symbols are filtered and ordered', () async {
      final prefs = await prefsWith({
        LocalWorkspacesRepository.storageKey: jsonEncode([
          {'id': 'a', 'name': '  Mixed   list ', 'symbols': ['XAU/USD', 'BTC/USD', 'EUR/USD', 'XAU/USD']},
          {'name': 'No id', 'symbols': ['EUR/USD']},
          {'id': 'b', 'name': '', 'symbols': ['EUR/USD']},
          {'id': 'c', 'name': 'x' * 25, 'symbols': ['EUR/USD']},
          {'id': 'd', 'name': 'Unknown', 'symbols': ['BTC/USD']},
          {'id': 'a', 'name': 'Same id', 'symbols': ['EUR/USD']},
          {'id': 'e', 'name': 'MIXED LIST', 'symbols': ['EUR/USD']},
          {'id': 'all', 'name': 'Fake default', 'symbols': ['EUR/USD']},
          {'id': 'f', 'name': 'Bad symbols', 'symbols': 'EUR/USD'},
          'garbage',
          {'id': 'g', 'name': 'Good', 'symbols': ['NZD/USD']},
        ]),
      });
      final list = await LocalWorkspacesRepository(prefs).list();
      expect(list.map((w) => w.id), ['a', 'g']);
      expect(list.first.name, 'Mixed list');
      expect(list.first.symbols, ['EUR/USD', 'XAU/USD']);
    });

    test('never more than the maximum', () async {
      final prefs = await prefsWith(stored([
        for (var i = 0; i < 15; i++) Workspace(id: 'w$i', name: 'W$i', symbols: const ['EUR/USD']),
      ]));
      expect(await LocalWorkspacesRepository(prefs).list(), hasLength(WorkspacesState.maxCount - 1));
    });
  });

  group('view model', () {
    test('empty storage: only "All instruments", active', () async {
      final c = containerFor(await prefsWith({}));
      final state = await c.read(workspacesViewModelProvider.future);
      expect(state.all, [Workspace.all]);
      expect(state.active, Workspace.all);
      expect(Workspace.all.symbols, kProductSymbols);
    });

    test('the active workspace survives a restart (same storage, new scope)', () async {
      final prefs = await prefsWith({});
      final first = containerFor(prefs);
      await first.read(workspacesViewModelProvider.future);
      await first.read(workspacesViewModelProvider.notifier).create(name: 'Gold', symbols: ['XAU/USD']);
      first.dispose();

      final second = containerFor(prefs);
      final state = await second.read(workspacesViewModelProvider.future);
      expect(state.active.name, 'Gold');
      expect(state.active.symbols, ['XAU/USD']);
    });

    test('unknown stored active id, corrupted data or a failed read → default', () async {
      var c = containerFor(await prefsWith(stored([gold], active: 'ws_gone')));
      expect((await c.read(workspacesViewModelProvider.future)).active, Workspace.all);

      c = containerFor(await prefsWith({
        LocalWorkspacesRepository.storageKey: '[[[',
        LocalWorkspacesRepository.activeKey: gold.id,
      }));
      final corrupted = await c.read(workspacesViewModelProvider.future);
      expect(corrupted.custom, isEmpty);
      expect(corrupted.active, Workspace.all);

      c = containerFor(await prefsWith({}), repo: MemoryRepo([gold], gold.id)..failList = true);
      expect(await c.read(workspacesViewModelProvider.future), const WorkspacesState());
    });

    test('rules: name required, length, unique (incl. the default in EN + AR), one instrument', () async {
      final c = containerFor(await prefsWith(stored([gold])));
      await c.read(workspacesViewModelProvider.future);
      final vm = c.read(workspacesViewModelProvider.notifier);

      Set<WorkspaceIssue> check(String name, [List<String> symbols = const ['EUR/USD'], String? id]) =>
          vm.validate(name: name, symbols: symbols, editingId: id);

      expect(check('   '), {WorkspaceIssue.nameRequired});
      expect(check('x' * 25), {WorkspaceIssue.nameTooLong});
      expect(check('x' * 24), isEmpty);
      expect(check(' gOLD '), {WorkspaceIssue.nameTaken});
      expect(check('all instruments'), {WorkspaceIssue.nameTaken});
      expect(check('كل الأدوات'), {WorkspaceIssue.nameTaken});
      expect(check('Gold', ['EUR/USD'], gold.id), isEmpty, reason: 'its own name is fine');
      expect(check('Euro', const []), {WorkspaceIssue.noInstruments});
      expect(check('Euro', const ['BTC/USD']), {WorkspaceIssue.noInstruments});
      expect(check('x', ['EUR/USD'], Workspace.defaultId), {WorkspaceIssue.defaultLocked});

      await expectLater(
        vm.create(name: 'gold', symbols: ['EUR/USD']),
        throwsA(isA<WorkspaceRuleException>().having((e) => e.issues, 'issues', {WorkspaceIssue.nameTaken})),
      );
      await expectLater(vm.delete(Workspace.defaultId), throwsA(isA<WorkspaceRuleException>()));
      await expectLater(
        vm.edit(Workspace.defaultId, name: 'Mine', symbols: ['EUR/USD']),
        throwsA(isA<WorkspaceRuleException>()),
      );
      expect(await vm.edit(gold.id, name: ' Gold ', symbols: ['XAU/USD']), isNull, reason: 'nothing changed');
    });

    test('maximum number of workspaces', () async {
      final c = containerFor(await prefsWith({}));
      await c.read(workspacesViewModelProvider.future);
      final vm = c.read(workspacesViewModelProvider.notifier);
      for (var i = 1; i < WorkspacesState.maxCount; i++) {
        await vm.create(name: 'W$i', symbols: ['EUR/USD']);
      }
      expect(c.read(workspacesViewModelProvider).requireValue.atLimit, isTrue);
      await expectLater(
        vm.create(name: 'One more', symbols: ['EUR/USD']),
        throwsA(isA<WorkspaceRuleException>().having((e) => e.issues, 'issues', {WorkspaceIssue.limitReached})),
      );
    });

    test('delete the active one → default; undo brings it back active; redo deletes again', () async {
      final prefs = await prefsWith(stored([gold, majors], active: majors.id));
      final c = containerFor(prefs);
      await c.read(workspacesViewModelProvider.future);
      final vm = c.read(workspacesViewModelProvider.notifier);

      final command = await vm.delete(majors.id);
      expect(command.wasActive, isTrue);
      expect(c.read(activeWorkspaceProvider).requireValue, Workspace.all);
      expect(prefs.getString(LocalWorkspacesRepository.activeKey), Workspace.defaultId);

      expect(await vm.undo(only: command), isTrue);
      expect(c.read(activeWorkspaceProvider).requireValue, majors);
      expect(c.read(workspacesViewModelProvider).requireValue.custom, [gold, majors]);
      expect(vm.canRedo, isTrue);

      expect(await vm.redo(), isTrue);
      expect(c.read(workspacesViewModelProvider).requireValue.custom, [gold]);
      expect(await vm.redo(), isFalse);
    });

    test('an old snackbar Undo does nothing once a newer command ran', () async {
      final c = containerFor(await prefsWith(stored([gold, majors])));
      await c.read(workspacesViewModelProvider.future);
      final vm = c.read(workspacesViewModelProvider.notifier);
      final first = await vm.delete(gold.id);
      await vm.edit(majors.id, name: 'FX majors', symbols: majors.symbols);
      expect(await vm.undo(only: first), isFalse);
      expect(c.read(workspacesViewModelProvider).requireValue.custom.single.name, 'FX majors');
      expect(await vm.undo(), isTrue, reason: 'the plain undo takes the latest');
      expect(c.read(workspacesViewModelProvider).requireValue.custom.single.name, 'Majors');
    });

    test('rapid taps: two creates with one name at once → one workspace, the second is refused', () async {
      final c = containerFor(await prefsWith({}));
      await c.read(workspacesViewModelProvider.future);
      final vm = c.read(workspacesViewModelProvider.notifier);
      final results = await Future.wait([
        vm.create(name: 'Gold', symbols: ['XAU/USD']).then<Object>((v) => v, onError: (Object e) => e),
        vm.create(name: 'Gold', symbols: ['XAU/USD']).then<Object>((v) => v, onError: (Object e) => e),
      ]);
      expect(results.first, isA<CreateWorkspaceCommand>());
      expect(results.last, isA<WorkspaceRuleException>());
      expect(c.read(workspacesViewModelProvider).requireValue.custom, hasLength(1));
    });

    test('switching: unknown id ignored; rapid switches end on the last one', () async {
      final prefs = await prefsWith(stored([gold, majors]));
      final c = containerFor(prefs);
      await c.read(workspacesViewModelProvider.future);
      final vm = c.read(workspacesViewModelProvider.notifier);
      await vm.setActive('nope');
      expect(c.read(activeWorkspaceProvider).requireValue, Workspace.all);
      await Future.wait([vm.setActive(gold.id), vm.setActive(majors.id), vm.setActive(gold.id)]);
      expect(c.read(activeWorkspaceProvider).requireValue, gold);
      expect(prefs.getString(LocalWorkspacesRepository.activeKey), gold.id);
    });

    test('disposed while saving: no error, nothing written to a dead provider', () async {
      final repo = MemoryRepo()..hold = Completer<void>();
      final c = ProviderContainer(overrides: [
        sharedPreferencesProvider.overrideWithValue(await prefsWith({})),
        workspacesRepositoryProvider.overrideWithValue(repo),
      ]);
      await c.read(workspacesViewModelProvider.future);
      final pending = c.read(workspacesViewModelProvider.notifier).create(name: 'Gold', symbols: ['XAU/USD']);
      await Future<void>.delayed(Duration.zero);
      c.dispose();
      repo.hold!.complete();
      await expectLater(pending, completes);
    });
  });

  group('sheet on Home', () {
    testWidgets('chip shows the active workspace; Home lists only its instruments', (tester) async {
      final semantics = tester.ensureSemantics();
      await pumpHome(tester, prefs: stored([majors], active: majors.id));
      expect(find.byType(WatchlistRow), findsNWidgets(3));
      expect(find.bySemanticsLabel('Workspace: Majors, 3 instruments'), findsOneWidget);
      final chip = tester.getSize(find.byType(WorkspaceChip));
      expect(chip.height, greaterThanOrEqualTo(48));
      semantics.dispose();
    });

    testWidgets('corrupted storage: Home falls back to all 8 instruments', (tester) async {
      await pumpHome(tester, prefs: {
        LocalWorkspacesRepository.storageKey: 'oops',
        LocalWorkspacesRepository.activeKey: 'ws_majors',
      });
      expect(find.byType(WatchlistRow), findsNWidgets(8));
      expect(find.textContaining('All instruments'), findsOneWidget);
    });

    testWidgets('switch: tapping a workspace updates Home behind; the sheet stays open', (tester) async {
      await pumpHome(tester, prefs: stored([gold]));
      await openSheet(tester);
      expect(inSheet(find.byTooltip('Edit All instruments')), findsNothing, reason: 'the default is locked');
      await tester.tap(inSheet(find.text('Gold')));
      await tester.pumpAndSettle();
      expect(find.byType(WorkspacesSheet), findsOneWidget);
      expect(find.byType(WatchlistRow, skipOffstage: false), findsOneWidget);
      await tester.tap(inSheet(find.text('All instruments')));
      await tester.pumpAndSettle();
      expect(find.byType(WatchlistRow, skipOffstage: false), findsNWidgets(8));
    });

    testWidgets('create: rules shown on Save; Save keeps the sheet open with "Saved"; a double tap saves once',
        (tester) async {
      await pumpHome(tester);
      await openSheet(tester);
      await tapInSheet(tester, inSheet(find.text('New workspace')));
      await tapInSheet(tester, inSheet(find.text('Save')));
      expect(inSheet(find.text('Enter a name.')), findsOneWidget);
      expect(inSheet(find.text('Pick at least one instrument.')), findsOneWidget);

      await tester.enterText(inSheet(find.byType(TextField)), 'all instruments');
      await tester.pump();
      expect(inSheet(find.text('You already have a workspace with this name.')), findsOneWidget);

      await tester.enterText(inSheet(find.byType(TextField)), 'Gold and euro');
      await tapInSheet(tester, symbolBox('XAU/USD'));
      await tapInSheet(tester, symbolBox('EUR/USD'));
      final save = inSheet(find.text('Save'));
      await tester.scrollUntilVisible(save, 200, scrollable: inSheet(find.byType(Scrollable)).first);
      await tester.tap(save);
      await tester.tap(save, warnIfMissed: false);
      await tester.pumpAndSettle();

      expect(find.byType(WorkspacesSheet), findsOneWidget);
      expect(inSheet(find.text('Saved')), findsOneWidget);
      expect(inSheet(find.text('Edit workspace')), findsOneWidget);
      final container = ProviderScope.containerOf(tester.element(find.byType(HomeScreen)));
      expect(container.read(workspacesViewModelProvider).requireValue.custom, hasLength(1));

      await tester.tap(find.byTooltip('Close'));
      await tester.pumpAndSettle();
      expect(find.byType(WorkspacesSheet), findsNothing);
      expect(find.byType(WatchlistRow), findsNWidgets(2));
      expect(find.textContaining('Gold and euro'), findsOneWidget);
    });

    testWidgets('edit: snackbar with Undo restores the old version', (tester) async {
      await pumpHome(tester, prefs: stored([majors], active: majors.id));
      await openSheet(tester);
      await tester.tap(inSheet(find.byTooltip('Edit Majors')));
      await tester.pumpAndSettle();
      await tapInSheet(tester, symbolBox('USD/JPY'));
      await tapInSheet(tester, inSheet(find.text('Save')));
      expect(find.text('Changes saved'), findsOneWidget);
      expect(inSheet(find.text('Saved')), findsOneWidget);
      expect(find.byType(WatchlistRow, skipOffstage: false), findsNWidgets(2));

      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();
      expect(find.byType(WatchlistRow, skipOffstage: false), findsNWidgets(3));
      final box = tester.widget<CheckboxListTile>(symbolBox('USD/JPY'));
      expect(box.value, isTrue, reason: 'the editor shows the restored version');
    });

    testWidgets('delete the active one: Home falls back to all; Undo brings it back', (tester) async {
      await pumpHome(tester, prefs: stored([gold], active: gold.id));
      expect(find.byType(WatchlistRow), findsOneWidget);
      await openSheet(tester);
      await tester.tap(inSheet(find.byTooltip('Edit Gold')));
      await tester.pumpAndSettle();
      await tapInSheet(tester, inSheet(find.text('Delete workspace')));
      expect(find.text('“Gold” deleted. Showing all instruments.'), findsOneWidget);
      expect(inSheet(find.text('Workspaces')), findsOneWidget, reason: 'back on the list');
      expect(find.byType(WatchlistRow, skipOffstage: false), findsNWidgets(8));

      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();
      expect(find.byType(WatchlistRow, skipOffstage: false), findsOneWidget);
      expect(inSheet(find.text('Gold')), findsOneWidget);
    });

    testWidgets('back from the editor returns to the list; the chip opens one sheet on a double tap',
        (tester) async {
      await pumpHome(tester, prefs: stored([gold]));
      await tester.tap(find.byType(WorkspaceChip));
      await tester.tap(find.byType(WorkspaceChip), warnIfMissed: false);
      await tester.pumpAndSettle();
      expect(find.byType(WorkspacesSheet), findsOneWidget);
      await tester.tap(inSheet(find.byTooltip('Edit Gold')));
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Back to workspaces'));
      await tester.pumpAndSettle();
      expect(inSheet(find.text('Workspaces')), findsOneWidget);
      expect(find.byType(WorkspacesSheet), findsOneWidget);
    });

    for (final (locale, theme) in [('ar', 'dark'), ('en', 'light')]) {
      testWidgets('largest font ($locale, $theme): chip, list and editor fit; no label cut off', (tester) async {
        useLargeText(tester);
        await pumpHome(
          tester,
          locale: locale,
          theme: theme,
          height: 900,
          prefs: stored([const Workspace(id: 'ws_long', name: 'Gold and the majors 24c', symbols: kProductSymbols)],
              active: 'ws_long'),
        );
        expect(tester.takeException(), isNull);
        await openSheet(tester);
        expect(tester.takeException(), isNull);
        final edit = inSheet(find.byIcon(Icons.edit_outlined));
        await tester.ensureVisible(edit);
        await tester.pumpAndSettle();
        await tester.tap(edit);
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        expect(inSheet(find.byType(CheckboxListTile)), findsWidgets);

        // الـ chip والـ sheet: ولا تسمية بتنقص بـ "…"
        final ours = find.descendant(
          of: find.byWidgetPredicate((w) => w is WorkspaceChip || w is WorkspacesSheet),
          matching: find.byType(RichText),
        );
        expect(ours, findsWidgets);
        for (final element in ours.evaluate()) {
          final paragraph = element.renderObject! as RenderParagraph;
          expect(paragraph.didExceedMaxLines, isFalse, reason: '"${paragraph.text.toPlainText()}" is cut off');
        }
        if (locale == 'ar') {
          expect(Directionality.of(tester.element(find.byType(WorkspacesSheet))), TextDirection.rtl);
        }
      });
    }
  });
}
