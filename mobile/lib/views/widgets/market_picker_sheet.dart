import 'package:flutter/material.dart';
import '../../models/market_item_model.dart';
import '../../utils/app_colors.dart';
import '../../l10n/app_localizations.dart';
import '../../utils/app_text_styles.dart';

/// Bottom Sheet لاختيار سوق من قائمة الأسواق المتاحة.
///
/// مُستخدَمة من زر "Markets" بالـ navbar - سواء انفتحت من HomeScreen
/// أو من أي شاشة تانية بالتطبيق عبر [handleGlobalBottomNavTap]، حتى
/// ما يضطر المستخدم يرجع عالهوم أول قبل ما يقدر يختار سوق.
///
/// (كانت هاي private جوا HomeScreen باسم _MarketPickerSheet، تم
/// رفعها كـ widget مشترك حتى تصير قابلة لإعادة الاستخدام).
class MarketPickerSheet extends StatelessWidget {
  const MarketPickerSheet({super.key, required this.items});

  final List<MarketItemModel> items;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return SafeArea(
      child: Container(
        margin: const EdgeInsets.fromLTRB(12, 0, 12, 12),
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [AppColors.bgSurface, AppColors.bgMid],
          ),
          borderRadius: BorderRadius.circular(24),
          border: Border.all(
            color: AppColors.gradientMid,
            width: 1.4,
          ),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // مقبض صغير أعلى القائمة (Drag Handle)
            Center(
              child: Container(
                width: 40,
                height: 4,
                margin: const EdgeInsets.only(bottom: 16),
                decoration: BoxDecoration(
                  color: AppColors.fieldBorder.withOpacity(0.5),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            Text(
              l10n.selectAMarket,
              style: AppTextStyles.heading3.copyWith(fontSize: 16),
            ),
            const SizedBox(height: 12),
            ...items.map(
              (item) => _MarketPickerTile(
                item: item,
                onTap: () => Navigator.of(context).pop(item),
              ),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}

/// صف واحد داخل [MarketPickerSheet] يمثّل سوق واحد قابل للاختيار
class _MarketPickerTile extends StatelessWidget {
  const _MarketPickerTile({required this.item, required this.onTap});

  final MarketItemModel item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 12),
        child: Row(
          children: [
            Padding(
              padding: const EdgeInsets.only(right: 12),
              child: item.icon.isNotEmpty
                  ? Image.asset(item.icon, width: 28, height: 28)
                  : Container(
                      padding: const EdgeInsets.all(6),
                      decoration: BoxDecoration(
                        color: AppColors.accentCyan.withOpacity(0.15),
                        shape: BoxShape.circle,
                      ),
                      child: Icon(
                        item.fallbackIcon,
                        size: 16,
                        color: AppColors.accentCyan,
                      ),
                    ),
            ),
            Expanded(
              child: Text(
                l10n.marketName(item.symbol),
                style: AppTextStyles.bodyMedium.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            Text(
              item.price.toStringAsFixed(item.symbol.contains('/') ? 4 : 2),
              style: AppTextStyles.bodyMedium.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(width: 10),
            Text(
              item.changeText,
              style: AppTextStyles.bodySmall.copyWith(
                color: item.isPositive ? AppColors.buyGreen : AppColors.sellRed,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
