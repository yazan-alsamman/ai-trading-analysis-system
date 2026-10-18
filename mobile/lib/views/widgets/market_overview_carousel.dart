import 'package:flutter/material.dart';
import '../../models/market_item_model.dart';
import '../../utils/app_colors.dart';
import 'market_item_card.dart';

/// كاروسيل أفقي لعرض عناصر السوق مع أسهم تنقل عائمة
/// فوق حواف القائمة (بدل أزرار ثابتة في الرأس).
class MarketOverviewCarousel extends StatefulWidget {
  const MarketOverviewCarousel({
    super.key,
    required this.items,
    required this.onTrade,
  });

  final List<MarketItemModel> items;
  final ValueChanged<MarketItemModel> onTrade;

  @override
  State<MarketOverviewCarousel> createState() =>
      _MarketOverviewCarouselState();
}

class _MarketOverviewCarouselState extends State<MarketOverviewCarousel> {
  final ScrollController _controller = ScrollController();

  /// مقدار التمرير لكل ضغطة سهم (عرض البطاقة + الهامش)
  static const double _scrollStep = 180;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _scrollBy(double delta) {
    if (!_controller.hasClients) return;
    final target = (_controller.offset + delta).clamp(
      0.0,
      _controller.position.maxScrollExtent,
    );
    _controller.animateTo(
      target,
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeOut,
    );
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 200,
      child: Stack(
        alignment: Alignment.center,
        children: [
          ListView.builder(
            controller: _controller,
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            itemCount: widget.items.length,
            itemBuilder: (context, index) {
              final item = widget.items[index];
              return MarketItemCard(
                item: item,
                onTrade: () => widget.onTrade(item),
              );
            },
          ),
          _EdgeArrow(
            isStart: true,
            icon: Icons.chevron_left_rounded,
            onTap: () => _scrollBy(-_scrollStep),
          ),
          _EdgeArrow(
            isStart: false,
            icon: Icons.chevron_right_rounded,
            onTap: () => _scrollBy(_scrollStep),
          ),
        ],
      ),
    );
  }
}

/// سهم عائم عند حافة الكاروسيل مع تدرج شفاف خلفه
///
/// [isStart] بيحدد سهم "الرجوع للخلف" (أيقونة `chevron_left` ثابتة،
/// تمرير -delta) مقابل سهم "الاستمرار للأمام" (أيقونة `chevron_right`
/// ثابتة، تمرير +delta).
///
/// **المكان فقط** بيتغيّر حسب اللغة عبر [AlignmentDirectional]:
/// - بالإنجليزي (LTR): سهم الرجوع (`<`) يسار، وسهم الاستمرار (`>`) يمين.
/// - بالعربي (RTL): بينعكس المكان تلقائيًا - سهم الرجوع (`<`) يصير
///   يمين، وسهم الاستمرار (`>`) يصير يسار.
///
/// ⚠️ عمدًا **بدون** أي `Transform.flip` على الأيقونة نفسها - شكل كل
/// سهم ثابت دايمًا (`<` يضل `<` مهما كان مكانه)، وبس المكان هو يلي
/// بينتقل. هيك بالضبط كانت المشكلة السابقة: كنا عم نبدّل المكان *و*
/// نقلب شكل الأيقونة سوا، فكانت النتيجة مو متزامنة صح.
class _EdgeArrow extends StatelessWidget {
  const _EdgeArrow({
    required this.isStart,
    required this.icon,
    required this.onTap,
  });

  final bool isStart;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final alignment = isStart
        ? AlignmentDirectional.centerStart
        : AlignmentDirectional.centerEnd;

    return Align(
      alignment: alignment,
      child: IgnorePointer(
        ignoring: false,
        child: Container(
          width: 48,
          height: 200,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: alignment,
              end: isStart
                  ? AlignmentDirectional.centerEnd
                  : AlignmentDirectional.centerStart,
              colors: [
                AppColors.bgDeep.withOpacity(0.85),
                AppColors.bgDeep.withOpacity(0.0),
              ],
            ),
          ),
          child: GestureDetector(
            onTap: onTap,
            child: Container(
              width: 30,
              height: 30,
              decoration: BoxDecoration(
                color: AppColors.accentGreen.withOpacity(0.15),
                shape: BoxShape.circle,
              ),
              child: Icon(
                icon,
                color: AppColors.accentGreen,
                size: 20,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
