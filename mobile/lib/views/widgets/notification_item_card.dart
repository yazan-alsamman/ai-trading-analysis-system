import 'package:flutter/material.dart';
import '../../models/notification_model.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_text_styles.dart';

// ═══════════════════════════════════════════════════════════
// Notification Item Card - بطاقة إشعار واحد
// ═══════════════════════════════════════════════════════════

/// بطاقة عرض إشعار واحد بشاشة [NotificationsScreen]
///
/// الدور المعماري: **View (واجهة) - Widget قابل لإعادة الاستخدام**
///
/// التخطيط: أيقونة دائرية ملوّنة حسب نوع الإشعار (يسار) + العنوان
/// والرسالة (وسط) + الوقت ونقطة "غير مقروء" إذا لزم (يمين/فوق)
class NotificationItemCard extends StatelessWidget {
  const NotificationItemCard({
    super.key,
    required this.notification,
    this.onTap,
    this.onDelete,
  });

  /// بيانات الإشعار
  final NotificationModel notification;

  /// يُستدعى عند الضغط على الكارد (فتح السوق المرتبط بالإشعار مثلاً)
  final VoidCallback? onTap;

  /// يُستدعى عند الضغط على زر الحذف - اختياري: إذا ما تم تمريره، ما
  /// تُعرض أيقونة الحذف إطلاقًا (متل استخدام الكارد بمعاينة الهوم
  /// المصغّرة لو احتجناه لاحقًا)
  final VoidCallback? onDelete;

  @override
  Widget build(BuildContext context) {
    final visuals = _visualsFor(notification.type);

    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 14),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          // إشعار غير مقروء بيبان بخلفية أوضح شوي حتى يلفت الانتباه
          color: notification.isRead
              ? AppColors.bgSurface.withOpacity(0.75)
              : AppColors.bgSurface.withOpacity(0.95),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(
            color: notification.isRead
                ? AppColors.fieldBorder.withOpacity(0.3)
                : visuals.color.withOpacity(0.45),
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildIcon(visuals),
            const SizedBox(width: 14),
            Expanded(child: _buildContent(visuals)),
          ],
        ),
      ),
    );
  }

  /// أيقونة دائرية ملوّنة حسب نوع الإشعار
  Widget _buildIcon(_NotificationVisuals visuals) {
    return Container(
      width: 42,
      height: 42,
      decoration: BoxDecoration(
        color: visuals.color.withOpacity(0.15),
        shape: BoxShape.circle,
      ),
      child: Icon(visuals.icon, color: visuals.color, size: 22),
    );
  }

  /// عنوان + رمز السوق (إن وجد) + الرسالة + الوقت
  Widget _buildContent(_NotificationVisuals visuals) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                notification.title,
                style: AppTextStyles.bodyMedium.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            // نقطة "غير مقروء"
            if (!notification.isRead)
              Container(
                width: 8,
                height: 8,
                margin: const EdgeInsets.only(left: 8, top: 4),
                decoration: BoxDecoration(
                  color: AppColors.accentGreen,
                  shape: BoxShape.circle,
                ),
              ),
            // زر حذف الإشعار
            if (onDelete != null)
              Padding(
                padding: const EdgeInsets.only(left: 4),
                child: InkWell(
                  onTap: onDelete,
                  borderRadius: BorderRadius.circular(14),
                  child: Padding(
                    padding: const EdgeInsets.all(4),
                    child: Icon(
                      Icons.close_rounded,
                      size: 16,
                      color: AppColors.textHint,
                    ),
                  ),
                ),
              ),
          ],
        ),
        if (notification.symbol != null) ...[
          const SizedBox(height: 4),
          Text(
            notification.symbol!,
            style: AppTextStyles.labelSmall.copyWith(color: visuals.color),
          ),
        ],
        const SizedBox(height: 8),
        Text(
          notification.message,
          style: AppTextStyles.bodySmall.copyWith(
            color: AppColors.textSecondary,
            height: 1.5,
          ),
        ),
        const SizedBox(height: 10),
        Text(
          notification.timeAgo,
          style: AppTextStyles.labelSmall.copyWith(color: AppColors.textHint),
        ),
      ],
    );
  }

  _NotificationVisuals _visualsFor(NotificationType type) {
    switch (type) {
      case NotificationType.buySignal:
        return const _NotificationVisuals(
          icon: Icons.trending_up_rounded,
          color: AppColors.buyGreen,
        );
      case NotificationType.sellSignal:
        return const _NotificationVisuals(
          icon: Icons.trending_down_rounded,
          color: AppColors.sellRed,
        );
      case NotificationType.priceAlert:
        return const _NotificationVisuals(
          icon: Icons.notifications_active_rounded,
          color: AppColors.gradientStart,
        );
      case NotificationType.general:
        return const _NotificationVisuals(
          icon: Icons.info_outline_rounded,
          color: AppColors.accentCyan,
        );
    }
  }
}

/// أيقونة + لون مرتبطين بنوع الإشعار
class _NotificationVisuals {
  const _NotificationVisuals({required this.icon, required this.color});

  final IconData icon;
  final Color color;
}
