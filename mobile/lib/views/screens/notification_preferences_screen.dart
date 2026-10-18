import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_text_styles.dart';
import '../widgets/auth_background.dart';

/// شاشة "Notification Preferences" - يختار المستخدم فيها أي أنواع
/// التنبيهات بده يستقبلها
///
/// الدور المعماري: **View (واجهة)**
///
/// حالة عرض محلية بسيطة (Local State) لحين ربطها بإعدادات حساب
/// حقيقية عبر API - نفس ملاحظة [SecurityScreen] لخيارات الحماية.
///
/// تُفتح من "Notification Preferences" بـ [ProfileScreen]
class NotificationPreferencesScreen extends StatefulWidget {
  const NotificationPreferencesScreen({super.key});

  @override
  State<NotificationPreferencesScreen> createState() =>
      _NotificationPreferencesScreenState();
}

class _NotificationPreferencesScreenState
    extends State<NotificationPreferencesScreen> {
  bool _pushEnabled = true;
  bool _priceAlerts = true;
  bool _tradeConfirmations = true;
  bool _marketNews = true;
  bool _aiInsights = false;
  bool _promotions = false;

  /// تبديل المفتاح الرئيسي: بيوقف/يشغّل كل التنبيهات الفرعية دفعة
  /// وحدة، مطابق لسلوك أنظمة الإشعارات المعروفة (iOS/Android)
  void _handleMasterToggle(bool value) {
    setState(() {
      _pushEnabled = value;
      if (!value) {
        _priceAlerts = false;
        _tradeConfirmations = false;
        _marketNews = false;
        _aiInsights = false;
        _promotions = false;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return Scaffold(
      body: AuthBackground(
        child: SafeArea(
          bottom: false,
          child: Column(
            children: [
              _buildTopBar(l10n),
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
                  children: [
                    const SizedBox(height: 8),
                    _buildSwitchTile(
                      icon: Icons.notifications_active_rounded,
                      title: l10n.pushNotifications,
                      subtitle: l10n.pushNotificationsSubtitle,
                      value: _pushEnabled,
                      onChanged: _handleMasterToggle,
                      highlighted: true,
                    ),
                    const SizedBox(height: 20),
                    _buildSectionLabel(l10n.trading),
                    const SizedBox(height: 12),
                    _buildSwitchTile(
                      icon: Icons.trending_up_rounded,
                      title: l10n.priceAlerts,
                      subtitle: l10n.priceAlertsSubtitle,
                      value: _pushEnabled && _priceAlerts,
                      onChanged: _pushEnabled
                          ? (value) => setState(() => _priceAlerts = value)
                          : null,
                    ),
                    _buildSwitchTile(
                      icon: Icons.receipt_long_rounded,
                      title: l10n.tradeConfirmations,
                      subtitle: l10n.tradeConfirmationsSubtitle,
                      value: _pushEnabled && _tradeConfirmations,
                      onChanged: _pushEnabled
                          ? (value) => setState(() => _tradeConfirmations = value)
                          : null,
                    ),
                    const SizedBox(height: 20),
                    _buildSectionLabel(l10n.newsAndInsights),
                    const SizedBox(height: 12),
                    _buildSwitchTile(
                      icon: Icons.newspaper_rounded,
                      title: l10n.marketNews,
                      subtitle: l10n.marketNewsSubtitle,
                      value: _pushEnabled && _marketNews,
                      onChanged: _pushEnabled
                          ? (value) => setState(() => _marketNews = value)
                          : null,
                    ),
                    _buildSwitchTile(
                      icon: Icons.auto_awesome_rounded,
                      title: l10n.aiInsights,
                      subtitle: l10n.aiInsightsSubtitle,
                      value: _pushEnabled && _aiInsights,
                      onChanged: _pushEnabled
                          ? (value) => setState(() => _aiInsights = value)
                          : null,
                    ),
                    const SizedBox(height: 20),
                    _buildSectionLabel(l10n.other),
                    const SizedBox(height: 12),
                    _buildSwitchTile(
                      icon: Icons.local_offer_outlined,
                      title: l10n.promotionsAndOffers,
                      subtitle: l10n.promotionsAndOffersSubtitle,
                      value: _pushEnabled && _promotions,
                      onChanged: _pushEnabled
                          ? (value) => setState(() => _promotions = value)
                          : null,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// شريط علوي: سهم رجوع + عنوان الشاشة
  Widget _buildTopBar(AppLocalizations l10n) {
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
          Text(l10n.notificationPreferences, style: AppTextStyles.heading2),
        ],
      ),
    );
  }

  /// عنوان قسم صغير
  Widget _buildSectionLabel(String label) {
    return Text(
      label,
      style: AppTextStyles.label.copyWith(
        color: AppColors.textHint,
        letterSpacing: 0.6,
      ),
    );
  }

  /// عنصر تبديل (Switch) واحد بقائمة التفضيلات
  Widget _buildSwitchTile({
    required IconData icon,
    required String title,
    required String subtitle,
    required bool value,
    required ValueChanged<bool>? onChanged,
    bool highlighted = false,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
      decoration: BoxDecoration(
        color: highlighted
            ? AppColors.accentGreen.withOpacity(0.1)
            : AppColors.bgSurface.withOpacity(0.7),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: highlighted
              ? AppColors.accentGreen.withOpacity(0.4)
              : AppColors.fieldBorder.withOpacity(0.3),
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: AppColors.accentCyan.withOpacity(0.15),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, color: AppColors.accentCyan, size: 20),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: AppTextStyles.bodyMedium.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: AppTextStyles.bodySmall.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
            activeColor: AppColors.accentGreen,
          ),
        ],
      ),
    );
  }
}
