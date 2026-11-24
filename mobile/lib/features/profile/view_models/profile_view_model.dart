import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/user_model.dart';
import '../../../providers/app_providers.dart';

/// كل يلي بتحتاجه شاشة البروفايل لترسم نفسها
@immutable
final class ProfileState {
  const ProfileState({
    required this.displayName,
    required this.email,
    required this.avatarPath,
    required this.role,
    this.isLoggingOut = false,
  });

  /// null لما المستخدم ما حط اسم - الشاشة بتعرض "Trader" بداله
  final String? displayName;
  final String? email;
  final String? avatarPath;
  final UserRole role;
  final bool isLoggingOut;

  ProfileState copyWith({bool? isLoggingOut}) => ProfileState(
        displayName: displayName,
        email: email,
        avatarPath: avatarPath,
        role: role,
        isLoggingOut: isLoggingOut ?? this.isLoggingOut,
      );
}

/// ViewModel تبويب Profile: الهوية + تسجيل الخروج. باقي التفضيلات صارت
/// بشاشة Settings (راجع SettingsViewModel).
class ProfileViewModel extends AutoDisposeNotifier<ProfileState> {
  bool _loggingOut = false;

  @override
  ProfileState build() {
    final user = ref.watch(authControllerProvider).currentUser;
    final name = user?.displayName?.trim();
    return ProfileState(
      displayName: name == null || name.isEmpty ? null : name,
      email: user?.email,
      avatarPath: user?.avatarUrl,
      role: user?.role ?? UserRole.trader,
      isLoggingOut: _loggingOut,
    );
  }

  Future<void> logout() async {
    _loggingOut = true;
    state = state.copyWith(isLoggingOut: true);
    try {
      await ref.read(authControllerProvider).logout();
    } finally {
      _loggingOut = false;
    }
  }
}

final profileViewModelProvider =
    AutoDisposeNotifierProvider<ProfileViewModel, ProfileState>(ProfileViewModel.new);
