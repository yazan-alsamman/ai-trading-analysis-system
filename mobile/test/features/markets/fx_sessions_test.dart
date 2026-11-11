// اختبارات جلسات الفوركس (نفس منطق web/src/domain/sessions.ts)

import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/features/markets/models/fx_sessions.dart';
import 'package:trading_app/l10n/app_localizations.dart';

void main() {
  final en = AppLocalizations(const Locale('en'));
  final ar = AppLocalizations(const Locale('ar'));

  // 2026-10-21 أربعاء
  DateTime wed(int hour) => DateTime.utc(2026, 10, 21, hour, 5);

  test('London + New York overlap at 14:05 UTC on a weekday', () {
    final states = fxSessionStates(wed(14));
    expect(states[FxSession.london], isTrue);
    expect(states[FxSession.newYork], isTrue);
    expect(states[FxSession.tokyo], isFalse);
    expect(states[FxSession.sydney], isFalse);
    expect(fxSessionSummary(en, wed(14)), 'London · New York overlap');
    expect(fxSessionSummary(ar, wed(14)), 'تداخل لندن · نيويورك');
  });

  test('a single session and the wrap past midnight (Sydney 22–7)', () {
    expect(fxSessionSummary(en, wed(10)), 'London session');
    expect(fxSessionSummary(ar, wed(10)), 'جلسة لندن');
    // 23:05: سيدني بس (طوكيو بتفتح 00:00)
    expect(fxSessionStates(wed(23))[FxSession.sydney], isTrue);
    expect(fxSessionSummary(en, wed(23)), 'Sydney session');
    // 03:05: سيدني + طوكيو
    expect(fxSessionSummary(en, wed(3)), 'Sydney · Tokyo overlap');
  });

  test('closed over the weekend: Friday 22:00 to Sunday 22:00 UTC', () {
    final fridayLate = DateTime.utc(2026, 10, 23, 22, 30);
    final saturday = DateTime.utc(2026, 10, 24, 12);
    final sundayEarly = DateTime.utc(2026, 10, 25, 21, 59);
    final sundayOpen = DateTime.utc(2026, 10, 25, 22, 0);

    for (final t in [fridayLate, saturday, sundayEarly]) {
      expect(isFxMarketOpen(t), isFalse, reason: '$t');
      expect(fxSessionStates(t).values, everyElement(isFalse));
      expect(fxSessionSummary(en, t), 'Market closed (weekend)');
    }
    expect(isFxMarketOpen(sundayOpen), isTrue);
    expect(fxSessionSummary(en, sundayOpen), 'Sydney session');
    expect(fxSessionSummary(ar, saturday), 'السوق مغلق (عطلة نهاية الأسبوع)');
  });

  test('uses UTC whatever the device time zone', () {
    final local = DateTime.utc(2026, 10, 21, 14, 5).toLocal();
    expect(fxSessionSummary(en, local), 'London · New York overlap');
  });
}
