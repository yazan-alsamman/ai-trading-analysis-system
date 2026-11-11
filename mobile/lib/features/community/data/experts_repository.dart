import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/json.dart';
import '../../../providers/locale_provider.dart';
import '../../markets/models/market_models.dart';
import '../models/expert.dart';
import '../models/expert_plan.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';

/// مصدر الخبراء - بيتبدّل بتنفيذ API
abstract interface class ExpertsRepository {
  /// API: `GET /experts?language=` (`Page[ExpertCard]`) + `GET /experts/{id}` (`ExpertDetail.plans`).
  /// TODO(API): الـ backend ما فيه `specialties`؛ `markets` عنده فئات (`forex`, `gold`) مش
  /// رموز؛ `languages` رموز (`ar`, `en`) مش أسماء. `is_subscribed` بينتجاهل: حالة
  /// الاشتراك من `GET /me/subscriptions` بس.
  Future<List<Expert>> experts({required String languageCode});
}

/// `PlanRead` (أو `PlanBrief` بدون perks) → domain (null لو ناقص أو موقوف)
ExpertPlan? expertPlanFromJson(Json json) {
  final id = json.string('id');
  final name = json.string('name')?.trim();
  final price = json.number('price');
  final currency = json.string('currency');
  final interval = switch (json.string('interval')) {
    'month' => PlanInterval.month,
    'year' => PlanInterval.year,
    _ => null,
  };
  if (id == null || name == null || name.isEmpty || price == null || price < 0 || currency == null || interval == null) {
    return null;
  }
  if (json.boolean('is_active') == false) return null;
  final perks = json.object('perks');
  return ExpertPlan(
    id: id,
    name: name,
    description: json.string('description')?.trim() ?? '',
    price: price,
    currency: currency,
    interval: interval,
    trialDays: (json.integer('trial_days') ?? 0).clamp(0, 30),
    // بدون perks (`PlanBrief`) = الافتراضي تبع الـ backend (`Perks`)
    perks: perks == null
        ? const {'chat': true, 'premium_posts': true, 'signals_feed': false}
        : {
            for (final e in perks.raw.entries)
              if (e.value is bool) e.key: e.value! as bool,
          },
  );
}

/// `ExpertCard` / `ExpertDetail` → domain (null لو ناقص). بيقبل الأسماء القديمة
/// (`name`, `availability`) كمان.
Expert? expertFromJson(Json json) {
  List<String> strings(String key) => switch (json.raw[key]) {
        final List<Object?> list => [
            for (final v in list)
              if (v is String && v.trim().isNotEmpty) v.trim()
          ],
        _ => const [],
      };
  final id = json.string('id');
  final name = (json.string('display_name') ?? json.string('name'))?.trim();
  final headline = json.string('headline')?.trim();
  final availability = (json.string('response_time_hint') ?? json.string('availability'))?.trim();
  if (id == null || name == null || name.isEmpty || headline == null || availability == null) return null;
  // أول خطة فعّالة من `plans` (التفاصيل)، وإلا `cheapest_plan` (البطاقة)
  final plans = mapValid(json.objects('plans'), expertPlanFromJson);
  final cheapest = json.object('cheapest_plan');
  return Expert(
    id: id,
    name: name,
    headline: headline,
    specialties: strings('specialties'),
    // قاعدة المنتج: فوركس + ذهب بس - أي رمز تاني بينشال
    markets: [
      for (final m in strings('markets'))
        if (kProductSymbols.contains(m)) m
    ],
    languages: strings('languages'),
    availability: availability,
    chatEnabled: json.boolean('chat_enabled') ?? true,
    plan: plans.isNotEmpty ? plans.first : (cheapest == null ? null : expertPlanFromJson(cheapest)),
  );
}

/// ملفات تجريبية (أسماء وهمية) لحد ما ينربط الـ API - الشاشة بتقول "Simulated"
final class SimulatedExpertsRepository implements ExpertsRepository {
  const SimulatedExpertsRepository();

  @override
  Future<List<Expert>> experts({required String languageCode}) async =>
      mapValid(_rows(arabic: languageCode == 'ar'), (r) => expertFromJson(Json(r)));

  static Map<String, Object?> _plan(String expertId, String name, String description, String price) => {
        'id': '$expertId-plan',
        'expert_id': expertId,
        'name': name,
        'description': description,
        'price': price,
        'currency': 'USD',
        'interval': 'month',
        'trial_days': 0,
        // الميزات يلي مبنية بالتطبيق بس (المحادثة)
        'perks': {'chat': true, 'premium_posts': false, 'signals_feed': false},
        'is_active': true,
      };

  static List<Map<String, Object?>> _rows({required bool arabic}) => [
        {
          'id': 'expert-1',
          'display_name': arabic ? 'لينا حداد' : 'Lina Haddad',
          'headline': arabic ? 'محللة ذهب واقتصاد كلي، 12 سنة خبرة' : 'Gold and macro analyst, 12 years in the market',
          'specialties': arabic ? ['الذهب', 'البيانات الاقتصادية'] : ['Gold', 'Economic data'],
          'markets': ['XAU/USD', 'EUR/USD'],
          'languages': arabic ? ['العربية', 'الإنجليزية'] : ['Arabic', 'English'],
          'chat_enabled': true,
          'response_time_hint': arabic ? 'أيام الأسبوع، جلسة لندن' : 'Weekdays, London session',
          'plans': [
            _plan(
              'expert-1',
              arabic ? 'مكتب الذهب' : 'Gold desk',
              arabic ? 'آراء لينا في الذهب وأثر البيانات الاقتصادية.' : 'Lina’s views on gold and how economic data moves it.',
              '29.00',
            ),
          ],
        },
        {
          'id': 'expert-2',
          'display_name': arabic ? 'عمر صالح' : 'Omar Saleh',
          'headline': arabic ? 'متداول عملات رئيسية، اتجاهات وكسر مستويات' : 'FX majors trader, trends and breakouts',
          'specialties': arabic ? ['تتبّع الاتجاه', 'الكسر'] : ['Trend following', 'Breakouts'],
          'markets': ['EUR/USD', 'GBP/USD', 'USD/JPY'],
          'languages': arabic ? ['العربية', 'الإنجليزية'] : ['Arabic', 'English'],
          'chat_enabled': true,
          'response_time_hint': arabic ? 'من الاثنين للخميس، جلسة نيويورك' : 'Monday to Thursday, New York session',
          'plans': [
            _plan(
              'expert-2',
              arabic ? 'العملات الرئيسية' : 'FX majors',
              arabic ? 'كيف يقرأ عمر الاتجاهات والكسر في العملات الرئيسية.' : 'How Omar reads trends and breakouts on the majors.',
              '19.00',
            ),
          ],
        },
        {
          'id': 'expert-3',
          'display_name': arabic ? 'سارة نصّار' : 'Sara Nassar',
          'headline': arabic ? 'مدرّبة إدارة مخاطر وحجم الصفقات' : 'Risk management and position sizing coach',
          'specialties': arabic ? ['إدارة المخاطر', 'حجم الصفقة'] : ['Risk management', 'Position sizing'],
          'markets': ['AUD/USD', 'NZD/USD', 'USD/CAD', 'USD/CHF'],
          'languages': arabic ? ['الإنجليزية'] : ['English'],
          'chat_enabled': true,
          'response_time_hint': arabic ? 'بالموعد، جلستا سيدني وطوكيو' : 'By appointment, Sydney and Tokyo sessions',
          'plans': [
            _plan(
              'expert-3',
              arabic ? 'تدريب المخاطر' : 'Risk coaching',
              arabic ? 'مراجعة حجم صفقاتك وحدود المخاطرة مع سارة.' : 'Go over your position sizes and risk limits with Sara.',
              '15.00',
            ),
          ],
        },
      ];
}

final expertsRepositoryProvider = Provider<ExpertsRepository>(
  (ref) => apiSource(ref, ApiFeature.experts, simulated: () => const SimulatedExpertsRepository()),
);

/// الخبراء بلغة الواجهة الحالية (بيتحدّثوا لما تتغيّر اللغة)
final expertsProvider = FutureProvider.autoDispose<List<Expert>>((ref) {
  final languageCode = ref.watch(localeProvider).languageCode;
  return ref.watch(expertsRepositoryProvider).experts(languageCode: languageCode);
});

/// خبير واحد بمعرّفه (شاشة المحادثة) - `AsyncData(null)` = مش موجود
final expertByIdProvider = Provider.autoDispose.family<AsyncValue<Expert?>, String>(
  (ref, id) => ref.watch(expertsProvider).whenData((list) {
    for (final e in list) {
      if (e.id == id) return e;
    }
    return null;
  }),
);
