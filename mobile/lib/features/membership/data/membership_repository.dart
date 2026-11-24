import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/membership_models.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_providers.dart';

/// مصدر بيانات العضوية - الطبقة الوحيدة يلي بتتغيّر لما ينربط الـ backend
///
/// لاستبدال البيانات التجريبية: اعمل `ApiMembershipRepository` (الكتالوج +
/// خطة المستخدم من السيرفر) وبدّل [membershipRepositoryProvider].
abstract interface class MembershipRepository {
  Future<MembershipCatalog> fetchCatalog();

  /// خطة المستخدم الحالية - null = بدون خطة (نفس افتراضي الويب)
  Future<PlanId?> fetchCurrentPlan();
}

final class MockMembershipRepository implements MembershipRepository {
  const MockMembershipRepository();

  @override
  Future<MembershipCatalog> fetchCatalog() async => kMembershipCatalog;

  /// ما في اشتراكات بعد - الافتراضي "بدون خطة" لحد ما ينربط الـ backend
  @override
  Future<PlanId?> fetchCurrentPlan() async => null;
}

final membershipRepositoryProvider = Provider<MembershipRepository>(
  (ref) => apiSource(ref, ApiFeature.membership, simulated: () => const MockMembershipRepository()),
);

// ═══════════════════════════════════════════════════════════
// الكتالوج - نسخة طبق الأصل من PLANS و FEATURES بالويب
// ═══════════════════════════════════════════════════════════

const _yes = Included();
const _no = NotIncluded();

const kMembershipCatalog = MembershipCatalog(
  features: [
    PlanFeature(FeatureId.workspace, FeatureGroup.research, FeatureStatus.demo),
    PlanFeature(FeatureId.instruments, FeatureGroup.research, FeatureStatus.demo),
    PlanFeature(FeatureId.timeframes, FeatureGroup.research, FeatureStatus.demo),
    PlanFeature(FeatureId.aiAnalysis, FeatureGroup.research, FeatureStatus.demo),
    PlanFeature(FeatureId.explanations, FeatureGroup.research, FeatureStatus.demo),
    PlanFeature(FeatureId.tfAlignment, FeatureGroup.research, FeatureStatus.demo),
    PlanFeature(FeatureId.signalFilters, FeatureGroup.personalisation, FeatureStatus.demo),
    PlanFeature(FeatureId.watchlist, FeatureGroup.personalisation, FeatureStatus.demo),
    PlanFeature(FeatureId.riskTools, FeatureGroup.riskReview, FeatureStatus.available),
    PlanFeature(FeatureId.analytics, FeatureGroup.riskReview, FeatureStatus.demo),
    PlanFeature(FeatureId.alerts, FeatureGroup.riskReview, FeatureStatus.demo),
    PlanFeature(FeatureId.alertDelivery, FeatureGroup.riskReview, FeatureStatus.backend),
    PlanFeature(FeatureId.assistant, FeatureGroup.assistantWorkflow, FeatureStatus.demo),
    PlanFeature(FeatureId.researchHistory, FeatureGroup.assistantWorkflow, FeatureStatus.planned),
    PlanFeature(FeatureId.savedWorkspaces, FeatureGroup.assistantWorkflow, FeatureStatus.available),
  ],
  plans: [
    Plan(id: PlanId.essential, access: {
      FeatureId.workspace: _yes,
      FeatureId.instruments: Scoped(AccessScope.gold),
      FeatureId.timeframes: Scoped(AccessScope.timeframes),
      FeatureId.aiAnalysis: _yes,
      FeatureId.explanations: _yes,
      FeatureId.tfAlignment: _no,
      FeatureId.signalFilters: _no,
      FeatureId.watchlist: Scoped(AccessScope.gold),
      FeatureId.riskTools: _yes,
      FeatureId.analytics: _yes,
      FeatureId.alerts: _yes,
      FeatureId.alertDelivery: _no,
      FeatureId.assistant: _no,
      FeatureId.researchHistory: _no,
      FeatureId.savedWorkspaces: Scoped(AccessScope.oneWorkspace),
    }),
    Plan(id: PlanId.professional, access: {
      FeatureId.workspace: _yes,
      FeatureId.instruments: Scoped(AccessScope.allInstruments),
      FeatureId.timeframes: Scoped(AccessScope.timeframes),
      FeatureId.aiAnalysis: _yes,
      FeatureId.explanations: _yes,
      FeatureId.tfAlignment: _yes,
      FeatureId.signalFilters: _yes,
      FeatureId.watchlist: Scoped(AccessScope.allInstruments),
      FeatureId.riskTools: _yes,
      FeatureId.analytics: _yes,
      FeatureId.alerts: _yes,
      FeatureId.alertDelivery: _yes,
      FeatureId.assistant: _no,
      FeatureId.researchHistory: _no,
      FeatureId.savedWorkspaces: Scoped(AccessScope.multipleWorkspaces),
    }),
    Plan(id: PlanId.elite, access: {
      FeatureId.workspace: _yes,
      FeatureId.instruments: Scoped(AccessScope.allInstruments),
      FeatureId.timeframes: Scoped(AccessScope.timeframes),
      FeatureId.aiAnalysis: _yes,
      FeatureId.explanations: _yes,
      FeatureId.tfAlignment: _yes,
      FeatureId.signalFilters: _yes,
      FeatureId.watchlist: Scoped(AccessScope.allInstruments),
      FeatureId.riskTools: _yes,
      FeatureId.analytics: _yes,
      FeatureId.alerts: _yes,
      FeatureId.alertDelivery: _yes,
      FeatureId.assistant: _yes,
      FeatureId.researchHistory: _yes,
      FeatureId.savedWorkspaces: Scoped(AccessScope.multipleWorkspaces),
    }),
  ],
);
