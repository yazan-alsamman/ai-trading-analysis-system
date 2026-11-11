import 'package:flutter/foundation.dart';

import 'expert_plan.dart';

/// حالة الاشتراك (`SubscriptionStatus` بالـ backend)
enum SubscriptionStatus {
  trialing('trialing'),
  active('active'),
  pastDue('past_due'),
  canceled('canceled'),
  expired('expired');

  const SubscriptionStatus(this.apiValue);

  final String apiValue;

  static SubscriptionStatus? fromApi(String? value) {
    for (final s in values) {
      if (s.apiValue == value) return s;
    }
    return null;
  }
}

/// اشتراك المستخدم عند خبير (`SubscriptionRead` بـ backend/app/schemas/experts.py).
/// بيانات الدفع (`payment_method`) ما بتنقرا ولا بتنحفظ بالتطبيق.
@immutable
final class ExpertSubscription {
  const ExpertSubscription({
    required this.id,
    required this.expertId,
    required this.expertName,
    required this.planId,
    required this.planName,
    required this.status,
    required this.price,
    required this.currency,
    required this.interval,
    required this.perks,
    required this.currentPeriodEnd,
    required this.createdAt,
    this.cancelAtPeriodEnd = false,
    this.canceledAt,
  });

  final String id;
  final String expertId;
  final String expertName;
  final String planId;
  final String planName;
  final SubscriptionStatus status;
  final double price;
  final String currency;
  final PlanInterval interval;
  final Map<String, bool> perks;
  final DateTime currentPeriodEnd;
  final DateTime createdAt;
  final bool cancelAtPeriodEnd;
  final DateTime? canceledAt;

  /// "مش منتهي" متل الـ backend: تجربة / فعّال / دفعة متأخرة (فترة سماح)
  bool get isEntitled =>
      status == SubscriptionStatus.trialing ||
      status == SubscriptionStatus.active ||
      status == SubscriptionStatus.pastDue;

  /// قاعدة الوصول للمحادثة: اشتراك مش منتهي وفيه ميزة `chat`
  bool get allowsChat => isEntitled && (perks['chat'] ?? false);
}
