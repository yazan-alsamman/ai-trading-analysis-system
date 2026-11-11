import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/data/json.dart';
import '../../../core/storage/preferences_provider.dart';
import '../models/expert.dart';
import '../models/expert_plan.dart';
import '../models/expert_subscription.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';

/// مصدر اشتراكات الخبراء - بيتبدّل بتنفيذ API بعدين.
///
/// التطبيق ما بيطلب ولا بيشوف بيانات بطاقة أبدًا: الدفع الحقيقي بصفحة مزوّد
/// الدفع (`checkout_url`) والنتيجة بترجع عبر الـ webhook.
abstract interface class ExpertSubscriptionsRepository {
  /// اشتراكاتك، الأحدث أول.
  /// API: `GET /me/subscriptions` (`list[SubscriptionRead]`).
  /// TODO(API): ربط مع الجلسة (JWT).
  Future<List<ExpertSubscription>> mine();

  /// اشتراك بـ [plan] عند [expert]. اشتراك مش منتهي موجود = نفسه بيرجع (ما في تكرار).
  /// API: `POST /subscriptions/checkout` (`plan_id`, `return_url`) → فتح `checkout_url`
  /// بالمتصفح → النتيجة بالـ webhook → `GET /me/subscriptions`.
  /// TODO(API): فتح صفحة الدفع + الرجوع للتطبيق (deep link بـ `return_url`) + انتظار الحالة.
  Future<ExpertSubscription> subscribe({required Expert expert, required ExpertPlan plan});

  /// إلغاء الاشتراك.
  /// API: `POST /me/subscriptions/{id}/cancel`.
  /// TODO(API): الـ backend بيلغي بآخر الفترة (`cancel_at_period_end`، الوصول بيضل لـ
  /// `current_period_end`)؛ المحاكاة بتنهيه فورًا.
  Future<ExpertSubscription> cancel(String subscriptionId);

  /// رجوع عن الإلغاء (Undo).
  /// API: `POST /me/subscriptions/{id}/resume`.
  /// TODO(API): بيشتغل بس قبل `current_period_end`.
  Future<ExpertSubscription> resume(String subscriptionId);
}

/// `SubscriptionRead` → domain (null لو ناقص)
ExpertSubscription? expertSubscriptionFromJson(Json json) {
  final id = json.string('id');
  final expert = json.object('expert');
  final expertId = expert?.string('id');
  final expertName = expert?.string('display_name')?.trim();
  final plan = json.object('plan');
  final planId = plan?.string('id');
  final status = SubscriptionStatus.fromApi(json.string('status'));
  final price = json.number('price');
  final currency = json.string('currency');
  final interval = switch (json.string('interval')) {
    'month' => PlanInterval.month,
    'year' => PlanInterval.year,
    _ => null,
  };
  final periodEnd = json.dateTime('current_period_end');
  final createdAt = json.dateTime('created_at');
  if (id == null ||
      expertId == null ||
      expertName == null ||
      planId == null ||
      status == null ||
      price == null ||
      currency == null ||
      interval == null ||
      periodEnd == null ||
      createdAt == null) {
    return null;
  }
  final perks = json.object('perks');
  return ExpertSubscription(
    id: id,
    expertId: expertId,
    expertName: expertName,
    planId: planId,
    planName: plan?.string('name')?.trim() ?? '',
    status: status,
    price: price,
    currency: currency,
    interval: interval,
    perks: {
      if (perks != null)
        for (final e in perks.raw.entries)
          if (e.value is bool) e.key: e.value! as bool,
    },
    currentPeriodEnd: periodEnd,
    createdAt: createdAt,
    cancelAtPeriodEnd: json.boolean('cancel_at_period_end') ?? false,
    canceledAt: json.dateTime('canceled_at'),
  );
}

/// domain → `SubscriptionRead` (للتخزين المحلي بنفس شكل الـ API). بدون
/// `payment_method`: ما في بيانات بطاقة.
Map<String, Object?> expertSubscriptionToJson(ExpertSubscription s) => {
      'id': s.id,
      'expert': {'id': s.expertId, 'display_name': s.expertName, 'role': 'expert'},
      'plan': {'id': s.planId, 'name': s.planName},
      'status': s.status.apiValue,
      'price': s.price.toStringAsFixed(2),
      'currency': s.currency,
      'interval': s.interval.name,
      'perks': s.perks,
      'current_period_end': s.currentPeriodEnd.toUtc().toIso8601String(),
      'cancel_at_period_end': s.cancelAtPeriodEnd,
      'canceled_at': s.canceledAt?.toUtc().toIso8601String(),
      'payment_method': null,
      'created_at': s.createdAt.toUtc().toIso8601String(),
      'invoices': const <Object?>[],
    };

/// محفوظ على الجهاز (SharedPreferences) لحد ما ينربط الدفع - محاكاة: ما في
/// دفع ولا تجديد ولا انتهاء لحالو. اشتراك واحد (آخر واحد) لكل خبير.
final class LocalExpertSubscriptionsRepository implements ExpertSubscriptionsRepository {
  LocalExpertSubscriptionsRepository(
    this.prefs, {
    DateTime Function()? clock,
    this.latency = Duration.zero,
  }) : _clock = clock ?? DateTime.now;

  static const storageKey = 'expert_subscriptions';

  final SharedPreferences prefs;
  final DateTime Function() _clock;
  final Duration latency;

  Future<void> _wait() async {
    if (latency > Duration.zero) await Future<void>.delayed(latency);
  }

  /// بيقرأ بأمان: JSON مكسور أو مش قائمة → فاضي؛ عنصر ناقص أو خبير مكرر بينشال
  List<ExpertSubscription> _read() {
    final raw = prefs.getString(storageKey);
    if (raw == null) return const [];
    Object? decoded;
    try {
      decoded = jsonDecode(raw);
    } on FormatException {
      return const [];
    }
    if (decoded is! List) return const [];
    final experts = <String>{};
    return [
      for (final item in decoded)
        if (Json.from(item) case final json?)
          if (expertSubscriptionFromJson(json) case final s? when experts.add(s.expertId)) s,
    ];
  }

  Future<void> _write(List<ExpertSubscription> list) =>
      prefs.setString(storageKey, jsonEncode([for (final s in list) expertSubscriptionToJson(s)]));

  Future<ExpertSubscription> _replace(ExpertSubscription s) async {
    final list = _read().where((e) => e.expertId != s.expertId).toList()..insert(0, s);
    await _write(list);
    return s;
  }

  ExpertSubscription _byId(String id) =>
      _read().firstWhere((s) => s.id == id, orElse: () => throw StateError('No subscription $id'));

  /// قراءة محلية فورية (بدون تأخير محاكى: البطاقات بتطلع بحالتها من أول إطار)
  @override
  Future<List<ExpertSubscription>> mine() async => _read();

  @override
  Future<ExpertSubscription> subscribe({required Expert expert, required ExpertPlan plan}) async {
    await _wait();
    for (final s in _read()) {
      if (s.expertId == expert.id && s.isEntitled) return s;
    }
    final now = _clock().toUtc();
    return _replace(ExpertSubscription(
      id: 'sub-${expert.id}-${now.microsecondsSinceEpoch}',
      expertId: expert.id,
      expertName: expert.name,
      planId: plan.id,
      planName: plan.name,
      status: SubscriptionStatus.active,
      price: plan.price,
      currency: plan.currency,
      interval: plan.interval,
      perks: plan.perks,
      currentPeriodEnd: now.add(Duration(days: plan.interval == PlanInterval.month ? 30 : 365)),
      createdAt: now,
    ));
  }

  @override
  Future<ExpertSubscription> cancel(String subscriptionId) async {
    await _wait();
    final s = _byId(subscriptionId);
    return _replace(_copy(s, status: SubscriptionStatus.canceled, canceledAt: _clock().toUtc()));
  }

  @override
  Future<ExpertSubscription> resume(String subscriptionId) async {
    await _wait();
    final s = _byId(subscriptionId);
    return _replace(_copy(s, status: SubscriptionStatus.active));
  }

  static ExpertSubscription _copy(ExpertSubscription s, {required SubscriptionStatus status, DateTime? canceledAt}) =>
      ExpertSubscription(
        id: s.id,
        expertId: s.expertId,
        expertName: s.expertName,
        planId: s.planId,
        planName: s.planName,
        status: status,
        price: s.price,
        currency: s.currency,
        interval: s.interval,
        perks: s.perks,
        currentPeriodEnd: s.currentPeriodEnd,
        createdAt: s.createdAt,
        canceledAt: canceledAt,
      );
}

final expertSubscriptionsRepositoryProvider = Provider<ExpertSubscriptionsRepository>(
  (ref) => apiSource(
    ref,
    ApiFeature.expertSubscriptions,
    simulated: () => LocalExpertSubscriptionsRepository(
      ref.watch(sharedPreferencesProvider),
      latency: const Duration(milliseconds: 600),
    ),
  ),
);
