import 'package:flutter/material.dart';
import '../../models/portfolio_model.dart';
import '../../utils/app_colors.dart';
import '../../l10n/app_localizations.dart';
import '../../utils/app_text_styles.dart';

/// بطاقة عرض معلومات المحفظة الرئيسية
class PortfolioCard extends StatelessWidget {
  const PortfolioCard({
    super.key,
    required this.portfolio,
  });
  
  final PortfolioModel portfolio;
  
  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.all(20),
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
        children: [
          // العنوان
          Text(
            l10n.totalEquityUsd,
            style: AppTextStyles.label.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          
          const SizedBox(height: 8),
          
          // المبلغ الرئيسي
          Text(
            '\$${_formatNumber(portfolio.totalEquity)}',
            style: AppTextStyles.heading1.copyWith(
              fontSize: 32,
              fontWeight: FontWeight.w700,
            ),
          ),
          
          const SizedBox(height: 12),
          
          // التغيير اليومي
          Row(
            children: [
              Icon(
                portfolio.isPositiveChange 
                    ? Icons.trending_up_rounded 
                    : Icons.trending_down_rounded,
                color: portfolio.isPositiveChange 
                    ? AppColors.success 
                    : AppColors.error,
                size: 18,
              ),
              const SizedBox(width: 4),
              Text(
                '${portfolio.isPositiveChange ? '+' : ''}\$${_formatNumber(portfolio.dailyChange.abs())}',
                style: AppTextStyles.bodyMedium.copyWith(
                  color: portfolio.isPositiveChange 
                      ? AppColors.success 
                      : AppColors.error,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(width: 4),
              Text(
                '(${portfolio.dailyChangePercent.toStringAsFixed(2)}%)',
                style: AppTextStyles.bodySmall.copyWith(
                  color: portfolio.isPositiveChange 
                      ? AppColors.success 
                      : AppColors.error,
                ),
              ),
              const Spacer(),
              Text(
                l10n.dailyPl,
                style: AppTextStyles.labelSmall.copyWith(
                  color: AppColors.textHint,
                ),
              ),
            ],
          ),
          
          const SizedBox(height: 16),
          
          // خط فاصل
          Container(
            height: 1,
            color: AppColors.fieldBorder.withOpacity(0.2),
          ),
          
          const SizedBox(height: 16),
          
          // معلومات إضافية
          Row(
            children: [
              Expanded(
                child: _InfoColumn(
                  label: l10n.availableBalance,
                  value: '\$${_formatNumber(portfolio.availableBalance)}',
                  valueColor: AppColors.textPrimary,
                ),
              ),
              Expanded(
                child: _InfoColumn(
                  label: l10n.marginUsed,
                  value: '\$${_formatNumber(portfolio.marginUsed)}',
                  valueColor: AppColors.textPrimary,
                ),
              ),
            ],
          ),
          
          const SizedBox(height: 12),
          
          Row(
            children: [
              Expanded(
                child: _InfoColumn(
                  label: l10n.availableBalance,
                  value: '${portfolio.isPositivePL ? '+' : ''}\$${_formatNumber(portfolio.profitLoss.abs())}',
                  valueColor: portfolio.isPositivePL 
                      ? AppColors.success 
                      : AppColors.error,
                ),
              ),
              Expanded(
                child: _InfoColumn(
                  label: l10n.availableBalance,
                  value: '${portfolio.profitLossPercent.toStringAsFixed(2)}%',
                  valueColor: AppColors.textPrimary,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
  
  String _formatNumber(double number) {
    return number.toStringAsFixed(2).replaceAllMapped(
      RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'),
      (Match m) => '${m[1]},',
    );
  }
}

/// عمود معلومات صغير
class _InfoColumn extends StatelessWidget {
  const _InfoColumn({
    required this.label,
    required this.value,
    required this.valueColor,
  });
  
  final String label;
  final String value;
  final Color valueColor;
  
  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: AppTextStyles.labelSmall.copyWith(
            color: AppColors.textHint,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          value,
          style: AppTextStyles.bodyMedium.copyWith(
            color: valueColor,
            fontWeight: FontWeight.w600,
            fontSize: 13,
          ),
        ),
      ],
    );
  }
}
