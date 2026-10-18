import 'package:flutter/material.dart';
import '../../utils/app_colors.dart';

/// بيانات عنصر واحد في شريط التنقل السفلي
final class NavBarItemData {
  const NavBarItemData({
    required this.imagePath,
    this.useNativeColor = false,
    this.size = 30,
  });

  /// مسار أيقونة العنصر
  final String imagePath;

  /// عندما تكون true، تُعرض الصورة بألوانها الأصلية دون أي تلوين إضافي
  final bool useNativeColor;

  /// حجم الأيقونة (عرض/طول). القيمة الافتراضية 30 هي نفس حجم كل
  /// أيقونات الشريط بباقي الشاشات. بتُستخدم لتكبير أيقونة معيّنة
  /// (مثلاً أيقونة الـ AI بشاشة [DiscussionScreen]) دون التأثير على
  /// باقي الشاشات يلي بتستخدم [AppBottomNav.defaultItems] الافتراضية.
  final double size;
}

/// شريط التنقل السفلي المشترك بين كل شاشات التطبيق
///
/// يُستخدم في HomeScreen وTradeScreen (وأي شاشة رئيسية أخرى مستقبلًا)
/// لتفادي تكرار نفس الكود في كل شاشة.
class AppBottomNav extends StatelessWidget {
  const AppBottomNav({
    super.key,
    required this.selectedIndex,
    required this.onTap,
    this.items = defaultItems,
  });

  /// فهرس العنصر المحدد حاليًا
  final int selectedIndex;

  /// دالة تُستدعى عند الضغط على أي عنصر، وتُمرّر فهرسه
  final ValueChanged<int> onTap;

  /// عناصر الشريط
  final List<NavBarItemData> items;

  /// عناصر شريط التنقل الافتراضية للتطبيق بالكامل
  /// (Home - Markets - AI - News - Profile)
  static const List<NavBarItemData> defaultItems = [
    NavBarItemData(imagePath: 'assets/images/nav_home.png'),
    NavBarItemData(imagePath: 'assets/images/nav_markets.png'),
    NavBarItemData(
      imagePath: 'assets/images/strategy_assistant.png',
      useNativeColor: true,
    ),
    NavBarItemData(imagePath: 'assets/images/nav_pages.png'),
    NavBarItemData(imagePath: 'assets/images/nav_profile.png'),
  ];

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.bgSurface.withOpacity(0.85),
        border: Border(
          top: BorderSide(
            color: AppColors.fieldBorder.withOpacity(0.15),
            width: 1,
          ),
        ),
      ),
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              for (var i = 0; i < items.length; i++)
                _NavItem(
                  data: items[i],
                  isSelected: selectedIndex == i,
                  onTap: () => onTap(i),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

/// عنصر واحد داخل شريط التنقل السفلي
class _NavItem extends StatelessWidget {
  const _NavItem({
    required this.data,
    required this.isSelected,
    required this.onTap,
  });

  final NavBarItemData data;
  final bool isSelected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(8),
        child: Image.asset(
          data.imagePath,
          width: data.size,
          height: data.size,
          color: data.useNativeColor
              ? null
              : (isSelected ? AppColors.accentCyan : AppColors.textHint),
        ),
      ),
    );
  }
}
