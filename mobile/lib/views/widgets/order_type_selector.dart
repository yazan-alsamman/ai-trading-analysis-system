import 'package:flutter/material.dart';
import '../../l10n/app_localizations.dart';
import '../../models/order_type_model.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_text_styles.dart';

/// شريط اختيار نوع الأمر (Market / Limit / Stop)
class OrderTypeSelector extends StatelessWidget {
  const OrderTypeSelector({
    super.key,
    required this.selected,
    required this.onChanged,
  });

  final OrderType selected;
  final ValueChanged<OrderType> onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: AppColors.fieldFill,
        borderRadius: BorderRadius.circular(30),
      ),
      child: Row(
        children: [
          for (final type in OrderType.values)
            Expanded(
              child: _Segment(
                type: type,
                isSelected: type == selected,
                onTap: () => onChanged(type),
              ),
            ),
        ],
      ),
    );
  }
}

class _Segment extends StatelessWidget {
  const _Segment({
    required this.type,
    required this.isSelected,
    required this.onTap,
  });

  final OrderType type;
  final bool isSelected;
  final VoidCallback onTap;

  String _labelFor(OrderType type, AppLocalizations l10n) {
    switch (type) {
      case OrderType.market:
        return l10n.orderTypeMarket;
      case OrderType.limit:
        return l10n.orderTypeLimit;
      case OrderType.stop:
        return l10n.orderTypeStop;
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOut,
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.bgSurface : Colors.transparent,
          borderRadius: BorderRadius.circular(26),
        ),
        alignment: Alignment.center,
        child: Text(
          _labelFor(type, l10n),
          style: AppTextStyles.bodyMedium.copyWith(
            color: isSelected ? AppColors.textPrimary : AppColors.textHint,
            fontWeight: isSelected ? FontWeight.w700 : FontWeight.w400,
          ),
        ),
      ),
    );
  }
}
