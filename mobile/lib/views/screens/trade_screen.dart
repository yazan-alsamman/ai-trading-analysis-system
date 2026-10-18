import 'dart:ui';

import 'package:flutter/material.dart';
import '../../l10n/app_localizations.dart';
import '../../models/market_item_model.dart';
import '../../models/order_type_model.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_navigation.dart';
import '../../utils/app_text_styles.dart';
import '../widgets/app_bottom_nav.dart';
import '../widgets/auth_background.dart';
import '../widgets/order_type_selector.dart';
import '../widgets/trade_form_fields.dart';
import '../widgets/trade_price_chart.dart';

/// شاشة التداول (Markets / Trade Screen)
///
/// الدور المعماري: **View (واجهة)**
/// - عرض سعر الرمز المُختار مباشرة (Live) مع نسبة التغيير
/// - عرض رسم بياني مبسّط لحركة السعر
/// - نموذج فتح صفقة: نوع الأمر / السعر / الكمية / الرافعة المالية
///   / وقف الخسارة / جني الأرباح
/// - ملخص فوري: الهامش المطلوب، الرسوم التقديرية، سعر التصفية التقديري
///
/// يُفتح من [HomeScreen] عند الضغط على زر "Trade" فوق أي عنصر
/// من قائمة "Market Overview".
class TradeScreen extends StatefulWidget {
  const TradeScreen({super.key, required this.market});

  /// عنصر السوق المُختار للتداول عليه
  final MarketItemModel market;

  @override
  State<TradeScreen> createState() => _TradeScreenState();
}

class _TradeScreenState extends State<TradeScreen> {
  // ═══════════════════════════════════════════════════════════
  // Controllers & State - المتحكمات والحالة
  // ═══════════════════════════════════════════════════════════

  late final TextEditingController _priceController;
  late final TextEditingController _quantityController;
  late final TextEditingController _stopLossController;
  late final TextEditingController _takeProfitController;

  OrderType _orderType = OrderType.limit;
  double _leverage = 10;
  int _selectedBottomIndex = 1; // تبويب Markets

  /// نسبة الرسوم التقديرية من قيمة الصفقة (Notional)
  static const double _feeRate = 0.001;

  /// أقصى رافعة مالية متاحة
  static const double _maxLeverage = 50;

  @override
  void initState() {
    super.initState();
    _priceController = TextEditingController(text: '0.00');
    _quantityController = TextEditingController(text: '1.0');
    _stopLossController = TextEditingController(text: '0.00');
    _takeProfitController = TextEditingController(text: '0.00');
  }

  @override
  void dispose() {
    _priceController.dispose();
    _quantityController.dispose();
    _stopLossController.dispose();
    _takeProfitController.dispose();
    super.dispose();
  }

  // ═══════════════════════════════════════════════════════════
  // Derived Values - قيم محسوبة
  // ═══════════════════════════════════════════════════════════

  bool get _isFxPair => widget.market.symbol.contains('/');

  int get _priceDecimals => _isFxPair ? 4 : 2;

  double get _quantity => double.tryParse(_quantityController.text) ?? 0;

  double get _limitPrice => double.tryParse(_priceController.text) ?? 0;

  /// السعر الفعلي المستخدم في الحسابات:
  /// - أمر السوق دائمًا يستخدم السعر الحالي
  /// - أمر Limit/Stop يستخدم السعر المُدخل إن وُجد، وإلا يعود للسعر الحالي
  double get _effectivePrice {
    if (!_orderType.requiresPrice || _limitPrice <= 0) {
      return widget.market.price;
    }
    return _limitPrice;
  }

  double get _requiredMargin =>
      _leverage <= 0 ? 0 : (_effectivePrice * _quantity) / _leverage;

  double get _estFee => _effectivePrice * _quantity * _feeRate;

  double get _estLiquidationPrice {
    if (_leverage <= 0) return 0;
    final value = _effectivePrice * (1 - 1 / _leverage);
    return value < 0 ? 0 : value;
  }

  double get _dailyChangeAmount =>
      widget.market.price * widget.market.changePercent / 100;

  // ═══════════════════════════════════════════════════════════
  // Event Handlers - معالجات الأحداث
  // ═══════════════════════════════════════════════════════════

  void _handleOrderTypeChanged(OrderType type) {
    setState(() => _orderType = type);
  }

  void _handleLeverageChanged(double value) {
    setState(() => _leverage = value);
  }

  void _handleFieldChanged(String _) {
    setState(() {});
  }

  /// معالج ضغطات شريط التنقل السفلي - مفوّض بالكامل للمعالج المشترك
  /// [handleGlobalBottomNavTap]. كان زر "Home" هون تحديدًا يستخدم
  /// `maybePop()` (يرجع درجة وحدة بس)، فلو المستخدم وصل لهاي الشاشة
  /// من مسار أعمق من درجة وحدة، الزر ما كان يرجّعه فعليًا عالهوم.
  /// المعالج المشترك بيرجع لجذر التطبيق دايمًا، بغض النظر عن العمق.
  void _handleBottomNavTap(int index) => handleGlobalBottomNavTap(index);

  void _handleBuy() => _showConfirmOrderDialog('BUY');

  void _handleSell() => _showConfirmOrderDialog('SELL');

  /// يعرض نافذة "Confirm Order" لمراجعة تفاصيل الصفقة قبل التنفيذ
  void _showConfirmOrderDialog(String side) {
    // نلتقط القيم الحالية لحظة الضغط حتى لا تتغير أثناء عرض النافذة
    final quantity = _quantity;
    final leverage = _leverage;
    final symbol = AppLocalizations.of(context)!.marketName(widget.market.symbol);

    showDialog(
      context: context,
      barrierColor: Colors.transparent,
      builder: (dialogContext) {
        return _BlurredOrderDialogRoute(
          child: _ConfirmOrderDialog(
            symbol: symbol,
            side: side,
            quantity: quantity,
            leverage: leverage,
            onCancel: () => Navigator.of(dialogContext).pop(),
            onConfirm: () {
              Navigator.of(dialogContext).pop();
              _showOrderExecutedDialog(
                side: side,
                quantity: quantity,
                symbol: symbol,
              );
            },
          ),
        );
      },
    );
  }

  /// يعرض نافذة "Order Executed" بعد تأكيد تنفيذ الصفقة بنجاح
  void _showOrderExecutedDialog({
    required String side,
    required double quantity,
    required String symbol,
  }) {
    showDialog(
      context: context,
      barrierColor: Colors.transparent,
      builder: (dialogContext) {
        return _BlurredOrderDialogRoute(
          child: _OrderExecutedDialog(
            side: side,
            quantity: quantity,
            symbol: symbol,
            onDone: () => Navigator.of(dialogContext).pop(),
          ),
        );
      },
    );
  }

  // ═══════════════════════════════════════════════════════════
  // Build Methods - دوال البناء
  // ═══════════════════════════════════════════════════════════

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return Scaffold(
      body: AuthBackground(
        child: SafeArea(
          child: Column(
            children: [
              _buildHeader(l10n),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
                  child: Column(
                    children: [
                      _buildPriceAndChart(),
                      const SizedBox(height: 20),
                      _buildOrderPanel(l10n),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
      bottomNavigationBar: AppBottomNav(
        selectedIndex: _selectedBottomIndex,
        onTap: _handleBottomNavTap,
      ),
    );
  }

  /// رأس الشاشة: سهم الرجوع + اسم الرمز + "Live Trading"
  Widget _buildHeader(AppLocalizations l10n) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
      child: Row(
        children: [
          _BackButton(onTap: () => Navigator.of(context).maybePop()),
          Expanded(
            child: Column(
              children: [
                Text(
                  l10n.marketName(widget.market.symbol),
                  style: AppTextStyles.heading2.copyWith(fontSize: 24),
                ),
                const SizedBox(height: 4),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      l10n.liveTrading,
                      style: AppTextStyles.subtitle,
                    ),
                    const SizedBox(width: 6),
                    const _LiveDot(),
                  ],
                ),
              ],
            ),
          ),
          // مساحة موازنة بعرض زر الرجوع حتى يبقى العنوان في المنتصف تمامًا
          const SizedBox(width: 44),
        ],
      ),
    );
  }

  /// بطاقة السعر + الرسم البياني، داخل إطار متوهج واحد
  Widget _buildPriceAndChart() {
    return _GlowPanel(
      child: Column(
        children: [
          _buildPriceCard(),
          const SizedBox(height: 12),
          SizedBox(
            height: 380,
            child: TradePriceChart(
              isPositive: widget.market.isPositive,
              seed: widget.market.symbol.hashCode,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPriceCard() {
    final isPositive = widget.market.isPositive;
    final trendColor = isPositive ? AppColors.success : AppColors.error;
    final sign = isPositive ? '+' : '';

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            widget.market.price.toStringAsFixed(_priceDecimals),
            style: AppTextStyles.heading1.copyWith(
              fontSize: 46,
              fontWeight: FontWeight.w700,
              letterSpacing: 0,
            ),
          ),
          const SizedBox(height: 10),
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                isPositive
                    ? Icons.trending_up_rounded
                    : Icons.trending_down_rounded,
                size: 18,
                color: trendColor,
              ),
              const SizedBox(width: 4),
              Text(
                '$sign${widget.market.changePercent.toStringAsFixed(2)}% '
                '($sign\$${_dailyChangeAmount.abs().toStringAsFixed(2)})',
                style: AppTextStyles.bodyLarge.copyWith(
                  color: trendColor,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  /// لوحة فتح الصفقة: نوع الأمر + الحقول + الرافعة + الملخص + أزرار التنفيذ
  Widget _buildOrderPanel(AppLocalizations l10n) {
    return _GlowPanel(
      padding: const EdgeInsets.all(20),
      child: Column(
        children: [
          OrderTypeSelector(
            selected: _orderType,
            onChanged: _handleOrderTypeChanged,
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: TradeFieldPill(
                  label: l10n.price,
                  controller: _priceController,
                  enabled: _orderType.requiresPrice,
                  onChanged: _handleFieldChanged,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: TradeFieldPill(
                  label: l10n.quantity,
                  controller: _quantityController,
                  onChanged: _handleFieldChanged,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          _buildLeverageField(l10n),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: TradeFieldBox(
                  label: l10n.stopLoss,
                  controller: _stopLossController,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: TradeFieldBox(
                  label: l10n.takeProfit,
                  controller: _takeProfitController,
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          _buildSummary(l10n),
          const SizedBox(height: 20),
          Divider(color: AppColors.textPrimary.withOpacity(0.12)),
          const SizedBox(height: 20),
          _buildActionButtons(l10n),
        ],
      ),
    );
  }

  Widget _buildLeverageField(AppLocalizations l10n) {
    return Container(
      height: 60,
      padding: const EdgeInsets.symmetric(horizontal: 20),
      decoration: BoxDecoration(
        color: AppColors.fieldFill,
        borderRadius: BorderRadius.circular(30),
      ),
      child: Row(
        children: [
          Text(
            l10n.leverage,
            style: AppTextStyles.bodyMedium.copyWith(
              color: AppColors.textHint,
            ),
          ),
          Expanded(
            child: SliderTheme(
              data: SliderThemeData(
                trackHeight: 6,
                activeTrackColor: AppColors.gradientMid,
                inactiveTrackColor: AppColors.fieldBorder,
                thumbColor: AppColors.gradientMid,
                overlayColor: AppColors.gradientMid.withOpacity(0.15),
                thumbShape: const RoundSliderThumbShape(
                  enabledThumbRadius: 10,
                ),
              ),
              child: Slider(
                value: _leverage,
                min: 1,
                max: _maxLeverage,
                onChanged: _handleLeverageChanged,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSummary(AppLocalizations l10n) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      decoration: BoxDecoration(
        color: AppColors.bgSurface,
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        children: [
          SummaryRow(
            label: l10n.requiredMargin,
            value: '\$${_requiredMargin.toStringAsFixed(2)}',
          ),
          SummaryRow(
            label: l10n.estFee,
            value: '\$${_estFee.toStringAsFixed(2)}',
          ),
          SummaryRow(
            label: l10n.estLiqPrice,
            value: '\$${_estLiquidationPrice.toStringAsFixed(2)}',
            valueColor: AppColors.error,
          ),
        ],
      ),
    );
  }

  Widget _buildActionButtons(AppLocalizations l10n) {
    return Row(
      children: [
        Expanded(
          child: _TradeActionButton(
            label: l10n.buy,
            color: AppColors.buyGreen,
            onTap: _handleBuy,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _TradeActionButton(
            label: l10n.sell,
            color: AppColors.sellRed,
            onTap: _handleSell,
          ),
        ),
      ],
    );
  }
}

// ═══════════════════════════════════════════════════════════
// Sub-widgets - مكونات فرعية
// ═══════════════════════════════════════════════════════════

/// لوحة بإطار متوهج بلون العلامة التجارية، تُستخدم لتغليف الأقسام الرئيسية
class _GlowPanel extends StatelessWidget {
  const _GlowPanel({
    required this.child,
    this.padding = const EdgeInsets.all(10),
  });

  final Widget child;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppColors.bgSurface,
            AppColors.bgMid,
          ],
        ),
        borderRadius: BorderRadius.circular(28),
        border: Border.all(
          color: AppColors.gradientMid.withOpacity(0.35),
          width: 1.4,
        ),
      ),
      child: child,
    );
  }
}

/// زر الرجوع الدائري في الرأس
class _BackButton extends StatelessWidget {
  const _BackButton({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: const Color(0xFF0D2539),
          shape: BoxShape.circle,
          border: Border.all(
            color: AppColors.fieldBorder.withOpacity(0.3),
            width: 1,
          ),
        ),
        child: const Icon(
          Icons.arrow_back_rounded,
          color: AppColors.textPrimary,
          size: 22,
        ),
      ),
    );
  }
}

/// نقطة "مباشر" الخضراء المتوهجة بجانب "Live Trading"
class _LiveDot extends StatelessWidget {
  const _LiveDot();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 6,
      height: 6,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: AppColors.accentGreen,
        boxShadow: [
          BoxShadow(
            color: AppColors.accentGreen.withOpacity(0.7),
            blurRadius: 6,
            spreadRadius: 1,
          ),
        ],
      ),
    );
  }
}

/// زر تنفيذ الصفقة (BUY / SELL)
class _TradeActionButton extends StatelessWidget {
  const _TradeActionButton({
    required this.label,
    required this.color,
    required this.onTap,
  });

  final String label;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 56,
      child: ElevatedButton(
        onPressed: onTap,
        style: ElevatedButton.styleFrom(
          backgroundColor: color,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(30),
          ),
        ),
        child: Text(
          label,
          style: AppTextStyles.button.copyWith(
            color: AppColors.textPrimary,
            fontSize: 17,
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════
// Order Dialogs - نوافذ تأكيد وتنفيذ الصفقة
// ═══════════════════════════════════════════════════════════

/// الغلاف المشترك لنوافذ الصفقة المنبثقة:
/// - يُغبّش (blur) كل ما هو خلف النافذة (الشاشة + شريط التنقل السفلي)
/// - يموضع البطاقة أسفل الشاشة، فوق شريط التنقل السفلي مباشرة
///   (بنفس مكان الظهور في التصميم المطلوب) بدل توسيطها بمنتصف الشاشة
class _BlurredOrderDialogRoute extends StatelessWidget {
  const _BlurredOrderDialogRoute({required this.child});

  final Widget child;

  /// المساحة المتروكة أسفل البطاقة لتترك شريط التنقل السفلي ظاهرًا وواضحًا
  static const double _bottomGap = 96;

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        // طبقة التغبيش (Blur) فوق كل الشاشة يلي ورا النافذة
        Positioned.fill(
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: 8, sigmaY: 8),
            child: Container(color: Colors.black.withOpacity(0.35)),
          ),
        ),
        // البطاقة نفسها، بأسفل الشاشة
        // ملاحظة: لا نلف child بـ _DialogCard هون، لأن كل ديالوغ
        // (_ConfirmOrderDialog / _OrderExecutedDialog) أصلاً بيرجع
        // _DialogCard من جوا نفسه. لفّها هون كمان كانت تسبب إطارين
        // فوق بعض (حدود مزدوجة).
        Align(
          alignment: Alignment.bottomCenter,
          child: Padding(
            padding: EdgeInsets.only(
              left: 20,
              right: 20,
              bottom: _bottomGap + MediaQuery.of(context).padding.bottom,
            ),
            child: child,
          ),
        ),
      ],
    );
  }
}

/// إطار موحّد للنوافذ المنبثقة (بطاقة داكنة بحدود متوهجة خضراء)
/// تُستخدم كأساس لكل من [_ConfirmOrderDialog] و [_OrderExecutedDialog]
class _DialogCard extends StatelessWidget {
  const _DialogCard({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              AppColors.bgSurface,
              AppColors.bgMid,
            ],
          ),
          borderRadius: BorderRadius.circular(24),
          border: Border.all(
            color: AppColors.gradientMid,
            width: 1.4,
          ),
        ),
        child: child,
      ),
    );
  }
}

/// صف عرض تفاصيل الصفقة داخل نافذة "Confirm Order"
class _ConfirmOrderRow extends StatelessWidget {
  const _ConfirmOrderRow({
    required this.label,
    required this.value,
    this.valueColor,
  });

  final String label;
  final String value;
  final Color? valueColor;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: AppTextStyles.bodyMedium.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          Text(
            value,
            style: AppTextStyles.bodyMedium.copyWith(
              color: valueColor ?? AppColors.textPrimary,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

/// نافذة "Confirm Order" - تظهر عند الضغط على BUY أو SELL
/// لمراجعة تفاصيل الصفقة (الرمز، الاتجاه، الكمية، الرافعة) قبل التنفيذ
class _ConfirmOrderDialog extends StatelessWidget {
  const _ConfirmOrderDialog({
    required this.symbol,
    required this.side,
    required this.quantity,
    required this.leverage,
    required this.onCancel,
    required this.onConfirm,
  });

  final String symbol;
  final String side;
  final double quantity;
  final double leverage;
  final VoidCallback onCancel;
  final VoidCallback onConfirm;

  bool get _isBuy => side == 'BUY';

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;

    return _DialogCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            l10n.confirmOrder,
            style: AppTextStyles.heading2.copyWith(fontSize: 22),
          ),
          const SizedBox(height: 12),
          _ConfirmOrderRow(label: l10n.asset, value: symbol),
          _ConfirmOrderRow(
            label: l10n.side,
            value: _isBuy ? l10n.buy : l10n.sell,
            valueColor: _isBuy ? AppColors.buyGreen : AppColors.sellRed,
          ),
          _ConfirmOrderRow(
            label: l10n.quantity,
            value: quantity.toStringAsFixed(1),
          ),
          _ConfirmOrderRow(
            label: l10n.leverage,
            value: '${leverage.toStringAsFixed(1)}x',
          ),
          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(
                child: _DialogButton(
                  label: l10n.cancel,
                  backgroundColor: AppColors.fieldFill,
                  textColor: AppColors.textPrimary,
                  onTap: onCancel,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _DialogButton(
                  label: l10n.confirm,
                  backgroundColor: AppColors.textPrimary,
                  textColor: AppColors.buttonText,
                  onTap: onConfirm,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// نافذة "Order Executed" - تظهر بعد تأكيد الصفقة لإعلام المستخدم
/// بأن الأمر تم تنفيذه بنجاح
class _OrderExecutedDialog extends StatelessWidget {
  const _OrderExecutedDialog({
    required this.side,
    required this.quantity,
    required this.symbol,
    required this.onDone,
  });

  final String side;
  final double quantity;
  final String symbol;
  final VoidCallback onDone;

  bool get _isBuy => side == 'BUY';

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;

    return _DialogCard(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const _SuccessIcon(),
          const SizedBox(height: 20),
          Text(
            l10n.orderExecuted,
            style: AppTextStyles.heading2.copyWith(fontSize: 22),
          ),
          const SizedBox(height: 10),
          Text(
            l10n.orderFilledMessage(
              _isBuy ? l10n.buy : l10n.sell,
              quantity.toStringAsFixed(1),
              symbol,
            ),
            textAlign: TextAlign.center,
            style: AppTextStyles.bodyMedium.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            child: _DialogButton(
              label: l10n.done,
              backgroundColor: AppColors.fieldFill,
              textColor: AppColors.textPrimary,
              onTap: onDone,
            ),
          ),
        ],
      ),
    );
  }
}

/// أيقونة النجاح: نفس أيقونة "Order Executed" المرسلة بالضبط (PNG جاهزة)
class _SuccessIcon extends StatelessWidget {
  const _SuccessIcon();

  @override
  Widget build(BuildContext context) {
    return Image.asset(
      'assets/images/order_executed_icon.png',
      width: 96,
      height: 80,
      fit: BoxFit.contain,
    );
  }
}

/// زر عام موحّد يُستخدم داخل نوافذ الصفقة (Cancel / Confirm / Done)
class _DialogButton extends StatelessWidget {
  const _DialogButton({
    required this.label,
    required this.backgroundColor,
    required this.textColor,
    required this.onTap,
  });

  final String label;
  final Color backgroundColor;
  final Color textColor;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 52,
      child: ElevatedButton(
        onPressed: onTap,
        style: ElevatedButton.styleFrom(
          backgroundColor: backgroundColor,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(30),
          ),
        ),
        child: Text(
          label,
          style: AppTextStyles.button.copyWith(
            color: textColor,
            fontSize: 15,
          ),
        ),
      ),
    );
  }
}
