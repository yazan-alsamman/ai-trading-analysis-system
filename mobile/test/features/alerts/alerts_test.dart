// اختبارات التنبيهات: تحويل PriceAlertRead، التحقق من السعر، الحالات (State
// pattern)، الـ repository، والـ ViewModel (ضغط مزدوج، حذف + Undo، فشل بيرجع).

import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/core/data/json.dart';
import 'package:trading_app/features/alerts/data/alerts_repository.dart';
import 'package:trading_app/features/alerts/models/price_alert.dart';
import 'package:trading_app/features/alerts/view_models/alerts_view_model.dart';

const _draft = AlertDraft(symbol: 'EUR/USD', condition: AlertCondition.crossesAbove, value: 1.09);

/// repository بطلبات بنتحكّم متى بتخلص أو بتفشل
final class ControlledRepo extends InMemoryAlertsRepository {
  Completer<void>? gate;
  bool failNext = false;
  int creates = 0;

  Future<void> _maybeWait() async {
    if (gate != null) await gate!.future;
    if (failNext) {
      failNext = false;
      throw StateError('network');
    }
  }

  @override
  Future<PriceAlert> create(AlertDraft draft) async {
    creates++;
    await _maybeWait();
    return super.create(draft);
  }

  @override
  Future<PriceAlert?> delete(String id) async {
    await _maybeWait();
    return super.delete(id);
  }

  @override
  Future<PriceAlert> setActive(String id, {required bool active}) async {
    await _maybeWait();
    return super.setActive(id, active: active);
  }
}

void main() {
  group('PriceAlertDto', () {
    test('parses backend PriceAlertRead', () {
      final a = const PriceAlertDto(Json({
        'id': 'a1',
        'instrument': {'id': 'u1', 'symbol': 'eur/usd'},
        'condition': 'crosses_below',
        'value': 1.05,
        'repeat': 'every',
        'is_active': false,
        'note': 'support',
        'last_triggered_at': '2026-10-20T10:00:00Z',
        'trigger_count': 2,
        'created_at': '2026-10-19T10:00:00Z',
      })).toDomain()!;
      expect(a.symbol, 'EUR/USD');
      expect(a.condition, AlertCondition.crossesBelow);
      expect(a.state, isA<AlertTriggered>());
    });

    test('unknown condition or missing instrument is dropped', () {
      expect(
        const PriceAlertDto(Json({'id': 'a', 'condition': 'above', 'value': 1, 'created_at': '2026-01-01T00:00:00Z'}))
            .toDomain(),
        isNull,
      );
      expect(
        const PriceAlertDto(Json({
          'id': 'a',
          'instrument': {'symbol': 'EUR/USD'},
          'condition': 'sideways',
          'value': 1,
          'created_at': '2026-01-01T00:00:00Z',
        })).toDomain(),
        isNull,
      );
    });

    test('create body follows PriceAlertCreate and drops a blank note', () {
      final body = PriceAlertDto.createBody(const AlertDraft(
        symbol: 'EUR/USD',
        condition: AlertCondition.crossesAbove,
        value: 1.1,
        note: '   ',
      ));
      expect(body['condition'], 'crosses_above');
      expect(body['repeat'], 'once');
      expect(body.containsKey('note'), isFalse);
    });
  });

  group('validation and state', () {
    test('validateAlertValue', () {
      expect(validateAlertValue('', current: 1.1, precision: 5), AlertValueError.empty);
      expect(validateAlertValue('1.2.3', current: 1.1, precision: 5), AlertValueError.invalid);
      expect(validateAlertValue('0', current: 1.1, precision: 5), AlertValueError.notPositive);
      expect(validateAlertValue('1.100001', current: 1.1, precision: 5), AlertValueError.equalsCurrent);
      expect(validateAlertValue('1,2', current: 1.1, precision: 5), isNull);
    });

    test('condition follows the target side of the current price', () {
      expect(AlertDraft.conditionFor(target: 1.2, current: 1.1), AlertCondition.crossesAbove);
      expect(AlertDraft.conditionFor(target: 1.0, current: 1.1), AlertCondition.crossesBelow);
    });

    test('each state owns its allowed actions', () {
      final base = PriceAlert(
        id: 'a',
        symbol: 'EUR/USD',
        condition: AlertCondition.crossesAbove,
        value: 1,
        status: AlertStatus.active,
        createdAt: DateTime.utc(2026),
      );
      expect(base.state, isA<AlertActive>());
      expect(base.state.actions, {AlertAction.pause, AlertAction.delete});
      expect(base.copyWith(isActive: false).state, isA<AlertPaused>());
      expect(base.copyWith(isActive: false).state.actions, contains(AlertAction.resume));
    });
  });

  group('InMemoryAlertsRepository', () {
    test('create, pause, delete, restore', () async {
      final repo = InMemoryAlertsRepository();
      final a = await repo.create(_draft);
      expect((await repo.list()).single.id, a.id);
      expect((await repo.setActive(a.id, active: false)).isActive, isFalse);
      await repo.delete(a.id);
      expect(await repo.list(), isEmpty);
      await repo.restore(a);
      await repo.restore(a); // مرتين ما بيكرّر
      expect(await repo.list(), hasLength(1));
    });

    test('a note over 200 characters is rejected', () {
      final repo = InMemoryAlertsRepository();
      expect(
        repo.create(AlertDraft(symbol: 'EUR/USD', condition: AlertCondition.crossesAbove, value: 1, note: 'x' * 201)),
        throwsArgumentError,
      );
    });
  });

  group('AlertsViewModel', () {
    late ControlledRepo repo;
    late ProviderContainer container;

    setUp(() {
      repo = ControlledRepo();
      container = ProviderContainer(overrides: [alertsRepositoryProvider.overrideWithValue(repo)]);
      addTearDown(container.dispose);
      container.listen(alertsViewModelProvider, (_, __) {});
    });

    AlertsViewModel vm() => container.read(alertsViewModelProvider.notifier);
    List<PriceAlert> alerts() => container.read(alertsViewModelProvider).value!;

    test('double tap on Create sends one request', () async {
      await container.read(alertsViewModelProvider.future);
      repo.gate = Completer();
      final first = vm().create(_draft);
      final second = vm().create(_draft);
      expect(await second, isNull);
      repo.gate!.complete();
      expect(await first, isNotNull);
      expect(repo.creates, 1);
      expect(alerts(), hasLength(1));
    });

    test('a failed create leaves the list unchanged and lets the user retry', () async {
      await container.read(alertsViewModelProvider.future);
      repo.failNext = true;
      await expectLater(vm().create(_draft), throwsStateError);
      expect(alerts(), isEmpty);
      expect(await vm().create(_draft), isNotNull);
    });

    test('remove is optimistic and Undo restores it in place', () async {
      await container.read(alertsViewModelProvider.future);
      final a = (await vm().create(_draft))!;
      final b = (await vm().create(const AlertDraft(symbol: 'EUR/USD', condition: AlertCondition.crossesBelow, value: 1)))!;
      final removed = await vm().remove(a.id);
      expect(alerts().map((x) => x.id), [b.id]);
      await vm().undoRemove(removed!);
      expect(alerts().map((x) => x.id).toSet(), {a.id, b.id});
      expect(await vm().remove('missing'), isNull);
    });

    test('a failed delete puts the alert back', () async {
      await container.read(alertsViewModelProvider.future);
      final a = (await vm().create(_draft))!;
      repo.failNext = true;
      await expectLater(vm().remove(a.id), throwsStateError);
      expect(alerts().single.id, a.id);
    });

    test('pause is optimistic and reverts on failure', () async {
      await container.read(alertsViewModelProvider.future);
      final a = (await vm().create(_draft))!;
      repo.gate = Completer();
      final pending = vm().setActive(a.id, active: false);
      expect(alerts().single.state, isA<AlertPaused>());
      repo.failNext = true;
      repo.gate!.complete();
      await expectLater(pending, throwsStateError);
      expect(alerts().single.state, isA<AlertActive>());
    });

    test('alertsForSymbolProvider filters by instrument', () async {
      await container.read(alertsViewModelProvider.future);
      await vm().create(_draft);
      await vm().create(const AlertDraft(symbol: 'XAU/USD', condition: AlertCondition.crossesAbove, value: 2100));
      expect(container.read(alertsForSymbolProvider('XAU/USD')).value, hasLength(1));
      expect(container.read(alertsForSymbolProvider('GBP/USD')).value, isEmpty);
    });
  });
}
