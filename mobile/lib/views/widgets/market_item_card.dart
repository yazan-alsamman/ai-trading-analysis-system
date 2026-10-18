import 'package:flutter/material.dart';
import '../../models/market_item_model.dart';
import '../../utils/app_colors.dart';
import '../../l10n/app_localizations.dart';
import '../../utils/app_text_styles.dart';

/// بطاقة عرض عنصر من السوق
class MarketItemCard extends StatelessWidget {
  const MarketItemCard({
    super.key,
    required this.item,
    required this.onTrade,
  });

  final MarketItemModel item;
  final VoidCallback onTrade;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final trendColor = item.isPositive ? AppColors.success : AppColors.error;

    return Container(
      width: 168,
      margin: const EdgeInsets.only(right: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF0D2539),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: AppColors.fieldBorder.withOpacity(0.3),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // الأيقونة
          item.icon.isNotEmpty
              ? Image.asset(
                  item.icon,
                  width: 28,
                  height: 28,
                )
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

          const SizedBox(height: 8),

          // اسم العنصر
          Text(
            l10n.marketName(item.symbol),
            style: AppTextStyles.labelSmall.copyWith(
              color: AppColors.textSecondary,
              fontSize: 12,
            ),
          ),

          const SizedBox(height: 4),

          // السعر
          Text(
            item.symbol.contains('/')
                ? item.price.toStringAsFixed(4)
                : '\$${item.price.toStringAsFixed(2)}',
            style: AppTextStyles.heading3.copyWith(
              fontSize: 18,
              fontWeight: FontWeight.w700,
            ),
          ),

          const SizedBox(height: 3),

          // التغيير: سهم صاعد/هابط + النسبة
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                item.isPositive
                    ? Icons.trending_up_rounded
                    : Icons.trending_down_rounded,
                size: 14,
                color: trendColor,
              ),
              const SizedBox(width: 3),
              Text(
                item.changeText,
                style: AppTextStyles.labelSmall.copyWith(
                  color: trendColor,
                  fontSize: 12,
                ),
              ),
            ],
          ),

          const SizedBox(height: 12),

          // زر Trade
          SizedBox(
            width: double.infinity,
            height: 32,
            child: ElevatedButton(
              onPressed: onTrade,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF5EFFB4),
                foregroundColor: AppColors.bgDeep,
                elevation: 0,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(18),
                ),
                padding: EdgeInsets.zero,
              ),
              child: Text(
                l10n.trade,
                style: AppTextStyles.labelSmall.copyWith(
                  color: AppColors.bgDeep,
                  fontWeight: FontWeight.w700,
                  fontSize: 13,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

