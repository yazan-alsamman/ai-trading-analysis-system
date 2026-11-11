import 'package:flutter/foundation.dart';

// ═══════════════════════════════════════════════════════════
// Membership - نفس نموذج الويب (web/src/domain/membership.ts)
// ═══════════════════════════════════════════════════════════
//
// إعدادات واجهة بس: ما في دفع ولا اشتراك ولا فرض صلاحيات على السيرفر.
// الأسعار مش محدّدة عن قصد (صاحب المشروع ما حدّد شروط تجارية). كل النصوص
// (الأسماء، الأوصاف، المزايا) بالـ l10n حسب المعرّفات تحت.

enum PlanId { essential, professional, elite }

/// شو بتشتغل عليه الميزة اليوم - مستقل عن الخطة
enum FeatureStatus { available, demo, backend, planned }

enum FeatureGroup { research, personalisation, riskReview, assistantWorkflow }

enum FeatureId {
  workspace,
  instruments,
  timeframes,
  aiAnalysis,
  explanations,
  tfAlignment,
  signalFilters,
  watchlist,
  riskTools,
  analytics,
  alerts,
  alertDelivery,
  assistant,
  researchHistory,
  savedWorkspaces,
}

/// نطاق مكتوب بدل "مشمول" فقط (متل "Gold + 7 FX majors")
enum AccessScope { gold, allInstruments, timeframes, oneWorkspace, multipleWorkspaces }

/// وصول خطة لميزة: مشمولة / غير مشمولة / مشمولة بنطاق محدد
@immutable
sealed class Access {
  const Access();

  bool get isIncluded => this is! NotIncluded;
}

final class Included extends Access {
  const Included();
}

final class NotIncluded extends Access {
  const NotIncluded();
}

final class Scoped extends Access {
  const Scoped(this.scope);

  final AccessScope scope;
}

@immutable
final class PlanFeature {
  const PlanFeature(this.id, this.group, this.status);

  final FeatureId id;
  final FeatureGroup group;
  final FeatureStatus status;
}

@immutable
final class Plan {
  const Plan({required this.id, required this.access});

  final PlanId id;
  final Map<FeatureId, Access> access;

  Access accessTo(FeatureId feature) => access[feature] ?? const NotIncluded();
}

/// الخطط + الميزات (كتالوج ثابت حاليًا، بيجي من الـ API لاحقًا)
@immutable
final class MembershipCatalog {
  const MembershipCatalog({required this.plans, required this.features});

  final List<Plan> plans;
  final List<PlanFeature> features;

  Plan plan(PlanId id) => plans.firstWhere((p) => p.id == id);

  List<PlanFeature> featuresIn(FeatureGroup group) =>
      features.where((f) => f.group == group).toList();

  List<PlanFeature> includedIn(PlanId id) =>
      features.where((f) => plan(id).accessTo(f.id).isIncluded).toList();

  List<PlanFeature> excludedFrom(PlanId id) =>
      features.where((f) => !plan(id).accessTo(f.id).isIncluded).toList();
}
