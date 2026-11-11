import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/membership_repository.dart';
import '../models/membership_models.dart';

/// الكتالوج + خطة المستخدم (مصدر وحيد لـ Profile وشاشة Plans)
@immutable
final class MembershipState {
  const MembershipState({required this.catalog, required this.currentPlan});

  final MembershipCatalog catalog;

  /// الخطة الفعلية من الـ backend - null لحد ما يصير في اشتراكات
  final PlanId? currentPlan;
}

/// ViewModel العضوية: كل القراءة عبر [MembershipRepository]
class MembershipViewModel extends AsyncNotifier<MembershipState> {
  @override
  Future<MembershipState> build() async {
    final repository = ref.watch(membershipRepositoryProvider);
    final (catalog, current) = await (
      repository.fetchCatalog(),
      repository.fetchCurrentPlan(),
    ).wait;
    return MembershipState(catalog: catalog, currentPlan: current);
  }
}

final membershipViewModelProvider =
    AsyncNotifierProvider<MembershipViewModel, MembershipState>(MembershipViewModel.new);
