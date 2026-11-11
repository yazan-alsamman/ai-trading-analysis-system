// مراجعة ما قبل التدقيق: (1) ولا كلمة "مضمون / guarantee" بالواجهة،
// (2) سطر "الإشارات لأغراض تعليمية وليست نصيحة استثمارية" بكل مكان فيه إشارة
// أو قراءة نموذج (نفس الويدجت ونفس النص)، (3) أقوى 3 أسباب أول بتفاصيل
// الإشارة والباقي ورا زر، (4) سطر "ليست نصيحة مالية" بنافذة المنشور،
// (5) الدخول الوهمي = متداول، والدور بيرجع بعد الإقلاع من جديد.

import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:trading_app/app/router/app_navigator.dart';
import 'package:trading_app/controllers/auth_controller.dart';
import 'package:trading_app/core/data/json.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/core/widgets/not_advice_notice.dart';
import 'package:trading_app/features/assistant/data/assistant_repository.dart';
import 'package:trading_app/features/assistant/views/assistant_screen.dart';
import 'package:trading_app/features/assistant/widgets/chat_messages.dart';
import 'package:trading_app/features/auth/data/session_store.dart';
import 'package:trading_app/features/community/views/community_screen.dart';
import 'package:trading_app/features/home/views/home_screen.dart';
import 'package:trading_app/features/markets/views/market_screen.dart';
import 'package:trading_app/features/markets/widgets/signal_summary.dart';
import 'package:trading_app/features/markets/data/market_providers.dart';
import 'package:trading_app/features/notifications/views/notifications_screen.dart';
import 'package:trading_app/features/signals/data/opportunity_dto.dart';
import 'package:trading_app/features/signals/data/signals_repository.dart';
import 'package:trading_app/features/signals/models/analysis_method.dart';
import 'package:trading_app/features/signals/models/analysis_request.dart';
import 'package:trading_app/features/signals/models/model_accuracy.dart';
import 'package:trading_app/features/signals/models/opportunity.dart';
import 'package:trading_app/features/signals/models/signal_profile.dart';
import 'package:trading_app/features/signals/models/signal_rationale.dart';
import 'package:trading_app/features/signals/views/signals_screen.dart';
import 'package:trading_app/l10n/app_localizations.dart';
import 'package:trading_app/models/user_model.dart';
import 'package:trading_app/services/secure_storage_service.dart';

import '../helpers/test_app.dart';

const _noticeEn = 'Signals are for educational purposes and are not investment advice.';
const _noticeAr = 'الإشارات لأغراض تعليمية وليست نصيحة استثمارية.';

Opportunity _signal(String id, {String tf = '1h', String risk = 'high', double probability = 0.7, double rr = 2}) =>
    OpportunityDto.fromJson(Json({
      'id': id,
      'symbol': 'EUR/USD',
      'timeframe': tf,
      'status': 'detected',
      'direction': 'long',
      'riskLevel': risk,
      'probability': probability,
      'entryZone': {'low': 1.0800, 'high': 1.0810},
      'stopLossZone': {'low': 1.0750, 'high': 1.0760},
      'takeProfitZone': {'low': 1.0900, 'high': 1.0910},
      'riskReward': rr,
      'generatedAt': kTestNow.subtract(const Duration(minutes: 12)).millisecondsSinceEpoch,
      'validUntil': kTestNow.add(const Duration(hours: 1)).millisecondsSinceEpoch,
    })).toDomain()!;

final class _Signals implements SignalsRepository {
  final byId = <String, Opportunity>{};

  /// false = ما في رأي على أطر تانية (سبب الاتفاق بيغيب)
  bool siblings = true;

  @override
  bool get isSimulated => true;

  @override
  Future<List<Opportunity>> feed(SignalProfile profile) async => byId.values.toList();

  @override
  Future<Opportunity?> opportunity(String id) async => byId[id];

  @override
  Future<Opportunity> requestAnalysis(
    AnalysisRequest request, {
    AnalysisCancelToken? cancel,
    void Function(AnalysisStage stage)? onStage,
  }) =>
      throw UnimplementedError();

  @override
  Future<List<Opportunity>> opportunities(String symbol, {String methodId = AnalysisMethod.defaultId}) async => [
        if (siblings)
          for (final o in byId.values)
            if (o.symbol == symbol) o,
      ];

  @override
  Future<ModelAccuracy> accuracy() async => const ModelAccuracy(resolved: 200, hits: 116, windowDays: 90);
}

class _Launcher extends StatelessWidget {
  const _Launcher();

  @override
  Widget build(BuildContext context) => Scaffold(
        body: Center(
          child: TextButton(
            onPressed: () => context.pushSignalDetail('s', symbol: 'EUR/USD'),
            child: const Text('open'),
          ),
        ),
      );
}

/// إشارة بـ 5 أسباب: اتجاه 0.5، اتفاق 2/2 = 1، احتمال 0.7، عائد 2 : 1 ≈ 0.67، تذبذب عالي 0.3
_Signals _fiveReasons() => _Signals()
  ..byId['s'] = _signal('s')
  ..byId['s-4h'] = _signal('s-4h', tf: '4h');

Future<void> _pump(WidgetTester tester, Widget home, {String locale = 'en', double height = 1600, List<Override> overrides = const []}) async {
  usePhoneSize(tester, height: height);
  await tester.pumpWidget(await testScope(TestApp(home: home), locale: locale, overrides: overrides));
  await settleMocks(tester);
}

void main() {
  group('1 · forbidden wording', () {
    test('no string in lib/ (EN + AR l10n and hard-coded text) uses guarantee wording', () {
      // "تتضمن / يتضمنه" (= بيشمل) مسموحة: الممنوع "تضمن / يضمن" كفعل ضمان
      final forbidden = RegExp(r'guarantee|مضمون|ضمان|(^|[\s«(])(ت|ي)ضمن', caseSensitive: false);
      final hits = <String>[];
      for (final file in Directory('lib').listSync(recursive: true).whereType<File>()) {
        if (!file.path.endsWith('.dart')) continue;
        final lines = file.readAsLinesSync();
        for (final (i, line) in lines.indexed) {
          if (forbidden.hasMatch(line)) hits.add('${file.path}:${i + 1}: ${line.trim()}');
        }
      }
      expect(hits, isEmpty);
    });
  });

  group('2 · not-advice notice on every signal / model-read surface', () {
    test('one l10n string, EN and AR', () {
      expect(AppLocalizations(const Locale('en')).notAdviceNotice, _noticeEn);
      expect(AppLocalizations(const Locale('ar')).notAdviceNotice, _noticeAr);
    });

    testWidgets('Signals list', (tester) async {
      await _pump(tester, const SignalsScreen(), height: 812);
      expect(find.byType(NotAdviceNotice), findsOneWidget);
      expect(find.text(_noticeEn), findsOneWidget);
    });

    testWidgets('Signal detail (replaces the auth line)', (tester) async {
      await _pump(tester, const _Launcher(), height: 2400, overrides: [signalsRepositoryProvider.overrideWithValue(_fiveReasons())]);
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();
      expect(find.byType(NotAdviceNotice), findsOneWidget);
      expect(find.text('Analysis and decision support only. Not financial advice, not a broker.'), findsNothing);
    });

    testWidgets('Home model-read rows', (tester) async {
      await _pump(tester, const HomeScreen(), height: 2000);
      expect(find.byType(NotAdviceNotice), findsOneWidget);
      expect(find.text('Analysis only, not financial advice. Model probabilities can be wrong.'), findsNothing);
    });

    testWidgets('Market model read', (tester) async {
      await _pump(tester, const MarketScreen(symbol: 'EUR/USD'), height: 2400);
      expect(find.descendant(of: find.byType(SignalSummary), matching: find.byType(NotAdviceNotice)), findsOneWidget);
    });

    testWidgets('opportunity notifications: shown with them, hidden on other filters', (tester) async {
      await _pump(tester, const NotificationsScreen(), height: 1600);
      expect(find.byType(NotAdviceNotice), findsOneWidget);
      Future<void> chip(String label) async {
        await tester.ensureVisible(find.widgetWithText(ChoiceChip, label));
        await tester.pumpAndSettle();
        await tester.tap(find.widgetWithText(ChoiceChip, label));
      }

      await chip('Opportunities');
      await tester.pumpAndSettle();
      expect(find.byType(NotAdviceNotice), findsOneWidget);
      await chip('System');
      await tester.pumpAndSettle();
      expect(find.byType(NotAdviceNotice), findsNothing);
    });

    testWidgets('Assistant model replies (Arabic)', (tester) async {
      const latency = Duration(milliseconds: 300);
      await _pump(tester, const AssistantScreen(), locale: 'ar', height: 1400, overrides: [
        assistantRepositoryProvider.overrideWithValue(RuleBasedAssistantRepository(latency: latency)),
      ]);
      expect(find.byType(NotAdviceNotice), findsNothing, reason: 'no model reply yet');
      await tester.tap(find.text('اشرح التحليل الحالي'));
      await tester.pump();
      await tester.pump(latency);
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pumpAndSettle();
      expect(find.descendant(of: find.byType(ReplyCard), matching: find.text(_noticeAr)), findsOneWidget);
    });

    for (final locale in ['en', 'ar']) {
      testWidgets('largest font fits with the notice ($locale)', (tester) async {
        useLargeText(tester);
        await _pump(tester, const SignalsScreen(), locale: locale, height: 1600);
        expect(tester.takeException(), isNull);
        expect(find.text(locale == 'en' ? _noticeEn : _noticeAr), findsOneWidget);
      });
    }
  });

  group('3 · top 3 reasons first', () {
    test('ranked strongest first, ties keep the original order', () {
      final reasons = buildSignalRationale(
        _signal('s'),
        siblings: [_signal('s'), _signal('s-4h', tf: '4h')],
        now: kTestNow,
      );
      expect(reasons.map((r) => r.runtimeType), [
        AgreementReason, // 2 of 2 = 1.0
        ChanceReason, // 0.7
        RewardRiskReason, // 2 : 1 ≈ 0.67
        MaCrossReason, // 0.5 (سبب الطريقة الافتراضية، A3c)
        VolatilityReason, // 0.3
      ]);
      final split = strongestFirst([const VolatilityReason(RiskLevel.high), const RewardRiskReason(1), const ChanceReason(0.5)]);
      expect(split.map((r) => r.runtimeType), [RewardRiskReason, ChanceReason, VolatilityReason]);
    });

    testWidgets('detail shows 3, the rest behind "More reasons", and folds back', (tester) async {
      final handle = tester.ensureSemantics();
      await _pump(tester, const _Launcher(), height: 2400, overrides: [signalsRepositoryProvider.overrideWithValue(_fiveReasons())]);
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();

      expect(find.text('2 of 2 timeframes point the same way.'), findsOneWidget);
      expect(find.textContaining('About 7 in 10'), findsOneWidget);
      expect(find.text('The target is 2× as far away as the stop.'), findsOneWidget);
      expect(find.text('The 10-period average is above the 30-period average on the 1h chart, so the trend points up.'), findsNothing);
      expect(find.textContaining('moving fast'), findsNothing);

      final more = find.text('More reasons (2)');
      expect(more, findsOneWidget);
      final button = find.ancestor(of: more, matching: find.byWidgetPredicate((w) => w is ButtonStyleButton));
      expect(tester.getSize(button).height, greaterThanOrEqualTo(48));
      await tester.tap(more);
      await tester.pumpAndSettle();
      expect(find.text('The 10-period average is above the 30-period average on the 1h chart, so the trend points up.'), findsOneWidget);
      expect(find.textContaining('moving fast'), findsOneWidget);

      await tester.tap(find.text('Fewer reasons'));
      await tester.pumpAndSettle();
      expect(find.text('The 10-period average is above the 30-period average on the 1h chart, so the trend points up.'), findsNothing);
      handle.dispose();
    });

    testWidgets('3 reasons or fewer: all shown, no expand control', (tester) async {
      // بدون أطر تانية وتذبذب متوسط: اتجاه + احتمال + عائد = 3
      final repo = _Signals()
        ..siblings = false
        ..byId['s'] = _signal('s', risk: 'medium');
      await _pump(tester, const _Launcher(), height: 2400, overrides: [signalsRepositoryProvider.overrideWithValue(repo)]);
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();
      expect(find.text('The 10-period average is above the 30-period average on the 1h chart, so the trend points up.'), findsOneWidget);
      expect(find.textContaining('More reasons'), findsNothing);
    });
  });

  group('4 · posts composer', () {
    for (final locale in ['en', 'ar']) {
      testWidgets('"not financial advice" line in the composer ($locale)', (tester) async {
        final en = locale == 'en';
        usePhoneSize(tester);
        await tester.pumpWidget(await testScope(
          const TestApp(home: CommunityScreen()),
          locale: locale,
          prefs: {themeModeStorageKey: 'dark'},
        ));
        await settleMocks(tester);
        await tester.tap(find.text(en ? 'Posts' : 'المنشورات'));
        await tester.pumpAndSettle();
        await tester.tap(find.widgetWithText(FloatingActionButton, en ? 'New post' : 'منشور جديد'));
        await tester.pumpAndSettle();
        expect(
          find.descendant(
            of: find.byType(BottomSheet),
            matching: find.text(en ? 'Shared opinions are not financial advice.' : 'الآراء المشاركة ليست نصيحة مالية.'),
          ),
          findsOneWidget,
        );
      });
    }
  });

  group('5 · mock sign-in role', () {
    late SessionStore store;

    setUp(() async {
      SharedPreferences.setMockInitialValues({});
      FlutterSecureStorage.setMockInitialValues({});
      store = SessionStore(secureStorage: SecureStorageService(), preferences: await SharedPreferences.getInstance());
    });

    test('log in = trader, saved as trader, restored as trader after a cold start', () async {
      final auth = AuthController(sessionStore: store);
      await auth.login(email: 'lina@example.com', password: 'research42');
      expect(auth.currentUser!.role, UserRole.trader);
      final saved = jsonDecode((await SharedPreferences.getInstance()).getString(SessionStore.userKey)!);
      expect(saved['role'], 'trader');

      // إقلاع جديد = controller جديد بنفس التخزين
      final restarted = AuthController(sessionStore: store);
      expect(await restarted.restoreSession(), isTrue);
      expect(restarted.currentUser!.role, UserRole.trader);
      expect(restarted.currentUser!.email, 'lina@example.com');
    });

    test('Create account = trader; verified session restores as trader', () async {
      final auth = AuthController(sessionStore: store);
      await auth.register(fullName: 'Sara Haddad', email: 'sara@example.com', password: 'research42');
      expect(auth.currentUser!.role, UserRole.trader);
      await auth.persistSession(); // التحقق من البريد
      final restarted = AuthController(sessionStore: store);
      expect(await restarted.restoreSession(), isTrue);
      expect(restarted.currentUser!.role, UserRole.trader);
    });

    test('the saved role round-trips (expert stays expert); unknown / missing = trader', () async {
      await store.save(const UserModel(id: 'u1', email: 'e@example.com', role: UserRole.expert));
      expect((await store.read())!.role, UserRole.expert);

      final prefs = await SharedPreferences.getInstance();
      for (final role in ['analyst', null]) {
        await prefs.setString(SessionStore.userKey, jsonEncode({'id': 'u1', 'email': 'e@example.com', if (role != null) 'role': role}));
        expect((await store.read())!.role, UserRole.trader, reason: '$role');
      }
    });
  });
}
