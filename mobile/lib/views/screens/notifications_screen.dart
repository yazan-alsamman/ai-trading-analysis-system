import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../controllers/notifications_repository.dart';
import '../../l10n/app_localizations.dart';
import '../../providers/app_providers.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_text_styles.dart';
import '../widgets/auth_background.dart';
import '../widgets/notification_item_card.dart';

/// شاشة "Notifications" - تعرض كل إشعارات التداول (إشارات شراء/بيع،
/// تنبيهات سعر، ورسائل عامة)
///
/// الدور المعماري: **View (واجهة)**
///
/// البيانات كلها من [NotificationsRepository] المشترك (نفس المصدر
/// يلي [HomeScreen] بتقرأ منه عدّاد النقطة الحمرا فوق الجرس)، حتى
/// تعليم إشعار كمقروء هون ينعكس فورًا هناك كمان.
///
/// نقطة الوصول لهذه الشاشة: أيقونة الجرس بأعلى [HomeScreen]
class NotificationsScreen extends ConsumerWidget {
  const NotificationsScreen({super.key});

  /// عند الضغط على إشعار: تعليمه كمقروء بالـ Repository المشترك
  void _handleTapNotification(WidgetRef ref, String notificationId) {
    ref.read(notificationsRepositoryProvider).markAsRead(notificationId);
  }

  /// عند سحب إشعار وحذفه: حذفه نهائيًا من الـ Repository المشترك
  void _handleDismissNotification(WidgetRef ref, String notificationId) {
    ref
        .read(notificationsRepositoryProvider)
        .removeNotification(notificationId);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    return Scaffold(
      body: AuthBackground(
        child: SafeArea(
          bottom: false,
          child: Column(
            children: [
              _buildTopBar(context, l10n),
              Expanded(child: _buildBody(context, ref, l10n)),
            ],
          ),
        ),
      ),
    );
  }

  /// شريط علوي: سهم رجوع + عنوان الشاشة
  Widget _buildTopBar(BuildContext context, AppLocalizations l10n) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(10, 6, 20, 0),
      child: Row(
        children: [
          InkWell(
            onTap: () => Navigator.of(context).maybePop(),
            borderRadius: BorderRadius.circular(14),
            child: const Padding(
              padding: EdgeInsets.all(12),
              child: Icon(
                Icons.arrow_back_rounded,
                color: AppColors.textPrimary,
                size: 22,
              ),
            ),
          ),
          const SizedBox(width: 4),
          Text(l10n.notifications, style: AppTextStyles.heading2),
        ],
      ),
    );
  }

  /// محتوى الشاشة: قائمة الإشعارات (من الـ Repository المشترك)، أو
  /// رسالة "لا يوجد إشعارات"
  Widget _buildBody(BuildContext context, WidgetRef ref, AppLocalizations l10n) {
    final notifications =
        ref.watch(notificationsRepositoryProvider).notifications;

    if (notifications.isEmpty) {
      return _buildEmptyState(l10n);
    }

    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
      itemCount: notifications.length,
      itemBuilder: (context, index) {
        final notification = notifications[index];
        return Dismissible(
          key: ValueKey(notification.id),
          direction: DismissDirection.endToStart,
          onDismissed: (_) =>
              _handleDismissNotification(ref, notification.id),
          background: _buildDismissBackground(),
          child: NotificationItemCard(
            notification: notification,
            onTap: () => _handleTapNotification(ref, notification.id),
            onDelete: () =>
                _handleDismissNotification(ref, notification.id),
          ),
        );
      },
    );
  }

  /// خلفية حمرا مع أيقونة سلة مهملات، تظهر خلف الإشعار أثناء سحبه للحذف
  Widget _buildDismissBackground() {
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.symmetric(horizontal: 20),
      alignment: Alignment.centerRight,
      decoration: BoxDecoration(
        color: AppColors.error.withOpacity(0.85),
        borderRadius: BorderRadius.circular(18),
      ),
      child: const Icon(
        Icons.delete_outline_rounded,
        color: AppColors.textPrimary,
        size: 24,
      ),
    );
  }

  /// حالة "لا يوجد إشعارات"
  Widget _buildEmptyState(AppLocalizations l10n) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.notifications_off_outlined,
              color: AppColors.textHint,
              size: 48,
            ),
            const SizedBox(height: 16),
            Text(
              l10n.noNotificationsYet,
              style: AppTextStyles.bodyMedium.copyWith(
                color: AppColors.textSecondary,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
