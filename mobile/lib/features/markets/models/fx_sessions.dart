import '../../../l10n/app_localizations.dart';

/// جلسات الفوركس الرئيسية بتوقيت UTC - نفس `web/src/domain/sessions.ts`
///
/// تقريب بالتوقيت الشتوي (فرق ±1 ساعة بالتوقيت الصيفي مش محسوب، متل الويب).
enum FxSession {
  sydney(openUtc: 22, closeUtc: 7),
  tokyo(openUtc: 0, closeUtc: 9),
  london(openUtc: 8, closeUtc: 17),
  newYork(openUtc: 13, closeUtc: 22);

  const FxSession({required this.openUtc, required this.closeUtc});

  final int openUtc;
  final int closeUtc;

  String label(AppLocalizations l10n) => switch (this) {
        FxSession.sydney => l10n.sessionSydney,
        FxSession.tokyo => l10n.sessionTokyo,
        FxSession.london => l10n.sessionLondon,
        FxSession.newYork => l10n.sessionNewYork,
      };

  bool _withinHours(int hour) =>
      openUtc < closeUtc ? hour >= openUtc && hour < closeUtc : hour >= openUtc || hour < closeUtc;
}

/// سوق الفوركس مسكّر من الجمعة 22:00 UTC لحد الأحد 22:00 UTC
bool isFxMarketOpen(DateTime time) {
  final utc = time.toUtc();
  final day = utc.weekday; // الاثنين = 1 ... الأحد = 7
  if (day == DateTime.saturday) return false;
  if (day == DateTime.friday && utc.hour >= 22) return false;
  if (day == DateTime.sunday && utc.hour < 22) return false;
  return true;
}

/// شو الجلسات المفتوحة هلق (كلها مسكّرة بالويكند) - بنفس ترتيب [FxSession]
Map<FxSession, bool> fxSessionStates(DateTime time) {
  final marketOpen = isFxMarketOpen(time);
  final hour = time.toUtc().hour;
  return {
    for (final s in FxSession.values) s: marketOpen && s._withinHours(hour),
  };
}

/// وصف قصير لحالة السوق: "London · New York overlap"، "Tokyo session"...
String fxSessionSummary(AppLocalizations l10n, DateTime time) {
  if (!isFxMarketOpen(time)) return l10n.sessionSummaryClosed;
  final open = [
    for (final e in fxSessionStates(time).entries)
      if (e.value) e.key.label(l10n),
  ];
  return switch (open) {
    [] => l10n.sessionSummaryBetween,
    [final only] => l10n.sessionSummaryOne(only),
    _ => l10n.sessionSummaryOverlap(open.join(' · ')),
  };
}
