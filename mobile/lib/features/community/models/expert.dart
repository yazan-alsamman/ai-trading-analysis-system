import 'package:flutter/foundation.dart';

import 'expert_plan.dart';

/// خبير تداول للاستشارة (`ExpertCard` / `ExpertDetail` بـ backend/app/schemas/experts.py)
@immutable
final class Expert {
  const Expert({
    required this.id,
    required this.name,
    required this.headline,
    required this.specialties,
    required this.markets,
    required this.languages,
    required this.availability,
    this.chatEnabled = true,
    this.plan,
  });

  final String id;

  /// `display_name`
  final String name;

  /// نبذة قصيرة (`headline`)
  final String headline;
  final List<String> specialties;

  /// رموز الأدوات (`XAU/USD`...) - دايمًا من الأدوات الثمانية
  final List<String> markets;
  final List<String> languages;

  /// `response_time_hint`
  final String availability;

  /// `chat_enabled`: الخبير فاتح المحادثة للمشتركين
  final bool chatEnabled;

  /// الخطة يلي بينعرض عليها الاشتراك (null = ما في خطة، ما في اشتراك)
  final ExpertPlan? plan;
}
