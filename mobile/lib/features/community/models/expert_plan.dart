import 'package:flutter/foundation.dart';

/// مدة الدفعة (`PlanInterval` بالـ backend)
enum PlanInterval { month, year }

/// خطة اشتراك عند خبير (`PlanRead` بـ backend/app/schemas/experts.py)
@immutable
final class ExpertPlan {
  const ExpertPlan({
    required this.id,
    required this.name,
    required this.price,
    required this.currency,
    required this.interval,
    this.description = '',
    this.trialDays = 0,
    this.perks = const {'chat': true},
  });

  final String id;
  final String name;
  final String description;

  /// السعر لكل [interval] (الـ backend بيبعته Decimal كنص "19.00")
  final double price;
  final String currency;
  final PlanInterval interval;
  final int trialDays;

  /// `perks`: `chat` / `premium_posts` / `signals_feed`
  final Map<String, bool> perks;

  /// المحادثة جزء من الخطة (الـ backend بيرجع 403 على `POST /conversations` بدونها)
  bool get includesChat => perks['chat'] ?? false;
}
