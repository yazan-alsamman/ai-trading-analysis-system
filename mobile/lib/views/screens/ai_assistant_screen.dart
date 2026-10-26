import 'package:flutter/material.dart';
import '../../l10n/app_localizations.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_navigation.dart';
import '../../utils/app_text_styles.dart';
import '../../utils/routes/app_navigator.dart';
import '../widgets/app_bottom_nav.dart';
import '../widgets/auth_background.dart';
import '../widgets/screen_back_button.dart';

/// شاشة "AI" - تعرض أدوات الذكاء الاصطناعي المتاحة بالتطبيق
/// (AI Strategy Assistant / AI Chart Analyzer / AI News Analyzer)
///
/// الدور المعماري: **View (واجهة)**
/// - صورة ترويجية أعلى الشاشة
/// - ثلاث بطاقات، كل وحدة بتفتح أداة AI مختلفة
///
/// تستخدم عمدًا نفس خلفية شاشات الدخول/التسجيل [AuthBackground]
/// (شمعات + إشارات دولار + نجوم) بدل [RegistrationBackground] الأبسط
/// المستخدمة بـ Home/Trade.
///
/// تُفتح من [HomeScreen] و[TradeScreen] عند الضغط على أيقونة المخ
/// بشريط التنقل السفلي (index == 2).
class AiAssistantScreen extends StatefulWidget {
  const AiAssistantScreen({super.key});

  @override
  State<AiAssistantScreen> createState() => _AiAssistantScreenState();
}

class _AiAssistantScreenState extends State<AiAssistantScreen> {
  /// فهرس تبويب AI بشريط التنقل السفلي
  static const int _ownIndex = 2;

  int _selectedBottomIndex = _ownIndex;

  // ═══════════════════════════════════════════════════════════
  // Event Handlers - معالجات الأحداث
  // ═══════════════════════════════════════════════════════════

  /// معالج ضغطات شريط التنقل السفلي - مفوّض بالكامل للمعالج المشترك
  /// [handleGlobalBottomNavTap]. سابقًا زر "Markets" (index == 1) هون
  /// كان بس بيأشّر التبويب كمحدد بدون ما يفتح فعليًا شاشة الاختيار -
  /// المعالج المشترك بيصلّح هيك حالات وبيخلي كل زر ياخد أثر فعلي.
  void _handleBottomNavTap(int index) => handleGlobalBottomNavTap(index);

  /// فتح شاشة شات AI Strategy Assistant الفعلية
  void _handleOpenStrategyAssistant() {
    context.pushAiChat();
  }

  /// فتح شاشة AI Chart Analyzer الفعلية
  void _handleOpenChartAnalyzer() {
    context.pushAiChartAnalyzer();
  }

  /// فتح شاشة AI News Analyzer الفعلية (بدون خبر محدد مسبقًا)
  void _handleOpenNewsAnalyzer() {
    context.pushAiNewsAnalyzer();
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
          bottom: false,
          child: Column(
            children: [
              const ScreenBackButton(),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(20, 4, 20, 28),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _buildHero(),
                      const SizedBox(height: 24),
                      _AiToolCard(
                        iconPath: 'assets/images/strategy_assistant.png',
                        title: l10n.aiStrategyAssistantTitle,
                        description: l10n.aiStrategyAssistantDesc,
                        onTap: _handleOpenStrategyAssistant,
                      ),
                      const SizedBox(height: 16),
                      _AiToolCard(
                        iconPath: 'assets/images/chart_analyzer_icon.png',
                        title: l10n.aiChartAnalyzerTitle,
                        description: l10n.aiChartAnalyzerDesc,
                        onTap: _handleOpenChartAnalyzer,
                      ),
                      const SizedBox(height: 16),
                      _AiToolCard(
                        iconPath: 'assets/images/nav_pages.png',
                        title: l10n.aiNewsAnalyzerTitle,
                        description: l10n.aiNewsAnalyzerDesc,
                        onTap: _handleOpenNewsAnalyzer,
                      ),
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

  /// الصورة الترويجية أعلى الشاشة (الرأس + شاشات الرسوم البيانية)
  Widget _buildHero() {
    return Image.asset(
      'assets/images/ai_assistant_hero.png',
      width: double.infinity,
      fit: BoxFit.contain,
    );
  }
}

// ═══════════════════════════════════════════════════════════
// Sub-widgets - مكونات فرعية
// ═══════════════════════════════════════════════════════════

/// بطاقة أداة AI واحدة: أيقونة + عنوان + وصف، بنفس ستايل بطاقات
/// التطبيق (خلفية داكنة شفافة قليلًا + حدود رفيعة)
class _AiToolCard extends StatelessWidget {
  const _AiToolCard({
    required this.iconPath,
    required this.title,
    required this.description,
    required this.onTap,
  });

  final String iconPath;
  final String title;
  final String description;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(24),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: AppColors.bgSurface.withOpacity(0.92),
          borderRadius: BorderRadius.circular(24),
          border: Border.all(
            color: AppColors.fieldBorder.withOpacity(0.45),
            width: 1,
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Image.asset(
              iconPath,
              width: 36,
              height: 36,
              color: AppColors.accentCyan,
            ),
            const SizedBox(width: 18),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: AppTextStyles.heading2.copyWith(fontSize: 19),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    description,
                    style: AppTextStyles.bodyMedium.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
