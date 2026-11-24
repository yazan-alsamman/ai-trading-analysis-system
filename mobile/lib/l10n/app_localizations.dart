import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';

// ═══════════════════════════════════════════════════════════
// AppLocalizations - نظام الترجمة (عربي / إنجليزي)
// ═══════════════════════════════════════════════════════════
//
// ⚠️ ملاحظة مهمة: هاد الملف مكتوب يدويًا (مش مولّد تلقائيًا عبر
// `flutter gen-l10n` من ملفات .arb) عشان يشتغل فورًا بدون أي خطوة
// build إضافية (`flutter gen-l10n` أو `flutter pub get` لباقة
// جديدة). لو حبيت لاحقًا تتحول لنظام ARB الرسمي من Flutter، بس
// انقل المفاتيح تحت لملفين app_en.arb / app_ar.arb وفعّل `generate:
// true` بـ pubspec.yaml - الاستخدام بباقي الشاشات (`l10n.someKey`)
// رح يضل نفسه بالضبط.
//
// الاستخدام من أي شاشة:
//   final l10n = AppLocalizations.of(context)!;
//   Text(l10n.welcomeBack)
//
// إضافة مفتاح جديد: ضيفه بالـ Map تبع 'en' وبالـ Map تبع 'ar' تحت
// (بنفس الاسم بالمكانين)، وضيف getter إله بأسفل الملف.

class AppLocalizations {
  AppLocalizations(this.locale);

  final Locale locale;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  static const List<Locale> supportedLocales = [
    Locale('en'),
    Locale('ar'),
  ];

  /// هل اللغة الحالية عربي؟ (مفيد لأي منطق شرطي بره الـ Directionality
  /// التلقائي يلي بيضبطه Flutter لوحده حسب الـ locale)
  bool get isArabic => locale.languageCode == 'ar';

  // ── الترجمات ─────────────────────────────────────────────

  static const Map<String, Map<String, String>> _values = {
    'en': {
      // Common
      'cancel': 'Cancel',
      'trader': 'Trader',

      // Login
      'email': 'Email',
      'password': 'Password',

      // Registration
      'confirmPassword': 'Confirm Password',

      // OTP
      'verify': 'Verify',

      // Validators
      'emailRequired': 'Email is required',
      'enterValidEmail': 'Enter a valid email address',
      'passwordRequired': 'Password is required',
      'passwordMinChars': 'Minimum 8 characters',
      'passwordNeedsNumber': 'Add at least one number',
      'passwordRequirementsHint':
          '8 to 128 characters, with at least one letter and one number',
      'pleaseConfirmPassword': 'Please confirm your password',
      'passwordsDoNotMatch': 'Passwords do not match',
      'thisFieldRequired': 'This field is required',
      'fieldRequired': '{field} is required',

      // Market widgets
      'mediumImpact': 'MEDIUM IMPACT',

      // Profile
      'notificationPreferences': 'Notification preferences',
      'chooseAlerts': 'Choose which alerts you receive',
      'logOut': 'Log out',
      'confirmLogOut': 'Are you sure you want to log out?',
      'guestEmail': 'guest@example.com',
      'language': 'Language',
      'chooseAppLanguage': 'Choose your app language',
      'english': 'English',
      'arabic': 'العربية',

      // Security screen
      'passwordUpdatedSuccessfully': 'Password updated successfully',
      'couldNotUpdatePassword': 'Could not update password',
      'changePassword': 'Change Password',
      'currentPassword': 'Current Password',
      'newPassword': 'New Password',
      'confirmNewPassword': 'Confirm New Password',
      'updatePassword': 'Update Password',

      // Edit profile screen
      'profileUpdatedSuccessfully': 'Profile updated successfully',
      'couldNotSaveChanges': 'Could not save changes',
      'takeAPhoto': 'Take a photo',
      'chooseFromGallery': 'Choose from gallery',
      'removeCurrentPhoto': 'Remove current photo',
      'displayName': 'Display Name',
      'enterYourName': 'Enter your name',
      'enterYourEmail': 'Enter your email',
      'saveChanges': 'Save Changes',
      'name': 'Name',

      // About screen
      'version': 'Version',
      'legal': 'Legal',
      'riskDisclosure': 'Risk disclosure',

      // Help & support screen
      'frequentlyAskedQuestions': 'Frequently asked questions',

      // AI Chart Analyzer screen

      // AI Chat screen


      // AI Assistant screen


      'price': 'Price',
      'confirm': 'Confirm',

      'justNow': 'Just now',

      'commentAuthorYou': 'You',
      'minutesAgo': '{minutes}m ago',
      'hoursAgo': '{hours}h ago',
      'daysAgo': '{days}d ago',
      'commentText1': 'This was expected, market already priced it in.',
      'commentText2': 'Curious how this affects EUR/USD next week.',
      'commentText3': 'Gold barely reacted, honestly surprised.',
      'commentText4': 'Good breakdown, thanks for sharing!',
      'commentText5': "I'm staying cautious until the next session.",

      // News Repository (mock market news)
      'newsFedTitle': 'Federal Reserve Announces Interest Rate Decision',
      'newsFedDescription':
          'The Fed has decided to maintain current interest rates '
              'at 5.25-5.50% amid ongoing inflation concerns.',
      'newsFedContent':
          'The Federal Reserve has decided to maintain current interest '
              'rates at 5.25-5.50% amid ongoing inflation concerns, marking '
              'the sixth consecutive meeting where rates have been held '
              'steady.\n\n'
              "Fed Chairman Jerome Powell emphasized the central bank's "
              'commitment to achieving its 2% inflation target while '
              'acknowledging recent progress in cooling price pressures. '
              '"We remain vigilant and data-dependent in our approach," '
              'Powell stated during the press conference.\n\n'
              'Market analysts expect rates to remain elevated through the '
              'first half of next year, with potential cuts not anticipated '
              'until economic conditions show more substantial '
              'improvement. The decision has immediate implications for '
              'currency pairs, particularly USD-based crosses.\n\n'
              'Traders should monitor upcoming employment data and '
              'inflation reports closely, as these will be key factors in '
              "determining the Fed's next moves. The central bank "
              'continues to balance its dual mandate of maximum employment '
              'and price stability.',
      'newsEcbTitle': 'ECB Signals Cautious Approach to Future Rate Cuts',
      'newsEcbDescription':
          'European Central Bank officials hint at a slower pace '
              'of monetary easing as inflation remains above target.',
      'newsEcbContent':
          'European Central Bank policymakers have signaled a more '
              'cautious approach toward further interest rate cuts, '
              'pushing back against market expectations for aggressive '
              'monetary easing in the coming months.\n\n'
              'Several ECB officials pointed to persistent core inflation '
              'and resilient wage growth across the eurozone as reasons to '
              'proceed gradually rather than rushing into additional cuts. '
              '"We need clear and convincing evidence that inflation is '
              'sustainably heading toward our target before easing '
              'further," one Governing Council member noted.\n\n'
              'The euro strengthened modestly against the US dollar '
              'following the comments, as traders trimmed bets on a '
              'near-term rate cut. Analysts now see the next move as more '
              'likely in the following quarter rather than the current '
              'one.\n\n'
              'Market participants are turning their attention to upcoming '
              'eurozone inflation and employment data, which are expected '
              "to shape the ECB's next policy decision.",
      'newsGoldTitle': 'Gold Prices Steady Ahead of Jobs Report',
      'newsGoldDescription':
          'Gold trades in a tight range as investors await the '
              'upcoming non-farm payrolls report for further direction.',
      'newsGoldContent':
          'Gold prices held within a narrow range in early trading as '
              'investors positioned themselves ahead of the closely '
              'watched non-farm payrolls report, with few willing to take '
              'large directional bets before the data lands.\n\n'
              "The metal's muted reaction to recent macro headlines has "
              'surprised some traders, who note that positioning already '
              'reflects a large share of the expected policy path from '
              'major central banks.\n\n'
              'A stronger-than-expected jobs number could pressure gold '
              'lower by reinforcing the case for rates staying higher for '
              'longer, while a soft reading may reignite demand for the '
              'safe-haven metal.\n\n'
              'Volume across major gold futures contracts has remained '
              'relatively thin this week, which analysts warn could '
              'amplify price swings once the jobs data is released.',
      'newsUkTitle': 'UK Retail Sales Beat Expectations in Latest Data',
      'newsUkDescription':
          'Stronger-than-expected consumer spending data offers '
              'modest support to the British pound against major peers.',
      'newsUkContent':
          'UK retail sales data released this week came in above '
              'expectations, offering a rare bright spot for an economy '
              'that has struggled with sluggish consumer spending over '
              'the past year.\n\n'
              'The stronger figures were driven largely by increased '
              'spending on clothing and household goods, suggesting that '
              'easing inflation may be starting to support real incomes '
              'and consumer confidence.\n\n'
              'The British pound edged higher against major peers '
              'following the release, as traders adjusted expectations '
              "around the timing of the Bank of England's next policy "
              'move.\n\n'
              "Economists caution that a single month of strong data "
              "isn't enough to signal a durable turnaround, and are "
              'watching upcoming wage and inflation reports for '
              'confirmation that the improvement can be sustained.',

      // AI News Analyzer screen
      'sentimentNeutral': 'Neutral',

      // Discussion screen

      // News detail screen
      'commentsCount': 'Comments ({count})',

      // Help & support screen (contact tiles)

      // Notifications
      'notifications': 'Notifications',

      // Notification content (mock)
      'notifWelcomeTitle': 'Welcome to AI Trading Assistance',

      // Notification preferences
      'pushNotifications': 'Push Notifications',
      'other': 'Other',

      // Membership (redesign 2026-10)
      'memPricingTba': 'Pricing to be announced',
      'memNoPayment': 'No commercial terms have been set. No payment is taken.',
      'memCtaHint': 'Not available yet',
      'memEssentialName': 'Essential',
      'memEssentialTagline': 'Gold research, done properly.',
      'memEssentialAudience': 'Traders focused on gold who want structured analysis and disciplined position sizing.',
      'memEssentialH1': 'Gold workspace with the model’s levels',
      'memEssentialH2': 'Evidence, invalidation and missing data',
      'memEssentialH3': 'Capital & risk tools',
      'memEssentialH4': 'Model analytics for full transparency',
      'memEssentialCta': 'Choose Essential',
      'memProfessionalName': 'Professional',
      'memProfessionalTagline': 'Personalised research across gold and FX.',
      'memProfessionalAudience': 'Active traders who follow several instruments and want setups filtered by their own rules.',
      'memProfessionalH1': 'Gold and the seven FX majors',
      'memProfessionalH2': 'Personalised signals with every check shown',
      'memProfessionalH3': 'Multi-timeframe alignment',
      'memProfessionalH4': 'Alert delivery by email & Telegram',
      'memProfessionalCta': 'Choose Professional',
      'memEliteName': 'Elite',
      'memEliteTagline': 'The complete research desk.',
      'memEliteAudience': 'Traders who want every module, including the assistant to question the evidence.',
      'memEliteH1': 'Everything in Professional',
      'memEliteH2': 'AI assistant in every module',
      'memEliteH3': 'Research history (planned)',
      'memEliteH4': 'Every future research view',
      'memEliteCta': 'Choose Elite',
      'memFWorkspace': 'Market workspace',
      'memFInstruments': 'Instruments',
      'memFTimeframes': 'Chart timeframes',
      'memFAiAnalysis': 'AI analysis',
      'memFExplanations': 'Research explanations',
      'memFTfAlignment': 'Multi-timeframe alignment',
      'memFSignalFilters': 'Personalised signal filters',
      'memFWatchlist': 'Watchlist',
      'memFRiskTools': 'Capital & risk tools',
      'memFAnalytics': 'Model analytics',
      'memFAlerts': 'Price alerts',
      'memFAlertDelivery': 'Email & Telegram delivery',
      'memFAssistant': 'AI assistant',
      'memFResearchHistory': 'Research history',
      'memFSavedWorkspaces': 'Saved workspaces',
      'memScopeGold': 'Gold (XAU/USD)',
      'memScopeAllInstruments': 'Gold + 7 FX majors',
      'memScopeTimeframes': '15m · 1h · 4h',
      'memScopeOneWorkspace': 'One workspace',
      'memScopeMultipleWorkspaces': 'Multiple workspaces',
      'memIncluded': 'Included',
      'memNotIncluded': 'Not included',
      'memGroupResearch': 'Research',
      'memGroupPersonalisation': 'Personalisation',
      'memGroupRiskReview': 'Risk & review',
      'memGroupAssistantWorkflow': 'Assistant & workflow',
      'memStatusLegend': 'What each status means',
      'memStatusAvailable': 'Works now',
      'memStatusAvailableDesc': 'Fully functional in the app with your own inputs.',
      'memStatusDemo': 'Demo data',
      'memStatusDemoDesc': 'The interface works; it runs on simulated market data and model output.',
      'memStatusBackend': 'Needs backend',
      'memStatusBackendDesc': 'The interface exists; delivery or storage needs a backend service that is not connected.',
      'memStatusPlanned': 'Planned',
      'memStatusPlannedDesc': 'Not built yet. Shown so the package is complete.',
      'memCompareEyebrow': 'Compare plans',
      'memComparePlan': 'Plan to compare',
      'memFaqEyebrow': 'Membership FAQ',
      'memFaqCostQ': 'What does each plan cost?',
      'memFaqCostA': 'Pricing has not been set by the project owner, so every plan shows “Pricing to be announced”. No price in this app is an offer.',
      'memFaqSubscribeQ': 'Can I subscribe today?',
      'memFaqSubscribeA': 'Not yet: no billing service is connected. You can compare the plans and see what each one includes. Nothing is charged.',
      'memFaqDemoQ': 'What does “Demo data” mean in the comparison?',
      'memFaqDemoA': 'The feature works in the interface but runs on simulated market data and model output until the backend is connected.',
      'memFaqLimitQ': 'Will my plan limit what I can see?',
      'memFaqLimitA': 'Not today. Real access control will happen on the server once membership is connected; until then no module is restricted.',
      'memFaqRiskQ': 'Why are risk tools and analytics in every plan?',
      'memFaqRiskA': 'Because sizing risk correctly and seeing how the model has performed should never be a premium feature.',
      'memSheetTitle': 'Your selection',
      'memSheetSelectedPlan': 'Selected plan',
      'memActivationTitle': 'Paid activation is not available yet.',
      'memActivationBody': 'No billing service is connected, so nothing is charged and no subscription is created.',
      'memClose': 'Close',
      'memCurrentPlan': 'Current plan',

      // Markets (redesign 2026-10)
      'selected': 'Selected',
      'instrumentEURUSD': 'Euro / US Dollar',
      'instrumentGBPUSD': 'British Pound / US Dollar',
      'instrumentUSDJPY': 'US Dollar / Japanese Yen',
      'instrumentUSDCHF': 'US Dollar / Swiss Franc',
      'instrumentAUDUSD': 'Australian Dollar / US Dollar',
      'instrumentUSDCAD': 'US Dollar / Canadian Dollar',
      'instrumentNZDUSD': 'New Zealand Dollar / US Dollar',
      'instrumentXAUUSD': 'Gold / US Dollar',

      // Shell + Profile (redesign 2026-10)
      'backToHome': 'Back to Home',
      'navHome': 'Home',
      'navSignals': 'Signals',
      'navAssistant': 'Assistant',
      'navCommunity': 'Community',
      'navProfile': 'Profile',
      'preferences': 'Preferences',
      'roleTrader': 'Trader',
      'roleExpert': 'Expert',
      'roleAdmin': 'Admin',
      'toolExperts': 'Experts',
      'toolPlans': 'Plans',
      'toolPlansSubtitle': 'Compare membership plans',
      'appearanceSubtitle': 'Light, dark, or follow your device',
      'editProfileHint': 'Edit profile',
      'loggingOut': 'Logging out…',
      'offlineBannerTitle': 'You’re offline',
      'offlineBannerBody': 'Showing the last received data.',
      'signalsEmptyTitle': 'No signals match your strategy',
      'signalsEmptyBody': 'Try a lower minimum probability, or add instruments and timeframes in Strategy.',
      'developer': 'Developer',
      'simulateOffline': 'Simulate offline',
      'simulateOfflineSubtitle': 'Debug builds only',

      // FX sessions (redesign 2026-10)
      'sessionSydney': 'Sydney',
      'sessionTokyo': 'Tokyo',
      'sessionLondon': 'London',
      'sessionNewYork': 'New York',
      'sessionSummaryClosed': 'Market closed (weekend)',
      'sessionSummaryBetween': 'Between sessions',
      'sessionSummaryOne': '{name} session',
      'sessionSummaryOverlap': '{names} overlap',
      'directionLong': 'Long',
      'directionShort': 'Short',
      'directionNeutral': 'Neutral',
      // Home + Market (redesign 2026-10, stage A)
      'ohlcOpen': 'Open',
      'ohlcHigh': 'High',
      'ohlcLow': 'Low',
      'ohlcClose': 'Close',
      'watchlist': 'Watchlist',
      'noSetup': 'No setup',
      'modelReadLabel': 'Model read: {direction}, {probability}, {timeframe}',
      'noSetupLabel': 'Model read: no setup right now',
      'watchlistEmpty': 'No instruments yet',
      'watchlistEmptyBody': 'Pull down to refresh.',
      'watchlistError': 'Prices could not be loaded.',
      'openChartHint': 'Opens the chart',
      'notificationsUnread': 'Notifications, {count} unread',
      'feedConnecting': 'Connecting',
      'feedLive': 'Live',
      'feedDelayed': 'Delayed',
      'feedStale': 'Stale',
      'feedMarketClosed': 'Market closed',
      'feedOffline': 'Offline',
      'feedError': 'Feed error',
      // H5a: offline cache
      'lastUpdated': 'Last updated {time}',
      'oldData': 'Old data',
      'marketOfflineNoCache': 'Prices haven’t been saved on this phone yet. They load by themselves when you’re back online.',
      'chartOfflineNoCache': 'This chart hasn’t been saved for offline use yet. It loads by itself when you’re back online.',
      'marketRefreshOffline': 'You’re offline, so prices can’t refresh. They update by themselves when you’re back online.',
      'clearMarketCache': 'Clear saved market data',
      'clearMarketCacheSubtitle': 'Prices, charts, signals, news and notifications kept for offline use',
      'marketCacheCleared': 'Saved market data cleared.',
      'marketCacheClearFailed': 'Couldn’t clear saved market data. Try again.',
      // H5b: offline cache part 2 + low data mode
      'newsOfflineNoCache': 'News hasn’t been saved on this phone yet. It loads by itself when you’re back online.',
      'newsRefreshOffline': 'You’re offline, so news can’t refresh. It updates by itself when you’re back online.',
      'notificationsOfflineNoCache': 'Notifications haven’t been saved on this phone yet. They load by themselves when you’re back online.',
      'notificationsRefreshOffline': 'You’re offline, so notifications can’t refresh. They update by themselves when you’re back online.',
      'signalsRefreshOffline': 'You’re offline, so signals can’t refresh. They update by themselves when you’re back online.',
      'commentsOffline': 'Comments need a connection. They load by themselves when you’re back online.',
      'commentsOfflineAction': 'You’re offline, so your comment wasn’t sent. It’s still here: send it when you’re back online.',
      'alertsOfflineAction': 'You’re offline. Alerts are saved on the server, so this needs a connection. Nothing was changed.',
      'lowDataMode': 'Low data mode',
      'lowDataModeSubtitle': 'Uses less data: prices update every 5 seconds, charts load fewer candles without animation, images load smaller, and tabs you aren’t viewing don’t refresh by themselves.',
      'lowDataPillLabel': 'Low data mode is on. Prices update every 5 seconds and charts show fewer candles.',
      'lowDataSuggestTitle': 'Use less data?',
      'lowDataSuggestMobile': 'You’re on mobile data. Low data mode updates prices less often and loads smaller charts and images.',
      'lowDataSuggestSlow': 'Your connection looks slow. Low data mode updates prices less often and loads smaller charts and images.',
      'lowDataTurnOn': 'Turn on',
      'lowDataNotNow': 'Not now',
      'lowDataTurnedOn': 'Low data mode is on. You can turn it off in Settings.',
      'feedStatusLabel': 'Price feed: {status}',
      'change24h': '24h',
      'chartCandles': 'Candles',
      'chartLine': 'Line',
      'chartArea': 'Area',
      'chartType': 'Chart type',
      'timeframe': 'Timeframe',
      'indicators': 'Indicators',
      'indicatorsCount': 'Indicators, {count} on',
      'indSma': 'SMA 20',
      'indSmaHint': 'Simple moving average',
      'indEma': 'EMA 50',
      'indEmaHint': 'Exponential moving average',
      'indBollinger': 'Bollinger (20, 2)',
      'indBollingerHint': 'Volatility bands around the price',
      'indRsi': 'RSI 14',
      'indRsiHint': 'Momentum, in a panel under the chart',
      'indMacd': 'MACD (12, 26, 9)',
      'indMacdHint': 'Trend momentum, in a panel under the chart',
      'indicatorsNote': 'Calculated from the prices shown on the chart.',
      'done': 'Done',
      'chartEmpty': 'No price history for this timeframe yet.',
      'chartError': 'The chart could not be loaded.',
      'chartLabel': '{symbol} {timeframe} chart. Last price {price}, {change} over the visible candles. High {high}, low {low}.',
      'zoneEntry': 'Entry',
      'zoneTarget': 'Target',
      'zoneStop': 'Stop',
      'modelRead': 'Model read',
      'probabilityCaption': 'chance the target is reached before the stop',
      'riskRewardLabel': 'Reward : risk',
      'timeframesAgree': '{count} of {total} timeframes agree',
      'validUntil': 'Valid until {time}',
      'noSetupTitle': 'No setup right now',
      'noSetupBody': 'The model sees no clear opportunity on 15m, 1h or 4h. That is a valid answer.',
      'signalDisclaimer': 'A probability, not a promise. An entry zone may not be filled, and a stop does not cap losses.',
      'showReadOnChart': 'Show the {timeframe} read on the chart',
      'readNoSetup': '{timeframe}: no setup',
      'setAlert': 'Set alert',
      'priceAlert': 'Price alert',
      'alertTargetLabel': 'Target price',
      'alertNow': 'Now {price}',
      'alertRisesTo': 'Alert me when it rises to {price}',
      'alertFallsTo': 'Alert me when it falls to {price}',
      'alertNote': 'Note (optional)',
      'alertCreate': 'Create alert',
      'alertCreated': 'Alert set: {symbol} at {price}',
      'alertDelivery': 'Delivered as a notification.',
      'alertErrorEmpty': 'Enter a price',
      'alertErrorInvalid': 'Enter a valid number',
      'alertErrorPositive': 'The price must be above zero',
      'alertErrorCurrent': 'That is the current price',
      'alertCreateFailed': 'The alert could not be saved. Try again.',
      'yourAlerts': 'Your alerts',
      'alertActive': 'Active',
      'alertPaused': 'Paused',
      'alertTriggered': 'Triggered',
      'alertPause': 'Pause',
      'alertResume': 'Resume',
      'alertDelete': 'Delete',
      'alertDeleted': 'Alert deleted',
      'alertActionFailed': 'That did not work. Try again.',
      'undo': 'Undo',
      'alertRowRises': 'Rises to {price}',
      'alertRowFalls': 'Falls to {price}',
      'alertRowLabel': '{rule}, {state}. Swipe to delete.',
      // H4a: alert states + workspace undo/redo
      'alertExpired': 'Expired',
      'alertTriggeredAt': 'Triggered at {price}',
      'alertUntil': 'Until {time}',
      'alertWaitsForCross': 'Waits for a new cross',
      'alertSetAgain': 'Set again',
      'alertsActiveHeading': 'Active alerts',
      'alertsHistoryHeading': 'Alert history',
      'alertsNoActive': 'No active alerts.',
      'alertExpiryLabel': 'Expires',
      'alertExpiryNone': 'No expiry',
      'alertExpiryDay': '1 day',
      'alertExpiryWeek': '1 week',
      'alertExpiryMonth': '1 month',
      'alertExpiryHint': 'An expired alert stops and never fires.',
      'alertsOffline': 'You’re offline. Alerts are checked again when prices update.',
      'notifAlertTriggeredTitle': '{symbol} reached {level}',
      'notifAlertTriggeredBody': 'Your price alert fired at {price}. Tap to open the instrument.',
      'workspaceUndo': 'Undo',
      'workspaceRedo': 'Redo',
      'workspaceUndoLabel': 'Undo last workspace change',
      'workspaceRedoLabel': 'Redo last workspace change',
      'workspaceUndone': 'Change undone',
      'workspaceRedone': 'Change redone',
      // Design system (redesign 2026-10)
      'appName': 'AI Trading Assistance',
      'appTagline': 'Gold & FX research',
      'appearance': 'Appearance',
      'themeLight': 'Light',
      'themeDark': 'Dark',
      'themeSystem': 'System',
      'sourceLive': 'Live',
      'sourceHistorical': 'Historical',
      'sourceModel': 'Model output',
      'sourceUser': 'Your input',
      'sourceDemo': 'Simulated',
      'sourceUnavailable': 'Not connected',
      'directionUp': 'Up',
      'directionDown': 'Down',
      'directionFlat': 'Unchanged',
      'tryAgain': 'Try again',
      'somethingWentWrong': 'Something went wrong',
      'loading': 'Loading',
      'showPassword': 'Show password',
      'hidePassword': 'Hide password',
      // Profile + Settings (redesign 2026-10, stage B)
      'profilePlan': 'Plan',
      'passwordAndSecurity': 'Password & security',
      'passwordAndSecuritySubtitle': 'Change your password',
      'settings': 'Settings',
      'settingsSubtitle': 'Appearance, language, notifications, risk limits',
      'helpAndAbout': 'Help & about',
      'helpAndAboutSubtitle': 'Questions, legal and app version',
      'save': 'Save',
      'changePhoto': 'Change photo',
      'discardChangesTitle': 'Discard changes?',
      'discardChangesBody': 'Your edits to your profile will be lost.',
      'discard': 'Discard',
      'keepEditing': 'Keep editing',
      'changePasswordIntro': 'Enter your current password, then choose a new one.',
      'riskGroup': 'Capital & risk',
      'riskLimits': 'Capital & risk limits',
      'riskLimitsIntro': 'You enter these yourself. They size trades and check signals against your limits. The app never sees your broker account.',
      'riskLimitsSummary': '{capital} · {perTrade} per trade · {daily} a day',
      'riskLimitsSummaryNoCapital': 'Capital not set · {perTrade} per trade · {daily} a day',
      'riskCapitalLabel': 'Account capital',
      'riskCapitalHelper': 'Leave it empty if you prefer. Trade sizing will ask for it.',
      'riskPerTradeLabel': 'Maximum risk per trade',
      'riskDailyLabel': 'Daily loss limit',
      'riskErrCapital': 'Enter an amount above zero',
      'riskErrRange': 'Enter a value from {min} to {max}',
      'riskErrDailyBelow': 'The daily limit must be at least the risk per trade',
      'riskLimitsSaved': 'Risk limits saved',
      'notifChannels': 'Channels',
      'notifKinds': 'What to send',
      'channelPush': 'Push',
      'channelPushHint': 'On this phone',
      'channelInApp': 'In the app',
      'channelInAppHint': 'In your notification centre',
      'channelEmail': 'Email',
      'channelEmailHint': 'To your account email',
      'channelTelegram': 'Telegram',
      'channelTelegramHint': 'To your linked Telegram account',
      'kindPriceAlert': 'Price alerts',
      'kindPriceAlertHint': 'When a price reaches a level you set',
      'kindOpportunity': 'Opportunities',
      'kindOpportunityHint': 'When the model finds a setup that fits your strategy',
      'kindSystem': 'System',
      'kindSystemHint': 'Account and service notices',
      'notifMuted': 'With every channel off, you will not receive any notification.',
      'notifPrefsNote': 'Saved on this phone until your account is connected. Delivery itself is handled by the service.',
      'aboutShort': 'A research assistant for gold and FX: charts, a model’s probabilities and your own risk limits in one place.',
      'neverTradesTitle': 'It never trades.',
      'neverTradesBody': 'It does not connect to a broker and never places, changes or closes an order. Every decision stays with you.',
      'faqModelReadQ': 'What is a model read?',
      'faqModelReadA': 'The model’s estimate, for one instrument and timeframe, of the chance that the target is reached before the stop. It is a probability, not a promise, and it can be wrong.',
      'faqSimulatedQ': 'Why does some data say “Simulated”?',
      'faqSimulatedA': 'Until the app is connected to the live service, prices and model outputs are generated on your phone. They show how the app works, not what the market is doing.',
      'faqAccuracyQ': 'How accurate is the model?',
      'faqAccuracyA': 'Signals shows the share of past signals that reached the target before the stop, and how many signals that share is based on. Past accuracy is not a promise of future results.',
      'faqStrategyQ': 'What does “Strategy” change?',
      'faqStrategyA': 'Which signals you see. Your analysis method decides how signals are found; your instruments, timeframes, directions and minimums filter the list.',
      'thirdPartyNotices': 'Third-party notices',
      'thirdPartyNoticesSubtitle': 'Open-source licences, fonts included',
      'versionLine': 'Version {version} ({build})',
      'legalDataTitle': 'Data on this phone',
      'legalUpdated': 'Last updated 25 October 2026',
      'legalRiskIntro': 'Please read this before using any analysis in the app. It explains what the app does, what it does not do, and the limits of everything it shows.',
      'legalRisk1Title': '1. What the app is',
      'legalRisk1Body': 'AI Trading Assistance is a research and decision-support tool for gold (XAU/USD) and major FX pairs. It shows charts, a model’s assessment and position-sizing calculations based on figures you enter. It is not financial advice, it is not a broker, and it never places, changes or closes trades. Any trading decision, and its consequences, are yours.',
      'legalRisk2Title': '2. Trading risk',
      'legalRisk2Body': 'Trading gold and FX carries a high level of risk and may not suit everyone. Leveraged products can lose value quickly. Do not trade money you cannot afford to lose. A stop-loss is an instruction, not a promise: prices can gap past it. An entry zone is an area of interest, and an order there may not be filled.',
      'legalRisk3Title': '3. Model outputs are estimates',
      'legalRisk3Body': 'The probability is the model’s estimate that the target is reached before the stop. It can be wrong, and it is not a prediction that something will happen. The reasons shown explain the output; they do not prove the market will follow.',
      'legalRisk4Title': '4. Simulated data',
      'legalRisk4Body': 'Until the app is connected to the live service, market data, model outputs and accuracy figures are simulated on your phone and labelled “Simulated”. They are examples of the workflow, not market information. Past or simulated results are not a promise of future results.',
      'legalRisk5Title': '5. Risk calculations depend on your inputs',
      'legalRisk5Body': 'Position size, money at risk and limit checks are calculated from the capital, risk percentage, entry and stop you enter, and assume the stop fills at its price. The app never guesses broker details: it shows size in units of the base asset, not lots, and does not calculate margin.',
      'legalRisk6Title': '6. About this document',
      'legalRisk6Body': 'This disclosure is informational. It was written for a graduation project and has not been reviewed as a legal document; it is not a substitute for advice from a licensed professional.',
      'legalDataIntro': 'This page lists what the app keeps on your phone and why. It describes the app as built today.',
      'legalData1Title': 'No analytics or trackers',
      'legalData1Body': 'The app includes no analytics, advertising or tracking code. Its fonts are bundled with the app, not loaded from third parties.',
      'legalData2Title': 'What is stored, and why',
      'legalData2Body': 'Your appearance setting, capital and risk limits, strategy filter and notification preferences are kept in the app’s storage. Your signed-in session and your language are kept in the phone’s secure storage. Price alerts, news and notifications are kept in memory only.',
      'legalData3Title': 'How to remove it',
      'legalData3Body': 'Logging out removes your session. Uninstalling the app, or clearing its storage in your phone’s settings, removes everything listed here.',
      'communityNews': 'News',
      'expertsIntro': 'Experienced traders you can subscribe to and chat with. Subscriptions and replies are simulated: no payment is taken.',
      'expertsEmpty': 'No experts listed yet',
      'expertMarkets': 'Markets: {markets}',
      'expertSubscribe': 'Subscribe',
      'accuracyLine': 'Model accuracy {rate} · {count} past signals · last {days} days',
      'accuracyNoResults': 'No finished signals in the last {days} days yet',
      'accuracyCaption': 'Share of past signals that reached the target before the stop.',
      'accuracyError': 'Accuracy could not be loaded.',
      'strategyIntro': 'Choose how signals are found and which ones you see.',
      'strategyInstruments': 'Instruments',
      'strategyTimeframes': 'Timeframes',
      'strategyDirections': 'Directions',
      'strategyMinProbability': 'Minimum probability',
      'strategyMinRiskReward': 'Minimum reward : risk',
      'strategyAny': 'Any',
      'strategyRiskFit': 'Only signals that fit my risk limits',
      'strategyRiskFitHint': 'Uses your capital and limits from Settings.',
      'strategyRiskFitNoCapital': 'Set your capital in Settings → Capital & risk to check this.',
      'strategyPickOne': 'Pick at least one instrument, timeframe and direction.',
      'strategyReset': 'Reset to defaults',
      'strategySaved': 'Strategy saved',
      'strategySavedState': 'Saved',
      'sizeTrade': 'Size this trade',
      'sizeFromRead': 'From the {timeframe} model plan',
      'sizePosition': 'Position size',
      'sizeUnits': '{units} {currency}',
      'sizeOunces': '{units} oz',
      'sizeMoneyAtRisk': 'Money at risk',
      'sizeStopDistance': 'Stop distance',
      'sizePips': '{pips} pips',
      'sizeReward': 'If the target is reached',
      'sizeRiskLabel': 'Risk for this trade',
      'sizeTargetLabel': 'Target (optional)',
      'sizeCapitalHint': 'Set it once in Settings → Capital & risk to fill this in.',
      'sizeIncomplete': 'Enter capital, risk, entry and stop to see the size.',
      'sizeErrStopEqual': 'The stop must differ from the entry.',
      'sizeErrTarget': 'The target must be on the other side of the entry from the stop.',
      'sizeErrRisk': 'Risk cannot be more than 100% of capital.',
      'sizeNote': 'A calculation only. Size is in units of the base asset because lots depend on your broker. The app never places trades.',
      'limitWithin': 'Within your limit',
      'limitNear': 'Close to your limit',
      'limitBreach': 'Above your limit',
      'limitDetail': '{risk} of capital against your {limit} per-trade limit.',
      // Auth, Assistant, Notifications, News (redesign 2026-10, stage C)
      'welcomeBody': 'Charts, a model’s probabilities and your own risk limits for gold and FX, with every decision left to you.',
      'createAccountAction': 'Create account',
      'logIn': 'Log in',
      'haveAccount': 'Already have an account?',
      'noAccount': 'New here?',
      'registerTitle': 'Create your account',
      'fullName': 'Full name',
      'fullNameRequired': 'Enter your full name.',
      'fullNameTooLong': 'Keep the name under 60 characters.',
      'confirmPasswordLabel': 'Confirm password',
      'passwordCheckLength': '8+ characters',
      'passwordCheckLetter': 'A letter',
      'passwordCheckNumber': 'A number',
      'passwordMaxChars': 'Use at most 128 characters',
      'passwordNeedsLetter': 'Add at least one letter',
      'checkMet': 'met',
      'checkNotMet': 'not met',
      'registerAdviceAck': 'I understand this is not financial advice.',
      'registerAdviceRequired': 'Please confirm you understand the app does not give financial advice.',
      'registerFailed': 'We couldn’t create your account. Check your connection and try again.',
      'loginTitle': 'Welcome back',
      'loginFailed': 'We couldn’t log you in. Check your details and connection, then try again.',
      'otpTitle': 'Check your email',
      'otpBody': 'Enter the 5-digit code we sent to',
      'otpLabel': 'Verification code',
      'otpIncomplete': 'Enter all 5 digits.',
      'otpSimulated': 'Any 5 digits work until the account service is connected.',
      'otpVerify': 'Verify',
      'otpResendIn': 'Resend code in {time}',
      'otpResend': 'Resend code',
      'otpResent': 'A new code is on its way.',
      'otpDoneTitle': 'You’re all set.',
      'otpDoneBody': 'Your email is verified and your account is ready.',
      'otpContinue': 'Continue',
      'notifInbox': 'Inbox',
      'notifInboxCount': 'Inbox · {count}',
      'notifAlerts': 'Alerts',
      'notifAlertsCount': 'Alerts · {count}',
      'filterAll': 'All',
      'notifMarkAllRead': 'Mark all as read',
      'notifMarkRead': 'Mark as read',
      'notifMarkUnread': 'Mark as unread',
      'notifDelete': 'Delete',
      'notifDeleted': 'Notification deleted',
      'notifUnread': 'Unread',
      'notifActionFailed': 'That didn’t work. Try again.',
      'notifLoadError': 'Notifications could not be loaded.',
      'notifEmptyTitle': 'You’re all caught up',
      'notifEmptyBody': 'Price alerts, model opportunities and account notices will appear here.',
      'notifFilterEmpty': 'Nothing under {kind}',
      'notifOpportunityTitle': '{symbol} · {direction} on {timeframe}',
      'notifOpportunityBody': 'The model sees a {probability} chance the target is reached before the stop. A probability, not a promise.',
      'notifAlertAboveTitle': '{symbol} rose to your level',
      'notifAlertAboveBody': 'Price crossed above the level you set. This alert is now off.',
      'notifAlertBelowTitle': '{symbol} fell to your level',
      'notifAlertBelowBody': 'Price crossed below the level you set. This alert is now off.',
      'notifSimulatedTitle': 'Market data is simulated',
      'notifSimulatedBody': 'Until the app is connected to the live service, prices and model outputs are generated on your phone.',
      'notifWelcomeBody': 'Start with the watchlist on Home. The app never places trades; every decision stays with you.',
      'alertsEmptyTitle': 'No price alerts',
      'alertsEmptyBody': 'Open an instrument from Home and tap Set alert to hear when price reaches a level.',
      'alertsHint': 'Swipe a row to delete it. Tap it to open the instrument.',
      'moodTitle': 'Market mood · 24h',
      'moodPositive': 'Leaning positive',
      'moodNegative': 'Leaning negative',
      'moodMixed': 'Mixed',
      'moodNone': 'Not enough news yet',
      'moodCounts': '{positive} positive, {neutral} neutral, {negative} negative',
      'sentimentPositive': 'Positive',
      'sentimentNegative': 'Negative',
      'sentimentLabel': 'News tone: {label}',
      'sentimentNote': 'The tone tag is a model’s reading of the text, not a price forecast.',
      'newsEmpty': 'No news right now',
      'newsEmptyBody': 'Pull down to check again.',
      'newsLoadError': 'News could not be loaded.',
      'newsNotFound': 'This story is no longer available.',
      'comments': 'Comments',
      'commentsTitle': 'Comments · {count}',
      'commentsEmpty': 'No comments yet',
      'commentsEmptyBody': 'Be the first to share what you make of this.',
      'commentHint': 'Add a comment',
      'commentSend': 'Post comment',
      'commentDelete': 'Delete comment',
      'commentDeleted': 'Comment deleted',
      'commentActionFailed': 'That didn’t work. Try again.',
      'asstContext': 'Context',
      'asstContextLabel': 'Context: {value}',
      'asstContextHint': 'Changes the instrument',
      'asstContextTitle': 'What the assistant can see',
      'asstContextBody': 'Pick one instrument. The assistant uses its price, the model’s read on it and your risk limits, and nothing else.',
      'asstContextNone': 'No instrument',
      'asstContextNoneHint': 'General questions only',
      'asstEmptyTitle': 'Ask about {symbol}',
      'asstEmptyTitleGeneral': 'Ask about gold and FX',
      'asstEmptyBody': 'Answers use only the data in this app. The assistant never tells you to buy or sell.',
      'asstSuggestExplain': 'Explain the current analysis',
      'asstSuggestInvalidate': 'What would invalidate it?',
      'asstSuggestRisk': 'Size the risk for my capital',
      'asstHint': 'Ask about the chart, the model or your risk',
      'asstSend': 'Send',
      'asstStop': 'Stop',
      'asstAttach': 'Attach a chart image',
      'asstAttachTitle': 'Read a chart image',
      'asstAttachBody': 'PNG or JPG, up to 10 MB. The same image again does not use another analysis.',
      'asstImageType': 'Use a PNG or JPG image.',
      'asstImageSize': 'The image is over 10 MB.',
      'asstImageUnreadable': 'The image could not be opened.',
      'asstChartImage': 'Chart image you sent',
      'asstNewChat': 'New chat',
      'asstCleared': 'Conversation cleared',
      'asstReplying': 'Assistant is replying',
      'asstFailed': 'The assistant could not answer.',
      'asstOffline': 'You are offline. The assistant needs a connection.',
      'asstRuleBased': 'Rule-based demo, not a language model',
      'asstAnswerLabel': 'Assistant answer: {kind}',
      'asstKindExplain': 'Analysis summary',
      'asstKindInvalidate': 'What would invalidate it',
      'asstKindRisk': 'Risk sizing',
      'asstKindChart': 'Chart analysis',
      'asstKindUnknown': 'What I can answer',
      'asstNoContext': 'Choose an instrument in Context above and I can answer about its chart, the model’s read and your risk.',
      'asstUnknown': 'I can explain the model’s read, say what would invalidate it and size the risk with your limits. I can’t predict prices or tell you to buy or sell.',
      'asstExplain': '{symbol} on {timeframe}: the model leans {direction}, with a {probability} chance that the target is reached before the stop. {agree} of {analysed} timeframes agree.\n\nEntry around {entry}, stop at {stop}, target at {target} (reward-to-risk {rr}).',
      'asstExplainNone': 'The model has no current setup on {symbol}: nothing on 15m, 1h or 4h passes its threshold right now. No setup is an answer too.',
      'asstInvalidate': 'This read is invalidated if price trades through the stop zone at {stop}. It also expires at {time} UTC; after that it is out of date even if price never moved.\n\nA higher timeframe turning the other way would weaken it too.',
      'asstInvalidateNone': 'There is no active read on {symbol}, so there is nothing to invalidate yet.',
      'asstRisk': 'With {capital} capital and {risk} risk per trade, the model’s stop is {pips} pips from entry, which allows about {units} units. That puts {money} at risk if the stop fills at its price.\n\nA stop is an instruction, not a promise: price can gap past it.',
      'asstRiskNoCapital': 'Set your capital in Profile → Settings → Capital & risk and I can size this for you.\n\nThe rule: money at risk = capital × risk per trade, and size = money at risk ÷ stop distance.',
      'asstRiskNone': 'There is no active setup on {symbol}, so there is no stop to size against. Open the instrument and use Size this trade with your own entry and stop.',
      'chartActionTitle': 'Analyze a chart image',
      'chartActionBody': 'Get the trend, key levels and pattern, checked against your saved strategy.',
      'chartQuotaCount': '{used} of {limit} analyses today',
      'chartLimitReached': 'Daily limit reached. Resets at {time}.',
      'chartLimitChat': 'You can still ask questions in the chat.',
      'chartPreviewLabel': 'Chart image to analyze',
      'chartFileSize': '{type} · {size} MB',
      'chartRemove': 'Remove',
      'chartAnalyze': 'Analyze',
      'chartAnalyzing': 'Analyzing the chart image…',
      'chartFailed': 'The chart could not be analyzed.',
      'chartOffline': 'You are offline. Nothing was sent.',
      'chartOrAsk': 'Or ask a question',
      'chartTrend': 'Trend',
      'chartKeyLevels': 'Key levels',
      'chartPattern': 'Pattern',
      'chartHighProbability': 'High probability',
      'chartNoSetup': 'No setup on {timeframe}',
      'chartNoLevels': 'None without a setup',
      'chartPictureOnly': '{trend}, in the picture only',
      'chartTrendRising': 'Rising',
      'chartTrendFalling': 'Falling',
      'chartTrendSideways': 'Sideways',
      'chartPatternChannel': 'Channel',
      'chartPatternTriangle': 'Triangle',
      'chartPatternRange': 'Range',
      'chartPatternFlag': 'Flag',
      'chartPatternWedge': 'Wedge',
      'chartReadSignal': '{symbol} on {timeframe}, pattern in the picture: {pattern}. Your strategy ({method}) reads {direction} here, with a {probability} chance that the target is reached before the stop.',
      'chartReadHigh': 'That is a high probability, not a certainty: price can still reach the stop first.',
      'chartReadNoSetup': '{symbol} on {timeframe}, pattern in the picture: {pattern}. Your strategy ({method}) has no setup on this timeframe right now, so there are no levels to show. No setup is an answer too.',
      'chartReadNoInstrument': 'Pattern in the picture: {pattern}. Trend in the picture: {trend}. The symbol and timeframe could not be read, so this is not compared with your strategy. A screenshot that shows both works best.',
      'chartStored': 'Same image as before: saved result, not counted',
      'chartYourStrategy': 'your strategy',
      'authOffline': 'You are offline. Connect to the internet and try again.',
      'welcomeTitle': 'A clearer way to read the markets.',
      'loginSubtitle': 'Log in to continue your research.',
      'registerSubtitle': 'It takes a minute. You’ll confirm your email next.',
      'authDisclaimer': 'Analysis and decision support only. Not financial advice, not a broker.',
      'notAdviceNotice': 'Signals are for educational purposes and are not investment advice.',
      'otpVerifiedRow': 'Email verified',
      'communityPosts': 'Posts',
      'postsIntro': 'Ideas shared by the community. Not financial advice.',
      'postsEmptyTitle': 'No posts yet',
      'postsEmptyBody': 'Share what you’re watching on gold or FX.',
      'postsLoadError': 'Posts could not be loaded.',
      'newPost': 'New post',
      'newPostTitle': 'New post',
      'newPostAs': 'Posting as {name}',
      'newPostLabel': 'Your post',
      'newPostHint': 'What are you watching on gold or FX?',
      'newPostInstrument': 'Instrument (optional)',
      'newPostNote': 'Posts are public to everyone in Community. Share analysis, not instructions to trade.',
      'newPostNotAdvice': 'Shared opinions are not financial advice.',
      'postAction': 'Post',
      'postShared': 'Post shared',
      'postFailed': 'Your post wasn’t shared. Check your connection and try again.',
      'postOffline': 'You’re offline. Your post was not sent.',
      'postOptions': 'Post options',
      'postDelete': 'Delete post',
      'postDeleted': 'Post deleted',
      'postActionFailed': 'That didn’t work. Try again.',
      'postLikes': 'Like, {count}',
      'postOpenInstrument': 'Open {symbol}',
      'postReport': 'Report post',
      'postReported': 'Reported',
      'reportTitle': 'Report this post',
      'reportBody': 'Tell us what’s wrong. A moderator will review it, and the author is not told who reported.',
      'reportSpam': 'Spam or advertising',
      'reportMisleading': 'Misleading, or promises profits',
      'reportAbusive': 'Abusive or hateful',
      'reportOther': 'Something else',
      'reportSend': 'Send report',
      'reportSent': 'Thanks. A moderator will review this post.',
      'postsOfflineTitle': 'You’re offline',
      'postsOfflineBody': 'Posts will load when you’re back online.',
      'postsOfflineAction': 'You’re offline. Try again when you’re connected.',
      // Signals list + detail (stage D1)
      'signalsListTitle': 'Opportunities',
      'signalsError': 'Signals could not be loaded.',
      'signalsOfflineBody': 'Signals will load when you’re back online.',
      'signalsOfflineAction': 'You’re offline. Try again when connected.',
      'signalRowLabel': '{symbol}, {name}. {direction}, {probability} chance, {timeframe}, {age}',
      'signalRowHint': 'Opens the signal',
      'signalGenerated': 'Generated {age}',
      'signalPlanTitle': 'The plan',
      'signalPipsAway': '{pips} pips from entry',
      'signalWhyTitle': 'Why the model sees this',
      'reasonAgreement': '{count} of {total} timeframes point the same way.',
      'reasonChance': 'About {count} in 10 similar setups reached the target before the stop. This one can still fail.',
      'reasonRewardRisk': 'The target is {ratio}× as far away as the stop.',
      'reasonVolatilityHigh': 'This instrument is moving fast, so price can pass the levels quickly.',
      'reasonVolatilityLow': 'Price is moving calmly, so the plan may take longer to play out.',
      // Strategy (A3): method reasons, influence, request analysis
      'reasonMaCrossUp': 'The 10-period average is above the 30-period average on the {timeframe} chart, so the trend points up.',
      'reasonMaCrossDown': 'The 10-period average is below the 30-period average on the {timeframe} chart, so the trend points down.',
      'reasonRsiOversold': 'RSI (14) is {value} on the {timeframe} chart: price fell far and fast, so a turn up has a higher probability.',
      'reasonRsiOverbought': 'RSI (14) is {value} on the {timeframe} chart: price rose far and fast, so a turn down has a higher probability.',
      'reasonNoSetupMa': 'The 10- and 30-period averages on the {timeframe} chart show no confirmed cross yet.',
      'reasonNoSetupRsi': 'RSI (14) is {value} on the {timeframe} chart: no confirmed turn yet.',
      'reasonInfluenceHigh': 'High',
      'reasonInfluenceMedium': 'Medium',
      'reasonInfluenceLow': 'Low',
      'reasonInfluenceLabel': 'Influence: {level}',
      'strategyTitle': 'Strategy',
      'strategyUsed': 'Strategy used: {method}',
      'requestedByYou': 'Requested by you',
      'analysisNoClearSetup': 'No clear setup right now',
      // Strategy UI (A3b): method section, card line, Request analysis
      'strategyMethodTitle': 'Analysis method',
      'strategyMethodsError': 'The analysis methods couldn’t load.',
      'strategyCardSummary': '{method} · {instruments}',
      'strategyCardDefault': 'Default: {method} · {instruments}',
      'strategyAboveProbability': 'above {value}',
      'requestAnalysisTitle': 'Request analysis',
      'requestAnalysisIntro': 'Analyze one instrument now. Results show a high-probability setup or say there is none.',
      'requestInstrument': 'Instrument',
      'requestPickInstrument': 'Pick an instrument to analyze.',
      'requestTimeframe': 'Timeframe',
      'requestMethodSaved': '{method} · from your saved strategy',
      'requestMethodOverride': '{method} · this request only',
      'requestChangeMethod': 'Change for this request',
      'requestUseSaved': 'Use my saved method',
      'requestOverrideNote': 'This applies to this request only. Your saved strategy doesn’t change.',
      'requestAnalyze': 'Analyze',
      'requestStepPending': 'Sending your request…',
      'requestStepAnalyzing': 'Analyzing {symbol} · {timeframe} with {method}…',
      'requestFailed': 'The analysis didn’t finish. Nothing was saved.',
      'requestInvalid': 'This request can’t be analyzed. Check the instrument and timeframe.',
      'requestOffline': 'You’re offline, so nothing was sent. Connect, then try again.',
      'requestNoSetupBody': 'Try another timeframe or method, or check again later.',
      'reasonsShowMore': 'More reasons ({count})',
      'reasonsShowLess': 'Fewer reasons',
      'signalExpiredTitle': 'This signal has expired',
      'signalExpiredBody': 'It was valid until {time}. Its levels are out of date; open the market for the current read.',
      'signalNotFoundTitle': 'Signal not available',
      'signalNotFoundBody': 'It may have expired or been replaced by a newer read.',
      'signalDetailError': 'The signal could not be loaded.',
      'openMarket': 'Open market',
      'backToSignals': 'Back to Signals',
      'signalExpiredBadge': 'Expired',
      'signalSummaryLabel': '{direction}, {probability} chance the target is reached before the stop, {timeframe}',

      // Insights
      'insightsTitle': 'Insights',
      'insightsPeriodsLabel': 'Period',
      'insightsPeriod7': '7 days',
      'insightsPeriod30': '30 days',
      'insightsPeriod90': '90 days',
      'insightsHitRate': 'Hit rate · last {period}',
      'insightsHeadlineCount': '{hits} of {count} finished signals reached the target before the stop',
      'insightsHeadlineMisses': '{count} hit the stop first',
      'insightsHeadlineLabel': 'Hit rate over the last {period}: {rate}. {hits} of {count} finished signals reached the target before the stop.',
      'insightsOverTime': 'Over time',
      'insightsChartCaption': 'Each point covers the signals that finished in that stretch. Tap a point to see how many.',
      'insightsChartLabel': 'Hit rate over time, last {period}: lowest {low}, highest {high}.',
      'insightsChartPoint': '{rate} · {count} signals',
      'insightsChartNoPoints': 'Not enough finished signals to draw a trend.',
      'insightsByInstrument': 'By instrument',
      'insightsByTimeframe': 'By timeframe',
      'insightsSignalsCount': '{count} signals',
      'insightsSmallSample': 'Small sample',
      'insightsRowLabel': '{name}: {rate}, {hits} of {count} signals reached the target.',
      'insightsRowEmptyLabel': '{name}: no finished signals.',
      'insightsNoteTitle': 'How to read this',
      'insightsIntro': 'The accuracy of the AI model’s signals. It is the same whichever analysis method you choose.',
      'insightsNoteBody': 'This is the AI model’s own record, independent of the analysis method in your strategy. Only signals that reached the target or the stop are counted; open and expired signals are left out. Figures from fewer than {min} signals are marked “Small sample”. Past results are not a promise of future results.',
      'insightsSimulatedNote': 'These figures are simulated on your phone until the app is connected to the live service.',
      'insightsEmptyTitle': 'No finished signals in this period',
      'insightsEmptyBody': 'A signal counts here once it reaches the target or the stop.',
      'insightsShowLonger': 'Show 90 days',
      'insightsError': 'The track record could not be loaded.',
      'insightsOfflineBody': 'The track record will load when you’re back online.',
      'accuracyOpenHint': 'Opens Insights',

      // Backtest
      'strategyTestPast': 'Test on past data',
      'strategyTestUsesSaved': 'Uses your saved strategy. Save first to test your changes.',
      'strategyRemove': 'Remove strategy',
      'strategyRemoved': 'Strategy removed. Showing every instrument.',
      'strategyAllInstruments': 'all instruments',
      'backtestUsingSaved': 'Using your saved strategy',
      'backtestUsingDefault': 'Using the default strategy',
      'backtestTitle': 'Backtest',
      'backtestDisclaimerSimulated': 'Simulated · past results are not a promise of future results',
      'backtestDisclaimer': 'Past results are not a promise of future results',
      'backtestIntro': 'See how past signals that match your strategy turned out.',
      'backtestPeriod1y': '1 year',
      'backtestPeriod2y': '2 years',
      'backtestPeriod3y': '3 years',
      'backtestPeriod5y': '5 years',
      'backtestStrategyLine': 'Filters: {timeframes} · {directions} · probability {probability} · reward : risk {rr}',
      'backtestRun': 'Run test',
      'backtestPickInstrument': 'Pick at least one instrument.',
      'backtestIdle': 'Choose instruments and a period, then run the test.',
      'backtestRunning': 'Testing on past data…',
      'backtestResults': 'Results · last {period}',
      'backtestSignals': 'Signals',
      'backtestSignalsCaption': 'matched your strategy and reached the target or the stop',
      'backtestHitRate': 'Hit rate',
      'backtestHitRateCaption': '{hits} of {count} signals reached the target first',
      'backtestAvgRiskReward': 'Average reward : risk',
      'backtestAvgRiskRewardCaption': 'planned, across {count} signals',
      'backtestMaxDrawdown': 'Max drawdown',
      'backtestMaxDrawdownCaption': 'largest drop from a high, across {count} signals',
      'backtestFigureLabel': '{name}: {value}, {caption}.',
      'backtestR': '{value} R',
      'backtestEquityTitle': 'Result over time',
      'backtestEquityCaption': 'In R, from {count} signals. 1 R is the amount at risk on one signal (entry to stop): a target adds its reward : risk, a stop takes away 1 R. Costs are not included.',
      'backtestEquityLabel': 'Result over time in R from {count} signals: ends at {end}, lowest {low}, highest {high}.',
      'backtestEquityPoint': '{r} · {count} signals',
      'backtestEmptyTitle': 'No past signals matched your strategy',
      'backtestEmptyBody': 'Try more instruments, a longer period, or wider filters in Strategy.',
      'backtestTryYear': 'Try 1 year',
      'backtestError': 'The test could not be run.',
      'backtestOfflineBody': 'The test will run when you’re back online.',
      'backtestNote': 'Each past signal counts once it reached its target or its stop; open and expired signals are left out. Figures from fewer than {min} signals are marked “Small sample”. This describes the past, not what will happen next.',
      // Workspaces (D4)
      'workspaces': 'Workspaces',
      'workspaceAll': 'All instruments',
      'workspacesIntro': 'Pick what the Home watchlist shows.',
      'workspacesHint': 'Make your own lists, for example one for gold and one for the majors.',
      'workspaceChipLabel': 'Workspace: {name}, {count}',
      'workspaceChipHint': 'Opens workspaces',
      'workspaceNew': 'New workspace',
      'workspaceEditTitle': 'Edit workspace',
      'workspaceEditNamed': 'Edit {name}',
      'workspaceName': 'Name',
      'workspaceNameHint': 'For example: Gold and majors',
      'workspaceInstruments': 'Instruments',
      'workspaceNameRequired': 'Enter a name.',
      'workspaceNameTooLong': 'Use {max} characters or fewer.',
      'workspaceNameTaken': 'You already have a workspace with this name.',
      'workspacePickInstrument': 'Pick at least one instrument.',
      'workspaceLimit': 'You can have up to {max} workspaces. Delete one to add another.',
      'workspaceSavedState': 'Saved',
      'workspaceSaved': 'Workspace saved',
      'workspaceUpdated': 'Changes saved',
      'workspaceDeleted': '“{name}” deleted',
      'workspaceDeletedActive': '“{name}” deleted. Showing all instruments.',
      'workspaceDelete': 'Delete workspace',
      'workspaceSwitched': 'Home shows {name}',
      'workspaceBack': 'Back to workspaces',
      'workspaceSaveError': 'Could not save. Try again.',
      'workspaceEmptyTitle': 'No instruments to show',
      'workspaceEmptyBody': 'None of this workspace’s instruments are available right now.',
      'workspaceShowAll': 'Show all instruments',
      'workspaceCount1': '1 instrument',
      'workspaceCount2': '2 instruments',
      'workspaceCountFew': '{count} instruments',
      'workspaceCountMany': '{count} instruments',
      // Experts subscriptions + chat (T2)
      'expertPricePerMonth': '{price} / month',
      'expertPricePerYear': '{price} / year',
      'expertSubscribed': 'Subscribed',
      'expertSubscribedLabel': 'Subscribed to {name}',
      'expertPlanLine': 'Plan: {plan} · {price}',
      'expertChat': 'Chat',
      'expertChatWith': 'Chat with {name}',
      'expertSubscribeTo': 'Subscribe to {name}',
      'expertUnsubscribe': 'Unsubscribe',
      'expertUnsubscribeFrom': 'Unsubscribe from {name}',
      'expertUnsubscribeTitle': 'Unsubscribe from {name}?',
      'expertUnsubscribeBody': 'Your chat with {name} closes. Simulated: nothing is charged or refunded.',
      'expertUnsubscribed': 'Unsubscribed from {name}',
      'expertSubscribedSnack': 'Subscribed to {name}. You can chat now.',
      'expertOffline': 'You’re offline. Nothing changed.',
      'expertActionFailed': 'That didn’t work, so nothing changed. Try again.',
      'subscribeIncluded': 'What’s included',
      'subscribeIncludesChat': 'Private chat with {name}',
      'subscribeAvailability': 'Available: {hint}',
      'subscribeCancelAnytime': 'Unsubscribe at any time',
      'subscribeNote': 'This is advice from a person sharing their own opinion. It is not financial advice, and this app is not a broker.',
      'subscribeSimulated': 'Simulated: no payment is taken and no card details are asked for.',
      'subscribeConfirm': 'Confirm subscription',
      'subscribeOffline': 'You’re offline. Nothing was sent. Try again when you’re connected.',
      'subscribeFailed': 'The subscription didn’t go through and nothing was charged. Try again.',
      'chatDisclaimer': 'Experts share opinions, not financial advice. Not a broker.',
      'chatEmptyTitle': 'Start the conversation',
      'chatEmptyBody': 'Ask {name} how they read a pair or manage risk. Replies here are simulated.',
      'chatHint': 'Message {name}',
      'chatSend': 'Send',
      'chatSending': 'Sending',
      'chatSent': 'Sent',
      'chatNotSent': 'Not sent',
      'chatOffline': 'You’re offline. Messages can’t be sent, and your draft stays here.',
      'chatSimulatedReply': 'Simulated reply',
      'chatMessageMine': 'You, {time}: {body}. {status}',
      'chatMessageTheirs': '{name}, {time}: {body}. Simulated reply',
      'chatLatest': 'Jump to latest message',
      'chatLockedTitle': 'Subscribe to chat with {name}',
      'chatLockedBody': 'Chat is part of {name}’s plan. Subscriptions here are simulated: no payment is taken.',
      'chatLoadError': 'The conversation could not be loaded.',
      'chatOfflineBody': 'The conversation will load when you’re back online.',
      'chatNotFound': 'This expert is no longer listed',
      'chatCount': '{count} of {max} characters',
      // Model forecast on the Market chart (H1)
      'forecastToggle': 'Forecast',
      'forecastToggleLoading': 'Forecast, loading',
      'forecastLabel': 'Model forecast · {probability} · {direction}',
      'forecastLikelihoodHigh': 'high',
      'forecastLikelihoodModerate': 'moderate',
      'forecastLikelihoodLow': 'low',
      'forecastDetail': 'Expected level {price} by {time}, over the next {count} candles. The model gives a {likelihood} probability ({probability}).',
      'forecastChartLabel': 'Model forecast: {direction}, {likelihood} probability ({probability}). Expected level {price} by {time}.',
      'forecastReadout': 'Model forecast',
      'forecastExpected': 'Expected',
      'forecastRange': 'Range',
      'forecastOutdated': 'Outdated',
      'forecastOutdatedBody': 'This forecast has passed its validity, so it is no longer drawn.',
      'forecastRefresh': 'Refresh forecast',
      'forecastNone': 'No forecast right now',
      'forecastNoneBody': 'Your strategy sees no clear setup right now. That is a valid answer.',
      'forecastTimeframeBody': 'Not available for this timeframe. Forecasts cover {timeframes}.',
      'forecastListSeparator': ', ',
      'forecastFollows': 'Follows your strategy’s {basis} signal, with a lower probability on {timeframe}.',
      'forecastError': 'The forecast could not be loaded.',
      'forecastOffline': 'You’re offline, so the forecast is hidden. It comes back when you’re online.',
      // Telegram link + notification permission (H4b)
      'telegramNotConnected': 'Not connected',
      'telegramConnectFirst': 'Connect Telegram first to turn this on.',
      'telegramConnected': 'Connected',
      'telegramConnectedAs': 'Connected as {handle}',
      'telegramConnect': 'Connect Telegram',
      'telegramDisconnect': 'Disconnect',
      'telegramDisconnectLabel': 'Disconnect Telegram',
      'telegramDisconnectedSnack': 'Telegram disconnected. Telegram notifications are off.',
      'telegramConnectedSnack': 'Telegram connected. Telegram notifications are on.',
      'telegramRestoredSnack': 'Telegram connected again',
      'telegramOffline': 'You’re offline, so nothing was sent. Try again when you’re online.',
      'telegramStatusError': 'Couldn’t check your Telegram connection.',
      'telegramStatusLoading': 'Checking your Telegram connection',
      'telegramSheetIntro': 'Send this one-time code to the bot in Telegram. It links your Telegram to this account so notifications can reach you there.',
      'telegramStepBot': '1. In Telegram, open the bot',
      'telegramStepCode': '2. Send it this code',
      'telegramStepCheck': '3. Come back and check the connection',
      'telegramBotLabel': 'Telegram bot {name}',
      'telegramCodeLabel': 'One-time code {code}',
      'telegramValidFor': 'Valid for {time}',
      'telegramValidMinutes': 'Valid for about {minutes} min',
      'telegramValidUnderMinute': 'Valid for less than a minute',
      'telegramOneMinuteLeft': 'One minute left to use the code',
      'telegramCopy': 'Copy',
      'telegramCopied': 'Copied',
      'telegramCopyCode': 'Copy code',
      'telegramCopyBot': 'Copy bot name',
      'telegramCodeCopied': 'Code copied',
      'telegramBotCopied': 'Bot name copied',
      'telegramCheck': 'Check connection',
      'telegramCodeExpired': 'Code expired',
      'telegramCodeExpiredBody': 'This code can’t be used any more. Get a new one to connect.',
      'telegramNewCode': 'Get a new code',
      'telegramNotYet': 'Not connected yet. Send the code to the bot, then check again.',
      'telegramFailed': 'Something went wrong. Please try again.',
      'telegramGettingCode': 'Getting your code',
      'telegramSheetNote': 'You can disconnect any time in Notification preferences.',
      'pushNotAllowed': 'Not allowed on this phone',
      'pushSettingsHint': 'To use Push, allow notifications for this app in your phone’s Settings.',
      'pushWhyTitle': 'Why we ask',
      'pushWhyBody': 'Your phone will ask you to allow notifications. With them on, this phone can show:',
      'pushWhyAlerts': 'Your price alerts when a level is reached',
      'pushWhyOpportunities': 'New opportunities from your strategy',
      'pushWhyControl': 'You choose the kinds here and can turn Push off any time.',
      'pushWhyNote': 'Notifications can arrive late or not at all, so check the app for the latest.',
      'pushWhyContinue': 'Continue',
      'pushWhyNotNow': 'Not now',
      'pushTurnedOn': 'Push notifications on',
    },
    'ar': {
      // Common
      'cancel': 'إلغاء',
      'trader': 'متداول',

      // Login
      'email': 'البريد الإلكتروني',
      'password': 'كلمة المرور',

      // Registration
      'confirmPassword': 'تأكيد كلمة المرور',

      // OTP
      'verify': 'تحقق',

      // Validators
      'emailRequired': 'البريد الإلكتروني مطلوب',
      'enterValidEmail': 'أدخل بريدًا إلكترونيًا صحيحًا',
      'passwordRequired': 'كلمة المرور مطلوبة',
      'passwordMinChars': '8 أحرف على الأقل',
      'passwordNeedsNumber': 'أضف رقمًا واحدًا على الأقل',
      'passwordRequirementsHint':
          'من 8 إلى 128 حرفًا، مع حرف واحد ورقم واحد على الأقل',
      'pleaseConfirmPassword': 'الرجاء تأكيد كلمة المرور',
      'passwordsDoNotMatch': 'كلمتا المرور غير متطابقتين',
      'thisFieldRequired': 'هذا الحقل مطلوب',
      'fieldRequired': '{field} مطلوب',

      // Market widgets
      'mediumImpact': 'تأثير متوسط',

      // Profile
      'notificationPreferences': 'تفضيلات الإشعارات',
      'chooseAlerts': 'اختر التنبيهات التي تريد استلامها',
      'logOut': 'تسجيل الخروج',
      'confirmLogOut': 'هل أنت متأكد أنك تريد تسجيل الخروج؟',
      'guestEmail': 'guest@example.com',
      'language': 'اللغة',
      'chooseAppLanguage': 'اختر لغة التطبيق',
      'english': 'English',
      'arabic': 'العربية',

      // Security screen
      'passwordUpdatedSuccessfully': 'تم تحديث كلمة المرور بنجاح',
      'couldNotUpdatePassword': 'تعذّر تحديث كلمة المرور',
      'changePassword': 'تغيير كلمة المرور',
      'currentPassword': 'كلمة المرور الحالية',
      'newPassword': 'كلمة المرور الجديدة',
      'confirmNewPassword': 'تأكيد كلمة المرور الجديدة',
      'updatePassword': 'تحديث كلمة المرور',

      // Edit profile screen
      'profileUpdatedSuccessfully': 'تم تحديث الملف الشخصي بنجاح',
      'couldNotSaveChanges': 'تعذّر حفظ التغييرات',
      'takeAPhoto': 'التقاط صورة',
      'chooseFromGallery': 'اختيار من المعرض',
      'removeCurrentPhoto': 'إزالة الصورة الحالية',
      'displayName': 'الاسم المعروض',
      'enterYourName': 'أدخل اسمك',
      'enterYourEmail': 'أدخل بريدك الإلكتروني',
      'saveChanges': 'حفظ التغييرات',
      'name': 'الاسم',

      // About screen
      'version': 'الإصدار',
      'legal': 'قانوني',
      'riskDisclosure': 'الإفصاح عن المخاطر',

      // Help & support screen
      'frequentlyAskedQuestions': 'الأسئلة الشائعة',

      // AI Chart Analyzer screen

      // AI Chat screen


      // AI Assistant screen


      'price': 'السعر',
      'confirm': 'تأكيد',

      'justNow': 'الآن',

      'commentAuthorYou': 'أنت',
      'minutesAgo': 'قبل {minutes} د',
      'hoursAgo': 'قبل {hours} س',
      'daysAgo': 'قبل {days} ي',
      'commentText1': 'هذا كان متوقعًا، السوق سعّرها مسبقًا.',
      'commentText2': 'أتساءل كيف سيؤثر هذا على EUR/USD الأسبوع القادم.',
      'commentText3': 'الذهب بالكاد تفاعل، صراحة متفاجئ.',
      'commentText4': 'تحليل جيد، شكرًا للمشاركة!',
      'commentText5': 'سأبقى حذرًا حتى الجلسة القادمة.',

      // News Repository (mock market news)
      'newsFedTitle': 'الاحتياطي الفيدرالي يعلن قرار سعر الفائدة',
      'newsFedDescription':
          'قرر الفيدرالي الإبقاء على أسعار الفائدة الحالية عند '
              '5.25-5.50% وسط مخاوف مستمرة من التضخم.',
      'newsFedContent':
          'قرر الاحتياطي الفيدرالي الإبقاء على أسعار الفائدة الحالية '
              'عند 5.25-5.50% وسط مخاوف مستمرة من التضخم، في سادس '
              'اجتماع متتالٍ يتم فيه تثبيت الفائدة.\n\n'
              'شدّد رئيس الفيدرالي جيروم باول على التزام البنك المركزي '
              'بتحقيق هدف التضخم عند 2% مع الإقرار بالتقدم الأخير في '
              'تهدئة الضغوط السعرية. وقال باول خلال المؤتمر الصحفي: '
              '"نبقى يقظين ومعتمدين على البيانات في نهجنا."\n\n'
              'يتوقع المحللون أن تبقى الفائدة مرتفعة حتى النصف الأول '
              'من العام المقبل، مع عدم توقع خفضات محتملة إلا عندما تُظهر '
              'الظروف الاقتصادية تحسنًا أكبر. للقرار تداعيات مباشرة '
              'على أزواج العملات، خاصة تلك المرتبطة بالدولار.\n\n'
              'ينبغي على المتداولين متابعة بيانات التوظيف وتقارير '
              'التضخم القادمة عن كثب، لأنها ستكون عوامل رئيسية في '
              'تحديد الخطوات القادمة للفيدرالي، الذي يواصل الموازنة '
              'بين هدفيه المزدوجين: أقصى توظيف واستقرار الأسعار.',
      'newsEcbTitle': 'البنك المركزي الأوروبي يشير لنهج حذر تجاه خفض الفائدة',
      'newsEcbDescription':
          'مسؤولو البنك المركزي الأوروبي يلمّحون لوتيرة أبطأ من '
              'التيسير النقدي مع بقاء التضخم فوق المستهدف.',
      'newsEcbContent':
          'أشار صناع السياسة في البنك المركزي الأوروبي إلى نهج أكثر '
              'حذرًا تجاه خفض أسعار الفائدة، متراجعين عن توقعات '
              'السوق لتيسير نقدي عدواني في الأشهر القادمة.\n\n'
              'أشار عدة مسؤولين في البنك المركزي إلى استمرار التضخم '
              'الأساسي ونمو الأجور القوي عبر منطقة اليورو كأسباب '
              'للتحرك تدريجيًا بدلًا من التسرع بخفضات إضافية. وقال '
              'أحد أعضاء مجلس الإدارة: "نحتاج دليلًا واضحًا ومقنعًا '
              'على أن التضخم يتجه بشكل مستدام نحو هدفنا قبل مزيد من '
              'التيسير."\n\n'
              'تعزز اليورو بشكل معتدل مقابل الدولار الأمريكي عقب '
              'التصريحات، مع تقليص المتداولين لرهاناتهم على خفض '
              'قريب للفائدة. يرى المحللون الآن أن الخطوة التالية '
              'أرجح أن تكون بالربع القادم بدلًا من الحالي.\n\n'
              'يتجه المشاركون بالسوق الآن لبيانات التضخم والتوظيف '
              'القادمة بمنطقة اليورو، والتي يُتوقع أن تحدد ملامح '
              'قرار السياسة القادم للبنك المركزي الأوروبي.',
      'newsGoldTitle': 'أسعار الذهب مستقرة قبل تقرير الوظائف',
      'newsGoldDescription':
          'الذهب يتداول ضمن نطاق ضيق مع ترقب المستثمرين لتقرير '
              'الوظائف غير الزراعية القادم لمزيد من الاتجاه.',
      'newsGoldContent':
          'حافظت أسعار الذهب على نطاق ضيق في التداولات المبكرة مع '
              'تموضع المستثمرين قبل تقرير الوظائف غير الزراعية '
              'المرتقب بشدة، حيث قلة راغبون بأخذ مراهنات اتجاهية '
              'كبيرة قبل صدور البيانات.\n\n'
              'فاجأ رد الفعل الهادئ للمعدن تجاه العناوين الاقتصادية '
              'الأخيرة بعض المتداولين، الذين يشيرون إلى أن التموضع '
              'الحالي يعكس أصلًا حصة كبيرة من مسار السياسة المتوقع '
              'من البنوك المركزية الكبرى.\n\n'
              'قد يضغط رقم وظائف أقوى من المتوقع على الذهب هبوطًا '
              'من خلال تعزيز فرضية بقاء الفائدة مرتفعة لفترة أطول، '
              'بينما قد تُعيد قراءة ضعيفة إشعال الطلب على المعدن '
              'كملاذ آمن.\n\n'
              'ظل حجم التداول عبر عقود الذهب الآجلة الرئيسية منخفضًا '
              'نسبيًا هذا الأسبوع، ما يحذر المحللون من أنه قد يضخم '
              'تقلبات الأسعار بمجرد صدور بيانات الوظائف.',
      'newsUkTitle': 'مبيعات التجزئة البريطانية تتجاوز التوقعات بأحدث البيانات',
      'newsUkDescription':
          'بيانات إنفاق استهلاكي أقوى من المتوقع تقدم دعمًا معتدلًا '
              'للجنيه الإسترليني مقابل العملات الرئيسية.',
      'newsUkContent':
          'جاءت بيانات مبيعات التجزئة البريطانية الصادرة هذا الأسبوع '
              'أعلى من التوقعات، مقدمةً نقطة مضيئة نادرة لاقتصاد عانى '
              'من إنفاق استهلاكي بطيء خلال العام الماضي.\n\n'
              'جاءت الأرقام الأقوى مدفوعة بشكل كبير بزيادة الإنفاق '
              'على الملابس والسلع المنزلية، ما يشير إلى أن تراجع '
              'التضخم قد يبدأ بدعم الدخل الحقيقي وثقة المستهلك.\n\n'
              'ارتفع الجنيه الإسترليني مقابل العملات الرئيسية عقب '
              'صدور البيانات، مع تعديل المتداولين لتوقعاتهم حول '
              'توقيت الخطوة السياسية القادمة لبنك إنجلترا.\n\n'
              'يحذر الاقتصاديون من أن شهرًا واحدًا من البيانات '
              'القوية لا يكفي للإشارة إلى تعافٍ دائم، ويترقبون '
              'تقارير الأجور والتضخم القادمة لتأكيد إمكانية استمرار '
              'التحسن.',

      // AI News Analyzer screen
      'sentimentNeutral': 'محايد',

      // Discussion screen

      // News detail screen
      'commentsCount': 'التعليقات ({count})',

      // Help & support screen (contact tiles)

      // Notifications
      'notifications': 'الإشعارات',

      // Notification content (mock)
      'notifWelcomeTitle': 'أهلًا بك في AI Trading Assistance',

      // Notification preferences
      'pushNotifications': 'الإشعارات الفورية',
      'other': 'أخرى',

      // Membership (redesign 2026-10)
      'memPricingTba': 'سيُعلَن عن الأسعار لاحقًا',
      'memNoPayment': 'لم تُحدَّد أي شروط تجارية. لا يُؤخذ أي مبلغ.',
      'memCtaHint': 'غير متاح بعد',
      'memEssentialName': 'Essential',
      'memEssentialTagline': 'أبحاث الذهب، كما يجب.',
      'memEssentialAudience': 'للمتداولين المركّزين على الذهب الذين يريدون تحليلًا منظمًا وتحديدًا منضبطًا لحجم الصفقة.',
      'memEssentialH1': 'مساحة عمل للذهب مع مستويات النموذج',
      'memEssentialH2': 'الأدلة وشروط الإبطال والبيانات الناقصة',
      'memEssentialH3': 'أدوات رأس المال والمخاطر',
      'memEssentialH4': 'تحليلات النموذج لشفافية كاملة',
      'memEssentialCta': 'اختر Essential',
      'memProfessionalName': 'Professional',
      'memProfessionalTagline': 'أبحاث مخصّصة للذهب والعملات.',
      'memProfessionalAudience': 'للمتداولين النشطين الذين يتابعون عدة أدوات ويريدون فرصًا مفلترة حسب قواعدهم.',
      'memProfessionalH1': 'الذهب وأزواج العملات الرئيسية السبعة',
      'memProfessionalH2': 'إشارات مخصّصة مع عرض كل فحص',
      'memProfessionalH3': 'توافق الأطر الزمنية',
      'memProfessionalH4': 'إرسال التنبيهات عبر البريد وتلغرام',
      'memProfessionalCta': 'اختر Professional',
      'memEliteName': 'Elite',
      'memEliteTagline': 'مكتب الأبحاث الكامل.',
      'memEliteAudience': 'للمتداولين الذين يريدون كل الوحدات، بما فيها المساعد لمناقشة الأدلة.',
      'memEliteH1': 'كل ما في Professional',
      'memEliteH2': 'مساعد الذكاء الاصطناعي في كل وحدة',
      'memEliteH3': 'سجل الأبحاث (مخطط له)',
      'memEliteH4': 'كل واجهات البحث المستقبلية',
      'memEliteCta': 'اختر Elite',
      'memFWorkspace': 'مساحة عمل السوق',
      'memFInstruments': 'الأدوات',
      'memFTimeframes': 'الأطر الزمنية للرسم',
      'memFAiAnalysis': 'تحليل الذكاء الاصطناعي',
      'memFExplanations': 'شروحات البحث',
      'memFTfAlignment': 'توافق الأطر الزمنية',
      'memFSignalFilters': 'فلاتر إشارات مخصّصة',
      'memFWatchlist': 'قائمة المتابعة',
      'memFRiskTools': 'أدوات رأس المال والمخاطر',
      'memFAnalytics': 'تحليلات النموذج',
      'memFAlerts': 'تنبيهات السعر',
      'memFAlertDelivery': 'الإرسال عبر البريد وتلغرام',
      'memFAssistant': 'مساعد الذكاء الاصطناعي',
      'memFResearchHistory': 'سجل الأبحاث',
      'memFSavedWorkspaces': 'مساحات العمل المحفوظة',
      'memScopeGold': 'الذهب (XAU/USD)',
      'memScopeAllInstruments': 'الذهب + 7 أزواج رئيسية',
      'memScopeTimeframes': '15m · 1h · 4h',
      'memScopeOneWorkspace': 'مساحة عمل واحدة',
      'memScopeMultipleWorkspaces': 'مساحات عمل متعددة',
      'memIncluded': 'مشمولة',
      'memNotIncluded': 'غير مشمولة',
      'memGroupResearch': 'البحث',
      'memGroupPersonalisation': 'التخصيص',
      'memGroupRiskReview': 'المخاطر والمراجعة',
      'memGroupAssistantWorkflow': 'المساعد وسير العمل',
      'memStatusLegend': 'معنى كل حالة',
      'memStatusAvailable': 'يعمل الآن',
      'memStatusAvailableDesc': 'يعمل بالكامل في التطبيق بمدخلاتك.',
      'memStatusDemo': 'بيانات تجريبية',
      'memStatusDemoDesc': 'الواجهة تعمل؛ وتعتمد على بيانات سوق ومخرجات نموذج محاكاة.',
      'memStatusBackend': 'يحتاج الخادم',
      'memStatusBackendDesc': 'الواجهة موجودة؛ الإرسال أو التخزين يحتاج خدمة خادم غير متصلة.',
      'memStatusPlanned': 'مخطط له',
      'memStatusPlannedDesc': 'لم تُبنَ بعد. تظهر لتكتمل الخطة.',
      'memCompareEyebrow': 'قارن الخطط',
      'memComparePlan': 'الخطة للمقارنة',
      'memFaqEyebrow': 'أسئلة العضوية',
      'memFaqCostQ': 'كم تكلّف كل خطة؟',
      'memFaqCostA': 'لم يحدد مالك المشروع الأسعار بعد، لذلك تظهر كل خطة بعبارة «سيُعلَن عن الأسعار لاحقًا». لا يُعد أي سعر في هذا التطبيق عرضًا.',
      'memFaqSubscribeQ': 'هل يمكنني الاشتراك اليوم؟',
      'memFaqSubscribeA': 'ليس بعد: لا توجد خدمة دفع متصلة. يمكنك مقارنة الخطط ومعرفة ما تتضمنه كل منها. لا يُحتسب أي مبلغ.',
      'memFaqDemoQ': 'ماذا تعني «بيانات تجريبية» في المقارنة؟',
      'memFaqDemoA': 'الميزة تعمل في الواجهة لكنها تعتمد على بيانات سوق ومخرجات نموذج محاكاة حتى يُربط الخادم.',
      'memFaqLimitQ': 'هل ستحدّ خطتي مما أراه؟',
      'memFaqLimitA': 'ليس اليوم. التحكم الفعلي بالوصول سيتم على الخادم عند ربط العضوية؛ وحتى ذلك الحين لا توجد أي وحدة مقيّدة.',
      'memFaqRiskQ': 'لماذا أدوات المخاطر والتحليلات في كل خطة؟',
      'memFaqRiskA': 'لأن تقدير المخاطر بشكل صحيح ومعرفة أداء النموذج يجب ألا تكون ميزة مدفوعة أبدًا.',
      'memSheetTitle': 'اختيارك',
      'memSheetSelectedPlan': 'الخطة المختارة',
      'memActivationTitle': 'التفعيل المدفوع غير متاح بعد.',
      'memActivationBody': 'لا توجد خدمة دفع متصلة، لذلك لا يُحتسب أي مبلغ ولا يُنشأ أي اشتراك.',
      'memClose': 'إغلاق',
      'memCurrentPlan': 'الخطة الحالية',

      // Markets (redesign 2026-10)
      'selected': 'محدد',
      'instrumentEURUSD': 'اليورو / الدولار الأمريكي',
      'instrumentGBPUSD': 'الجنيه الإسترليني / الدولار الأمريكي',
      'instrumentUSDJPY': 'الدولار الأمريكي / الين الياباني',
      'instrumentUSDCHF': 'الدولار الأمريكي / الفرنك السويسري',
      'instrumentAUDUSD': 'الدولار الأسترالي / الدولار الأمريكي',
      'instrumentUSDCAD': 'الدولار الأمريكي / الدولار الكندي',
      'instrumentNZDUSD': 'الدولار النيوزيلندي / الدولار الأمريكي',
      'instrumentXAUUSD': 'الذهب / الدولار الأمريكي',

      // Shell + Profile (redesign 2026-10)
      'backToHome': 'رجوع إلى الرئيسية',
      'navHome': 'الرئيسية',
      'navSignals': 'الإشارات',
      'navAssistant': 'المساعد',
      'navCommunity': 'المجتمع',
      'navProfile': 'حسابي',
      'preferences': 'التفضيلات',
      'roleTrader': 'متداول',
      'roleExpert': 'خبير',
      'roleAdmin': 'مدير',
      'toolExperts': 'الخبراء',
      'toolPlans': 'الخطط',
      'toolPlansSubtitle': 'قارن خطط الاشتراك',
      'appearanceSubtitle': 'فاتح أو داكن أو حسب جهازك',
      'editProfileHint': 'تعديل الملف الشخصي',
      'loggingOut': 'جارٍ تسجيل الخروج…',
      'offlineBannerTitle': 'أنت غير متصل',
      'offlineBannerBody': 'نعرض آخر بيانات وصلت.',
      'signalsEmptyTitle': 'لا توجد إشارات تطابق استراتيجيتك',
      'signalsEmptyBody': 'جرّب احتمالًا أدنى، أو أضف أدوات وأطرًا زمنية من الاستراتيجية.',
      'developer': 'المطوّر',
      'simulateOffline': 'محاكاة عدم الاتصال',
      'simulateOfflineSubtitle': 'في نسخ التطوير فقط',

      // FX sessions (redesign 2026-10)
      'sessionSydney': 'سيدني',
      'sessionTokyo': 'طوكيو',
      'sessionLondon': 'لندن',
      'sessionNewYork': 'نيويورك',
      'sessionSummaryClosed': 'السوق مغلق (عطلة نهاية الأسبوع)',
      'sessionSummaryBetween': 'بين الجلسات',
      'sessionSummaryOne': 'جلسة {name}',
      'sessionSummaryOverlap': 'تداخل {names}',
      'directionLong': 'صعود',
      'directionShort': 'هبوط',
      'directionNeutral': 'محايد',
      // Home + Market (redesign 2026-10, stage A)
      'ohlcOpen': 'افتتاح',
      'ohlcHigh': 'أعلى',
      'ohlcLow': 'أدنى',
      'ohlcClose': 'إغلاق',
      'watchlist': 'قائمة المتابعة',
      'noSetup': 'لا توجد فرصة',
      'modelReadLabel': 'قراءة النموذج: {direction}، {probability}، {timeframe}',
      'noSetupLabel': 'قراءة النموذج: لا توجد فرصة الآن',
      'watchlistEmpty': 'لا توجد أدوات بعد',
      'watchlistEmptyBody': 'اسحب للأسفل للتحديث.',
      'watchlistError': 'تعذّر تحميل الأسعار.',
      'openChartHint': 'يفتح الرسم البياني',
      'notificationsUnread': 'الإشعارات، {count} غير مقروءة',
      'feedConnecting': 'جارٍ الاتصال',
      'feedLive': 'مباشر',
      'feedDelayed': 'متأخر',
      'feedStale': 'قديم',
      'feedMarketClosed': 'السوق مغلق',
      'feedOffline': 'غير متصل',
      'feedError': 'خطأ في التدفق',
      // H5a: offline cache
      'lastUpdated': 'آخر تحديث {time}',
      'oldData': 'بيانات قديمة',
      'marketOfflineNoCache': 'لم تُحفظ الأسعار على هذا الهاتف بعد. ستظهر تلقائيًا عندما تعود متصلًا.',
      'chartOfflineNoCache': 'لم يُحفظ هذا الرسم للاستخدام دون اتصال بعد. سيظهر تلقائيًا عندما تعود متصلًا.',
      'marketRefreshOffline': 'أنت غير متصل، لذا لا يمكن تحديث الأسعار. ستتحدّث تلقائيًا عندما تعود متصلًا.',
      'clearMarketCache': 'مسح بيانات السوق المحفوظة',
      'clearMarketCacheSubtitle': 'الأسعار والرسوم والإشارات والأخبار والإشعارات المحفوظة للاستخدام دون اتصال',
      'marketCacheCleared': 'مُسحت بيانات السوق المحفوظة.',
      'marketCacheClearFailed': 'تعذّر مسح بيانات السوق المحفوظة. حاول مجددًا.',
      // H5b
      'newsOfflineNoCache': 'لم تُحفظ الأخبار على هذا الهاتف بعد. ستظهر تلقائيًا عندما تعود متصلًا.',
      'newsRefreshOffline': 'أنت غير متصل، لذا لا يمكن تحديث الأخبار. ستتحدّث تلقائيًا عندما تعود متصلًا.',
      'notificationsOfflineNoCache': 'لم تُحفظ الإشعارات على هذا الهاتف بعد. ستظهر تلقائيًا عندما تعود متصلًا.',
      'notificationsRefreshOffline': 'أنت غير متصل، لذا لا يمكن تحديث الإشعارات. ستتحدّث تلقائيًا عندما تعود متصلًا.',
      'signalsRefreshOffline': 'أنت غير متصل، لذا لا يمكن تحديث الإشارات. ستتحدّث تلقائيًا عندما تعود متصلًا.',
      'commentsOffline': 'التعليقات تحتاج إلى اتصال. ستظهر تلقائيًا عندما تعود متصلًا.',
      'commentsOfflineAction': 'أنت غير متصل، لذا لم يُرسل تعليقك. ما زال هنا: أرسله عندما تعود متصلًا.',
      'alertsOfflineAction': 'أنت غير متصل. التنبيهات محفوظة على الخادم، لذا يحتاج هذا إلى اتصال. لم يتغيّر شيء.',
      'lowDataMode': 'وضع البيانات المنخفضة',
      'lowDataModeSubtitle': 'يستهلك بيانات أقل: تتحدّث الأسعار كل 5 ثوانٍ، وتحمّل الرسوم شموعًا أقل بلا حركة، وتُحمَّل الصور بحجم أصغر، ولا تتحدّث التبويبات التي لا تعرضها تلقائيًا.',
      'lowDataPillLabel': 'وضع البيانات المنخفضة مفعّل. تتحدّث الأسعار كل 5 ثوانٍ وتعرض الرسوم شموعًا أقل.',
      'lowDataSuggestTitle': 'استهلاك بيانات أقل؟',
      'lowDataSuggestMobile': 'أنت على بيانات الجوال. وضع البيانات المنخفضة يحدّث الأسعار بوتيرة أقل ويحمّل رسومًا وصورًا أصغر.',
      'lowDataSuggestSlow': 'يبدو اتصالك بطيئًا. وضع البيانات المنخفضة يحدّث الأسعار بوتيرة أقل ويحمّل رسومًا وصورًا أصغر.',
      'lowDataTurnOn': 'تفعيل',
      'lowDataNotNow': 'ليس الآن',
      'lowDataTurnedOn': 'وضع البيانات المنخفضة مفعّل. يمكنك إيقافه من الإعدادات.',
      'feedStatusLabel': 'تدفق الأسعار: {status}',
      'change24h': '24 س',
      'chartCandles': 'شموع',
      'chartLine': 'خط',
      'chartArea': 'مساحة',
      'chartType': 'نوع الرسم',
      'timeframe': 'الإطار الزمني',
      'indicators': 'المؤشرات',
      'indicatorsCount': 'المؤشرات، {count} مفعّلة',
      'indSma': 'SMA 20',
      'indSmaHint': 'المتوسط المتحرك البسيط',
      'indEma': 'EMA 50',
      'indEmaHint': 'المتوسط المتحرك الأسي',
      'indBollinger': 'بولينجر (20، 2)',
      'indBollingerHint': 'نطاقات التذبذب حول السعر',
      'indRsi': 'RSI 14',
      'indRsiHint': 'الزخم، في لوحة أسفل الرسم',
      'indMacd': 'MACD (12، 26، 9)',
      'indMacdHint': 'زخم الاتجاه، في لوحة أسفل الرسم',
      'indicatorsNote': 'تُحسب من الأسعار المعروضة على الرسم.',
      'done': 'تم',
      'chartEmpty': 'لا يوجد سجل أسعار لهذا الإطار الزمني بعد.',
      'chartError': 'تعذّر تحميل الرسم البياني.',
      'chartLabel': 'رسم {symbol} على {timeframe}. آخر سعر {price}، {change} خلال الشموع الظاهرة. الأعلى {high}، الأدنى {low}.',
      'zoneEntry': 'الدخول',
      'zoneTarget': 'الهدف',
      'zoneStop': 'الوقف',
      'modelRead': 'قراءة النموذج',
      'probabilityCaption': 'فرصة بلوغ الهدف قبل الوقف',
      'riskRewardLabel': 'العائد : المخاطرة',
      'timeframesAgree': '{count} من {total} أطر زمنية متفقة',
      'validUntil': 'صالحة حتى {time}',
      'noSetupTitle': 'لا توجد فرصة الآن',
      'noSetupBody': 'لا يرى النموذج فرصة واضحة على 15m أو 1h أو 4h، وهذه إجابة صحيحة.',
      'signalDisclaimer': 'احتمال وليس وعدًا. منطقة الدخول قد لا تُنفَّذ، والوقف لا يحدّ الخسارة بالضرورة.',
      'showReadOnChart': 'اعرض قراءة {timeframe} على الرسم',
      'readNoSetup': '{timeframe}: لا توجد فرصة',
      'setAlert': 'ضبط تنبيه',
      'priceAlert': 'تنبيه سعر',
      'alertTargetLabel': 'السعر المستهدف',
      'alertNow': 'الآن {price}',
      'alertRisesTo': 'نبّهني عندما يرتفع إلى {price}',
      'alertFallsTo': 'نبّهني عندما ينخفض إلى {price}',
      'alertNote': 'ملاحظة (اختيارية)',
      'alertCreate': 'إنشاء التنبيه',
      'alertCreated': 'تم ضبط التنبيه: {symbol} عند {price}',
      'alertDelivery': 'يصلك كإشعار.',
      'alertErrorEmpty': 'أدخل سعرًا',
      'alertErrorInvalid': 'أدخل رقمًا صحيحًا',
      'alertErrorPositive': 'يجب أن يكون السعر أكبر من صفر',
      'alertErrorCurrent': 'هذا هو السعر الحالي',
      'alertCreateFailed': 'تعذّر حفظ التنبيه. حاول مجددًا.',
      'yourAlerts': 'تنبيهاتك',
      'alertActive': 'نشط',
      'alertPaused': 'متوقف',
      'alertTriggered': 'تم التنبيه',
      'alertPause': 'إيقاف مؤقت',
      'alertResume': 'استئناف',
      'alertDelete': 'حذف',
      'alertDeleted': 'تم حذف التنبيه',
      'alertActionFailed': 'لم تنجح العملية. حاول مجددًا.',
      'undo': 'تراجع',
      'alertRowRises': 'يرتفع إلى {price}',
      'alertRowFalls': 'ينخفض إلى {price}',
      'alertRowLabel': '{rule}، {state}. اسحب للحذف.',
      // H4a: alert states + workspace undo/redo
      'alertExpired': 'منتهي',
      'alertTriggeredAt': 'تم التنبيه عند {price}',
      'alertUntil': 'حتى {time}',
      'alertWaitsForCross': 'ينتظر عبورًا جديدًا',
      'alertSetAgain': 'اضبطه مجددًا',
      'alertsActiveHeading': 'التنبيهات النشطة',
      'alertsHistoryHeading': 'سجل التنبيهات',
      'alertsNoActive': 'لا توجد تنبيهات نشطة.',
      'alertExpiryLabel': 'ينتهي بعد',
      'alertExpiryNone': 'بلا انتهاء',
      'alertExpiryDay': 'يوم واحد',
      'alertExpiryWeek': 'أسبوع واحد',
      'alertExpiryMonth': 'شهر واحد',
      'alertExpiryHint': 'التنبيه المنتهي يتوقف ولا يُطلق أبدًا.',
      'alertsOffline': 'أنت غير متصل. تُفحص التنبيهات من جديد عندما تتحدّث الأسعار.',
      'notifAlertTriggeredTitle': '{symbol} بلغ {level}',
      'notifAlertTriggeredBody': 'انطلق تنبيه السعر عند {price}. اضغط لفتح الأداة.',
      'workspaceUndo': 'تراجع',
      'workspaceRedo': 'إعادة',
      'workspaceUndoLabel': 'تراجع عن آخر تغيير في مساحات العمل',
      'workspaceRedoLabel': 'أعد آخر تغيير في مساحات العمل',
      'workspaceUndone': 'تم التراجع عن التغيير',
      'workspaceRedone': 'تمت إعادة التغيير',
      // Design system (redesign 2026-10)
      'appName': 'AI Trading Assistance',
      'appTagline': 'أبحاث الذهب والعملات',
      'appearance': 'المظهر',
      'themeLight': 'فاتح',
      'themeDark': 'داكن',
      'themeSystem': 'حسب النظام',
      'sourceLive': 'مباشر',
      'sourceHistorical': 'تاريخي',
      'sourceModel': 'مخرجات النموذج',
      'sourceUser': 'إدخالك',
      'sourceDemo': 'محاكاة',
      'sourceUnavailable': 'غير متصل',
      'directionUp': 'صعود',
      'directionDown': 'هبوط',
      'directionFlat': 'دون تغيير',
      'tryAgain': 'حاول مجددًا',
      'somethingWentWrong': 'حدث خطأ ما',
      'loading': 'جارٍ التحميل',
      'showPassword': 'إظهار كلمة المرور',
      'hidePassword': 'إخفاء كلمة المرور',
      // Profile + Settings (redesign 2026-10, stage B)
      'profilePlan': 'الخطة',
      'passwordAndSecurity': 'كلمة المرور والأمان',
      'passwordAndSecuritySubtitle': 'غيّر كلمة المرور',
      'settings': 'الإعدادات',
      'settingsSubtitle': 'المظهر، اللغة، الإشعارات، حدود المخاطرة',
      'helpAndAbout': 'المساعدة وحول التطبيق',
      'helpAndAboutSubtitle': 'أسئلة، معلومات قانونية، نسخة التطبيق',
      'save': 'حفظ',
      'changePhoto': 'تغيير الصورة',
      'discardChangesTitle': 'تجاهل التغييرات؟',
      'discardChangesBody': 'ستضيع التعديلات التي أجريتها على ملفك.',
      'discard': 'تجاهل',
      'keepEditing': 'متابعة التعديل',
      'changePasswordIntro': 'أدخل كلمة المرور الحالية، ثم اختر كلمة جديدة.',
      'riskGroup': 'رأس المال والمخاطرة',
      'riskLimits': 'رأس المال وحدود المخاطرة',
      'riskLimitsIntro': 'تُدخل هذه القيم بنفسك. تُستخدم لحساب حجم الصفقة ومطابقة الإشارات مع حدودك. التطبيق لا يرى حسابك لدى الوسيط.',
      'riskLimitsSummary': '{capital} · {perTrade} للصفقة · {daily} يوميًا',
      'riskLimitsSummaryNoCapital': 'رأس المال غير محدد · {perTrade} للصفقة · {daily} يوميًا',
      'riskCapitalLabel': 'رأس مال الحساب',
      'riskCapitalHelper': 'يمكنك تركه فارغًا، وسيطلبه حساب حجم الصفقة عند الحاجة.',
      'riskPerTradeLabel': 'أقصى مخاطرة للصفقة الواحدة',
      'riskDailyLabel': 'حد الخسارة اليومي',
      'riskErrCapital': 'أدخل مبلغًا أكبر من صفر',
      'riskErrRange': 'أدخل قيمة من {min} إلى {max}',
      'riskErrDailyBelow': 'يجب ألا يقل الحد اليومي عن مخاطرة الصفقة الواحدة',
      'riskLimitsSaved': 'تم حفظ حدود المخاطرة',
      'notifChannels': 'القنوات',
      'notifKinds': 'ما يُرسَل',
      'channelPush': 'إشعارات الهاتف',
      'channelPushHint': 'على هذا الهاتف',
      'channelInApp': 'داخل التطبيق',
      'channelInAppHint': 'في مركز الإشعارات',
      'channelEmail': 'البريد الإلكتروني',
      'channelEmailHint': 'إلى بريد حسابك',
      'channelTelegram': 'تيليغرام',
      'channelTelegramHint': 'إلى حساب تيليغرام المرتبط',
      'kindPriceAlert': 'تنبيهات الأسعار',
      'kindPriceAlertHint': 'عندما يصل السعر إلى مستوى حددته',
      'kindOpportunity': 'الفرص',
      'kindOpportunityHint': 'عندما يجد النموذج فرصة تناسب استراتيجيتك',
      'kindSystem': 'النظام',
      'kindSystemHint': 'إشعارات الحساب والخدمة',
      'notifMuted': 'مع إيقاف كل القنوات لن يصلك أي إشعار.',
      'notifPrefsNote': 'تُحفظ على هذا الهاتف إلى أن يُربط حسابك. أما التوصيل نفسه فتتولاه الخدمة.',
      'aboutShort': 'مساعد بحثي للذهب والعملات: الرسوم البيانية واحتمالات النموذج وحدود مخاطرتك في مكان واحد.',
      'neverTradesTitle': 'لا ينفّذ أي صفقة.',
      'neverTradesBody': 'لا يتصل بأي وسيط، ولا يفتح أمرًا أو يعدّله أو يغلقه أبدًا. القرار دائمًا لك.',
      'faqModelReadQ': 'ما هي قراءة النموذج؟',
      'faqModelReadA': 'تقدير النموذج، لأداة وإطار زمني محددين، لاحتمال بلوغ الهدف قبل الوقف. إنه احتمال وليس وعدًا، وقد يكون خاطئًا.',
      'faqSimulatedQ': 'لماذا تظهر بعض البيانات بعبارة «محاكاة»؟',
      'faqSimulatedA': 'إلى أن يُربط التطبيق بالخدمة الحية، تُولَّد الأسعار ومخرجات النموذج على هاتفك. هي توضّح طريقة عمل التطبيق، لا ما يحدث في السوق.',
      'faqAccuracyQ': 'ما مدى دقة النموذج؟',
      'faqAccuracyA': 'يعرض تبويب الإشارات نسبة الإشارات السابقة التي بلغت الهدف قبل الوقف، وعدد الإشارات التي بُنيت عليها النسبة. الدقة السابقة ليست وعدًا بنتائج مستقبلية.',
      'faqStrategyQ': 'ماذا تغيّر «الاستراتيجية»؟',
      'faqStrategyA': 'ما تراه من إشارات. طريقة التحليل تحدّد كيف تُكتشف الإشارات، والأدوات والأطر الزمنية والاتجاهات والحدود الدنيا التي تختارها تصفّي القائمة.',
      'thirdPartyNotices': 'تراخيص الطرف الثالث',
      'thirdPartyNoticesSubtitle': 'تراخيص المصادر المفتوحة، ومنها الخطوط',
      'versionLine': 'الإصدار {version} ({build})',
      'legalDataTitle': 'البيانات على هذا الهاتف',
      'legalUpdated': 'آخر تحديث: 25 تشرين الأول 2026',
      'legalRiskIntro': 'يُرجى قراءة هذا قبل استخدام أي تحليل في التطبيق. يوضّح ما يفعله التطبيق وما لا يفعله، وحدود كل ما يعرضه.',
      'legalRisk1Title': '1. ما هو التطبيق',
      'legalRisk1Body': 'AI Trading Assistance أداة بحث ودعم قرار للذهب (XAU/USD) وأزواج العملات الرئيسية. يعرض الرسوم البيانية وتقييم النموذج وحسابات حجم الصفقة بناءً على أرقام تُدخلها. ليس نصيحة مالية، وليس وسيطًا، ولا يفتح الصفقات أو يعدّلها أو يغلقها أبدًا. أي قرار تداول وعواقبه تعود إليك.',
      'legalRisk2Title': '2. مخاطر التداول',
      'legalRisk2Body': 'ينطوي تداول الذهب والعملات على مخاطر عالية وقد لا يناسب الجميع. المنتجات ذات الرافعة قد تفقد قيمتها بسرعة. لا تتداول بمال لا تستطيع تحمّل خسارته. أمر وقف الخسارة تعليمة وليس وعدًا، فقد يقفز السعر متجاوزًا إياه. ومنطقة الدخول منطقة اهتمام، وقد لا يُنفَّذ أمر عندها.',
      'legalRisk3Title': '3. مخرجات النموذج تقديرات',
      'legalRisk3Body': 'الاحتمال هو تقدير النموذج لبلوغ الهدف قبل الوقف. قد يكون خاطئًا، وليس تنبؤًا بأن شيئًا ما سيحدث. الأسباب المعروضة تشرح المخرجات، ولا تثبت أن السوق سيتبعها.',
      'legalRisk4Title': '4. البيانات المحاكاة',
      'legalRisk4Body': 'إلى أن يُربط التطبيق بالخدمة الحية، تُحاكى بيانات السوق ومخرجات النموذج وأرقام الدقة على هاتفك وتُعلَّم بعبارة «محاكاة». هي أمثلة على طريقة العمل، وليست معلومات عن السوق. النتائج السابقة أو المحاكاة ليست وعدًا بنتائج مستقبلية.',
      'legalRisk5Title': '5. حسابات المخاطرة تعتمد على مدخلاتك',
      'legalRisk5Body': 'يُحسب حجم الصفقة والمبلغ المعرّض للخسارة ومطابقة الحدود من رأس المال ونسبة المخاطرة والدخول والوقف التي تُدخلها، مع افتراض تنفيذ الوقف عند سعره. لا يخمّن التطبيق تفاصيل الوسيط: يعرض الحجم بوحدات الأصل الأساسي لا باللوتات، ولا يحسب الهامش.',
      'legalRisk6Title': '6. عن هذه الوثيقة',
      'legalRisk6Body': 'هذا الإفصاح للمعلومات فقط. كُتب ضمن مشروع تخرّج ولم يُراجَع كوثيقة قانونية، ولا يغني عن استشارة مختص مرخّص.',
      'legalDataIntro': 'تعرض هذه الصفحة ما يحتفظ به التطبيق على هاتفك ولماذا، كما هو التطبيق اليوم.',
      'legalData1Title': 'لا تحليلات ولا تتبّع',
      'legalData1Body': 'لا يحتوي التطبيق على أي شيفرة تحليلات أو إعلانات أو تتبّع. خطوطه مضمّنة فيه ولا تُحمَّل من أطراف ثالثة.',
      'legalData2Title': 'ما يُخزَّن ولماذا',
      'legalData2Body': 'يُحفظ إعداد المظهر ورأس مالك وحدود مخاطرتك وفلتر استراتيجيتك وتفضيلات الإشعارات في مساحة تخزين التطبيق. وتُحفظ جلسة الدخول واللغة في التخزين الآمن للهاتف. أما تنبيهات الأسعار والأخبار والإشعارات فتبقى في الذاكرة فقط.',
      'legalData3Title': 'كيف تحذفها',
      'legalData3Body': 'تسجيل الخروج يحذف جلستك. وحذف التطبيق، أو مسح بياناته من إعدادات الهاتف، يحذف كل ما ورد هنا.',
      'communityNews': 'الأخبار',
      'expertsIntro': 'متداولون ذوو خبرة يمكنك الاشتراك معهم ومحادثتهم. الاشتراكات والردود محاكاة: لا يُدفع أي مبلغ.',
      'expertsEmpty': 'لا يوجد خبراء بعد',
      'expertMarkets': 'الأسواق: {markets}',
      'expertSubscribe': 'اشترك',
      'accuracyLine': 'دقة النموذج {rate} · {count} إشارة سابقة · آخر {days} يومًا',
      'accuracyNoResults': 'لا إشارات مكتملة في آخر {days} يومًا بعد',
      'accuracyCaption': 'نسبة الإشارات السابقة التي بلغت الهدف قبل الوقف.',
      'accuracyError': 'تعذّر تحميل الدقة.',
      'strategyIntro': 'اختر كيف تُكتشف الإشارات وأيّها تراه.',
      'strategyInstruments': 'الأدوات',
      'strategyTimeframes': 'الأطر الزمنية',
      'strategyDirections': 'الاتجاهات',
      'strategyMinProbability': 'أدنى احتمال',
      'strategyMinRiskReward': 'أدنى عائد : مخاطرة',
      'strategyAny': 'أي',
      'strategyRiskFit': 'فقط الإشارات التي تناسب حدود مخاطرتي',
      'strategyRiskFitHint': 'يستخدم رأس مالك وحدودك من الإعدادات.',
      'strategyRiskFitNoCapital': 'حدّد رأس مالك من الإعدادات ← رأس المال والمخاطرة لتفعيل هذا الفحص.',
      'strategyPickOne': 'اختر أداة وإطارًا زمنيًا واتجاهًا واحدًا على الأقل.',
      'strategyReset': 'استعادة الافتراضي',
      'strategySaved': 'تم حفظ الاستراتيجية',
      'strategySavedState': 'تم الحفظ',
      'sizeTrade': 'احسب حجم الصفقة',
      'sizeFromRead': 'من خطة النموذج على {timeframe}',
      'sizePosition': 'حجم الصفقة',
      'sizeUnits': '{units} {currency}',
      'sizeOunces': '{units} oz',
      'sizeMoneyAtRisk': 'المبلغ المعرّض للخسارة',
      'sizeStopDistance': 'مسافة الوقف',
      'sizePips': '{pips} نقطة',
      'sizeReward': 'إذا بلغ الهدف',
      'sizeRiskLabel': 'مخاطرة هذه الصفقة',
      'sizeTargetLabel': 'الهدف (اختياري)',
      'sizeCapitalHint': 'حدّده مرة واحدة من الإعدادات ← رأس المال والمخاطرة ليُملأ هنا.',
      'sizeIncomplete': 'أدخل رأس المال والمخاطرة والدخول والوقف لترى الحجم.',
      'sizeErrStopEqual': 'يجب أن يختلف الوقف عن سعر الدخول.',
      'sizeErrTarget': 'يجب أن يكون الهدف في الجهة المقابلة للوقف من سعر الدخول.',
      'sizeErrRisk': 'لا يمكن أن تتجاوز المخاطرة 100% من رأس المال.',
      'sizeNote': 'حساب فقط. الحجم بوحدات الأصل الأساسي لأن اللوتات تعتمد على الوسيط. التطبيق لا ينفّذ أي صفقة.',
      'limitWithin': 'ضمن حدّك',
      'limitNear': 'قريب من حدّك',
      'limitBreach': 'فوق حدّك',
      'limitDetail': '{risk} من رأس المال مقابل حدّك {limit} للصفقة.',
      // Auth, Assistant, Notifications, News (redesign 2026-10, stage C)
      'welcomeBody': 'رسوم بيانية واحتمالات نموذج وحدود مخاطرك الخاصة للذهب والعملات، وكل قرار يبقى لك.',
      'createAccountAction': 'إنشاء حساب',
      'logIn': 'تسجيل الدخول',
      'haveAccount': 'لديك حساب؟',
      'noAccount': 'جديد هنا؟',
      'registerTitle': 'أنشئ حسابك',
      'fullName': 'الاسم الكامل',
      'fullNameRequired': 'أدخل اسمك الكامل.',
      'fullNameTooLong': 'اجعل الاسم أقل من 60 حرفًا.',
      'confirmPasswordLabel': 'تأكيد كلمة المرور',
      'passwordCheckLength': '8 أحرف أو أكثر',
      'passwordCheckLetter': 'حرف',
      'passwordCheckNumber': 'رقم',
      'passwordMaxChars': 'استخدم 128 حرفًا كحد أقصى',
      'passwordNeedsLetter': 'أضف حرفًا واحدًا على الأقل',
      'checkMet': 'متحقق',
      'checkNotMet': 'غير متحقق',
      'registerAdviceAck': 'أفهم أن هذا ليس نصيحة مالية.',
      'registerAdviceRequired': 'يُرجى تأكيد أنك تفهم أن التطبيق لا يقدّم نصيحة مالية.',
      'registerFailed': 'تعذّر إنشاء حسابك. تحقّق من اتصالك وحاول مجددًا.',
      'loginTitle': 'أهلًا بعودتك',
      'loginFailed': 'تعذّر تسجيل دخولك. تحقّق من بياناتك واتصالك ثم حاول مجددًا.',
      'otpTitle': 'تحقّق من بريدك',
      'otpBody': 'أدخل الرمز المكوّن من 5 أرقام الذي أرسلناه إلى',
      'otpLabel': 'رمز التحقق',
      'otpIncomplete': 'أدخل الأرقام الخمسة كلها.',
      'otpSimulated': 'أي 5 أرقام تعمل إلى أن تُربط خدمة الحسابات.',
      'otpVerify': 'تحقّق',
      'otpResendIn': 'إعادة إرسال الرمز بعد {time}',
      'otpResend': 'إعادة إرسال الرمز',
      'otpResent': 'رمز جديد في الطريق إليك.',
      'otpDoneTitle': 'كل شيء جاهز.',
      'otpDoneBody': 'تم التحقق من بريدك وحسابك جاهز.',
      'otpContinue': 'متابعة',
      'notifInbox': 'الوارد',
      'notifInboxCount': 'الوارد · {count}',
      'notifAlerts': 'التنبيهات',
      'notifAlertsCount': 'التنبيهات · {count}',
      'filterAll': 'الكل',
      'notifMarkAllRead': 'تعليم الكل كمقروء',
      'notifMarkRead': 'تعليم كمقروء',
      'notifMarkUnread': 'تعليم كغير مقروء',
      'notifDelete': 'حذف',
      'notifDeleted': 'تم حذف الإشعار',
      'notifUnread': 'غير مقروء',
      'notifActionFailed': 'لم ينجح ذلك. حاول مجددًا.',
      'notifLoadError': 'تعذّر تحميل الإشعارات.',
      'notifEmptyTitle': 'لا جديد لديك',
      'notifEmptyBody': 'ستظهر هنا تنبيهات الأسعار وفرص النموذج وإشعارات الحساب.',
      'notifFilterEmpty': 'لا شيء ضمن «{kind}»',
      'notifOpportunityTitle': '{symbol} · {direction} على {timeframe}',
      'notifOpportunityBody': 'يرى النموذج احتمال {probability} أن يُبلَغ الهدف قبل الوقف. هذا احتمال وليس وعدًا.',
      'notifAlertAboveTitle': '{symbol} ارتفع إلى مستواك',
      'notifAlertAboveBody': 'تجاوز السعر صعودًا المستوى الذي حددته. أُوقف هذا التنبيه الآن.',
      'notifAlertBelowTitle': '{symbol} انخفض إلى مستواك',
      'notifAlertBelowBody': 'تجاوز السعر هبوطًا المستوى الذي حددته. أُوقف هذا التنبيه الآن.',
      'notifSimulatedTitle': 'بيانات السوق محاكاة',
      'notifSimulatedBody': 'إلى أن يُربط التطبيق بالخدمة الحية، تُولَّد الأسعار ونتائج النموذج على هاتفك.',
      'notifWelcomeBody': 'ابدأ بقائمة المتابعة في الرئيسية. التطبيق لا ينفّذ أي صفقة، وكل قرار يبقى لك.',
      'alertsEmptyTitle': 'لا توجد تنبيهات أسعار',
      'alertsEmptyBody': 'افتح أداة من الرئيسية واضغط «ضبط تنبيه» ليصلك إشعار عندما يبلغ السعر مستوى تحدده.',
      'alertsHint': 'اسحب الصف لحذفه، واضغط عليه لفتح الأداة.',
      'moodTitle': 'مزاج السوق · 24 ساعة',
      'moodPositive': 'يميل للإيجابية',
      'moodNegative': 'يميل للسلبية',
      'moodMixed': 'متباين',
      'moodNone': 'لا توجد أخبار كافية بعد',
      'moodCounts': '{positive} إيجابي، {neutral} محايد، {negative} سلبي',
      'sentimentPositive': 'إيجابي',
      'sentimentNegative': 'سلبي',
      'sentimentLabel': 'نبرة الخبر: {label}',
      'sentimentNote': 'وسم النبرة قراءة نموذج للنص، وليس توقعًا للسعر.',
      'newsEmpty': 'لا توجد أخبار حاليًا',
      'newsEmptyBody': 'اسحب للأسفل للتحقق مجددًا.',
      'newsLoadError': 'تعذّر تحميل الأخبار.',
      'newsNotFound': 'هذا الخبر لم يعد متاحًا.',
      'comments': 'التعليقات',
      'commentsTitle': 'التعليقات · {count}',
      'commentsEmpty': 'لا توجد تعليقات بعد',
      'commentsEmptyBody': 'كن أول من يشارك رأيه في هذا الخبر.',
      'commentHint': 'أضف تعليقًا',
      'commentSend': 'نشر التعليق',
      'commentDelete': 'حذف التعليق',
      'commentDeleted': 'تم حذف التعليق',
      'commentActionFailed': 'لم ينجح ذلك. حاول مجددًا.',
      'asstContext': 'السياق',
      'asstContextLabel': 'السياق: {value}',
      'asstContextHint': 'يغيّر الأداة',
      'asstContextTitle': 'ما يراه المساعد',
      'asstContextBody': 'اختر أداة واحدة. يستخدم المساعد سعرها وقراءة النموذج لها وحدود المخاطرة لديك، ولا شيء غير ذلك.',
      'asstContextNone': 'بلا أداة',
      'asstContextNoneHint': 'أسئلة عامة فقط',
      'asstEmptyTitle': 'اسأل عن {symbol}',
      'asstEmptyTitleGeneral': 'اسأل عن الذهب والعملات',
      'asstEmptyBody': 'تعتمد الإجابات على بيانات هذا التطبيق فقط، ولا يطلب منك المساعد أبدًا أن تشتري أو تبيع.',
      'asstSuggestExplain': 'اشرح التحليل الحالي',
      'asstSuggestInvalidate': 'ما الذي قد يُلغيه؟',
      'asstSuggestRisk': 'احسب المخاطرة لرأس مالي',
      'asstHint': 'اسأل عن الرسم أو النموذج أو مخاطرك',
      'asstSend': 'إرسال',
      'asstStop': 'إيقاف',
      'asstAttach': 'إرفاق صورة رسم بياني',
      'asstAttachTitle': 'قراءة صورة رسم بياني',
      'asstAttachBody': 'PNG أو JPG حتى 10 ميغابايت. الصورة نفسها مرة أخرى لا تستهلك تحليلًا إضافيًا.',
      'asstImageType': 'استخدم صورة PNG أو JPG.',
      'asstImageSize': 'حجم الصورة أكبر من 10 ميغابايت.',
      'asstImageUnreadable': 'تعذّر فتح الصورة.',
      'asstChartImage': 'صورة الرسم البياني التي أرسلتها',
      'asstNewChat': 'محادثة جديدة',
      'asstCleared': 'تم مسح المحادثة',
      'asstReplying': 'المساعد يكتب الرد',
      'asstFailed': 'تعذّر على المساعد الإجابة.',
      'asstOffline': 'أنت غير متصل. يحتاج المساعد إلى اتصال.',
      'asstRuleBased': 'عرض قائم على قواعد، وليس نموذجًا لغويًا',
      'asstAnswerLabel': 'إجابة المساعد: {kind}',
      'asstKindExplain': 'ملخّص التحليل',
      'asstKindInvalidate': 'ما الذي يُلغيه',
      'asstKindRisk': 'حساب المخاطرة',
      'asstKindChart': 'تحليل الرسم',
      'asstKindUnknown': 'ما يمكنني الإجابة عنه',
      'asstNoContext': 'اختر أداة من «السياق» في الأعلى لأجيب عن رسمها وقراءة النموذج ومخاطرك.',
      'asstUnknown': 'أستطيع شرح قراءة النموذج، وتوضيح ما قد يُلغيها، وحساب المخاطرة وفق حدودك. لا أستطيع توقّع الأسعار ولا أن أطلب منك الشراء أو البيع.',
      'asstExplain': '{symbol} على إطار {timeframe}: يميل النموذج إلى {direction}، مع احتمال {probability} أن يُبلَغ الهدف قبل الوقف. {agree} من {analysed} أطر زمنية متفقة.\n\nالدخول حوالي {entry}، والوقف عند {stop}، والهدف عند {target} (العائد إلى المخاطرة {rr}).',
      'asstExplainNone': 'لا يوجد لدى النموذج إعداد حالي على {symbol}: لا شيء على 15m أو 1h أو 4h يتجاوز عتبته الآن. وغياب الإعداد إجابة أيضًا.',
      'asstInvalidate': 'تُلغى هذه القراءة إذا تجاوز السعر منطقة الوقف عند {stop}. وتنتهي صلاحيتها عند {time} بتوقيت UTC، وبعدها تصبح قديمة حتى لو لم يتحرك السعر.\n\nوانقلاب إطار زمني أعلى إلى الاتجاه المعاكس يُضعفها أيضًا.',
      'asstInvalidateNone': 'لا توجد قراءة نشطة على {symbol}، فلا يوجد ما يُلغى بعد.',
      'asstRisk': 'برأس مال {capital} ومخاطرة {risk} لكل صفقة، يبعد وقف النموذج {pips} نقطة عن الدخول، ما يسمح بحوالي {units} وحدة. أي أن {money} معرّضة للخسارة إذا نُفّذ الوقف عند سعره.\n\nالوقف أمرٌ وليس وعدًا: قد يقفز السعر متجاوزًا إياه.',
      'asstRiskNoCapital': 'حدّد رأس مالك من حسابي ← الإعدادات ← رأس المال والمخاطرة لأحسب الحجم لك.\n\nالقاعدة: المبلغ المعرّض = رأس المال × المخاطرة لكل صفقة، والحجم = المبلغ المعرّض ÷ مسافة الوقف.',
      'asstRiskNone': 'لا يوجد إعداد نشط على {symbol}، فلا يوجد وقف يُحسب الحجم عليه. افتح الأداة واستخدم «احسب حجم الصفقة» بدخولك ووقفك.',
      'chartActionTitle': 'حلّل صورة رسم بياني',
      'chartActionBody': 'احصل على الاتجاه والمستويات الرئيسية والشكل الفني، مطابقةً لاستراتيجيتك المحفوظة.',
      'chartQuotaCount': '{used} من {limit} تحليلات اليوم',
      'chartLimitReached': 'بلغت الحد اليومي. يُعاد ضبطه عند {time}.',
      'chartLimitChat': 'ما زال بإمكانك طرح الأسئلة في المحادثة.',
      'chartPreviewLabel': 'صورة الرسم البياني للتحليل',
      'chartFileSize': '{type} · {size} ميغابايت',
      'chartRemove': 'إزالة',
      'chartAnalyze': 'حلّل',
      'chartAnalyzing': 'جارٍ تحليل صورة الرسم البياني…',
      'chartFailed': 'تعذّر تحليل الرسم البياني.',
      'chartOffline': 'أنت غير متصل. لم يُرسَل أي شيء.',
      'chartOrAsk': 'أو اطرح سؤالًا',
      'chartTrend': 'الاتجاه',
      'chartKeyLevels': 'المستويات الرئيسية',
      'chartPattern': 'الشكل الفني',
      'chartHighProbability': 'احتمال مرتفع',
      'chartNoSetup': 'لا يوجد إعداد على {timeframe}',
      'chartNoLevels': 'لا توجد من دون إعداد',
      'chartPictureOnly': '{trend}، في الصورة فقط',
      'chartTrendRising': 'صاعد',
      'chartTrendFalling': 'هابط',
      'chartTrendSideways': 'عرضي',
      'chartPatternChannel': 'قناة',
      'chartPatternTriangle': 'مثلث',
      'chartPatternRange': 'نطاق',
      'chartPatternFlag': 'علم',
      'chartPatternWedge': 'وتد',
      'chartReadSignal': '{symbol} على {timeframe}، والشكل الفني في الصورة: {pattern}. تقرأ استراتيجيتك ({method}) هنا {direction}، باحتمال {probability} أن يُبلَغ الهدف قبل الوقف.',
      'chartReadHigh': 'هذا احتمال مرتفع وليس يقينًا: قد يبلغ السعر الوقف أولًا.',
      'chartReadNoSetup': '{symbol} على {timeframe}، والشكل الفني في الصورة: {pattern}. لا يوجد لاستراتيجيتك ({method}) إعداد على هذا الإطار الآن، لذا لا توجد مستويات لعرضها. وعدم وجود إعداد إجابة أيضًا.',
      'chartReadNoInstrument': 'الشكل الفني في الصورة: {pattern}. الاتجاه في الصورة: {trend}. تعذّرت قراءة الرمز والإطار الزمني، لذا لم تُقارَن باستراتيجيتك. الأفضل لقطة شاشة تُظهرهما.',
      'chartStored': 'الصورة نفسها: نتيجة محفوظة لم تُحتسب',
      'chartYourStrategy': 'استراتيجيتك',
      'authOffline': 'أنت غير متصل. اتصل بالإنترنت وحاول مجددًا.',
      'welcomeTitle': 'طريقة أوضح لقراءة الأسواق.',
      'loginSubtitle': 'سجّل الدخول لمتابعة أبحاثك.',
      'registerSubtitle': 'يستغرق الأمر دقيقة، ثم تؤكّد بريدك.',
      'authDisclaimer': 'للتحليل ودعم القرار فقط. ليس نصيحة مالية، وليس وسيطًا.',
      'notAdviceNotice': 'الإشارات لأغراض تعليمية وليست نصيحة استثمارية.',
      'otpVerifiedRow': 'تم التحقق من البريد',
      'communityPosts': 'المنشورات',
      'postsIntro': 'أفكار يشاركها أعضاء المجتمع. ليست نصيحة مالية.',
      'postsEmptyTitle': 'لا منشورات بعد',
      'postsEmptyBody': 'شارك ما تراقبه في الذهب أو العملات.',
      'postsLoadError': 'تعذّر تحميل المنشورات.',
      'newPost': 'منشور جديد',
      'newPostTitle': 'منشور جديد',
      'newPostAs': 'تنشر باسم {name}',
      'newPostLabel': 'منشورك',
      'newPostHint': 'ماذا تراقب في الذهب أو العملات؟',
      'newPostInstrument': 'الأداة (اختياري)',
      'newPostNote': 'المنشورات علنية لكل من في المجتمع. شارك تحليلًا، لا تعليمات تداول.',
      'newPostNotAdvice': 'الآراء المشاركة ليست نصيحة مالية.',
      'postAction': 'انشر',
      'postShared': 'تم نشر المنشور',
      'postFailed': 'لم يُنشر منشورك. تحقّق من اتصالك وحاول مجددًا.',
      'postOffline': 'أنت غير متصل. لم يُرسَل منشورك.',
      'postOptions': 'خيارات المنشور',
      'postDelete': 'احذف المنشور',
      'postDeleted': 'تم حذف المنشور',
      'postActionFailed': 'لم ينجح ذلك. حاول مجددًا.',
      'postLikes': 'إعجاب، {count}',
      'postOpenInstrument': 'افتح {symbol}',
      'postReport': 'الإبلاغ عن المنشور',
      'postReported': 'تم الإبلاغ',
      'reportTitle': 'الإبلاغ عن هذا المنشور',
      'reportBody': 'أخبرنا ما المشكلة. سيراجعه مشرف، ولن يعرف الكاتب من أبلغ.',
      'reportSpam': 'رسائل مزعجة أو إعلان',
      'reportMisleading': 'مضلّل أو يعد بأرباح',
      'reportAbusive': 'مسيء أو يحضّ على الكراهية',
      'reportOther': 'سبب آخر',
      'reportSend': 'أرسل البلاغ',
      'reportSent': 'شكرًا. سيراجع مشرف هذا المنشور.',
      'postsOfflineTitle': 'أنت غير متصل',
      'postsOfflineBody': 'ستظهر المنشورات عند عودة الاتصال.',
      'postsOfflineAction': 'أنت غير متصل. حاول مجددًا عند الاتصال.',
      // Signals list + detail (stage D1)
      'signalsListTitle': 'الفرص',
      'signalsError': 'تعذّر تحميل الإشارات.',
      'signalsOfflineBody': 'ستظهر الإشارات عند عودة الاتصال.',
      'signalsOfflineAction': 'أنت غير متصل. حاول مجددًا عند الاتصال.',
      'signalRowLabel': '{symbol}، {name}. {direction}، احتمال {probability}، {timeframe}، {age}',
      'signalRowHint': 'يفتح الإشارة',
      'signalGenerated': 'صدرت {age}',
      'signalPlanTitle': 'الخطة',
      'signalPipsAway': '{pips} نقطة عن الدخول',
      'signalWhyTitle': 'لماذا يرى النموذج ذلك',
      'reasonAgreement': '{count} من {total} أطر زمنية تشير إلى الاتجاه نفسه.',
      'reasonChance': 'نحو {count} من كل 10 إعدادات مشابهة بلغت الهدف قبل الوقف، وقد تفشل هذه المرة.',
      'reasonRewardRisk': 'الهدف أبعد من الوقف بـ {ratio} مرة.',
      'reasonVolatilityHigh': 'هذه الأداة تتحرك بسرعة، وقد يتجاوز السعر المستويات بسرعة.',
      'reasonVolatilityLow': 'السعر يتحرك بهدوء، وقد تحتاج الخطة وقتًا أطول.',
      // الاستراتيجية (A3): أسباب الطرق، درجة التأثير، طلب التحليل
      'reasonMaCrossUp': 'متوسط 10 فترات فوق متوسط 30 فترة على إطار {timeframe}، فالاتجاه نحو الصعود.',
      'reasonMaCrossDown': 'متوسط 10 فترات تحت متوسط 30 فترة على إطار {timeframe}، فالاتجاه نحو الهبوط.',
      'reasonRsiOversold': 'مؤشر RSI (14) عند {value} على إطار {timeframe}: هبط السعر كثيرًا وبسرعة، فاحتمال الارتداد للصعود أعلى.',
      'reasonRsiOverbought': 'مؤشر RSI (14) عند {value} على إطار {timeframe}: ارتفع السعر كثيرًا وبسرعة، فاحتمال الارتداد للهبوط أعلى.',
      'reasonNoSetupMa': 'لا يُظهر متوسطا 10 و30 فترة على إطار {timeframe} تقاطعًا مؤكدًا بعد.',
      'reasonNoSetupRsi': 'مؤشر RSI (14) عند {value} على إطار {timeframe}: لا انعكاس مؤكد بعد.',
      'reasonInfluenceHigh': 'مرتفع',
      'reasonInfluenceMedium': 'متوسط',
      'reasonInfluenceLow': 'منخفض',
      'reasonInfluenceLabel': 'التأثير: {level}',
      'strategyTitle': 'الاستراتيجية',
      'strategyUsed': 'الاستراتيجية المستخدمة: {method}',
      'requestedByYou': 'طلبتَها أنت',
      'analysisNoClearSetup': 'لا يوجد إعداد واضح الآن',
      // واجهة الاستراتيجية (A3b): قسم الطريقة، سطر البطاقة، طلب التحليل
      'strategyMethodTitle': 'طريقة التحليل',
      'strategyMethodsError': 'تعذّر تحميل طرق التحليل.',
      'strategyCardSummary': '{method} · {instruments}',
      'strategyCardDefault': 'الافتراضي: {method} · {instruments}',
      'strategyAboveProbability': 'فوق {value}',
      'requestAnalysisTitle': 'طلب تحليل',
      'requestAnalysisIntro': 'حلّل أداة واحدة الآن. تُظهر النتيجة إعدادًا عالي الاحتمال أو تخبرك أنه لا يوجد.',
      'requestInstrument': 'الأداة',
      'requestPickInstrument': 'اختر أداة لتحليلها.',
      'requestTimeframe': 'الإطار الزمني',
      'requestMethodSaved': '{method} · من استراتيجيتك المحفوظة',
      'requestMethodOverride': '{method} · لهذا الطلب فقط',
      'requestChangeMethod': 'غيّرها لهذا الطلب',
      'requestUseSaved': 'استخدم طريقتي المحفوظة',
      'requestOverrideNote': 'ينطبق هذا على هذا الطلب فقط. لا تتغير استراتيجيتك المحفوظة.',
      'requestAnalyze': 'حلّل',
      'requestStepPending': 'جارٍ إرسال طلبك…',
      'requestStepAnalyzing': 'جارٍ تحليل {symbol} · {timeframe} بطريقة {method}…',
      'requestFailed': 'لم يكتمل التحليل. لم يُحفظ شيء.',
      'requestInvalid': 'لا يمكن تحليل هذا الطلب. تحقّق من الأداة والإطار الزمني.',
      'requestOffline': 'أنت غير متصل، لذلك لم يُرسل شيء. اتصل ثم حاول مجددًا.',
      'requestNoSetupBody': 'جرّب إطارًا زمنيًا أو طريقة أخرى، أو تحقّق لاحقًا.',
      'reasonsShowMore': 'أسباب أخرى ({count})',
      'reasonsShowLess': 'أسباب أقل',
      'signalExpiredTitle': 'انتهت صلاحية هذه الإشارة',
      'signalExpiredBody': 'كانت صالحة حتى {time}. مستوياتها قديمة؛ افتح السوق لقراءة النموذج الحالية.',
      'signalNotFoundTitle': 'الإشارة غير متاحة',
      'signalNotFoundBody': 'ربما انتهت صلاحيتها أو حلّت محلها قراءة أحدث.',
      'signalDetailError': 'تعذّر تحميل الإشارة.',
      'openMarket': 'افتح السوق',
      'backToSignals': 'العودة إلى الإشارات',
      'signalExpiredBadge': 'منتهية',
      'signalSummaryLabel': '{direction}، احتمال {probability} أن يُبلغ الهدف قبل الوقف، {timeframe}',

      // Insights
      'insightsTitle': 'أداء النموذج',
      'insightsPeriodsLabel': 'الفترة',
      'insightsPeriod7': '7 أيام',
      'insightsPeriod30': '30 يومًا',
      'insightsPeriod90': '90 يومًا',
      'insightsHitRate': 'نسبة الإصابة · آخر {period}',
      'insightsHeadlineCount': '{hits} من {count} إشارة مكتملة بلغت الهدف قبل الوقف',
      'insightsHeadlineMisses': '{count} بلغت الوقف أولًا',
      'insightsHeadlineLabel': 'نسبة الإصابة في آخر {period}: {rate}. {hits} من {count} إشارة مكتملة بلغت الهدف قبل الوقف.',
      'insightsOverTime': 'عبر الزمن',
      'insightsChartCaption': 'كل نقطة تمثّل الإشارات التي اكتملت في تلك المدة. اضغط على نقطة لترى عددها.',
      'insightsChartLabel': 'نسبة الإصابة عبر الزمن، آخر {period}: الأدنى {low}، الأعلى {high}.',
      'insightsChartPoint': '{rate} · {count} إشارة',
      'insightsChartNoPoints': 'لا توجد إشارات مكتملة كافية لرسم اتجاه.',
      'insightsByInstrument': 'حسب الأداة',
      'insightsByTimeframe': 'حسب الإطار الزمني',
      'insightsSignalsCount': '{count} إشارة',
      'insightsSmallSample': 'عيّنة صغيرة',
      'insightsRowLabel': '{name}: {rate}، {hits} من {count} إشارة بلغت الهدف.',
      'insightsRowEmptyLabel': '{name}: لا إشارات مكتملة.',
      'insightsNoteTitle': 'كيف تقرأ هذه الأرقام',
      'insightsIntro': 'دقة إشارات نموذج الذكاء الاصطناعي. لا تتغير مهما كانت طريقة التحليل التي تختارها.',
      'insightsNoteBody': 'هذا سجل نموذج الذكاء الاصطناعي نفسه، ولا يتأثر بطريقة التحليل في استراتيجيتك. تُحسب فقط الإشارات التي بلغت الهدف أو الوقف؛ الإشارات المفتوحة والمنتهية لا تُحسب. الأرقام المبنية على أقل من {min} إشارات معلَّمة بـ «عيّنة صغيرة». النتائج السابقة ليست وعدًا بنتائج مستقبلية.',
      'insightsSimulatedNote': 'هذه الأرقام محاكاة على هاتفك إلى أن يُربط التطبيق بالخدمة الفعلية.',
      'insightsEmptyTitle': 'لا إشارات مكتملة في هذه الفترة',
      'insightsEmptyBody': 'تُحسب الإشارة هنا عندما تبلغ الهدف أو الوقف.',
      'insightsShowLonger': 'اعرض 90 يومًا',
      'insightsError': 'تعذّر تحميل سجل النموذج.',
      'insightsOfflineBody': 'سيظهر سجل النموذج عند عودة الاتصال.',
      'accuracyOpenHint': 'يفتح أداء النموذج',

      // Backtest
      'strategyTestPast': 'اختبر على بيانات سابقة',
      'strategyTestUsesSaved': 'يستخدم استراتيجيتك المحفوظة. احفظ أولًا لاختبار تعديلاتك.',
      'strategyRemove': 'إزالة الاستراتيجية',
      'strategyRemoved': 'أُزيلت الاستراتيجية. تظهر كل الأدوات.',
      'strategyAllInstruments': 'كل الأدوات',
      'backtestUsingSaved': 'يستخدم استراتيجيتك المحفوظة',
      'backtestUsingDefault': 'يستخدم الاستراتيجية الافتراضية',
      'backtestTitle': 'اختبار تاريخي',
      'backtestDisclaimerSimulated': 'محاكاة · النتائج السابقة ليست وعدًا بنتائج مستقبلية',
      'backtestDisclaimer': 'النتائج السابقة ليست وعدًا بنتائج مستقبلية',
      'backtestIntro': 'شاهد ما آلت إليه الإشارات السابقة المطابقة لاستراتيجيتك.',
      'backtestPeriod1y': 'سنة واحدة',
      'backtestPeriod2y': 'سنتين',
      'backtestPeriod3y': '3 سنوات',
      'backtestPeriod5y': '5 سنوات',
      'backtestStrategyLine': 'الفلاتر: {timeframes} · {directions} · الاحتمال {probability} · العائد : المخاطرة {rr}',
      'backtestRun': 'شغّل الاختبار',
      'backtestPickInstrument': 'اختر أداة واحدة على الأقل.',
      'backtestIdle': 'اختر الأدوات والفترة، ثم شغّل الاختبار.',
      'backtestRunning': 'جارٍ الاختبار على بيانات سابقة…',
      'backtestResults': 'النتائج · آخر {period}',
      'backtestSignals': 'الإشارات',
      'backtestSignalsCaption': 'طابقت استراتيجيتك وبلغت الهدف أو الوقف',
      'backtestHitRate': 'نسبة الإصابة',
      'backtestHitRateCaption': '{hits} من {count} إشارة بلغت الهدف أولًا',
      'backtestAvgRiskReward': 'متوسط العائد : المخاطرة',
      'backtestAvgRiskRewardCaption': 'المخطط له، عبر {count} إشارة',
      'backtestMaxDrawdown': 'أقصى تراجع',
      'backtestMaxDrawdownCaption': 'أكبر هبوط عن أعلى مستوى، عبر {count} إشارة',
      'backtestFigureLabel': '{name}: {value}، {caption}.',
      'backtestR': '{value} R',
      'backtestEquityTitle': 'النتيجة عبر الزمن',
      'backtestEquityCaption': 'بوحدة R، من {count} إشارة. ‏1 R هي قيمة المخاطرة في إشارة واحدة (من الدخول إلى الوقف): الهدف يضيف العائد : المخاطرة، والوقف يطرح 1 R. التكاليف غير محسوبة.',
      'backtestEquityLabel': 'النتيجة عبر الزمن بوحدة R من {count} إشارة: تنتهي عند {end}، الأدنى {low}، الأعلى {high}.',
      'backtestEquityPoint': '{r} · {count} إشارة',
      'backtestEmptyTitle': 'لم تطابق أي إشارة سابقة استراتيجيتك',
      'backtestEmptyBody': 'جرّب أدوات أكثر أو فترة أطول أو فلاتر أوسع في الاستراتيجية.',
      'backtestTryYear': 'جرّب سنة واحدة',
      'backtestError': 'تعذّر تشغيل الاختبار.',
      'backtestOfflineBody': 'سيعمل الاختبار عند عودة الاتصال.',
      'backtestNote': 'تُحسب كل إشارة سابقة عندما تبلغ هدفها أو وقفها؛ الإشارات المفتوحة والمنتهية لا تُحسب. الأرقام المبنية على أقل من {min} إشارات معلَّمة بـ «عيّنة صغيرة». هذا وصف لما مضى، لا لما سيحدث.',
      // Workspaces (D4)
      'workspaces': 'مساحات العمل',
      'workspaceAll': 'كل الأدوات',
      'workspacesIntro': 'اختر ما تعرضه قائمة المتابعة في الرئيسية.',
      'workspacesHint': 'أنشئ قوائمك الخاصة، مثلًا واحدة للذهب وأخرى للعملات الرئيسية.',
      'workspaceChipLabel': 'مساحة العمل: {name}، {count}',
      'workspaceChipHint': 'يفتح مساحات العمل',
      'workspaceNew': 'مساحة عمل جديدة',
      'workspaceEditTitle': 'تعديل مساحة العمل',
      'workspaceEditNamed': 'تعديل {name}',
      'workspaceName': 'الاسم',
      'workspaceNameHint': 'مثلًا: الذهب والعملات الرئيسية',
      'workspaceInstruments': 'الأدوات',
      'workspaceNameRequired': 'أدخل اسمًا.',
      'workspaceNameTooLong': 'استخدم {max} حرفًا أو أقل.',
      'workspaceNameTaken': 'لديك مساحة عمل بهذا الاسم.',
      'workspacePickInstrument': 'اختر أداة واحدة على الأقل.',
      'workspaceLimit': 'يمكنك إنشاء {max} مساحات عمل كحدّ أقصى. احذف واحدة لإضافة أخرى.',
      'workspaceSavedState': 'تم الحفظ',
      'workspaceSaved': 'تم حفظ مساحة العمل',
      'workspaceUpdated': 'تم حفظ التغييرات',
      'workspaceDeleted': 'حُذفت «{name}»',
      'workspaceDeletedActive': 'حُذفت «{name}». تظهر كل الأدوات.',
      'workspaceDelete': 'حذف مساحة العمل',
      'workspaceSwitched': 'الرئيسية تعرض {name}',
      'workspaceBack': 'العودة إلى مساحات العمل',
      'workspaceSaveError': 'تعذّر الحفظ. حاول مرة أخرى.',
      'workspaceEmptyTitle': 'لا توجد أدوات للعرض',
      'workspaceEmptyBody': 'لا تتوفر أي من أدوات مساحة العمل هذه الآن.',
      'workspaceShowAll': 'عرض كل الأدوات',
      'workspaceCount1': 'أداة واحدة',
      'workspaceCount2': 'أداتان',
      'workspaceCountFew': '{count} أدوات',
      'workspaceCountMany': '{count} أداة',
      // اشتراكات الخبراء + المحادثة (T2)
      'expertPricePerMonth': '{price} شهريًا',
      'expertPricePerYear': '{price} سنويًا',
      'expertSubscribed': 'مشترك',
      'expertSubscribedLabel': 'أنت مشترك مع {name}',
      'expertPlanLine': 'الخطة: {plan} · {price}',
      'expertChat': 'محادثة',
      'expertChatWith': 'محادثة {name}',
      'expertSubscribeTo': 'الاشتراك مع {name}',
      'expertUnsubscribe': 'إلغاء الاشتراك',
      'expertUnsubscribeFrom': 'إلغاء الاشتراك مع {name}',
      'expertUnsubscribeTitle': 'إلغاء الاشتراك مع {name}؟',
      'expertUnsubscribeBody': 'ستُغلق محادثتك مع {name}. محاكاة: لا يُحتسب أي مبلغ ولا يُسترد.',
      'expertUnsubscribed': 'أُلغي اشتراكك مع {name}',
      'expertSubscribedSnack': 'اشتركت مع {name}. يمكنك المحادثة الآن.',
      'expertOffline': 'أنت غير متصل. لم يتغيّر شيء.',
      'expertActionFailed': 'لم ينجح ذلك ولم يتغيّر شيء. حاول مجددًا.',
      'subscribeIncluded': 'ما يتضمنه الاشتراك',
      'subscribeIncludesChat': 'محادثة خاصة مع {name}',
      'subscribeAvailability': 'التوفّر: {hint}',
      'subscribeCancelAnytime': 'يمكنك إلغاء الاشتراك في أي وقت',
      'subscribeNote': 'هذه نصيحة من شخص يشارك رأيه الخاص. ليست نصيحة مالية، وهذا التطبيق ليس وسيطًا.',
      'subscribeSimulated': 'محاكاة: لا يُدفع أي مبلغ ولا تُطلب بيانات بطاقة.',
      'subscribeConfirm': 'تأكيد الاشتراك',
      'subscribeOffline': 'أنت غير متصل. لم يُرسل شيء. حاول مجددًا عند الاتصال.',
      'subscribeFailed': 'لم يكتمل الاشتراك ولم يُحتسب أي مبلغ. حاول مجددًا.',
      'chatDisclaimer': 'الخبراء يشاركون آراءهم، وليست نصيحة مالية. لسنا وسيطًا.',
      'chatEmptyTitle': 'ابدأ المحادثة',
      'chatEmptyBody': 'اسأل {name} عن قراءة زوج ما أو عن إدارة المخاطر. الردود هنا محاكاة.',
      'chatHint': 'رسالة إلى {name}',
      'chatSend': 'إرسال',
      'chatSending': 'جارٍ الإرسال',
      'chatSent': 'أُرسلت',
      'chatNotSent': 'لم تُرسل',
      'chatOffline': 'أنت غير متصل. لا يمكن إرسال الرسائل، ومسودتك تبقى هنا.',
      'chatSimulatedReply': 'رد محاكى',
      'chatMessageMine': 'أنت، {time}: {body}. {status}',
      'chatMessageTheirs': '{name}، {time}: {body}. رد محاكى',
      'chatLatest': 'الانتقال إلى أحدث رسالة',
      'chatLockedTitle': 'اشترك لمحادثة {name}',
      'chatLockedBody': 'المحادثة جزء من خطة {name}. الاشتراكات هنا محاكاة: لا يُدفع أي مبلغ.',
      'chatLoadError': 'تعذّر تحميل المحادثة.',
      'chatOfflineBody': 'ستظهر المحادثة عند عودة الاتصال.',
      'chatNotFound': 'هذا الخبير لم يعد مدرجًا',
      'chatCount': '{count} من {max} حرفًا',
      // توقّع النموذج على رسم الأداة (H1)
      'forecastToggle': 'التوقّع',
      'forecastToggleLoading': 'التوقّع، قيد التحميل',
      'forecastLabel': 'توقّع النموذج · {probability} · {direction}',
      'forecastLikelihoodHigh': 'مرتفع',
      'forecastLikelihoodModerate': 'متوسط',
      'forecastLikelihoodLow': 'منخفض',
      'forecastDetail': 'المستوى المتوقّع {price} بحلول {time}، خلال الشموع القادمة ({count}). الاحتمال {likelihood} ({probability}) حسب النموذج.',
      'forecastChartLabel': 'توقّع النموذج: {direction}، احتمال {likelihood} ({probability}). المستوى المتوقّع {price} بحلول {time}.',
      'forecastReadout': 'توقّع النموذج',
      'forecastExpected': 'المتوقّع',
      'forecastRange': 'النطاق',
      'forecastOutdated': 'قديم',
      'forecastOutdatedBody': 'انتهت صلاحية هذا التوقّع، لذلك لم يعد مرسومًا.',
      'forecastRefresh': 'تحديث التوقّع',
      'forecastNone': 'لا يوجد توقّع الآن',
      'forecastNoneBody': 'لا ترى استراتيجيتك فرصة واضحة الآن. وهذه إجابة صحيحة.',
      'forecastTimeframeBody': 'غير متاح لهذا الإطار. التوقّعات متاحة على {timeframes}.',
      'forecastListSeparator': '، ',
      'forecastFollows': 'يتبع إشارة استراتيجيتك على {basis}، باحتمال أقل على {timeframe}.',
      'forecastError': 'تعذّر تحميل التوقّع.',
      'forecastOffline': 'أنت غير متصل، لذلك التوقّع مخفي. سيعود عند عودة الاتصال.',
      // ربط تيليغرام وإذن الإشعارات (H4b)
      'telegramNotConnected': 'غير مربوط',
      'telegramConnectFirst': 'اربط تيليغرام أولًا لتشغيل هذه القناة.',
      'telegramConnected': 'مربوط',
      'telegramConnectedAs': 'مربوط بالحساب {handle}',
      'telegramConnect': 'ربط تيليغرام',
      'telegramDisconnect': 'فك الربط',
      'telegramDisconnectLabel': 'فك ربط تيليغرام',
      'telegramDisconnectedSnack': 'تم فك ربط تيليغرام. إشعارات تيليغرام متوقفة.',
      'telegramConnectedSnack': 'تم ربط تيليغرام. إشعارات تيليغرام مفعّلة.',
      'telegramRestoredSnack': 'عاد ربط تيليغرام',
      'telegramOffline': 'أنت غير متصل، لذلك لم يُرسل شيء. حاول مجددًا عند عودة الاتصال.',
      'telegramStatusError': 'تعذّر التحقق من ربط تيليغرام.',
      'telegramStatusLoading': 'جارٍ التحقق من ربط تيليغرام',
      'telegramSheetIntro': 'أرسل هذا الرمز لمرة واحدة إلى البوت في تيليغرام. سيربط حسابك في تيليغرام بهذا الحساب لتصلك الإشعارات هناك.',
      'telegramStepBot': '1. افتح البوت في تيليغرام',
      'telegramStepCode': '2. أرسل له هذا الرمز',
      'telegramStepCheck': '3. عُد إلى هنا وتحقّق من الربط',
      'telegramBotLabel': 'بوت تيليغرام {name}',
      'telegramCodeLabel': 'الرمز لمرة واحدة {code}',
      'telegramValidFor': 'صالح لمدة {time}',
      'telegramValidMinutes': 'صالح لنحو {minutes} دقيقة',
      'telegramValidUnderMinute': 'صالح لأقل من دقيقة',
      'telegramOneMinuteLeft': 'بقيت دقيقة واحدة لاستخدام الرمز',
      'telegramCopy': 'نسخ',
      'telegramCopied': 'تم النسخ',
      'telegramCopyCode': 'نسخ الرمز',
      'telegramCopyBot': 'نسخ اسم البوت',
      'telegramCodeCopied': 'تم نسخ الرمز',
      'telegramBotCopied': 'تم نسخ اسم البوت',
      'telegramCheck': 'التحقق من الربط',
      'telegramCodeExpired': 'انتهت صلاحية الرمز',
      'telegramCodeExpiredBody': 'لم يعد بالإمكان استخدام هذا الرمز. احصل على رمز جديد للربط.',
      'telegramNewCode': 'الحصول على رمز جديد',
      'telegramNotYet': 'لم يتم الربط بعد. أرسل الرمز إلى البوت، ثم تحقّق مجددًا.',
      'telegramFailed': 'حدث خطأ ما. حاول مجددًا.',
      'telegramGettingCode': 'جارٍ تجهيز الرمز',
      'telegramSheetNote': 'يمكنك فك الربط في أي وقت من تفضيلات الإشعارات.',
      'pushNotAllowed': 'غير مسموح على هذا الهاتف',
      'pushSettingsHint': 'لاستخدام الإشعارات الفورية، اسمح بإشعارات هذا التطبيق من إعدادات هاتفك.',
      'pushWhyTitle': 'لماذا نطلب الإذن',
      'pushWhyBody': 'سيطلب هاتفك السماح بالإشعارات. عند السماح بها يمكن لهذا الهاتف أن يعرض:',
      'pushWhyAlerts': 'تنبيهات السعر عند الوصول إلى المستوى',
      'pushWhyOpportunities': 'الفرص الجديدة من استراتيجيتك',
      'pushWhyControl': 'تختار الأنواع من هنا ويمكنك إيقاف الإشعارات الفورية في أي وقت.',
      'pushWhyNote': 'قد تتأخر الإشعارات أو لا تصل، لذلك راجع التطبيق لمعرفة الأحدث.',
      'pushWhyContinue': 'متابعة',
      'pushWhyNotNow': 'ليس الآن',
      'pushTurnedOn': 'الإشعارات الفورية مفعّلة',
    },
  };

  String _v(String key) {
    return _values[locale.languageCode]?[key] ?? _values['en']![key] ?? key;
  }

  /// استبدال placeholders بالشكل {name} داخل نص مترجم (مثلاً
  /// fieldRequired: '{field} is required')
  String _f(String key, Map<String, String> args) {
    var result = _v(key);
    args.forEach((k, v) {
      result = result.replaceAll('{$k}', v);
    });
    return result;
  }

  // ── Getters ──────────────────────────────────────────────

  String get cancel => _v('cancel');
  String get trader => _v('trader');

  String get email => _v('email');
  String get password => _v('password');

  String get confirmPassword => _v('confirmPassword');

  String get verify => _v('verify');

  String get emailRequired => _v('emailRequired');
  String get enterValidEmail => _v('enterValidEmail');
  String get passwordRequired => _v('passwordRequired');
  String get passwordMinChars => _v('passwordMinChars');
  String get passwordNeedsNumber => _v('passwordNeedsNumber');
  String get passwordRequirementsHint => _v('passwordRequirementsHint');
  String get pleaseConfirmPassword => _v('pleaseConfirmPassword');
  String get passwordsDoNotMatch => _v('passwordsDoNotMatch');
  String get thisFieldRequired => _v('thisFieldRequired');
  String fieldRequired(String field) => _f('fieldRequired', {'field': field});



  String get mediumImpact => _v('mediumImpact');


  String get notificationPreferences => _v('notificationPreferences');
  String get chooseAlerts => _v('chooseAlerts');
  String get logOut => _v('logOut');
  String get confirmLogOut => _v('confirmLogOut');
  String get guestEmail => _v('guestEmail');
  String get language => _v('language');
  String get chooseAppLanguage => _v('chooseAppLanguage');
  String get english => _v('english');
  String get arabic => _v('arabic');

  String get passwordUpdatedSuccessfully => _v('passwordUpdatedSuccessfully');
  String get couldNotUpdatePassword => _v('couldNotUpdatePassword');
  String get changePassword => _v('changePassword');
  String get currentPassword => _v('currentPassword');
  String get newPassword => _v('newPassword');
  String get confirmNewPassword => _v('confirmNewPassword');
  String get updatePassword => _v('updatePassword');

  String get profileUpdatedSuccessfully => _v('profileUpdatedSuccessfully');
  String get couldNotSaveChanges => _v('couldNotSaveChanges');
  String get takeAPhoto => _v('takeAPhoto');
  String get chooseFromGallery => _v('chooseFromGallery');
  String get removeCurrentPhoto => _v('removeCurrentPhoto');
  String get displayName => _v('displayName');
  String get enterYourName => _v('enterYourName');
  String get enterYourEmail => _v('enterYourEmail');
  String get saveChanges => _v('saveChanges');
  String get name => _v('name');

  String get version => _v('version');
  String get legal => _v('legal');
  String get riskDisclosure => _v('riskDisclosure');

  String get frequentlyAskedQuestions => _v('frequentlyAskedQuestions');






  String get price => _v('price');
  String get confirm => _v('confirm');

  String get justNow => _v('justNow');

  String get commentAuthorYou => _v('commentAuthorYou');
  String minutesAgo(int minutes) => _f('minutesAgo', {'minutes': '$minutes'});
  String hoursAgo(int hours) => _f('hoursAgo', {'hours': '$hours'});
  String daysAgo(int days) => _f('daysAgo', {'days': '$days'});
  String get commentText1 => _v('commentText1');
  String get commentText2 => _v('commentText2');
  String get commentText3 => _v('commentText3');
  String get commentText4 => _v('commentText4');
  String get commentText5 => _v('commentText5');

  String get newsFedTitle => _v('newsFedTitle');
  String get newsFedDescription => _v('newsFedDescription');
  String get newsFedContent => _v('newsFedContent');
  String get newsEcbTitle => _v('newsEcbTitle');
  String get newsEcbDescription => _v('newsEcbDescription');
  String get newsEcbContent => _v('newsEcbContent');
  String get newsGoldTitle => _v('newsGoldTitle');
  String get newsGoldDescription => _v('newsGoldDescription');
  String get newsGoldContent => _v('newsGoldContent');
  String get newsUkTitle => _v('newsUkTitle');
  String get newsUkDescription => _v('newsUkDescription');
  String get newsUkContent => _v('newsUkContent');

  String get sentimentNeutral => _v('sentimentNeutral');


  String commentsCount(int count) => _f('commentsCount', {'count': '$count'});


  String get notifications => _v('notifications');

  String get notifWelcomeTitle => _v('notifWelcomeTitle');

  String get pushNotifications => _v('pushNotifications');
  String get other => _v('other');

  // Membership (redesign 2026-10)
  String get memPricingTba => _v('memPricingTba');
  String get memNoPayment => _v('memNoPayment');
  String get memCtaHint => _v('memCtaHint');
  String get memEssentialName => _v('memEssentialName');
  String get memEssentialTagline => _v('memEssentialTagline');
  String get memEssentialAudience => _v('memEssentialAudience');
  String get memEssentialH1 => _v('memEssentialH1');
  String get memEssentialH2 => _v('memEssentialH2');
  String get memEssentialH3 => _v('memEssentialH3');
  String get memEssentialH4 => _v('memEssentialH4');
  String get memEssentialCta => _v('memEssentialCta');
  String get memProfessionalName => _v('memProfessionalName');
  String get memProfessionalTagline => _v('memProfessionalTagline');
  String get memProfessionalAudience => _v('memProfessionalAudience');
  String get memProfessionalH1 => _v('memProfessionalH1');
  String get memProfessionalH2 => _v('memProfessionalH2');
  String get memProfessionalH3 => _v('memProfessionalH3');
  String get memProfessionalH4 => _v('memProfessionalH4');
  String get memProfessionalCta => _v('memProfessionalCta');
  String get memEliteName => _v('memEliteName');
  String get memEliteTagline => _v('memEliteTagline');
  String get memEliteAudience => _v('memEliteAudience');
  String get memEliteH1 => _v('memEliteH1');
  String get memEliteH2 => _v('memEliteH2');
  String get memEliteH3 => _v('memEliteH3');
  String get memEliteH4 => _v('memEliteH4');
  String get memEliteCta => _v('memEliteCta');
  String get memFWorkspace => _v('memFWorkspace');
  String get memFInstruments => _v('memFInstruments');
  String get memFTimeframes => _v('memFTimeframes');
  String get memFAiAnalysis => _v('memFAiAnalysis');
  String get memFExplanations => _v('memFExplanations');
  String get memFTfAlignment => _v('memFTfAlignment');
  String get memFSignalFilters => _v('memFSignalFilters');
  String get memFWatchlist => _v('memFWatchlist');
  String get memFRiskTools => _v('memFRiskTools');
  String get memFAnalytics => _v('memFAnalytics');
  String get memFAlerts => _v('memFAlerts');
  String get memFAlertDelivery => _v('memFAlertDelivery');
  String get memFAssistant => _v('memFAssistant');
  String get memFResearchHistory => _v('memFResearchHistory');
  String get memFSavedWorkspaces => _v('memFSavedWorkspaces');
  String get memScopeGold => _v('memScopeGold');
  String get memScopeAllInstruments => _v('memScopeAllInstruments');
  String get memScopeTimeframes => _v('memScopeTimeframes');
  String get memScopeOneWorkspace => _v('memScopeOneWorkspace');
  String get memScopeMultipleWorkspaces => _v('memScopeMultipleWorkspaces');
  String get memIncluded => _v('memIncluded');
  String get memNotIncluded => _v('memNotIncluded');
  String get memGroupResearch => _v('memGroupResearch');
  String get memGroupPersonalisation => _v('memGroupPersonalisation');
  String get memGroupRiskReview => _v('memGroupRiskReview');
  String get memGroupAssistantWorkflow => _v('memGroupAssistantWorkflow');
  String get memStatusLegend => _v('memStatusLegend');
  String get memStatusAvailable => _v('memStatusAvailable');
  String get memStatusAvailableDesc => _v('memStatusAvailableDesc');
  String get memStatusDemo => _v('memStatusDemo');
  String get memStatusDemoDesc => _v('memStatusDemoDesc');
  String get memStatusBackend => _v('memStatusBackend');
  String get memStatusBackendDesc => _v('memStatusBackendDesc');
  String get memStatusPlanned => _v('memStatusPlanned');
  String get memStatusPlannedDesc => _v('memStatusPlannedDesc');
  String get memCompareEyebrow => _v('memCompareEyebrow');
  String get memComparePlan => _v('memComparePlan');
  String get memFaqEyebrow => _v('memFaqEyebrow');
  String get memFaqCostQ => _v('memFaqCostQ');
  String get memFaqCostA => _v('memFaqCostA');
  String get memFaqSubscribeQ => _v('memFaqSubscribeQ');
  String get memFaqSubscribeA => _v('memFaqSubscribeA');
  String get memFaqDemoQ => _v('memFaqDemoQ');
  String get memFaqDemoA => _v('memFaqDemoA');
  String get memFaqLimitQ => _v('memFaqLimitQ');
  String get memFaqLimitA => _v('memFaqLimitA');
  String get memFaqRiskQ => _v('memFaqRiskQ');
  String get memFaqRiskA => _v('memFaqRiskA');
  String get memSheetTitle => _v('memSheetTitle');
  String get memSheetSelectedPlan => _v('memSheetSelectedPlan');
  String get memActivationTitle => _v('memActivationTitle');
  String get memActivationBody => _v('memActivationBody');
  String get memClose => _v('memClose');
  String get memCurrentPlan => _v('memCurrentPlan');

  // Markets (redesign 2026-10)
  String get selected => _v('selected');

  /// الاسم الكامل للأداة ("Euro / US Dollar") - الرمز نفسه لو ما إلها ترجمة
  String instrumentName(String symbol) {
    final key = 'instrument${symbol.replaceAll('/', '')}';
    return _values[locale.languageCode]?[key] ?? _values['en']?[key] ?? symbol;
  }

  // Shell + Profile (redesign 2026-10)
  String get backToHome => _v('backToHome');
  String get navHome => _v('navHome');
  String get navSignals => _v('navSignals');
  String get navAssistant => _v('navAssistant');
  String get navCommunity => _v('navCommunity');
  String get navProfile => _v('navProfile');
  String get preferences => _v('preferences');
  String get roleTrader => _v('roleTrader');
  String get roleExpert => _v('roleExpert');
  String get roleAdmin => _v('roleAdmin');
  String get toolExperts => _v('toolExperts');
  String get toolPlans => _v('toolPlans');
  String get toolPlansSubtitle => _v('toolPlansSubtitle');
  String get appearanceSubtitle => _v('appearanceSubtitle');
  String get editProfileHint => _v('editProfileHint');
  String get loggingOut => _v('loggingOut');
  String get offlineBannerTitle => _v('offlineBannerTitle');
  String get offlineBannerBody => _v('offlineBannerBody');
  String get signalsEmptyTitle => _v('signalsEmptyTitle');
  String get signalsEmptyBody => _v('signalsEmptyBody');
  String get developer => _v('developer');
  String get simulateOffline => _v('simulateOffline');
  String get simulateOfflineSubtitle => _v('simulateOfflineSubtitle');

  // FX sessions (redesign 2026-10)
  String get sessionSydney => _v('sessionSydney');
  String get sessionTokyo => _v('sessionTokyo');
  String get sessionLondon => _v('sessionLondon');
  String get sessionNewYork => _v('sessionNewYork');
  String get sessionSummaryClosed => _v('sessionSummaryClosed');
  String get sessionSummaryBetween => _v('sessionSummaryBetween');
  String sessionSummaryOne(String name) => _f('sessionSummaryOne', {'name': name});
  String sessionSummaryOverlap(String names) => _f('sessionSummaryOverlap', {'names': names});
  String get directionLong => _v('directionLong');
  String get directionShort => _v('directionShort');
  String get directionNeutral => _v('directionNeutral');

  // Home + Market (redesign 2026-10, stage A)
  String get ohlcOpen => _v('ohlcOpen');
  String get ohlcHigh => _v('ohlcHigh');
  String get ohlcLow => _v('ohlcLow');
  String get ohlcClose => _v('ohlcClose');
  String get watchlist => _v('watchlist');
  String get noSetup => _v('noSetup');
  String modelReadLabel(String direction, String probability, String timeframe) => _f('modelReadLabel', {'direction': direction, 'probability': probability, 'timeframe': timeframe});
  String get noSetupLabel => _v('noSetupLabel');
  String get watchlistEmpty => _v('watchlistEmpty');
  String get watchlistEmptyBody => _v('watchlistEmptyBody');
  String get watchlistError => _v('watchlistError');
  String get openChartHint => _v('openChartHint');
  String notificationsUnread(String count) => _f('notificationsUnread', {'count': count});
  String get feedConnecting => _v('feedConnecting');
  String get feedLive => _v('feedLive');
  String get feedDelayed => _v('feedDelayed');
  String get feedStale => _v('feedStale');
  String get feedMarketClosed => _v('feedMarketClosed');
  String get feedOffline => _v('feedOffline');
  String get feedError => _v('feedError');
  String lastUpdated(String time) => _f('lastUpdated', {'time': time});
  String get oldData => _v('oldData');
  String get marketOfflineNoCache => _v('marketOfflineNoCache');
  String get chartOfflineNoCache => _v('chartOfflineNoCache');
  String get marketRefreshOffline => _v('marketRefreshOffline');
  String get clearMarketCache => _v('clearMarketCache');
  String get clearMarketCacheSubtitle => _v('clearMarketCacheSubtitle');
  String get marketCacheCleared => _v('marketCacheCleared');
  String get marketCacheClearFailed => _v('marketCacheClearFailed');
  String get newsOfflineNoCache => _v('newsOfflineNoCache');
  String get newsRefreshOffline => _v('newsRefreshOffline');
  String get notificationsOfflineNoCache => _v('notificationsOfflineNoCache');
  String get notificationsRefreshOffline => _v('notificationsRefreshOffline');
  String get signalsRefreshOffline => _v('signalsRefreshOffline');
  String get commentsOffline => _v('commentsOffline');
  String get commentsOfflineAction => _v('commentsOfflineAction');
  String get alertsOfflineAction => _v('alertsOfflineAction');
  String get lowDataMode => _v('lowDataMode');
  String get lowDataModeSubtitle => _v('lowDataModeSubtitle');
  String get lowDataPillLabel => _v('lowDataPillLabel');
  String get lowDataSuggestTitle => _v('lowDataSuggestTitle');
  String get lowDataSuggestMobile => _v('lowDataSuggestMobile');
  String get lowDataSuggestSlow => _v('lowDataSuggestSlow');
  String get lowDataTurnOn => _v('lowDataTurnOn');
  String get lowDataNotNow => _v('lowDataNotNow');
  String get lowDataTurnedOn => _v('lowDataTurnedOn');
  String feedStatusLabel(String status) => _f('feedStatusLabel', {'status': status});
  String get change24h => _v('change24h');
  String get chartCandles => _v('chartCandles');
  String get chartLine => _v('chartLine');
  String get chartArea => _v('chartArea');
  String get chartType => _v('chartType');
  String get timeframe => _v('timeframe');
  String get indicators => _v('indicators');
  String indicatorsCount(String count) => _f('indicatorsCount', {'count': count});
  String get indSma => _v('indSma');
  String get indSmaHint => _v('indSmaHint');
  String get indEma => _v('indEma');
  String get indEmaHint => _v('indEmaHint');
  String get indBollinger => _v('indBollinger');
  String get indBollingerHint => _v('indBollingerHint');
  String get indRsi => _v('indRsi');
  String get indRsiHint => _v('indRsiHint');
  String get indMacd => _v('indMacd');
  String get indMacdHint => _v('indMacdHint');
  String get indicatorsNote => _v('indicatorsNote');
  String get done => _v('done');
  String get chartEmpty => _v('chartEmpty');
  String get chartError => _v('chartError');
  String chartLabel(String symbol, String timeframe, String price, String change, String high, String low) =>
      _f('chartLabel', {'symbol': symbol, 'timeframe': timeframe, 'price': price, 'change': change, 'high': high, 'low': low});
  String get zoneEntry => _v('zoneEntry');
  String get zoneTarget => _v('zoneTarget');
  String get zoneStop => _v('zoneStop');
  String get modelRead => _v('modelRead');
  String get probabilityCaption => _v('probabilityCaption');
  String get riskRewardLabel => _v('riskRewardLabel');
  String timeframesAgree(String count, String total) => _f('timeframesAgree', {'count': count, 'total': total});
  String validUntil(String time) => _f('validUntil', {'time': time});
  String get noSetupTitle => _v('noSetupTitle');
  String get noSetupBody => _v('noSetupBody');
  String get signalDisclaimer => _v('signalDisclaimer');
  String showReadOnChart(String timeframe) => _f('showReadOnChart', {'timeframe': timeframe});
  String readNoSetup(String timeframe) => _f('readNoSetup', {'timeframe': timeframe});
  String get setAlert => _v('setAlert');
  String get priceAlert => _v('priceAlert');
  String get alertTargetLabel => _v('alertTargetLabel');
  String alertNow(String price) => _f('alertNow', {'price': price});
  String alertRisesTo(String price) => _f('alertRisesTo', {'price': price});
  String alertFallsTo(String price) => _f('alertFallsTo', {'price': price});
  String get alertNote => _v('alertNote');
  String get alertCreate => _v('alertCreate');
  String alertCreated(String symbol, String price) => _f('alertCreated', {'symbol': symbol, 'price': price});
  String get alertDelivery => _v('alertDelivery');
  String get alertErrorEmpty => _v('alertErrorEmpty');
  String get alertErrorInvalid => _v('alertErrorInvalid');
  String get alertErrorPositive => _v('alertErrorPositive');
  String get alertErrorCurrent => _v('alertErrorCurrent');
  String get alertCreateFailed => _v('alertCreateFailed');
  String get yourAlerts => _v('yourAlerts');
  String get alertActive => _v('alertActive');
  String get alertPaused => _v('alertPaused');
  String get alertTriggered => _v('alertTriggered');
  String get alertPause => _v('alertPause');
  String get alertResume => _v('alertResume');
  String get alertDelete => _v('alertDelete');
  String get alertDeleted => _v('alertDeleted');
  String get alertActionFailed => _v('alertActionFailed');
  String get undo => _v('undo');
  String alertRowRises(String price) => _f('alertRowRises', {'price': price});
  String alertRowFalls(String price) => _f('alertRowFalls', {'price': price});
  String alertRowLabel(String rule, String state) => _f('alertRowLabel', {'rule': rule, 'state': state});
  // H4a
  String get alertExpired => _v('alertExpired');
  String alertTriggeredAt(String price) => _f('alertTriggeredAt', {'price': price});
  String alertUntil(String time) => _f('alertUntil', {'time': time});
  String get alertWaitsForCross => _v('alertWaitsForCross');
  String get alertSetAgain => _v('alertSetAgain');
  String get alertsActiveHeading => _v('alertsActiveHeading');
  String get alertsHistoryHeading => _v('alertsHistoryHeading');
  String get alertsNoActive => _v('alertsNoActive');
  String get alertExpiryLabel => _v('alertExpiryLabel');
  String get alertExpiryNone => _v('alertExpiryNone');
  String get alertExpiryDay => _v('alertExpiryDay');
  String get alertExpiryWeek => _v('alertExpiryWeek');
  String get alertExpiryMonth => _v('alertExpiryMonth');
  String get alertExpiryHint => _v('alertExpiryHint');
  String get alertsOffline => _v('alertsOffline');
  String notifAlertTriggeredTitle(String symbol, String level) =>
      _f('notifAlertTriggeredTitle', {'symbol': symbol, 'level': level});
  String notifAlertTriggeredBody(String price) => _f('notifAlertTriggeredBody', {'price': price});
  String get workspaceUndo => _v('workspaceUndo');
  String get workspaceRedo => _v('workspaceRedo');
  String get workspaceUndoLabel => _v('workspaceUndoLabel');
  String get workspaceRedoLabel => _v('workspaceRedoLabel');
  String get workspaceUndone => _v('workspaceUndone');
  String get workspaceRedone => _v('workspaceRedone');

  // Design system (redesign 2026-10)
  String get appName => _v('appName');
  String get appTagline => _v('appTagline');
  String get appearance => _v('appearance');
  String get themeLight => _v('themeLight');
  String get themeDark => _v('themeDark');
  String get themeSystem => _v('themeSystem');
  String get sourceLive => _v('sourceLive');
  String get sourceHistorical => _v('sourceHistorical');
  String get sourceModel => _v('sourceModel');
  String get sourceUser => _v('sourceUser');
  String get sourceDemo => _v('sourceDemo');
  String get sourceUnavailable => _v('sourceUnavailable');
  String get directionUp => _v('directionUp');
  String get directionDown => _v('directionDown');
  String get directionFlat => _v('directionFlat');
  String get tryAgain => _v('tryAgain');
  String get somethingWentWrong => _v('somethingWentWrong');
  String get loading => _v('loading');
  String get showPassword => _v('showPassword');
  String get hidePassword => _v('hidePassword');

  // Profile + Settings (redesign 2026-10, stage B)
  String get profilePlan => _v('profilePlan');
  String get passwordAndSecurity => _v('passwordAndSecurity');
  String get passwordAndSecuritySubtitle => _v('passwordAndSecuritySubtitle');
  String get settings => _v('settings');
  String get settingsSubtitle => _v('settingsSubtitle');
  String get helpAndAbout => _v('helpAndAbout');
  String get helpAndAboutSubtitle => _v('helpAndAboutSubtitle');
  String get save => _v('save');
  String get changePhoto => _v('changePhoto');
  String get discardChangesTitle => _v('discardChangesTitle');
  String get discardChangesBody => _v('discardChangesBody');
  String get discard => _v('discard');
  String get keepEditing => _v('keepEditing');
  String get changePasswordIntro => _v('changePasswordIntro');
  String get riskGroup => _v('riskGroup');
  String get riskLimits => _v('riskLimits');
  String get riskLimitsIntro => _v('riskLimitsIntro');
  String riskLimitsSummary(String capital, String perTrade, String daily) => _f('riskLimitsSummary', {'capital': capital, 'perTrade': perTrade, 'daily': daily});
  String riskLimitsSummaryNoCapital(String perTrade, String daily) => _f('riskLimitsSummaryNoCapital', {'perTrade': perTrade, 'daily': daily});
  String get riskCapitalLabel => _v('riskCapitalLabel');
  String get riskCapitalHelper => _v('riskCapitalHelper');
  String get riskPerTradeLabel => _v('riskPerTradeLabel');
  String get riskDailyLabel => _v('riskDailyLabel');
  String get riskErrCapital => _v('riskErrCapital');
  String riskErrRange(String min, String max) => _f('riskErrRange', {'min': min, 'max': max});
  String get riskErrDailyBelow => _v('riskErrDailyBelow');
  String get riskLimitsSaved => _v('riskLimitsSaved');
  String get notifChannels => _v('notifChannels');
  String get notifKinds => _v('notifKinds');
  String get channelPush => _v('channelPush');
  String get channelPushHint => _v('channelPushHint');
  String get channelInApp => _v('channelInApp');
  String get channelInAppHint => _v('channelInAppHint');
  String get channelEmail => _v('channelEmail');
  String get channelEmailHint => _v('channelEmailHint');
  String get channelTelegram => _v('channelTelegram');
  String get channelTelegramHint => _v('channelTelegramHint');
  String get kindPriceAlert => _v('kindPriceAlert');
  String get kindPriceAlertHint => _v('kindPriceAlertHint');
  String get kindOpportunity => _v('kindOpportunity');
  String get kindOpportunityHint => _v('kindOpportunityHint');
  String get kindSystem => _v('kindSystem');
  String get kindSystemHint => _v('kindSystemHint');
  String get notifMuted => _v('notifMuted');
  String get notifPrefsNote => _v('notifPrefsNote');
  String get aboutShort => _v('aboutShort');
  String get neverTradesTitle => _v('neverTradesTitle');
  String get neverTradesBody => _v('neverTradesBody');
  String get faqModelReadQ => _v('faqModelReadQ');
  String get faqModelReadA => _v('faqModelReadA');
  String get faqSimulatedQ => _v('faqSimulatedQ');
  String get faqSimulatedA => _v('faqSimulatedA');
  String get faqAccuracyQ => _v('faqAccuracyQ');
  String get faqAccuracyA => _v('faqAccuracyA');
  String get faqStrategyQ => _v('faqStrategyQ');
  String get faqStrategyA => _v('faqStrategyA');
  String get thirdPartyNotices => _v('thirdPartyNotices');
  String get thirdPartyNoticesSubtitle => _v('thirdPartyNoticesSubtitle');
  String versionLine(String version, String build) => _f('versionLine', {'version': version, 'build': build});
  String get legalDataTitle => _v('legalDataTitle');
  String get legalUpdated => _v('legalUpdated');
  String get legalRiskIntro => _v('legalRiskIntro');
  String get legalRisk1Title => _v('legalRisk1Title');
  String get legalRisk1Body => _v('legalRisk1Body');
  String get legalRisk2Title => _v('legalRisk2Title');
  String get legalRisk2Body => _v('legalRisk2Body');
  String get legalRisk3Title => _v('legalRisk3Title');
  String get legalRisk3Body => _v('legalRisk3Body');
  String get legalRisk4Title => _v('legalRisk4Title');
  String get legalRisk4Body => _v('legalRisk4Body');
  String get legalRisk5Title => _v('legalRisk5Title');
  String get legalRisk5Body => _v('legalRisk5Body');
  String get legalRisk6Title => _v('legalRisk6Title');
  String get legalRisk6Body => _v('legalRisk6Body');
  String get legalDataIntro => _v('legalDataIntro');
  String get legalData1Title => _v('legalData1Title');
  String get legalData1Body => _v('legalData1Body');
  String get legalData2Title => _v('legalData2Title');
  String get legalData2Body => _v('legalData2Body');
  String get legalData3Title => _v('legalData3Title');
  String get legalData3Body => _v('legalData3Body');
  String get communityNews => _v('communityNews');
  String get expertsIntro => _v('expertsIntro');
  String get expertsEmpty => _v('expertsEmpty');
  String expertMarkets(String markets) => _f('expertMarkets', {'markets': markets});
  String get expertSubscribe => _v('expertSubscribe');
  String accuracyLine(String rate, String count, String days) => _f('accuracyLine', {'rate': rate, 'count': count, 'days': days});
  String accuracyNoResults(String days) => _f('accuracyNoResults', {'days': days});
  String get accuracyCaption => _v('accuracyCaption');
  String get accuracyError => _v('accuracyError');
  String get strategyIntro => _v('strategyIntro');
  String get strategyInstruments => _v('strategyInstruments');
  String get strategyTimeframes => _v('strategyTimeframes');
  String get strategyDirections => _v('strategyDirections');
  String get strategyMinProbability => _v('strategyMinProbability');
  String get strategyMinRiskReward => _v('strategyMinRiskReward');
  String get strategyAny => _v('strategyAny');
  String get strategyRiskFit => _v('strategyRiskFit');
  String get strategyRiskFitHint => _v('strategyRiskFitHint');
  String get strategyRiskFitNoCapital => _v('strategyRiskFitNoCapital');
  String get strategyPickOne => _v('strategyPickOne');
  String get strategyReset => _v('strategyReset');
  String get strategySaved => _v('strategySaved');
  String get strategySavedState => _v('strategySavedState');
  String get sizeTrade => _v('sizeTrade');
  String sizeFromRead(String timeframe) => _f('sizeFromRead', {'timeframe': timeframe});
  String get sizePosition => _v('sizePosition');
  String sizeUnits(String units, String currency) => _f('sizeUnits', {'units': units, 'currency': currency});
  String sizeOunces(String units) => _f('sizeOunces', {'units': units});
  String get sizeMoneyAtRisk => _v('sizeMoneyAtRisk');
  String get sizeStopDistance => _v('sizeStopDistance');
  String sizePips(String pips) => _f('sizePips', {'pips': pips});
  String get sizeReward => _v('sizeReward');
  String get sizeRiskLabel => _v('sizeRiskLabel');
  String get sizeTargetLabel => _v('sizeTargetLabel');
  String get sizeCapitalHint => _v('sizeCapitalHint');
  String get sizeIncomplete => _v('sizeIncomplete');
  String get sizeErrStopEqual => _v('sizeErrStopEqual');
  String get sizeErrTarget => _v('sizeErrTarget');
  String get sizeErrRisk => _v('sizeErrRisk');
  String get sizeNote => _v('sizeNote');
  String get limitWithin => _v('limitWithin');
  String get limitNear => _v('limitNear');
  String get limitBreach => _v('limitBreach');
  String limitDetail(String risk, String limit) => _f('limitDetail', {'risk': risk, 'limit': limit});

  // Auth, Assistant, Notifications, News (redesign 2026-10, stage C)
  String get welcomeBody => _v('welcomeBody');
  String get createAccountAction => _v('createAccountAction');
  String get logIn => _v('logIn');
  String get haveAccount => _v('haveAccount');
  String get noAccount => _v('noAccount');
  String get registerTitle => _v('registerTitle');
  String get fullName => _v('fullName');
  String get fullNameRequired => _v('fullNameRequired');
  String get fullNameTooLong => _v('fullNameTooLong');
  String get confirmPasswordLabel => _v('confirmPasswordLabel');
  String get passwordCheckLength => _v('passwordCheckLength');
  String get passwordCheckLetter => _v('passwordCheckLetter');
  String get passwordCheckNumber => _v('passwordCheckNumber');
  String get passwordMaxChars => _v('passwordMaxChars');
  String get passwordNeedsLetter => _v('passwordNeedsLetter');
  String get checkMet => _v('checkMet');
  String get checkNotMet => _v('checkNotMet');
  String get registerAdviceAck => _v('registerAdviceAck');
  String get registerAdviceRequired => _v('registerAdviceRequired');
  String get registerFailed => _v('registerFailed');
  String get loginTitle => _v('loginTitle');
  String get loginFailed => _v('loginFailed');
  String get otpTitle => _v('otpTitle');
  String get otpBody => _v('otpBody');
  String get otpLabel => _v('otpLabel');
  String get otpIncomplete => _v('otpIncomplete');
  String get otpSimulated => _v('otpSimulated');
  String get otpVerify => _v('otpVerify');
  String otpResendIn(String time) => _f('otpResendIn', {'time': time});
  String get otpResend => _v('otpResend');
  String get otpResent => _v('otpResent');
  String get otpDoneTitle => _v('otpDoneTitle');
  String get otpDoneBody => _v('otpDoneBody');
  String get otpContinue => _v('otpContinue');
  String get notifInbox => _v('notifInbox');
  String notifInboxCount(String count) => _f('notifInboxCount', {'count': count});
  String get notifAlerts => _v('notifAlerts');
  String notifAlertsCount(String count) => _f('notifAlertsCount', {'count': count});
  String get filterAll => _v('filterAll');
  String get notifMarkAllRead => _v('notifMarkAllRead');
  String get notifMarkRead => _v('notifMarkRead');
  String get notifMarkUnread => _v('notifMarkUnread');
  String get notifDelete => _v('notifDelete');
  String get notifDeleted => _v('notifDeleted');
  String get notifUnread => _v('notifUnread');
  String get notifActionFailed => _v('notifActionFailed');
  String get notifLoadError => _v('notifLoadError');
  String get notifEmptyTitle => _v('notifEmptyTitle');
  String get notifEmptyBody => _v('notifEmptyBody');
  String notifFilterEmpty(String kind) => _f('notifFilterEmpty', {'kind': kind});
  String notifOpportunityTitle(String symbol, String direction, String timeframe) => _f('notifOpportunityTitle', {'symbol': symbol, 'direction': direction, 'timeframe': timeframe});
  String notifOpportunityBody(String probability) => _f('notifOpportunityBody', {'probability': probability});
  String notifAlertAboveTitle(String symbol) => _f('notifAlertAboveTitle', {'symbol': symbol});
  String get notifAlertAboveBody => _v('notifAlertAboveBody');
  String notifAlertBelowTitle(String symbol) => _f('notifAlertBelowTitle', {'symbol': symbol});
  String get notifAlertBelowBody => _v('notifAlertBelowBody');
  String get notifSimulatedTitle => _v('notifSimulatedTitle');
  String get notifSimulatedBody => _v('notifSimulatedBody');
  String get notifWelcomeBody => _v('notifWelcomeBody');
  String get alertsEmptyTitle => _v('alertsEmptyTitle');
  String get alertsEmptyBody => _v('alertsEmptyBody');
  String get alertsHint => _v('alertsHint');
  String get moodTitle => _v('moodTitle');
  String get moodPositive => _v('moodPositive');
  String get moodNegative => _v('moodNegative');
  String get moodMixed => _v('moodMixed');
  String get moodNone => _v('moodNone');
  String moodCounts(String positive, String neutral, String negative) => _f('moodCounts', {'positive': positive, 'neutral': neutral, 'negative': negative});
  String get sentimentPositive => _v('sentimentPositive');
  String get sentimentNegative => _v('sentimentNegative');
  String sentimentLabel(String label) => _f('sentimentLabel', {'label': label});
  String get sentimentNote => _v('sentimentNote');
  String get newsEmpty => _v('newsEmpty');
  String get newsEmptyBody => _v('newsEmptyBody');
  String get newsLoadError => _v('newsLoadError');
  String get newsNotFound => _v('newsNotFound');
  String get comments => _v('comments');
  String commentsTitle(String count) => _f('commentsTitle', {'count': count});
  String get commentsEmpty => _v('commentsEmpty');
  String get commentsEmptyBody => _v('commentsEmptyBody');
  String get commentHint => _v('commentHint');
  String get commentSend => _v('commentSend');
  String get commentDelete => _v('commentDelete');
  String get commentDeleted => _v('commentDeleted');
  String get commentActionFailed => _v('commentActionFailed');
  String get asstContext => _v('asstContext');
  String asstContextLabel(String value) => _f('asstContextLabel', {'value': value});
  String get asstContextHint => _v('asstContextHint');
  String get asstContextTitle => _v('asstContextTitle');
  String get asstContextBody => _v('asstContextBody');
  String get asstContextNone => _v('asstContextNone');
  String get asstContextNoneHint => _v('asstContextNoneHint');
  String asstEmptyTitle(String symbol) => _f('asstEmptyTitle', {'symbol': symbol});
  String get asstEmptyTitleGeneral => _v('asstEmptyTitleGeneral');
  String get asstEmptyBody => _v('asstEmptyBody');
  String get asstSuggestExplain => _v('asstSuggestExplain');
  String get asstSuggestInvalidate => _v('asstSuggestInvalidate');
  String get asstSuggestRisk => _v('asstSuggestRisk');
  String get asstHint => _v('asstHint');
  String get asstSend => _v('asstSend');
  String get asstStop => _v('asstStop');
  String get asstAttach => _v('asstAttach');
  String get asstAttachTitle => _v('asstAttachTitle');
  String get asstAttachBody => _v('asstAttachBody');
  String get asstImageType => _v('asstImageType');
  String get asstImageSize => _v('asstImageSize');
  String get asstImageUnreadable => _v('asstImageUnreadable');
  String get asstChartImage => _v('asstChartImage');
  String get asstNewChat => _v('asstNewChat');
  String get asstCleared => _v('asstCleared');
  String get asstReplying => _v('asstReplying');
  String get asstFailed => _v('asstFailed');
  String get asstOffline => _v('asstOffline');
  String get asstRuleBased => _v('asstRuleBased');
  String asstAnswerLabel(String kind) => _f('asstAnswerLabel', {'kind': kind});
  String get asstKindExplain => _v('asstKindExplain');
  String get asstKindInvalidate => _v('asstKindInvalidate');
  String get asstKindRisk => _v('asstKindRisk');
  String get asstKindChart => _v('asstKindChart');
  String get asstKindUnknown => _v('asstKindUnknown');
  String get asstNoContext => _v('asstNoContext');
  String get asstUnknown => _v('asstUnknown');
  String asstExplain(String symbol, String timeframe, String direction, String probability, String agree, String analysed, String entry, String stop, String target, String rr) => _f('asstExplain', {'symbol': symbol, 'timeframe': timeframe, 'direction': direction, 'probability': probability, 'agree': agree, 'analysed': analysed, 'entry': entry, 'stop': stop, 'target': target, 'rr': rr});
  String asstExplainNone(String symbol) => _f('asstExplainNone', {'symbol': symbol});
  String asstInvalidate(String stop, String time) => _f('asstInvalidate', {'stop': stop, 'time': time});
  String asstInvalidateNone(String symbol) => _f('asstInvalidateNone', {'symbol': symbol});
  String asstRisk(String capital, String risk, String pips, String units, String money) => _f('asstRisk', {'capital': capital, 'risk': risk, 'pips': pips, 'units': units, 'money': money});
  String get asstRiskNoCapital => _v('asstRiskNoCapital');
  String asstRiskNone(String symbol) => _f('asstRiskNone', {'symbol': symbol});
  String get chartActionTitle => _v('chartActionTitle');
  String get chartActionBody => _v('chartActionBody');
  String chartQuotaCount(String used, String limit) => _f('chartQuotaCount', {'used': used, 'limit': limit});
  String chartLimitReached(String time) => _f('chartLimitReached', {'time': time});
  String get chartLimitChat => _v('chartLimitChat');
  String get chartPreviewLabel => _v('chartPreviewLabel');
  String chartFileSize(String type, String size) => _f('chartFileSize', {'type': type, 'size': size});
  String get chartRemove => _v('chartRemove');
  String get chartAnalyze => _v('chartAnalyze');
  String get chartAnalyzing => _v('chartAnalyzing');
  String get chartFailed => _v('chartFailed');
  String get chartOffline => _v('chartOffline');
  String get chartOrAsk => _v('chartOrAsk');
  String get chartTrend => _v('chartTrend');
  String get chartKeyLevels => _v('chartKeyLevels');
  String get chartPattern => _v('chartPattern');
  String get chartHighProbability => _v('chartHighProbability');
  String chartNoSetup(String timeframe) => _f('chartNoSetup', {'timeframe': timeframe});
  String get chartNoLevels => _v('chartNoLevels');
  String chartPictureOnly(String trend) => _f('chartPictureOnly', {'trend': trend});
  String get chartTrendRising => _v('chartTrendRising');
  String get chartTrendFalling => _v('chartTrendFalling');
  String get chartTrendSideways => _v('chartTrendSideways');
  String get chartPatternChannel => _v('chartPatternChannel');
  String get chartPatternTriangle => _v('chartPatternTriangle');
  String get chartPatternRange => _v('chartPatternRange');
  String get chartPatternFlag => _v('chartPatternFlag');
  String get chartPatternWedge => _v('chartPatternWedge');
  String chartReadSignal(String symbol, String timeframe, String pattern, String method, String direction, String probability) => _f('chartReadSignal', {'symbol': symbol, 'timeframe': timeframe, 'pattern': pattern, 'method': method, 'direction': direction, 'probability': probability});
  String get chartReadHigh => _v('chartReadHigh');
  String chartReadNoSetup(String symbol, String timeframe, String pattern, String method) => _f('chartReadNoSetup', {'symbol': symbol, 'timeframe': timeframe, 'pattern': pattern, 'method': method});
  String chartReadNoInstrument(String pattern, String trend) => _f('chartReadNoInstrument', {'pattern': pattern, 'trend': trend});
  String get chartStored => _v('chartStored');
  String get chartYourStrategy => _v('chartYourStrategy');
  String get authOffline => _v('authOffline');
  String get welcomeTitle => _v('welcomeTitle');
  String get loginSubtitle => _v('loginSubtitle');
  String get registerSubtitle => _v('registerSubtitle');
  String get authDisclaimer => _v('authDisclaimer');
  String get notAdviceNotice => _v('notAdviceNotice');
  String get otpVerifiedRow => _v('otpVerifiedRow');
  String get communityPosts => _v('communityPosts');
  String get postsIntro => _v('postsIntro');
  String get postsEmptyTitle => _v('postsEmptyTitle');
  String get postsEmptyBody => _v('postsEmptyBody');
  String get postsLoadError => _v('postsLoadError');
  String get newPost => _v('newPost');
  String get newPostTitle => _v('newPostTitle');
  String newPostAs(String name) => _f('newPostAs', {'name': name});
  String get newPostLabel => _v('newPostLabel');
  String get newPostHint => _v('newPostHint');
  String get newPostInstrument => _v('newPostInstrument');
  String get newPostNote => _v('newPostNote');
  String get newPostNotAdvice => _v('newPostNotAdvice');
  String get postAction => _v('postAction');
  String get postShared => _v('postShared');
  String get postFailed => _v('postFailed');
  String get postOffline => _v('postOffline');
  String get postOptions => _v('postOptions');
  String get postDelete => _v('postDelete');
  String get postDeleted => _v('postDeleted');
  String get postActionFailed => _v('postActionFailed');
  String postLikes(String count) => _f('postLikes', {'count': count});
  String postOpenInstrument(String symbol) => _f('postOpenInstrument', {'symbol': symbol});
  String get postReport => _v('postReport');
  String get postReported => _v('postReported');
  String get reportTitle => _v('reportTitle');
  String get reportBody => _v('reportBody');
  String get reportSpam => _v('reportSpam');
  String get reportMisleading => _v('reportMisleading');
  String get reportAbusive => _v('reportAbusive');
  String get reportOther => _v('reportOther');
  String get reportSend => _v('reportSend');
  String get reportSent => _v('reportSent');
  String get postsOfflineTitle => _v('postsOfflineTitle');
  String get postsOfflineBody => _v('postsOfflineBody');
  String get postsOfflineAction => _v('postsOfflineAction');
  // Signals list + detail (stage D1)
  String get signalsListTitle => _v('signalsListTitle');
  String get signalsError => _v('signalsError');
  String get signalsOfflineBody => _v('signalsOfflineBody');
  String get signalsOfflineAction => _v('signalsOfflineAction');
  String signalRowLabel(String symbol, String name, String direction, String probability, String timeframe, String age) =>
      _f('signalRowLabel', {
        'symbol': symbol,
        'name': name,
        'direction': direction,
        'probability': probability,
        'timeframe': timeframe,
        'age': age,
      });
  String get signalRowHint => _v('signalRowHint');
  String signalGenerated(String age) => _f('signalGenerated', {'age': age});
  String get signalPlanTitle => _v('signalPlanTitle');
  String signalPipsAway(String pips) => _f('signalPipsAway', {'pips': pips});
  String get signalWhyTitle => _v('signalWhyTitle');
  String reasonAgreement(String count, String total) => _f('reasonAgreement', {'count': count, 'total': total});
  String reasonChance(String count) => _f('reasonChance', {'count': count});
  String reasonRewardRisk(String ratio) => _f('reasonRewardRisk', {'ratio': ratio});
  String get reasonVolatilityHigh => _v('reasonVolatilityHigh');
  String get reasonVolatilityLow => _v('reasonVolatilityLow');
  String reasonMaCrossUp(String timeframe) => _f('reasonMaCrossUp', {'timeframe': timeframe});
  String reasonMaCrossDown(String timeframe) => _f('reasonMaCrossDown', {'timeframe': timeframe});
  String reasonRsiOversold(String value, String timeframe) =>
      _f('reasonRsiOversold', {'value': value, 'timeframe': timeframe});
  String reasonRsiOverbought(String value, String timeframe) =>
      _f('reasonRsiOverbought', {'value': value, 'timeframe': timeframe});
  String reasonNoSetupMa(String timeframe) => _f('reasonNoSetupMa', {'timeframe': timeframe});
  String reasonNoSetupRsi(String value, String timeframe) =>
      _f('reasonNoSetupRsi', {'value': value, 'timeframe': timeframe});
  String get reasonInfluenceHigh => _v('reasonInfluenceHigh');
  String get reasonInfluenceMedium => _v('reasonInfluenceMedium');
  String get reasonInfluenceLow => _v('reasonInfluenceLow');
  String reasonInfluenceLabel(String level) => _f('reasonInfluenceLabel', {'level': level});
  String get strategyTitle => _v('strategyTitle');
  String strategyUsed(String method) => _f('strategyUsed', {'method': method});
  String get requestedByYou => _v('requestedByYou');
  String get analysisNoClearSetup => _v('analysisNoClearSetup');
  String get strategyMethodTitle => _v('strategyMethodTitle');
  String get strategyMethodsError => _v('strategyMethodsError');
  String strategyCardSummary(String method, String instruments) =>
      _f('strategyCardSummary', {'method': method, 'instruments': instruments});
  String strategyCardDefault(String method, String instruments) =>
      _f('strategyCardDefault', {'method': method, 'instruments': instruments});
  String strategyAboveProbability(String value) => _f('strategyAboveProbability', {'value': value});
  String get requestAnalysisTitle => _v('requestAnalysisTitle');
  String get requestAnalysisIntro => _v('requestAnalysisIntro');
  String get requestInstrument => _v('requestInstrument');
  String get requestPickInstrument => _v('requestPickInstrument');
  String get requestTimeframe => _v('requestTimeframe');
  String requestMethodSaved(String method) => _f('requestMethodSaved', {'method': method});
  String requestMethodOverride(String method) => _f('requestMethodOverride', {'method': method});
  String get requestChangeMethod => _v('requestChangeMethod');
  String get requestUseSaved => _v('requestUseSaved');
  String get requestOverrideNote => _v('requestOverrideNote');
  String get requestAnalyze => _v('requestAnalyze');
  String get requestStepPending => _v('requestStepPending');
  String requestStepAnalyzing(String symbol, String timeframe, String method) =>
      _f('requestStepAnalyzing', {'symbol': symbol, 'timeframe': timeframe, 'method': method});
  String get requestFailed => _v('requestFailed');
  String get requestInvalid => _v('requestInvalid');
  String get requestOffline => _v('requestOffline');
  String get requestNoSetupBody => _v('requestNoSetupBody');
  String reasonsShowMore(String count) => _f('reasonsShowMore', {'count': count});
  String get reasonsShowLess => _v('reasonsShowLess');
  String get signalExpiredTitle => _v('signalExpiredTitle');
  String signalExpiredBody(String time) => _f('signalExpiredBody', {'time': time});
  String get signalNotFoundTitle => _v('signalNotFoundTitle');
  String get signalNotFoundBody => _v('signalNotFoundBody');
  String get signalDetailError => _v('signalDetailError');
  String get openMarket => _v('openMarket');
  String get backToSignals => _v('backToSignals');
  String get signalExpiredBadge => _v('signalExpiredBadge');
  String signalSummaryLabel(String direction, String probability, String timeframe) =>
      _f('signalSummaryLabel', {'direction': direction, 'probability': probability, 'timeframe': timeframe});

  // Insights
  String get insightsTitle => _v('insightsTitle');
  String get insightsPeriodsLabel => _v('insightsPeriodsLabel');
  String get insightsPeriod7 => _v('insightsPeriod7');
  String get insightsPeriod30 => _v('insightsPeriod30');
  String get insightsPeriod90 => _v('insightsPeriod90');
  String insightsHitRate(String period) => _f('insightsHitRate', {'period': period});
  String insightsHeadlineCount(String hits, String count) => _f('insightsHeadlineCount', {'hits': hits, 'count': count});
  String insightsHeadlineMisses(String count) => _f('insightsHeadlineMisses', {'count': count});
  String insightsHeadlineLabel(String period, String rate, String hits, String count) => _f('insightsHeadlineLabel', {'period': period, 'rate': rate, 'hits': hits, 'count': count});
  String get insightsOverTime => _v('insightsOverTime');
  String get insightsChartCaption => _v('insightsChartCaption');
  String insightsChartLabel(String period, String low, String high) => _f('insightsChartLabel', {'period': period, 'low': low, 'high': high});
  String insightsChartPoint(String rate, String count) => _f('insightsChartPoint', {'rate': rate, 'count': count});
  String get insightsChartNoPoints => _v('insightsChartNoPoints');
  String get insightsByInstrument => _v('insightsByInstrument');
  String get insightsByTimeframe => _v('insightsByTimeframe');
  String insightsSignalsCount(String count) => _f('insightsSignalsCount', {'count': count});
  String get insightsSmallSample => _v('insightsSmallSample');
  String insightsRowLabel(String name, String rate, String hits, String count) => _f('insightsRowLabel', {'name': name, 'rate': rate, 'hits': hits, 'count': count});
  String insightsRowEmptyLabel(String name) => _f('insightsRowEmptyLabel', {'name': name});
  String get insightsNoteTitle => _v('insightsNoteTitle');
  String get insightsIntro => _v('insightsIntro');
  String insightsNoteBody(String min) => _f('insightsNoteBody', {'min': min});
  String get insightsSimulatedNote => _v('insightsSimulatedNote');
  String get insightsEmptyTitle => _v('insightsEmptyTitle');
  String get insightsEmptyBody => _v('insightsEmptyBody');
  String get insightsShowLonger => _v('insightsShowLonger');
  String get insightsError => _v('insightsError');
  String get insightsOfflineBody => _v('insightsOfflineBody');
  String get accuracyOpenHint => _v('accuracyOpenHint');
  String get strategyTestPast => _v('strategyTestPast');
  String get strategyTestUsesSaved => _v('strategyTestUsesSaved');
  String get strategyRemove => _v('strategyRemove');
  String get strategyRemoved => _v('strategyRemoved');
  String get strategyAllInstruments => _v('strategyAllInstruments');
  String get backtestUsingSaved => _v('backtestUsingSaved');
  String get backtestUsingDefault => _v('backtestUsingDefault');
  String get backtestTitle => _v('backtestTitle');
  String get backtestDisclaimerSimulated => _v('backtestDisclaimerSimulated');
  String get backtestDisclaimer => _v('backtestDisclaimer');
  String get backtestIntro => _v('backtestIntro');
  String get backtestPeriod1y => _v('backtestPeriod1y');
  String get backtestPeriod2y => _v('backtestPeriod2y');
  String get backtestPeriod3y => _v('backtestPeriod3y');
  String get backtestPeriod5y => _v('backtestPeriod5y');
  String backtestStrategyLine(String timeframes, String directions, String probability, String rr) => _f('backtestStrategyLine', {'timeframes': timeframes, 'directions': directions, 'probability': probability, 'rr': rr});
  String get backtestRun => _v('backtestRun');
  String get backtestPickInstrument => _v('backtestPickInstrument');
  String get backtestIdle => _v('backtestIdle');
  String get backtestRunning => _v('backtestRunning');
  String backtestResults(String period) => _f('backtestResults', {'period': period});
  String get backtestSignals => _v('backtestSignals');
  String get backtestSignalsCaption => _v('backtestSignalsCaption');
  String get backtestHitRate => _v('backtestHitRate');
  String backtestHitRateCaption(String hits, String count) => _f('backtestHitRateCaption', {'hits': hits, 'count': count});
  String get backtestAvgRiskReward => _v('backtestAvgRiskReward');
  String backtestAvgRiskRewardCaption(String count) => _f('backtestAvgRiskRewardCaption', {'count': count});
  String get backtestMaxDrawdown => _v('backtestMaxDrawdown');
  String backtestMaxDrawdownCaption(String count) => _f('backtestMaxDrawdownCaption', {'count': count});
  String backtestFigureLabel(String name, String value, String caption) => _f('backtestFigureLabel', {'name': name, 'value': value, 'caption': caption});
  String backtestR(String value) => _f('backtestR', {'value': value});
  String get backtestEquityTitle => _v('backtestEquityTitle');
  String backtestEquityCaption(String count) => _f('backtestEquityCaption', {'count': count});
  String backtestEquityLabel(String count, String end, String low, String high) => _f('backtestEquityLabel', {'count': count, 'end': end, 'low': low, 'high': high});
  String backtestEquityPoint(String r, String count) => _f('backtestEquityPoint', {'r': r, 'count': count});
  String get backtestEmptyTitle => _v('backtestEmptyTitle');
  String get backtestEmptyBody => _v('backtestEmptyBody');
  String get backtestTryYear => _v('backtestTryYear');
  String get backtestError => _v('backtestError');
  String get backtestOfflineBody => _v('backtestOfflineBody');
  String backtestNote(String min) => _f('backtestNote', {'min': min});

  // Workspaces (D4)
  String get workspaces => _v('workspaces');
  String get workspaceAll => _v('workspaceAll');
  String get workspacesIntro => _v('workspacesIntro');
  String get workspacesHint => _v('workspacesHint');
  String workspaceChipLabel(String name, String count) => _f('workspaceChipLabel', {'name': name, 'count': count});
  String get workspaceChipHint => _v('workspaceChipHint');
  String get workspaceNew => _v('workspaceNew');
  String get workspaceEditTitle => _v('workspaceEditTitle');
  String workspaceEditNamed(String name) => _f('workspaceEditNamed', {'name': name});
  String get workspaceName => _v('workspaceName');
  String get workspaceNameHint => _v('workspaceNameHint');
  String get workspaceInstruments => _v('workspaceInstruments');
  String get workspaceNameRequired => _v('workspaceNameRequired');
  String workspaceNameTooLong(String max) => _f('workspaceNameTooLong', {'max': max});
  String get workspaceNameTaken => _v('workspaceNameTaken');
  String get workspacePickInstrument => _v('workspacePickInstrument');
  String workspaceLimit(String max) => _f('workspaceLimit', {'max': max});
  String get workspaceSavedState => _v('workspaceSavedState');
  String get workspaceSaved => _v('workspaceSaved');
  String get workspaceUpdated => _v('workspaceUpdated');
  String workspaceDeleted(String name) => _f('workspaceDeleted', {'name': name});
  String workspaceDeletedActive(String name) => _f('workspaceDeletedActive', {'name': name});
  String get workspaceDelete => _v('workspaceDelete');
  String workspaceSwitched(String name) => _f('workspaceSwitched', {'name': name});
  String get workspaceBack => _v('workspaceBack');
  String get workspaceSaveError => _v('workspaceSaveError');
  String get workspaceEmptyTitle => _v('workspaceEmptyTitle');
  String get workspaceEmptyBody => _v('workspaceEmptyBody');
  String get workspaceShowAll => _v('workspaceShowAll');

  /// "N instruments" - بالعربي: واحدة / اثنتان / 3–10 جمع / 11+ مفرد
  String workspaceInstrumentCount(int count) => switch (count) {
        1 => _v('workspaceCount1'),
        2 => _v('workspaceCount2'),
        >= 3 && <= 10 => _f('workspaceCountFew', {'count': '$count'}),
        _ => _f('workspaceCountMany', {'count': '$count'}),
      };

  // Experts subscriptions + chat (T2)
  String expertPricePerMonth(String price) => _f('expertPricePerMonth', {'price': price});
  String expertPricePerYear(String price) => _f('expertPricePerYear', {'price': price});
  String get expertSubscribed => _v('expertSubscribed');
  String expertSubscribedLabel(String name) => _f('expertSubscribedLabel', {'name': name});
  String expertPlanLine(String plan, String price) => _f('expertPlanLine', {'plan': plan, 'price': price});
  String get expertChat => _v('expertChat');
  String expertChatWith(String name) => _f('expertChatWith', {'name': name});
  String expertSubscribeTo(String name) => _f('expertSubscribeTo', {'name': name});
  String get expertUnsubscribe => _v('expertUnsubscribe');
  String expertUnsubscribeFrom(String name) => _f('expertUnsubscribeFrom', {'name': name});
  String expertUnsubscribeTitle(String name) => _f('expertUnsubscribeTitle', {'name': name});
  String expertUnsubscribeBody(String name) => _f('expertUnsubscribeBody', {'name': name});
  String expertUnsubscribed(String name) => _f('expertUnsubscribed', {'name': name});
  String expertSubscribedSnack(String name) => _f('expertSubscribedSnack', {'name': name});
  String get expertOffline => _v('expertOffline');
  String get expertActionFailed => _v('expertActionFailed');
  String get subscribeIncluded => _v('subscribeIncluded');
  String subscribeIncludesChat(String name) => _f('subscribeIncludesChat', {'name': name});
  String subscribeAvailability(String hint) => _f('subscribeAvailability', {'hint': hint});
  String get subscribeCancelAnytime => _v('subscribeCancelAnytime');
  String get subscribeNote => _v('subscribeNote');
  String get subscribeSimulated => _v('subscribeSimulated');
  String get subscribeConfirm => _v('subscribeConfirm');
  String get subscribeOffline => _v('subscribeOffline');
  String get subscribeFailed => _v('subscribeFailed');
  String get chatDisclaimer => _v('chatDisclaimer');
  String get chatEmptyTitle => _v('chatEmptyTitle');
  String chatEmptyBody(String name) => _f('chatEmptyBody', {'name': name});
  String chatHint(String name) => _f('chatHint', {'name': name});
  String get chatSend => _v('chatSend');
  String get chatSending => _v('chatSending');
  String get chatSent => _v('chatSent');
  String get chatNotSent => _v('chatNotSent');
  String get chatOffline => _v('chatOffline');
  String get chatSimulatedReply => _v('chatSimulatedReply');
  String chatMessageMine(String time, String body, String status) => _f('chatMessageMine', {'time': time, 'body': body, 'status': status});
  String chatMessageTheirs(String name, String time, String body) => _f('chatMessageTheirs', {'name': name, 'time': time, 'body': body});
  String get chatLatest => _v('chatLatest');
  String chatLockedTitle(String name) => _f('chatLockedTitle', {'name': name});
  String chatLockedBody(String name) => _f('chatLockedBody', {'name': name});
  String get chatLoadError => _v('chatLoadError');
  String get chatOfflineBody => _v('chatOfflineBody');
  String get chatNotFound => _v('chatNotFound');
  String chatCount(String count, String max) => _f('chatCount', {'count': count, 'max': max});

  // Model forecast on the Market chart (H1)
  String get forecastToggle => _v('forecastToggle');
  String get forecastToggleLoading => _v('forecastToggleLoading');
  String forecastLabel(String probability, String direction) =>
      _f('forecastLabel', {'probability': probability, 'direction': direction});
  String get forecastLikelihoodHigh => _v('forecastLikelihoodHigh');
  String get forecastLikelihoodModerate => _v('forecastLikelihoodModerate');
  String get forecastLikelihoodLow => _v('forecastLikelihoodLow');
  String forecastDetail(String price, String time, String count, String likelihood, String probability) => _f(
      'forecastDetail', {'price': price, 'time': time, 'count': count, 'likelihood': likelihood, 'probability': probability});
  String forecastChartLabel(String direction, String likelihood, String probability, String price, String time) => _f(
      'forecastChartLabel',
      {'direction': direction, 'likelihood': likelihood, 'probability': probability, 'price': price, 'time': time});
  String get forecastReadout => _v('forecastReadout');
  String get forecastExpected => _v('forecastExpected');
  String get forecastRange => _v('forecastRange');
  String get forecastOutdated => _v('forecastOutdated');
  String get forecastOutdatedBody => _v('forecastOutdatedBody');
  String get forecastRefresh => _v('forecastRefresh');
  String get forecastNone => _v('forecastNone');
  String get forecastNoneBody => _v('forecastNoneBody');
  String forecastTimeframeBody(String timeframes) => _f('forecastTimeframeBody', {'timeframes': timeframes});
  String get forecastListSeparator => _v('forecastListSeparator');
  String forecastFollows(String basis, String timeframe) =>
      _f('forecastFollows', {'basis': basis, 'timeframe': timeframe});
  String get forecastError => _v('forecastError');
  String get forecastOffline => _v('forecastOffline');
  // H4b
  String get telegramNotConnected => _v('telegramNotConnected');
  String get telegramConnectFirst => _v('telegramConnectFirst');
  String get telegramConnected => _v('telegramConnected');
  String telegramConnectedAs(String handle) => _f('telegramConnectedAs', {'handle': handle});
  String get telegramConnect => _v('telegramConnect');
  String get telegramDisconnect => _v('telegramDisconnect');
  String get telegramDisconnectLabel => _v('telegramDisconnectLabel');
  String get telegramDisconnectedSnack => _v('telegramDisconnectedSnack');
  String get telegramConnectedSnack => _v('telegramConnectedSnack');
  String get telegramRestoredSnack => _v('telegramRestoredSnack');
  String get telegramOffline => _v('telegramOffline');
  String get telegramStatusError => _v('telegramStatusError');
  String get telegramStatusLoading => _v('telegramStatusLoading');
  String get telegramSheetIntro => _v('telegramSheetIntro');
  String get telegramStepBot => _v('telegramStepBot');
  String get telegramStepCode => _v('telegramStepCode');
  String get telegramStepCheck => _v('telegramStepCheck');
  String telegramBotLabel(String name) => _f('telegramBotLabel', {'name': name});
  String telegramCodeLabel(String code) => _f('telegramCodeLabel', {'code': code});
  String telegramValidFor(String time) => _f('telegramValidFor', {'time': time});
  String telegramValidMinutes(String minutes) => _f('telegramValidMinutes', {'minutes': minutes});
  String get telegramValidUnderMinute => _v('telegramValidUnderMinute');
  String get telegramOneMinuteLeft => _v('telegramOneMinuteLeft');
  String get telegramCopy => _v('telegramCopy');
  String get telegramCopied => _v('telegramCopied');
  String get telegramCopyCode => _v('telegramCopyCode');
  String get telegramCopyBot => _v('telegramCopyBot');
  String get telegramCodeCopied => _v('telegramCodeCopied');
  String get telegramBotCopied => _v('telegramBotCopied');
  String get telegramCheck => _v('telegramCheck');
  String get telegramCodeExpired => _v('telegramCodeExpired');
  String get telegramCodeExpiredBody => _v('telegramCodeExpiredBody');
  String get telegramNewCode => _v('telegramNewCode');
  String get telegramNotYet => _v('telegramNotYet');
  String get telegramFailed => _v('telegramFailed');
  String get telegramGettingCode => _v('telegramGettingCode');
  String get telegramSheetNote => _v('telegramSheetNote');
  String get pushNotAllowed => _v('pushNotAllowed');
  String get pushSettingsHint => _v('pushSettingsHint');
  String get pushWhyTitle => _v('pushWhyTitle');
  String get pushWhyBody => _v('pushWhyBody');
  String get pushWhyAlerts => _v('pushWhyAlerts');
  String get pushWhyOpportunities => _v('pushWhyOpportunities');
  String get pushWhyControl => _v('pushWhyControl');
  String get pushWhyNote => _v('pushWhyNote');
  String get pushWhyContinue => _v('pushWhyContinue');
  String get pushWhyNotNow => _v('pushWhyNotNow');
  String get pushTurnedOn => _v('pushTurnedOn');
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  bool isSupported(Locale locale) =>
      AppLocalizations.supportedLocales.any((l) => l.languageCode == locale.languageCode);

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(AppLocalizations(locale));
  }

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}
