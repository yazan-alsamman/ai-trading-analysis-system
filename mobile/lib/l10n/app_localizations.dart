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
      'save': 'Save',
      'ok': 'OK',
      'trader': 'Trader',

      // Login
      'welcomeBack': 'Welcome Back',
      'signInToContinue': 'Sign in to continue trading',
      'email': 'Email',
      'password': 'Password',
      'signIn': 'Sign In',
      'noAccountQuestion': "Don't have an account?  ",
      'signUp': 'Sign up',
      'signedInSuccessfully': 'Signed in successfully!',

      // Registration
      'createAccount': 'Create Account',
      'joinTraders': 'Join thousands of smart traders',
      'confirmPassword': 'Confirm Password',
      'createAccountButton': 'Create account',
      'alreadyHaveAccount': 'Already have an account?  ',
      'accountCreatedSuccessfully': 'Account created successfully!',

      // OTP
      'verifyEmail': 'Verify Email',
      'enterCodeSent': 'Enter the Code Sent to email to\nContinue Log in Registration',
      'second': 'second',
      'verify': 'Verify',
      'didntReceiveCode': "Didn't receive a Code?  ",
      'resendCode': 'Resend Code',
      'emailVerifiedSuccessfully': 'Email verified successfully!',
      'verificationCodeSent': 'Verification code sent successfully!',
      'enterCompleteCode': 'Please enter the complete code',

      // Validators
      'emailRequired': 'Email is required',
      'enterValidEmail': 'Enter a valid email address',
      'passwordRequired': 'Password is required',
      'passwordMinChars': 'Minimum 8 characters',
      'passwordNeedsUppercase': 'Add at least one uppercase letter',
      'passwordNeedsLowercase': 'Add at least one lowercase letter',
      'passwordNeedsNumber': 'Add at least one number',
      'passwordNeedsSymbol': 'Add at least one special character',
      'passwordRequirementsHint':
          '8+ characters, with uppercase, lowercase, a number and a symbol',
      'pleaseConfirmPassword': 'Please confirm your password',
      'passwordsDoNotMatch': 'Passwords do not match',
      'thisFieldRequired': 'This field is required',
      'fieldRequired': '{field} is required',
      'fieldMinLength': '{field} must be at least {min} characters',
      'fieldMaxLength': '{field} must be at most {max} characters',

      // Home
      'welcome': 'Welcome back',
      'marketOverview': 'Market Overview',
      'quantitativeIntelligence': 'Quantitative Intelligence',
      'aiQuickAccess': 'AI Quick\nAccess',
      'chartAnalyzer': 'Chart\nAnalyzer',
      'newsAnalyzer': 'News\nAnalyzer',
      'marketIntel': 'Market Intel',
      'readMore': 'Read More',

      // Portfolio card
      'totalEquityUsd': 'Total Equity (USD)',
      'dailyPl': 'Daily P/L',
      'availableBalance': 'Available Balance',
      'marginUsed': 'Margin Used',

      // Market widgets
      'trade': 'Trade',
      'selectAMarket': 'Select a Market',
      'highImpact': 'HIGH IMPACT',
      'mediumImpact': 'MEDIUM IMPACT',
      'lowImpact': 'LOW IMPACT',

      // أسماء الأسواق (تُستخدم مع MarketItemModel.symbol عبر
      // AppLocalizations.marketName بدل الاعتماد على displayName
      // الثابت بالإنجليزي دايمًا - راجع mock_market_items.dart)
      'marketNameEURUSD': 'EUR/USD',
      'marketNameGOLD': 'Gold',
      'marketNameGBPUSD': 'GBP/USD',

      // Profile
      'profileSettings': 'Profile Settings',
      'account': 'Account',
      'accountSettings': 'Account Settings',
      'updatePersonalInfo': 'Update your personal information',
      'security': 'Security',
      'passwordAndLoginPrefs': 'Password and login preferences',
      'notificationPreferences': 'Notification Preferences',
      'chooseAlerts': 'Choose which alerts you receive',
      'support': 'Support',
      'helpAndSupport': 'Help & Support',
      'faqsAndContact': 'FAQs and contact options',
      'aboutTradeX': 'About TradeX',
      'appVersionAndLegal': 'App version and legal information',
      'logOut': 'Log Out',
      'confirmLogOut': 'Are you sure you want to log out?',
      'guestEmail': 'guest@tradex.app',
      'language': 'Language',
      'chooseAppLanguage': 'Choose your app language',
      'english': 'English',
      'arabic': 'العربية',

      // Security screen
      'passwordUpdatedSuccessfully': 'Password updated successfully',
      'couldNotUpdatePassword': 'Could not update password',
      'changePassword': 'Change Password',
      'currentPassword': 'Current Password',
      'enterCurrentPassword': 'Enter current password',
      'newPassword': 'New Password',
      'enterNewPassword': 'Enter new password',
      'confirmNewPassword': 'Confirm New Password',
      'reEnterNewPassword': 'Re-enter new password',
      'updatePassword': 'Update Password',
      'protection': 'Protection',
      'biometricLogin': 'Biometric Login',
      'biometricLoginSubtitle': 'Use Face ID / fingerprint to sign in',
      'twoFactorAuth': 'Two-Factor Authentication',
      'twoFactorAuthSubtitle': 'Add an extra layer of account security',
      'newLoginAlerts': 'New Login Alerts',
      'newLoginAlertsSubtitle': 'Get notified about unrecognized sign-ins',

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
      'buildNumber': 'Build Number',
      'platform': 'Platform',
      'aboutThisApp': 'About This App',
      'aboutBody':
          'TradeX is a professional trading companion that brings live '
              'markets, portfolio tracking, community discussion, and '
              'AI-powered analysis together in one clean, dark-themed '
              'experience.',
      'legal': 'Legal',
      'termsOfService': 'Terms of Service',
      'privacyPolicy': 'Privacy Policy',
      'riskDisclosure': 'Risk Disclosure',

      // Help & support screen
      'contactUs': 'Contact Us',
      'emailSupport': 'Email Support',
      'liveChat': 'Live Chat',
      'avgResponseTime': 'Avg. response time: 5 minutes',
      'callUs': 'Call Us',
      'frequentlyAskedQuestions': 'Frequently Asked Questions',
      'faqFundQuestion': 'How do I fund my trading account?',
      'faqFundAnswer':
          'Go to your Portfolio, tap "Deposit", then choose your preferred '
              'payment method. Funds are usually available within a few '
              'minutes for card deposits.',
      'faqFirstTradeQuestion': 'How do I place my first trade?',
      'faqFirstTradeAnswer':
          'Pick a market from the Markets tab, review the price chart on '
              'the Trade screen, choose Buy or Sell, set your amount, and '
              'confirm the order.',
      'faqProtectedQuestion': 'Is my account protected?',
      'faqProtectedAnswer':
          'Yes. You can enable biometric login and two-factor '
              'authentication from Profile → Security to add extra layers '
              'of protection to your account.',
      'faqAiQuestion': 'How does the AI Assistant work?',
      'faqAiAnswer':
          'The AI tab gives you a strategy assistant, a chart analyzer, '
              'and a news analyzer to help you evaluate markets before '
              'placing a trade. It offers guidance, not guaranteed outcomes.',
      'faqWithdrawQuestion': 'How do I withdraw funds?',
      'faqWithdrawAnswer':
          'From Portfolio, tap "Withdraw" and select a destination. '
              'Withdrawals are typically reviewed within one business day.',

      // AI Chart Analyzer screen
      'aiChartAnalyzerSubtitle': 'Upload a chart for instant analysis',
      'analysisComplete': 'Analysis complete',
      'analyzeChartButton': 'Analyze Chart',
      'analyzeAnotherChart': 'Analyze Another Chart',
      'uploadChartImage': 'Upload Chart Image',
      'pngJpgMax10mb': 'PNG, JPG or JPEG (Max 10MB)',
      'selectImage': 'Select Image',
      'analyzingChart': 'Analyzing chart...',
      'keyLevelsLabel': 'Key levels',
      'confidencePercentLabel': '{percent}% confidence',
      'tipsForBestResults': 'Tips for best results:',
      'chartTip1': 'Use clear, high-quality chart screenshots',
      'chartTip2': 'Include visible timeframe and price levels',
      'chartTip3': 'Remove unnecessary indicators for clearer analysis',
      'chartTip4': 'Candlestick charts work best',
      'trendBullish': 'Bullish',
      'trendBearish': 'Bearish',
      'trendNeutral': 'Neutral',
      'invalidImageTypeError': 'Please select a PNG, JPG or JPEG image.',
      'imageTooLargeError': 'Image size must be under 10MB.',
      'imageOpenError': 'Could not open the image. Please try again.',
      'chartMockSummary':
          'Price is forming a series of higher lows above a rising '
              'trendline, suggesting continued bullish momentum in the '
              'near term. Volume is picking up on the recent push higher, '
              'which supports the move.',
      'chartMockSupport': 'Support: 1.0820',
      'chartMockResistance': 'Resistance: 1.0950',
      'chartMockTarget': 'Target: 1.1020',

      // AI Chat screen
      'aiChatSubtitle': 'Ask me anything about trading strategies',
      'quickQuestionsLabel': 'Quick questions:',
      'askAboutStrategiesHint': 'Ask about trading strategies...',
      'aiChatWelcome':
          "Hello! I'm your AI Strategy Assistant. Ask me about market "
              'analysis, trading strategies, or get personalized '
              'recommendations based on current market conditions.',
      'aiChatQuickQ1': 'Analyze EUR/USD trend',
      'aiChatQuickQ2': 'Best scalping strategy for today',
      'aiChatQuickQ3': 'How much should I risk per trade?',
      'aiChatReplyEurUsd':
          'EUR/USD is currently trading with a mild bearish bias below '
              'the 1.0900 resistance. Watch the 1.0820 support level — a '
              'clean break below it could open the way toward 1.0750. '
              "I'd wait for confirmation before entering a position.",
      'aiChatReplyScalping':
          'For scalping today, focus on high-liquidity pairs during the '
              'London/New York session overlap. Use a tight stop loss of '
              '5-10 pips with a risk-reward ratio of at least 1:1.5, and '
              'avoid opening new trades right around major news releases.',
      'aiChatReplyRisk':
          'A common rule of thumb is to risk 1-2% of your account '
              'balance per trade. This keeps a losing streak from doing '
              'serious damage while still letting your winning trades '
              'compound over time.',
      'aiChatReplyDefault':
          "That's a great question. Based on current market conditions, "
              "I'd recommend confirming your trade idea with at least two "
              'indicators before entering, and always define your stop '
              'loss in advance so risk stays controlled.',

      'selectImageSource': 'Select Image Source',
      'takePhoto': 'Take Photo',
      'chooseFromGalleryImage': 'Choose from Gallery',

      // AI Assistant screen
      'aiStrategyAssistantTitle': 'AI Strategy Assistant',
      'aiStrategyAssistantDesc': 'Get personalized trading strategies and '
          'market insights powered by advanced AI analysis',
      'aiChartAnalyzerTitle': 'AI Chart Analyzer',
      'aiChartAnalyzerDesc': 'Upload chart screenshots and receive '
          'instant technical analysis with entry/exit signals.',
      'aiNewsAnalyzerTitle': 'AI News Analyzer',
      'aiNewsAnalyzerDesc': 'Analyze market news impact and get trading '
          'recommendations based on sentiment analysis.',

      'orderTypeMarket': 'Market',
      'orderTypeLimit': 'Limit',
      'orderTypeStop': 'Stop',

      // Trade screen
      'liveTrading': 'Live Trading',
      'price': 'Price',
      'quantity': 'Quantity',
      'stopLoss': 'Stop Loss',
      'takeProfit': 'Take Profit',
      'leverage': 'Leverage',
      'requiredMargin': 'Required Margin',
      'estFee': 'Est. Fee',
      'estLiqPrice': 'Est. Liq. Price',
      'buy': 'BUY',
      'sell': 'SELL',
      'confirmOrder': 'Confirm Order',
      'asset': 'Asset',
      'side': 'Side',
      'confirm': 'Confirm',
      'orderExecuted': 'Order Executed',
      'orderFilledMessage':
          'Your {side} order for {quantity} {symbol} has been filled.',
      'done': 'Done',

      'showPasswordTooltip': 'Show password',
      'hidePasswordTooltip': 'Hide password',
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
      'commentText6': 'Volume looks thin, could be a fake move.',
      'commentText7': 'Thanks for the update, very useful timing.',
      'commentText8': 'Watching the daily close before deciding anything.',

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
              'first half of 2026, with potential cuts not anticipated '
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
      'newsAnalyzerTitle': 'AI News Analyzer',
      'newsAnalyzerSubtitleLocked':
          "Ready to analyze this news's market impact",
      'newsAnalyzerSubtitleUnlocked': 'Select news to analyze market impact',
      'analyzing': 'Analyzing...',
      'analyzeSelectedNews': 'Analyze Selected News',
      'analyzeAnotherNews': 'Analyze Another News',
      'affectedAssets': 'Affected assets',
      'tradingRecommendation': 'Trading recommendation',
      'confidencePercent': '{percent}% confidence',
      'sentimentBullish': 'Bullish',
      'sentimentBearish': 'Bearish',
      'sentimentNeutral': 'Neutral',
      'impactLevelHigh': 'high',
      'impactLevelMedium': 'medium',
      'impactLevelLow': 'low',
      'volatilitySignificant': 'significant',
      'volatilityLimited': 'limited',
      'relatedMarketPairs': 'Related market pairs',
      'newsAnalysisFedSummary':
          'Holding rates steady removes near-term uncertainty and signals '
              'the Fed is data-dependent rather than aggressively hawkish. '
              'USD may see a modest pullback as markets price in a longer '
              'pause, while risk assets tend to benefit from reduced policy '
              'uncertainty.',
      'newsAnalysisFedRecommendation':
          'Watch for USD weakness on further dovish comments; gold may '
              'attract safe-haven flow if rate-cut bets increase.',
      'newsAnalysisEcbSummary':
          'A cautious ECB tone pushes back on aggressive easing bets, '
              'which is modestly supportive for the euro in the near term. '
              'The impact is more contained than a full policy decision, '
              'but still shifts short-term rate-cut expectations.',
      'newsAnalysisEcbRecommendation':
          'Favor EUR strength on pullbacks; confirm with upcoming eurozone '
              'inflation data before sizing up.',
      'newsAnalysisGoldSummary':
          'Gold is consolidating in a tight range with thin volume ahead '
              'of the jobs report, meaning current price action carries '
              "limited signal value on its own. Direction is more likely "
              "to come from the upcoming data than from today's headline.",
      'newsAnalysisGoldRecommendation':
          'Low-conviction setup — wait for the payrolls release before '
              'taking a directional position on gold.',
      'newsAnalysisUkSummary':
          'Stronger consumer spending is a modestly positive signal for '
              'the pound, but a single month of data is not enough to '
              "shift the Bank of England's policy path on its own.",
      'newsAnalysisUkRecommendation':
          'Small tactical GBP long possible on the headline; keep size '
              'modest until wage and inflation data confirm the trend.',
      'newsAnalysisGenericSummary':
          'Based on the reported {impact} market impact, this headline is '
              'likely to cause {volatility} short-term volatility. Review '
              'the full article and confirm with price action before '
              'trading the news.',
      'newsAnalysisGenericRecommendation':
          'Confirm direction with price action before sizing a position '
              '— headline-only signals carry lower confidence.',

      // Discussion screen
      'discussion': 'Discussion',
      'noCommentsYet': 'No comments yet',
      'addYourComment': 'Add your comment...',

      // News detail screen
      'backToNews': 'Back to News',
      'aiAnalyze': 'AI Analyze',
      'commentsCount': 'Comments ({count})',

      // Help & support screen (contact tiles)
      'emailAddressLabel': 'Email address',
      'phoneNumberLabel': 'Phone number',
      'copiedToClipboard': '{label} copied to clipboard',

      // Notifications
      'notifications': 'Notifications',
      'noNotificationsYet': 'No notifications yet',

      // Notification content (mock)
      'notifGoldBuyTitle': 'Market is up — good time to buy',
      'notifGoldBuyMessage':
          'XAU/USD climbed 2.1% in the last hour. Momentum looks strong — '
          'this could be a good entry point to buy.',
      'notifEurSellTitle': 'Trend turning bearish',
      'notifEurSellMessage':
          'EUR/USD dropped below its support level after the Fed statement. '
          'Consider selling or tightening your stop-loss.',
      'notifBtcAlertTitle': 'Price alert triggered',
      'notifBtcAlertMessage':
          'BTC/USD just reached your target price of \$68,000. Tap to open '
          'the chart and review your position.',
      'notifOilBuyTitle': 'Breakout above resistance',
      'notifOilBuyMessage':
          'Crude Oil broke above its resistance level on strong volume — '
          'a possible buy opportunity if the breakout holds.',
      'notifWelcomeTitle': 'Welcome to TradeX',
      'notifWelcomeMessage':
          'Your account is all set up. Explore the AI tools from the home '
          'screen to get quick insights before you trade.',

      // Notification preferences
      'pushNotifications': 'Push Notifications',
      'pushNotificationsSubtitle': 'Master switch for all app notifications',
      'trading': 'Trading',
      'priceAlerts': 'Price Alerts',
      'priceAlertsSubtitle': 'Notify me when a market hits my target price',
      'tradeConfirmations': 'Trade Confirmations',
      'tradeConfirmationsSubtitle': 'Order fills, cancellations and updates',
      'newsAndInsights': 'News & Insights',
      'marketNews': 'Market News',
      'marketNewsSubtitle': 'Breaking news that may impact your markets',
      'aiInsights': 'AI Insights',
      'aiInsightsSubtitle': 'Smart signals from the AI assistant',
      'other': 'Other',
      'promotionsAndOffers': 'Promotions & Offers',
      'promotionsAndOffersSubtitle': 'Occasional updates about new features',
    },
    'ar': {
      // Common
      'cancel': 'إلغاء',
      'save': 'حفظ',
      'ok': 'حسنًا',
      'trader': 'متداول',

      // Login
      'welcomeBack': 'مرحبًا بعودتك',
      'signInToContinue': 'سجّل الدخول لمتابعة التداول',
      'email': 'البريد الإلكتروني',
      'password': 'كلمة المرور',
      'signIn': 'تسجيل الدخول',
      'noAccountQuestion': 'ليس لديك حساب؟  ',
      'signUp': 'إنشاء حساب',
      'signedInSuccessfully': 'تم تسجيل الدخول بنجاح!',

      // Registration
      'createAccount': 'إنشاء حساب',
      'joinTraders': 'انضم إلى آلاف المتداولين الأذكياء',
      'confirmPassword': 'تأكيد كلمة المرور',
      'createAccountButton': 'إنشاء حساب',
      'alreadyHaveAccount': 'لديك حساب بالفعل؟  ',
      'accountCreatedSuccessfully': 'تم إنشاء الحساب بنجاح!',

      // OTP
      'verifyEmail': 'تحقق من البريد الإلكتروني',
      'enterCodeSent': 'أدخل الرمز المرسل إلى بريدك الإلكتروني\nلمتابعة تسجيل الدخول',
      'second': 'ثانية',
      'verify': 'تحقق',
      'didntReceiveCode': 'لم يصلك الرمز؟  ',
      'resendCode': 'إعادة إرسال الرمز',
      'emailVerifiedSuccessfully': 'تم التحقق من البريد الإلكتروني بنجاح!',
      'verificationCodeSent': 'تم إرسال رمز التحقق بنجاح!',
      'enterCompleteCode': 'الرجاء إدخال الرمز كاملًا',

      // Validators
      'emailRequired': 'البريد الإلكتروني مطلوب',
      'enterValidEmail': 'أدخل بريدًا إلكترونيًا صحيحًا',
      'passwordRequired': 'كلمة المرور مطلوبة',
      'passwordMinChars': '8 أحرف على الأقل',
      'passwordNeedsUppercase': 'أضف حرفًا كبيرًا واحدًا على الأقل',
      'passwordNeedsLowercase': 'أضف حرفًا صغيرًا واحدًا على الأقل',
      'passwordNeedsNumber': 'أضف رقمًا واحدًا على الأقل',
      'passwordNeedsSymbol': 'أضف رمزًا خاصًا واحدًا على الأقل',
      'passwordRequirementsHint':
          '8 أحرف على الأقل، تحتوي على حرف كبير وصغير ورقم ورمز',
      'pleaseConfirmPassword': 'الرجاء تأكيد كلمة المرور',
      'passwordsDoNotMatch': 'كلمتا المرور غير متطابقتين',
      'thisFieldRequired': 'هذا الحقل مطلوب',
      'fieldRequired': '{field} مطلوب',
      'fieldMinLength': 'يجب أن يحتوي {field} على {min} أحرف على الأقل',
      'fieldMaxLength': 'يجب ألا يتجاوز {field} {max} حرفًا',

      // Home
      'welcome': 'مرحبًا بعودتك',
      'marketOverview': 'نظرة عامة على السوق',
      'quantitativeIntelligence': 'الذكاء الكمي',
      'aiQuickAccess': 'وصول سريع\nللذكاء الاصطناعي',
      'chartAnalyzer': 'محلل\nالرسم البياني',
      'newsAnalyzer': 'محلل\nالأخبار',
      'marketIntel': 'ملخص السوق',
      'readMore': 'اقرأ المزيد',

      // Portfolio card
      'totalEquityUsd': 'إجمالي الرصيد (دولار)',
      'dailyPl': 'الربح/الخسارة اليومي',
      'availableBalance': 'الرصيد المتاح',
      'marginUsed': 'الهامش المستخدم',

      // Market widgets
      'trade': 'تداول',
      'selectAMarket': 'اختر سوقًا',
      'highImpact': 'تأثير عالٍ',
      'mediumImpact': 'تأثير متوسط',
      'lowImpact': 'تأثير منخفض',

      // أسماء الأسواق
      'marketNameEURUSD': 'يورو/دولار',
      'marketNameGOLD': 'الذهب',
      'marketNameGBPUSD': 'جنيه إسترليني/دولار',

      // Profile
      'profileSettings': 'إعدادات الملف الشخصي',
      'account': 'الحساب',
      'accountSettings': 'إعدادات الحساب',
      'updatePersonalInfo': 'تحديث معلوماتك الشخصية',
      'security': 'الأمان',
      'passwordAndLoginPrefs': 'كلمة المرور وتفضيلات تسجيل الدخول',
      'notificationPreferences': 'تفضيلات الإشعارات',
      'chooseAlerts': 'اختر التنبيهات التي تريد استلامها',
      'support': 'الدعم',
      'helpAndSupport': 'المساعدة والدعم',
      'faqsAndContact': 'الأسئلة الشائعة وخيارات التواصل',
      'aboutTradeX': 'عن TradeX',
      'appVersionAndLegal': 'إصدار التطبيق والمعلومات القانونية',
      'logOut': 'تسجيل الخروج',
      'confirmLogOut': 'هل أنت متأكد أنك تريد تسجيل الخروج؟',
      'guestEmail': 'guest@tradex.app',
      'language': 'اللغة',
      'chooseAppLanguage': 'اختر لغة التطبيق',
      'english': 'English',
      'arabic': 'العربية',

      // Security screen
      'passwordUpdatedSuccessfully': 'تم تحديث كلمة المرور بنجاح',
      'couldNotUpdatePassword': 'تعذّر تحديث كلمة المرور',
      'changePassword': 'تغيير كلمة المرور',
      'currentPassword': 'كلمة المرور الحالية',
      'enterCurrentPassword': 'أدخل كلمة المرور الحالية',
      'newPassword': 'كلمة المرور الجديدة',
      'enterNewPassword': 'أدخل كلمة المرور الجديدة',
      'confirmNewPassword': 'تأكيد كلمة المرور الجديدة',
      'reEnterNewPassword': 'أعد إدخال كلمة المرور الجديدة',
      'updatePassword': 'تحديث كلمة المرور',
      'protection': 'الحماية',
      'biometricLogin': 'تسجيل الدخول البيومتري',
      'biometricLoginSubtitle': 'استخدم بصمة الوجه / الإصبع لتسجيل الدخول',
      'twoFactorAuth': 'المصادقة الثنائية',
      'twoFactorAuthSubtitle': 'أضف طبقة حماية إضافية لحسابك',
      'newLoginAlerts': 'تنبيهات تسجيل الدخول الجديد',
      'newLoginAlertsSubtitle': 'احصل على إشعار عند تسجيل دخول غير معروف',

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
      'buildNumber': 'رقم البناء',
      'platform': 'المنصة',
      'aboutThisApp': 'عن هذا التطبيق',
      'aboutBody':
          'TradeX هو رفيقك المحترف في التداول، يجمع الأسواق المباشرة، '
              'وتتبع المحفظة، ونقاشات المجتمع، والتحليل المعتمد على '
              'الذكاء الاصطناعي في تجربة أنيقة داكنة واحدة.',
      'legal': 'قانوني',
      'termsOfService': 'شروط الخدمة',
      'privacyPolicy': 'سياسة الخصوصية',
      'riskDisclosure': 'الإفصاح عن المخاطر',

      // Help & support screen
      'contactUs': 'تواصل معنا',
      'emailSupport': 'الدعم عبر البريد الإلكتروني',
      'liveChat': 'محادثة مباشرة',
      'avgResponseTime': 'متوسط وقت الاستجابة: 5 دقائق',
      'callUs': 'اتصل بنا',
      'frequentlyAskedQuestions': 'الأسئلة الشائعة',
      'faqFundQuestion': 'كيف أموّل حساب التداول الخاص بي؟',
      'faqFundAnswer':
          'اذهب إلى المحفظة، اضغط على "إيداع"، ثم اختر طريقة الدفع '
              'المفضلة لديك. عادةً ما تتوفر الأموال خلال دقائق قليلة '
              'لعمليات الإيداع بالبطاقة.',
      'faqFirstTradeQuestion': 'كيف أنفّذ أول صفقة لي؟',
      'faqFirstTradeAnswer':
          'اختر سوقًا من تبويب الأسواق، راجع الرسم البياني للسعر في '
              'شاشة التداول، اختر شراء أو بيع، حدد المبلغ، ثم أكّد الأمر.',
      'faqProtectedQuestion': 'هل حسابي محمي؟',
      'faqProtectedAnswer':
          'نعم. يمكنك تفعيل تسجيل الدخول البيومتري والمصادقة الثنائية '
              'من الملف الشخصي ← الأمان لإضافة طبقات حماية إضافية '
              'لحسابك.',
      'faqAiQuestion': 'كيف يعمل مساعد الذكاء الاصطناعي؟',
      'faqAiAnswer':
          'يمنحك تبويب الذكاء الاصطناعي مساعد استراتيجيات، ومحلل رسوم '
              'بيانية، ومحلل أخبار لمساعدتك على تقييم الأسواق قبل تنفيذ '
              'صفقة. يقدّم إرشادات وليس نتائج مضمونة.',
      'faqWithdrawQuestion': 'كيف أسحب أموالي؟',
      'faqWithdrawAnswer':
          'من المحفظة، اضغط على "سحب" واختر وجهة السحب. تتم مراجعة '
              'عمليات السحب عادةً خلال يوم عمل واحد.',

      // AI Chart Analyzer screen
      'aiChartAnalyzerSubtitle': 'ارفع شارتًا للحصول على تحليل فوري',
      'analysisComplete': 'اكتمل التحليل',
      'analyzeChartButton': 'تحليل الشارت',
      'analyzeAnotherChart': 'تحليل شارت آخر',
      'uploadChartImage': 'رفع صورة الشارت',
      'pngJpgMax10mb': 'PNG أو JPG أو JPEG (بحد أقصى 10 ميغابايت)',
      'selectImage': 'اختر صورة',
      'analyzingChart': 'جاري تحليل الشارت...',
      'keyLevelsLabel': 'المستويات الأساسية',
      'confidencePercentLabel': 'ثقة {percent}%',
      'tipsForBestResults': 'نصائح لأفضل النتائج:',
      'chartTip1': 'استخدم لقطات شاشة واضحة وعالية الجودة للشارت',
      'chartTip2': 'أدرج الإطار الزمني ومستويات السعر الظاهرة',
      'chartTip3': 'أزل المؤشرات غير الضرورية لتحليل أوضح',
      'chartTip4': 'الشموع اليابانية تعطي أفضل النتائج',
      'trendBullish': 'صاعد',
      'trendBearish': 'هابط',
      'trendNeutral': 'محايد',
      'invalidImageTypeError': 'الرجاء اختيار صورة PNG أو JPG أو JPEG.',
      'imageTooLargeError': 'يجب أن يكون حجم الصورة أقل من 10 ميغابايت.',
      'imageOpenError': 'تعذّر فتح الصورة. حاول مرة أخرى.',
      'chartMockSummary':
          'يشكّل السعر سلسلة من القيعان المرتفعة فوق خط اتجاه صاعد، '
              'مما يشير لاستمرار الزخم الصاعد على المدى القريب. حجم '
              'التداول يزداد مع الدفعة الأخيرة للأعلى، ما يدعم هذه '
              'الحركة.',
      'chartMockSupport': 'الدعم: 1.0820',
      'chartMockResistance': 'المقاومة: 1.0950',
      'chartMockTarget': 'الهدف: 1.1020',

      // AI Chat screen
      'aiChatSubtitle': 'اسألني أي شيء عن استراتيجيات التداول',
      'quickQuestionsLabel': 'أسئلة سريعة:',
      'askAboutStrategiesHint': 'اسأل عن استراتيجيات التداول...',
      'aiChatWelcome':
          'مرحبًا! أنا مساعد استراتيجياتك بالذكاء الاصطناعي. اسألني عن '
              'تحليل السوق، استراتيجيات التداول، أو احصل على توصيات '
              'مخصصة بناءً على ظروف السوق الحالية.',
      'aiChatQuickQ1': 'حلّل اتجاه اليورو/الدولار',
      'aiChatQuickQ2': 'أفضل استراتيجية سكالبينج اليوم',
      'aiChatQuickQ3': 'كم يجب أن أخاطر بكل صفقة؟',
      'aiChatReplyEurUsd':
          'يتداول اليورو/الدولار حاليًا بميل هبوطي خفيف تحت مقاومة '
              '1.0900. راقب مستوى الدعم عند 1.0820 — كسر واضح تحته قد '
              'يفتح الطريق نحو 1.0750. أنصح بانتظار التأكيد قبل الدخول '
              'بصفقة.',
      'aiChatReplyScalping':
          'للسكالبينج اليوم، ركّز على الأزواج عالية السيولة أثناء تداخل '
              'جلستي لندن ونيويورك. استخدم وقف خسارة ضيق من 5-10 نقاط '
              'بنسبة مخاطرة/عائد لا تقل عن 1:1.5، وتجنّب فتح صفقات جديدة '
              'وقت صدور أخبار مهمة.',
      'aiChatReplyRisk':
          'القاعدة الشائعة هي المخاطرة بـ 1-2% من رصيد حسابك بكل صفقة. '
              'هذا يمنع سلسلة خسائر من التسبب بضرر كبير، مع السماح '
              'لصفقاتك الرابحة بالتراكم مع الوقت.',
      'aiChatReplyDefault':
          'سؤال رائع. بناءً على ظروف السوق الحالية، أنصحك بتأكيد فكرة '
              'صفقتك بمؤشرين على الأقل قبل الدخول، وتحديد وقف الخسارة '
              'مسبقًا دائمًا حتى تبقى المخاطرة تحت السيطرة.',

      'selectImageSource': 'اختر مصدر الصورة',
      'takePhoto': 'التقاط صورة',
      'chooseFromGalleryImage': 'اختيار من المعرض',

      // AI Assistant screen
      'aiStrategyAssistantTitle': 'مساعد استراتيجيات الذكاء الاصطناعي',
      'aiStrategyAssistantDesc': 'احصل على استراتيجيات تداول مخصصة '
          'وتحليلات للسوق مدعومة بذكاء اصطناعي متقدم',
      'aiChartAnalyzerTitle': 'محلل الرسوم البيانية بالذكاء الاصطناعي',
      'aiChartAnalyzerDesc': 'ارفع لقطات شاشة للرسم البياني واحصل على '
          'تحليل فني فوري مع إشارات دخول/خروج.',
      'aiNewsAnalyzerTitle': 'محلل الأخبار بالذكاء الاصطناعي',
      'aiNewsAnalyzerDesc': 'حلّل تأثير أخبار السوق واحصل على توصيات '
          'تداول بناءً على تحليل المشاعر.',

      'orderTypeMarket': 'سوق',
      'orderTypeLimit': 'محدد',
      'orderTypeStop': 'إيقاف',

      // Trade screen
      'liveTrading': 'تداول مباشر',
      'price': 'السعر',
      'quantity': 'الكمية',
      'stopLoss': 'وقف الخسارة',
      'takeProfit': 'جني الأرباح',
      'leverage': 'الرافعة المالية',
      'requiredMargin': 'الهامش المطلوب',
      'estFee': 'الرسوم التقديرية',
      'estLiqPrice': 'سعر التصفية التقديري',
      'buy': 'شراء',
      'sell': 'بيع',
      'confirmOrder': 'تأكيد الأمر',
      'asset': 'الأصل',
      'side': 'الاتجاه',
      'confirm': 'تأكيد',
      'orderExecuted': 'تم تنفيذ الأمر',
      'orderFilledMessage':
          'تم تنفيذ أمر {side} لكمية {quantity} {symbol}.',
      'done': 'تم',

      'showPasswordTooltip': 'إظهار كلمة المرور',
      'hidePasswordTooltip': 'إخفاء كلمة المرور',
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
      'commentText6': 'حجم التداول يبدو ضعيفًا، ممكن تكون حركة وهمية.',
      'commentText7': 'شكرًا على التحديث، توقيت مفيد جدًا.',
      'commentText8': 'أراقب إغلاق اليوم قبل اتخاذ أي قرار.',

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
              'من 2026، مع عدم توقع خفضات محتملة إلا عندما تُظهر '
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
      'newsAnalyzerTitle': 'محلل الأخبار بالذكاء الاصطناعي',
      'newsAnalyzerSubtitleLocked': 'جاهز لتحليل تأثير هذا الخبر على السوق',
      'newsAnalyzerSubtitleUnlocked': 'اختر خبرًا لتحليل تأثيره على السوق',
      'analyzing': 'جارٍ التحليل...',
      'analyzeSelectedNews': 'حلّل الخبر المحدد',
      'analyzeAnotherNews': 'تحليل خبر آخر',
      'affectedAssets': 'الأصول المتأثرة',
      'tradingRecommendation': 'توصية التداول',
      'confidencePercent': 'ثقة {percent}%',
      'sentimentBullish': 'صاعد',
      'sentimentBearish': 'هابط',
      'sentimentNeutral': 'محايد',
      'impactLevelHigh': 'عالٍ',
      'impactLevelMedium': 'متوسط',
      'impactLevelLow': 'منخفض',
      'volatilitySignificant': 'ملحوظة',
      'volatilityLimited': 'محدودة',
      'relatedMarketPairs': 'أزواج السوق ذات الصلة',
      'newsAnalysisFedSummary':
          'إبقاء الفائدة ثابتة يزيل عدم اليقين على المدى القريب ويشير '
              'إلى أن الفيدرالي يعتمد على البيانات أكثر من التشدد '
              'المفرط. قد يشهد الدولار تراجعًا طفيفًا مع تسعير الأسواق '
              'لوقفة أطول، بينما تميل الأصول عالية المخاطر للاستفادة من '
              'تراجع عدم اليقين بالسياسة النقدية.',
      'newsAnalysisFedRecommendation':
          'راقب ضعف الدولار عند صدور تصريحات أكثر تيسيرًا؛ قد يجذب '
              'الذهب تدفقات الملاذ الآمن إذا زادت رهانات خفض الفائدة.',
      'newsAnalysisEcbSummary':
          'نبرة حذرة من البنك المركزي الأوروبي تحد من رهانات التيسير '
              'العدواني، وهذا داعم بشكل معتدل لليورو على المدى القريب. '
              'التأثير أقل من قرار سياسة كامل، لكنه لا يزال يغيّر '
              'توقعات خفض الفائدة القصيرة الأجل.',
      'newsAnalysisEcbRecommendation':
          'فضّل قوة اليورو عند التراجعات؛ تأكد من بيانات التضخم '
              'القادمة لمنطقة اليورو قبل زيادة الحجم.',
      'newsAnalysisGoldSummary':
          'الذهب يتماسك ضمن نطاق ضيق بحجم تداول منخفض قبل تقرير '
              'الوظائف، ما يعني أن حركة السعر الحالية ذات قيمة إشارية '
              'محدودة بحد ذاتها. من المرجح أن يأتي الاتجاه من البيانات '
              'القادمة أكثر من عنوان اليوم.',
      'newsAnalysisGoldRecommendation':
          'إعداد منخفض القناعة — انتظر صدور بيانات الوظائف قبل اتخاذ '
              'مركز اتجاهي على الذهب.',
      'newsAnalysisUkSummary':
          'الإنفاق الاستهلاكي الأقوى إشارة إيجابية معتدلة للجنيه '
              'الإسترليني، لكن شهرًا واحدًا من البيانات لا يكفي لتغيير '
              'مسار سياسة بنك إنجلترا بمفرده.',
      'newsAnalysisUkRecommendation':
          'إمكانية شراء تكتيكي صغير للجنيه عند العنوان؛ حافظ على حجم '
              'متواضع حتى تؤكد بيانات الأجور والتضخم الاتجاه.',
      'newsAnalysisGenericSummary':
          'استنادًا إلى تأثير السوق المُبلَّغ عنه بمستوى {impact}، من '
              'المرجح أن يتسبب هذا العنوان في تقلبات قصيرة المدى '
              '{volatility}. راجع المقال كاملًا وتأكد من حركة السعر '
              'قبل التداول بناءً على الخبر.',
      'newsAnalysisGenericRecommendation':
          'تأكد من الاتجاه عبر حركة السعر قبل تحديد حجم المركز — '
              'الإشارات المعتمدة على العنوان فقط أقل ثقة.',

      // Discussion screen
      'discussion': 'النقاش',
      'noCommentsYet': 'لا توجد تعليقات بعد',
      'addYourComment': 'أضف تعليقك...',

      // News detail screen
      'backToNews': 'العودة للأخبار',
      'aiAnalyze': 'تحليل بالذكاء الاصطناعي',
      'commentsCount': 'التعليقات ({count})',

      // Help & support screen (contact tiles)
      'emailAddressLabel': 'عنوان البريد الإلكتروني',
      'phoneNumberLabel': 'رقم الهاتف',
      'copiedToClipboard': 'تم نسخ {label} إلى الحافظة',

      // Notifications
      'notifications': 'الإشعارات',
      'noNotificationsYet': 'لا توجد إشعارات بعد',

      // Notification content (mock)
      'notifGoldBuyTitle': 'السوق طالع — وقت مناسب للشراء',
      'notifGoldBuyMessage':
          'صعد الذهب (XAU/USD) بنسبة 2.1% خلال الساعة الماضية. الزخم يبدو '
          'قويًا — ممكن تكون هاي نقطة دخول جيدة للشراء.',
      'notifEurSellTitle': 'الاتجاه يتحول للهبوط',
      'notifEurSellMessage':
          'انخفض زوج يورو/دولار (EUR/USD) تحت مستوى الدعم بعد تصريح '
          'الاحتياطي الفيدرالي. فكّر بالبيع أو تضييق وقف الخسارة.',
      'notifBtcAlertTitle': 'تم تفعيل تنبيه السعر',
      'notifBtcAlertMessage':
          'وصل بيتكوين (BTC/USD) لسعرك المستهدف 68,000\$. اضغط لفتح '
          'الرسم البياني ومراجعة صفقتك.',
      'notifOilBuyTitle': 'اختراق فوق مستوى المقاومة',
      'notifOilBuyMessage':
          'اخترق النفط الخام مستوى المقاومة بحجم تداول قوي — فرصة شراء '
          'محتملة إذا استمر الاختراق.',
      'notifWelcomeTitle': 'أهلًا فيك بـ TradeX',
      'notifWelcomeMessage':
          'حسابك جاهز بالكامل. استكشف أدوات الذكاء الاصطناعي من شاشة '
          'الهوم للحصول على تحليلات سريعة قبل ما تبدأ تداولك.',

      // Notification preferences
      'pushNotifications': 'الإشعارات الفورية',
      'pushNotificationsSubtitle': 'المفتاح الرئيسي لكل إشعارات التطبيق',
      'trading': 'التداول',
      'priceAlerts': 'تنبيهات الأسعار',
      'priceAlertsSubtitle': 'نبّهني عند وصول سوق إلى السعر المستهدف',
      'tradeConfirmations': 'تأكيدات الصفقات',
      'tradeConfirmationsSubtitle': 'تنفيذ الأوامر، الإلغاءات والتحديثات',
      'newsAndInsights': 'الأخبار والتحليلات',
      'marketNews': 'أخبار السوق',
      'marketNewsSubtitle': 'الأخبار العاجلة التي قد تؤثر على أسواقك',
      'aiInsights': 'تحليلات الذكاء الاصطناعي',
      'aiInsightsSubtitle': 'إشارات ذكية من مساعد الذكاء الاصطناعي',
      'other': 'أخرى',
      'promotionsAndOffers': 'العروض والترويجات',
      'promotionsAndOffersSubtitle': 'تحديثات دورية عن الميزات الجديدة',
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
  String get save => _v('save');
  String get ok => _v('ok');
  String get trader => _v('trader');

  String get welcomeBack => _v('welcomeBack');
  String get signInToContinue => _v('signInToContinue');
  String get email => _v('email');
  String get password => _v('password');
  String get signIn => _v('signIn');
  String get noAccountQuestion => _v('noAccountQuestion');
  String get signUp => _v('signUp');
  String get signedInSuccessfully => _v('signedInSuccessfully');

  String get createAccount => _v('createAccount');
  String get joinTraders => _v('joinTraders');
  String get confirmPassword => _v('confirmPassword');
  String get createAccountButton => _v('createAccountButton');
  String get alreadyHaveAccount => _v('alreadyHaveAccount');
  String get accountCreatedSuccessfully => _v('accountCreatedSuccessfully');

  String get verifyEmail => _v('verifyEmail');
  String get enterCodeSent => _v('enterCodeSent');
  String get second => _v('second');
  String get verify => _v('verify');
  String get didntReceiveCode => _v('didntReceiveCode');
  String get resendCode => _v('resendCode');
  String get emailVerifiedSuccessfully => _v('emailVerifiedSuccessfully');
  String get verificationCodeSent => _v('verificationCodeSent');
  String get enterCompleteCode => _v('enterCompleteCode');

  String get emailRequired => _v('emailRequired');
  String get enterValidEmail => _v('enterValidEmail');
  String get passwordRequired => _v('passwordRequired');
  String get passwordMinChars => _v('passwordMinChars');
  String get passwordNeedsUppercase => _v('passwordNeedsUppercase');
  String get passwordNeedsLowercase => _v('passwordNeedsLowercase');
  String get passwordNeedsNumber => _v('passwordNeedsNumber');
  String get passwordNeedsSymbol => _v('passwordNeedsSymbol');
  String get passwordRequirementsHint => _v('passwordRequirementsHint');
  String get pleaseConfirmPassword => _v('pleaseConfirmPassword');
  String get passwordsDoNotMatch => _v('passwordsDoNotMatch');
  String get thisFieldRequired => _v('thisFieldRequired');
  String fieldRequired(String field) => _f('fieldRequired', {'field': field});
  String fieldMinLength(String field, int min) =>
      _f('fieldMinLength', {'field': field, 'min': '$min'});
  String fieldMaxLength(String field, int max) =>
      _f('fieldMaxLength', {'field': field, 'max': '$max'});

  String get welcome => _v('welcome');
  String get marketOverview => _v('marketOverview');
  String get quantitativeIntelligence => _v('quantitativeIntelligence');
  String get aiQuickAccess => _v('aiQuickAccess');
  String get chartAnalyzer => _v('chartAnalyzer');
  String get newsAnalyzer => _v('newsAnalyzer');
  String get marketIntel => _v('marketIntel');
  String get readMore => _v('readMore');

  String get totalEquityUsd => _v('totalEquityUsd');
  String get dailyPl => _v('dailyPl');
  String get availableBalance => _v('availableBalance');
  String get marginUsed => _v('marginUsed');

  String get trade => _v('trade');
  String get selectAMarket => _v('selectAMarket');
  String get highImpact => _v('highImpact');
  String get mediumImpact => _v('mediumImpact');
  String get lowImpact => _v('lowImpact');

  /// اسم السوق المترجم حسب [MarketItemModel.symbol] (مثلًا 'GOLD' ->
  /// 'الذهب' بالعربي). لو الرمز مش موجود بقائمة الترجمات (سوق جديد لسا
  /// ما انضاف إلها مفتاح ترجمة)، بيرجع الرمز نفسه كـ fallback حتى
  /// ما تنكسر الواجهة.
  String marketName(String symbol) {
    final key = 'marketName${symbol.replaceAll('/', '')}';
    return _values[locale.languageCode]?[key] ?? _values['en']?[key] ?? symbol;
  }

  String get profileSettings => _v('profileSettings');
  String get account => _v('account');
  String get accountSettings => _v('accountSettings');
  String get updatePersonalInfo => _v('updatePersonalInfo');
  String get security => _v('security');
  String get passwordAndLoginPrefs => _v('passwordAndLoginPrefs');
  String get notificationPreferences => _v('notificationPreferences');
  String get chooseAlerts => _v('chooseAlerts');
  String get support => _v('support');
  String get helpAndSupport => _v('helpAndSupport');
  String get faqsAndContact => _v('faqsAndContact');
  String get aboutTradeX => _v('aboutTradeX');
  String get appVersionAndLegal => _v('appVersionAndLegal');
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
  String get enterCurrentPassword => _v('enterCurrentPassword');
  String get newPassword => _v('newPassword');
  String get enterNewPassword => _v('enterNewPassword');
  String get confirmNewPassword => _v('confirmNewPassword');
  String get reEnterNewPassword => _v('reEnterNewPassword');
  String get updatePassword => _v('updatePassword');
  String get protection => _v('protection');
  String get biometricLogin => _v('biometricLogin');
  String get biometricLoginSubtitle => _v('biometricLoginSubtitle');
  String get twoFactorAuth => _v('twoFactorAuth');
  String get twoFactorAuthSubtitle => _v('twoFactorAuthSubtitle');
  String get newLoginAlerts => _v('newLoginAlerts');
  String get newLoginAlertsSubtitle => _v('newLoginAlertsSubtitle');

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
  String get buildNumber => _v('buildNumber');
  String get platform => _v('platform');
  String get aboutThisApp => _v('aboutThisApp');
  String get aboutBody => _v('aboutBody');
  String get legal => _v('legal');
  String get termsOfService => _v('termsOfService');
  String get privacyPolicy => _v('privacyPolicy');
  String get riskDisclosure => _v('riskDisclosure');

  String get contactUs => _v('contactUs');
  String get emailSupport => _v('emailSupport');
  String get liveChat => _v('liveChat');
  String get avgResponseTime => _v('avgResponseTime');
  String get callUs => _v('callUs');
  String get frequentlyAskedQuestions => _v('frequentlyAskedQuestions');
  String get faqFundQuestion => _v('faqFundQuestion');
  String get faqFundAnswer => _v('faqFundAnswer');
  String get faqFirstTradeQuestion => _v('faqFirstTradeQuestion');
  String get faqFirstTradeAnswer => _v('faqFirstTradeAnswer');
  String get faqProtectedQuestion => _v('faqProtectedQuestion');
  String get faqProtectedAnswer => _v('faqProtectedAnswer');
  String get faqAiQuestion => _v('faqAiQuestion');
  String get faqAiAnswer => _v('faqAiAnswer');
  String get faqWithdrawQuestion => _v('faqWithdrawQuestion');
  String get faqWithdrawAnswer => _v('faqWithdrawAnswer');

  String get aiChartAnalyzerSubtitle => _v('aiChartAnalyzerSubtitle');
  String get analysisComplete => _v('analysisComplete');
  String get analyzeChartButton => _v('analyzeChartButton');
  String get analyzeAnotherChart => _v('analyzeAnotherChart');
  String get uploadChartImage => _v('uploadChartImage');
  String get pngJpgMax10mb => _v('pngJpgMax10mb');
  String get selectImage => _v('selectImage');
  String get analyzingChart => _v('analyzingChart');
  String get keyLevelsLabel => _v('keyLevelsLabel');
  String confidencePercentLabel(String percent) =>
      _f('confidencePercentLabel', {'percent': percent});
  String get tipsForBestResults => _v('tipsForBestResults');
  String get chartTip1 => _v('chartTip1');
  String get chartTip2 => _v('chartTip2');
  String get chartTip3 => _v('chartTip3');
  String get chartTip4 => _v('chartTip4');
  String get trendBullish => _v('trendBullish');
  String get trendBearish => _v('trendBearish');
  String get trendNeutral => _v('trendNeutral');
  String get invalidImageTypeError => _v('invalidImageTypeError');
  String get imageTooLargeError => _v('imageTooLargeError');
  String get imageOpenError => _v('imageOpenError');
  String get chartMockSummary => _v('chartMockSummary');
  String get chartMockSupport => _v('chartMockSupport');
  String get chartMockResistance => _v('chartMockResistance');
  String get chartMockTarget => _v('chartMockTarget');

  String get aiChatSubtitle => _v('aiChatSubtitle');
  String get quickQuestionsLabel => _v('quickQuestionsLabel');
  String get askAboutStrategiesHint => _v('askAboutStrategiesHint');
  String get aiChatWelcome => _v('aiChatWelcome');
  String get aiChatQuickQ1 => _v('aiChatQuickQ1');
  String get aiChatQuickQ2 => _v('aiChatQuickQ2');
  String get aiChatQuickQ3 => _v('aiChatQuickQ3');
  String get aiChatReplyEurUsd => _v('aiChatReplyEurUsd');
  String get aiChatReplyScalping => _v('aiChatReplyScalping');
  String get aiChatReplyRisk => _v('aiChatReplyRisk');
  String get aiChatReplyDefault => _v('aiChatReplyDefault');

  String get selectImageSource => _v('selectImageSource');
  String get takePhoto => _v('takePhoto');
  String get chooseFromGalleryImage => _v('chooseFromGalleryImage');

  String get aiStrategyAssistantTitle => _v('aiStrategyAssistantTitle');
  String get aiStrategyAssistantDesc => _v('aiStrategyAssistantDesc');
  String get aiChartAnalyzerTitle => _v('aiChartAnalyzerTitle');
  String get aiChartAnalyzerDesc => _v('aiChartAnalyzerDesc');
  String get aiNewsAnalyzerTitle => _v('aiNewsAnalyzerTitle');
  String get aiNewsAnalyzerDesc => _v('aiNewsAnalyzerDesc');

  String get orderTypeMarket => _v('orderTypeMarket');
  String get orderTypeLimit => _v('orderTypeLimit');
  String get orderTypeStop => _v('orderTypeStop');

  String get liveTrading => _v('liveTrading');
  String get price => _v('price');
  String get quantity => _v('quantity');
  String get stopLoss => _v('stopLoss');
  String get takeProfit => _v('takeProfit');
  String get leverage => _v('leverage');
  String get requiredMargin => _v('requiredMargin');
  String get estFee => _v('estFee');
  String get estLiqPrice => _v('estLiqPrice');
  String get buy => _v('buy');
  String get sell => _v('sell');
  String get confirmOrder => _v('confirmOrder');
  String get asset => _v('asset');
  String get side => _v('side');
  String get confirm => _v('confirm');
  String get orderExecuted => _v('orderExecuted');
  String orderFilledMessage(String side, String quantity, String symbol) =>
      _f('orderFilledMessage', {'side': side, 'quantity': quantity, 'symbol': symbol});
  String get done => _v('done');

  String get showPasswordTooltip => _v('showPasswordTooltip');
  String get hidePasswordTooltip => _v('hidePasswordTooltip');
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
  String get commentText6 => _v('commentText6');
  String get commentText7 => _v('commentText7');
  String get commentText8 => _v('commentText8');

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

  String get newsAnalyzerTitle => _v('newsAnalyzerTitle');
  String get newsAnalyzerSubtitleLocked => _v('newsAnalyzerSubtitleLocked');
  String get newsAnalyzerSubtitleUnlocked => _v('newsAnalyzerSubtitleUnlocked');
  String get analyzing => _v('analyzing');
  String get analyzeSelectedNews => _v('analyzeSelectedNews');
  String get analyzeAnotherNews => _v('analyzeAnotherNews');
  String get affectedAssets => _v('affectedAssets');
  String get tradingRecommendation => _v('tradingRecommendation');
  String confidencePercent(String percent) =>
      _f('confidencePercent', {'percent': percent});
  String get sentimentBullish => _v('sentimentBullish');
  String get sentimentBearish => _v('sentimentBearish');
  String get sentimentNeutral => _v('sentimentNeutral');
  String get impactLevelHigh => _v('impactLevelHigh');
  String get impactLevelMedium => _v('impactLevelMedium');
  String get impactLevelLow => _v('impactLevelLow');
  String get volatilitySignificant => _v('volatilitySignificant');
  String get volatilityLimited => _v('volatilityLimited');
  String get relatedMarketPairs => _v('relatedMarketPairs');
  String get newsAnalysisFedSummary => _v('newsAnalysisFedSummary');
  String get newsAnalysisFedRecommendation => _v('newsAnalysisFedRecommendation');
  String get newsAnalysisEcbSummary => _v('newsAnalysisEcbSummary');
  String get newsAnalysisEcbRecommendation => _v('newsAnalysisEcbRecommendation');
  String get newsAnalysisGoldSummary => _v('newsAnalysisGoldSummary');
  String get newsAnalysisGoldRecommendation => _v('newsAnalysisGoldRecommendation');
  String get newsAnalysisUkSummary => _v('newsAnalysisUkSummary');
  String get newsAnalysisUkRecommendation => _v('newsAnalysisUkRecommendation');
  String newsAnalysisGenericSummary(String impact, String volatility) =>
      _f('newsAnalysisGenericSummary', {'impact': impact, 'volatility': volatility});
  String get newsAnalysisGenericRecommendation => _v('newsAnalysisGenericRecommendation');

  String get discussion => _v('discussion');
  String get noCommentsYet => _v('noCommentsYet');
  String get addYourComment => _v('addYourComment');

  String get backToNews => _v('backToNews');
  String get aiAnalyze => _v('aiAnalyze');
  String commentsCount(int count) => _f('commentsCount', {'count': '$count'});

  String get emailAddressLabel => _v('emailAddressLabel');
  String get phoneNumberLabel => _v('phoneNumberLabel');
  String copiedToClipboard(String label) => _f('copiedToClipboard', {'label': label});

  String get notifications => _v('notifications');
  String get noNotificationsYet => _v('noNotificationsYet');

  String get notifGoldBuyTitle => _v('notifGoldBuyTitle');
  String get notifGoldBuyMessage => _v('notifGoldBuyMessage');
  String get notifEurSellTitle => _v('notifEurSellTitle');
  String get notifEurSellMessage => _v('notifEurSellMessage');
  String get notifBtcAlertTitle => _v('notifBtcAlertTitle');
  String get notifBtcAlertMessage => _v('notifBtcAlertMessage');
  String get notifOilBuyTitle => _v('notifOilBuyTitle');
  String get notifOilBuyMessage => _v('notifOilBuyMessage');
  String get notifWelcomeTitle => _v('notifWelcomeTitle');
  String get notifWelcomeMessage => _v('notifWelcomeMessage');

  String get pushNotifications => _v('pushNotifications');
  String get pushNotificationsSubtitle => _v('pushNotificationsSubtitle');
  String get trading => _v('trading');
  String get priceAlerts => _v('priceAlerts');
  String get priceAlertsSubtitle => _v('priceAlertsSubtitle');
  String get tradeConfirmations => _v('tradeConfirmations');
  String get tradeConfirmationsSubtitle => _v('tradeConfirmationsSubtitle');
  String get newsAndInsights => _v('newsAndInsights');
  String get marketNews => _v('marketNews');
  String get marketNewsSubtitle => _v('marketNewsSubtitle');
  String get aiInsights => _v('aiInsights');
  String get aiInsightsSubtitle => _v('aiInsightsSubtitle');
  String get other => _v('other');
  String get promotionsAndOffers => _v('promotionsAndOffers');
  String get promotionsAndOffersSubtitle => _v('promotionsAndOffersSubtitle');
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
