import '../models/market_item_model.dart';

/// الأسواق الافتراضية المعروضة بـ HomeScreen وبقائمة اختيار السوق
/// (Market Picker) اللي بيفتحها زر "Markets" بالـ navbar - من أي شاشة
/// بالتطبيق، مش بس من الـ Home.
///
/// كانت هاي القائمة مُعرّفة جوا [HomeScreen] بس (private)، تم رفعها
/// هون كثابت مشترك حتى تقدر [handleGlobalBottomNavTap] تستخدمها وهي
/// فاتحة الـ Market Picker من أي مكان بالتطبيق دون ما تعتمد على حالة
/// HomeScreen.
const List<MarketItemModel> kDefaultMarketItems = [
  MarketItemModel(
    symbol: 'EUR/USD',
    displayName: 'EUR/USD',
    price: 1.0876,
    changePercent: -0.96,
    icon: 'assets/images/euro.png',
  ),
  MarketItemModel(
    symbol: 'GOLD',
    displayName: 'GOLD',
    price: 2045.30,
    changePercent: 1.24,
    icon: 'assets/images/gold.png',
  ),
  MarketItemModel(
    symbol: 'GBP/USD',
    displayName: 'GBP/USD',
    price: 1.2654,
    changePercent: 0.45,
    icon: '',
  ),
];
