import '../../../l10n/app_localizations.dart';
import '../models/membership_models.dart';

/// نصوص العضوية حسب المعرّفات - نفس نصوص الويب، مترجمة
extension MembershipCopy on AppLocalizations {
  String planName(PlanId id) => switch (id) {
        PlanId.essential => memEssentialName,
        PlanId.professional => memProfessionalName,
        PlanId.elite => memEliteName,
      };

  String planTagline(PlanId id) => switch (id) {
        PlanId.essential => memEssentialTagline,
        PlanId.professional => memProfessionalTagline,
        PlanId.elite => memEliteTagline,
      };

  String planAudience(PlanId id) => switch (id) {
        PlanId.essential => memEssentialAudience,
        PlanId.professional => memProfessionalAudience,
        PlanId.elite => memEliteAudience,
      };

  List<String> planHighlights(PlanId id) => switch (id) {
        PlanId.essential => [memEssentialH1, memEssentialH2, memEssentialH3, memEssentialH4],
        PlanId.professional => [
            memProfessionalH1,
            memProfessionalH2,
            memProfessionalH3,
            memProfessionalH4,
          ],
        PlanId.elite => [memEliteH1, memEliteH2, memEliteH3, memEliteH4],
      };

  String planCta(PlanId id) => switch (id) {
        PlanId.essential => memEssentialCta,
        PlanId.professional => memProfessionalCta,
        PlanId.elite => memEliteCta,
      };

  String featureLabel(FeatureId id) => switch (id) {
        FeatureId.workspace => memFWorkspace,
        FeatureId.instruments => memFInstruments,
        FeatureId.timeframes => memFTimeframes,
        FeatureId.aiAnalysis => memFAiAnalysis,
        FeatureId.explanations => memFExplanations,
        FeatureId.tfAlignment => memFTfAlignment,
        FeatureId.signalFilters => memFSignalFilters,
        FeatureId.watchlist => memFWatchlist,
        FeatureId.riskTools => memFRiskTools,
        FeatureId.analytics => memFAnalytics,
        FeatureId.alerts => memFAlerts,
        FeatureId.alertDelivery => memFAlertDelivery,
        FeatureId.assistant => memFAssistant,
        FeatureId.researchHistory => memFResearchHistory,
        FeatureId.savedWorkspaces => memFSavedWorkspaces,
      };

  String scopeLabel(AccessScope scope) => switch (scope) {
        AccessScope.gold => memScopeGold,
        AccessScope.allInstruments => memScopeAllInstruments,
        AccessScope.timeframes => memScopeTimeframes,
        AccessScope.oneWorkspace => memScopeOneWorkspace,
        AccessScope.multipleWorkspaces => memScopeMultipleWorkspaces,
      };

  /// النص المقروء لقيمة الوصول (للقارئ الصوتي والجداول)
  String accessLabel(Access access) => switch (access) {
        Included() => memIncluded,
        NotIncluded() => memNotIncluded,
        Scoped(:final scope) => scopeLabel(scope),
      };

  String groupLabel(FeatureGroup group) => switch (group) {
        FeatureGroup.research => memGroupResearch,
        FeatureGroup.personalisation => memGroupPersonalisation,
        FeatureGroup.riskReview => memGroupRiskReview,
        FeatureGroup.assistantWorkflow => memGroupAssistantWorkflow,
      };

  String statusLabel(FeatureStatus status) => switch (status) {
        FeatureStatus.available => memStatusAvailable,
        FeatureStatus.demo => memStatusDemo,
        FeatureStatus.backend => memStatusBackend,
        FeatureStatus.planned => memStatusPlanned,
      };

  String statusDescription(FeatureStatus status) => switch (status) {
        FeatureStatus.available => memStatusAvailableDesc,
        FeatureStatus.demo => memStatusDemoDesc,
        FeatureStatus.backend => memStatusBackendDesc,
        FeatureStatus.planned => memStatusPlannedDesc,
      };
}
