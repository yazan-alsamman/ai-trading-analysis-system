import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../controllers/ai_chart_analyzer_controller.dart';
import '../../l10n/app_localizations.dart';
import '../../models/chart_analysis_model.dart';
import '../../providers/screen_providers.dart';
import '../../utils/app_colors.dart';
import '../../utils/app_navigation.dart';
import '../../utils/app_text_styles.dart';
import '../widgets/app_bottom_nav.dart';
import '../widgets/auth_background.dart';

/// شاشة AI Chart Analyzer — رفع صورة شارت والحصول على تحليل فوري
///
/// الدور المعماري: **View (واجهة)**
/// - تعرض منطقة رفع الصورة (Dropzone) بأربع حالات: فاضية / صورة
///   مختارة جاهزة للتحليل / جاري التحليل / نتيجة جاهزة
/// - تعرض نصائح ثابتة لأفضل نتيجة تحليل
/// - كل منطق الاختيار والتحقق والتحليل يمر عبر [AiChartAnalyzerController]
///
/// نقاط الوصول لهذه الشاشة:
/// - من [HomeScreen]: زر "Chart Analyzer" بقسم Quantitative Intelligence
/// - من [AiAssistantScreen] ("AI Hub"): بطاقة "AI Chart Analyzer"
/// - و[AiAssistantScreen] نفسها توصلها من أيقونة المخ بالـ navbar
///
/// تُغلّف [_AiChartAnalyzerView] بـ [ProviderScope] محلي (override لـ
/// [aiChartAnalyzerControllerProvider])، بحيث تبدأ الشاشة نظيفة (بدون
/// صورة سابقة) بكل مرة تُفتح فيها.
class AiChartAnalyzerScreen extends StatelessWidget {
  const AiChartAnalyzerScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return ProviderScope(
      overrides: [
        aiChartAnalyzerControllerProvider.overrideWith(
          (ref) => AiChartAnalyzerController(l10n: l10n),
        ),
      ],
      child: const _AiChartAnalyzerView(),
    );
  }
}

// ═══════════════════════════════════════════════════════════
// Screen View - جسم الشاشة الفعلي
// ═══════════════════════════════════════════════════════════

class _AiChartAnalyzerView extends ConsumerStatefulWidget {
  const _AiChartAnalyzerView();

  @override
  ConsumerState<_AiChartAnalyzerView> createState() =>
      _AiChartAnalyzerViewState();
}

class _AiChartAnalyzerViewState
    extends ConsumerState<_AiChartAnalyzerView> {
  /// فهرس تبويب AI بشريط التنقل السفلي (نفس فهرس [AiAssistantScreen])
  static const int _ownIndex = 2;

  int _selectedBottomIndex = _ownIndex;

  // ═══════════════════════════════════════════════════════════
  // Event Handlers - معالجات الأحداث
  // ═══════════════════════════════════════════════════════════

  /// معالج ضغطات شريط التنقل السفلي - مفوّض بالكامل للمعالج المشترك
  /// [handleGlobalBottomNavTap] حتى يشتغل زر "Markets" (كان مو مفعّل
  /// أساسًا هون) بنفس سلوك باقي شاشات التطبيق.
  void _handleBottomNavTap(int index) => handleGlobalBottomNavTap(index);

  /// يعرض Bottom Sheet لاختيار مصدر الصورة: كاميرا أو معرض الصور
  Future<void> _showImageSourceSheet(AiChartAnalyzerController controller) {
    return showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (_) => _ImageSourceSheet(
        onPickCamera: () {
          Navigator.of(context).pop();
          controller.pickImageFromCamera();
        },
        onPickGallery: () {
          Navigator.of(context).pop();
          controller.pickImageFromGallery();
        },
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════
  // Build Methods - دوال البناء
  // ═══════════════════════════════════════════════════════════

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final controller = ref.watch(aiChartAnalyzerControllerProvider);

    return Scaffold(
      body: AuthBackground(
        child: SafeArea(
          bottom: false,
          child: Column(
            children: [
              _buildTopBar(),
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
                  children: [
                    _buildHeader(l10n),
                    const SizedBox(height: 8),
                    _buildDropzone(controller, l10n),
                    if (controller.errorMessage != null) ...[
                      const SizedBox(height: 12),
                      _ErrorBanner(message: controller.errorMessage!),
                    ],
                    if (controller.status.isSuccess &&
                        controller.result != null) ...[
                      const SizedBox(height: 20),
                      _ResultCard(result: controller.result!, l10n: l10n),
                      const SizedBox(height: 16),
                      _buildAnalyzeAnotherButton(controller, l10n),
                    ],
                    const SizedBox(height: 24),
                    _TipsCard(l10n: l10n),
                  ],
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

  /// شريط علوي: سهم رجوع فقط (بدون نص "Back to AI Hub")
  Widget _buildTopBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(10, 6, 10, 0),
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
        ],
      ),
    );
  }

  /// عنوان الشاشة ووصفها
  Widget _buildHeader(AppLocalizations l10n) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(0, 8, 0, 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l10n.aiChartAnalyzerTitle, style: AppTextStyles.heading1),
          const SizedBox(height: 8),
          Text(
            l10n.aiChartAnalyzerSubtitle,
            style: AppTextStyles.subtitle.copyWith(fontSize: 16),
          ),
        ],
      ),
    );
  }

  /// منطقة رفع/معاينة الصورة — بتختلف حسب حالة [AiChartAnalyzerController]
  Widget _buildDropzone(AiChartAnalyzerController controller, AppLocalizations l10n) {
    final image = controller.selectedImage;

    if (image == null) {
      return _EmptyUploadCard(
        l10n: l10n,
        onSelectImage: () => _showImageSourceSheet(controller),
      );
    }

    return _SelectedImageCard(
      image: image,
      onChangeImage: controller.status.isAnalyzing
          ? null
          : () => _showImageSourceSheet(controller),
      footer: _buildDropzoneFooter(controller, l10n),
    );
  }

  /// الجزء السفلي جوا كرت معاينة الصورة — بيتغير حسب حالة التحليل
  Widget _buildDropzoneFooter(AiChartAnalyzerController controller, AppLocalizations l10n) {
    if (controller.status.isAnalyzing) {
      return _AnalyzingIndicator(l10n: l10n);
    }
    if (controller.status.isSuccess) {
      return Row(
        children: [
          const Icon(Icons.check_circle_rounded,
              color: AppColors.buyGreen, size: 20),
          const SizedBox(width: 8),
          Text(
            l10n.analysisComplete,
            style: AppTextStyles.bodyMedium.copyWith(
              color: AppColors.buyGreen,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      );
    }
    // idle مع صورة مختارة و لسا ما انبدأ التحليل
    return SizedBox(
      width: double.infinity,
      height: 52,
      child: ElevatedButton(
        onPressed: controller.analyzeChart,
        child: Text(l10n.analyzeChartButton),
      ),
    );
  }

  /// زر "تحليل شارت تاني" — بيرجع الشاشة لحالتها الأولية
  Widget _buildAnalyzeAnotherButton(AiChartAnalyzerController controller, AppLocalizations l10n) {
    return SizedBox(
      width: double.infinity,
      height: 52,
      child: OutlinedButton(
        onPressed: controller.reset,
        style: OutlinedButton.styleFrom(
          foregroundColor: AppColors.textPrimary,
          side: BorderSide(color: AppColors.fieldBorder.withOpacity(0.6)),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(30),
          ),
        ),
        child: Text(l10n.analyzeAnotherChart),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════
// Sub-widgets - مكونات فرعية
// ═══════════════════════════════════════════════════════════

/// كرت الحالة الفاضية: حدود متقطّعة + أيقونة رفع + "Select Image"
class _EmptyUploadCard extends StatelessWidget {
  const _EmptyUploadCard({required this.onSelectImage, required this.l10n});

  final VoidCallback onSelectImage;
  final AppLocalizations l10n;

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      foregroundPainter: _DashedBorderPainter(
        color: AppColors.textSecondary.withOpacity(0.5),
      ),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 24),
        decoration: BoxDecoration(
          color: AppColors.bgSurface.withOpacity(0.55),
          borderRadius: BorderRadius.circular(24),
        ),
        child: Column(
          children: [
            Container(
              width: 68,
              height: 68,
              decoration: BoxDecoration(
                color: AppColors.gradientMid,
                borderRadius: BorderRadius.circular(18),
              ),
              child: const Icon(
                Icons.file_download_outlined,
                color: AppColors.bgDeep,
                size: 34,
              ),
            ),
            const SizedBox(height: 20),
            Text(l10n.uploadChartImage, style: AppTextStyles.heading3),
            const SizedBox(height: 10),
            Text(
              l10n.pngJpgMax10mb,
              style: AppTextStyles.bodyMedium.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: 28),
            SizedBox(
              width: double.infinity,
              height: 52,
              child: ElevatedButton(
                onPressed: onSelectImage,
                child: Text(l10n.selectImage),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// كرت معاينة الصورة المختارة — حدود عادية (غير متقطّعة)، صورة بالأعلى
/// وزر "Change" فوقها، وجزء سفلي (footer) بيتغير حسب حالة التحليل
class _SelectedImageCard extends StatelessWidget {
  const _SelectedImageCard({
    required this.image,
    required this.onChangeImage,
    required this.footer,
  });

  final File image;
  final VoidCallback? onChangeImage;
  final Widget footer;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.bgSurface.withOpacity(0.92),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: AppColors.fieldBorder.withOpacity(0.45)),
      ),
      child: Column(
        children: [
          Stack(
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(16),
                child: Image.file(
                  image,
                  width: double.infinity,
                  height: 190,
                  fit: BoxFit.cover,
                ),
              ),
              if (onChangeImage != null)
                Positioned(
                  top: 10,
                  right: 10,
                  child: _ChangeImageButton(onTap: onChangeImage!),
                ),
            ],
          ),
          const SizedBox(height: 18),
          footer,
        ],
      ),
    );
  }
}

/// زر صغير دائري شفاف فوق الصورة يسمح بتغييرها
class _ChangeImageButton extends StatelessWidget {
  const _ChangeImageButton({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      customBorder: const CircleBorder(),
      child: Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: AppColors.bgDeep.withOpacity(0.75),
          shape: BoxShape.circle,
          border: Border.all(color: AppColors.fieldBorder.withOpacity(0.6)),
        ),
        child: const Icon(
          Icons.edit_rounded,
          color: AppColors.textPrimary,
          size: 16,
        ),
      ),
    );
  }
}

/// مؤشر "جاري التحليل..." — سبينر صغير + نص
class _AnalyzingIndicator extends StatelessWidget {
  const _AnalyzingIndicator({required this.l10n});

  final AppLocalizations l10n;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const SizedBox(
          width: 20,
          height: 20,
          child: CircularProgressIndicator(
            strokeWidth: 2.4,
            color: AppColors.accentCyan,
          ),
        ),
        const SizedBox(width: 12),
        Text(
          l10n.analyzingChart,
          style: AppTextStyles.bodyMedium.copyWith(
            color: AppColors.textSecondary,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}

/// شريط رسالة خطأ (نوع/حجم صورة غير صالح، أو فشل التحليل)
class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: AppColors.error.withOpacity(0.12),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.error.withOpacity(0.4)),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline_rounded,
              color: AppColors.error, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: AppTextStyles.bodySmall.copyWith(color: AppColors.error),
            ),
          ),
        ],
      ),
    );
  }
}

/// كرت نتيجة التحليل: الاتجاه + نسبة الثقة + الملخص + المستويات السعرية
class _ResultCard extends StatelessWidget {
  const _ResultCard({required this.result, required this.l10n});

  final ChartAnalysisResultModel result;
  final AppLocalizations l10n;

  Color get _trendColor {
    switch (result.trend) {
      case ChartTrend.bullish:
        return AppColors.buyGreen;
      case ChartTrend.bearish:
        return AppColors.sellRed;
      case ChartTrend.neutral:
        return AppColors.accentCyan;
    }
  }

  IconData get _trendIcon {
    switch (result.trend) {
      case ChartTrend.bullish:
        return Icons.trending_up_rounded;
      case ChartTrend.bearish:
        return Icons.trending_down_rounded;
      case ChartTrend.neutral:
        return Icons.trending_flat_rounded;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.bgSurface.withOpacity(0.92),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: _trendColor.withOpacity(0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: _trendColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(30),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(_trendIcon, color: _trendColor, size: 18),
                    const SizedBox(width: 6),
                    Text(
                      result.trend.label(l10n),
                      style: AppTextStyles.bodyMedium.copyWith(
                        color: _trendColor,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
              const Spacer(),
              Text(
                l10n.confidencePercentLabel(result.confidencePercent.toStringAsFixed(0)),
                style: AppTextStyles.labelSmall.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            result.summary,
            style: AppTextStyles.bodyMedium.copyWith(height: 1.5),
          ),
          const SizedBox(height: 18),
          Divider(color: AppColors.fieldBorder.withOpacity(0.3)),
          const SizedBox(height: 14),
          Text(l10n.keyLevelsLabel, style: AppTextStyles.label),
          const SizedBox(height: 10),
          for (final level in result.keyLevels)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                children: [
                  Icon(Icons.circle, size: 6, color: _trendColor),
                  const SizedBox(width: 10),
                  Text(level, style: AppTextStyles.bodyMedium),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

/// كرت النصائح الثابت — نفس نمط بطاقات التطبيق (خلفية + حدود مخضرّة)
class _TipsCard extends StatelessWidget {
  const _TipsCard({required this.l10n});

  final AppLocalizations l10n;

  List<String> get _tips => [
        l10n.chartTip1,
        l10n.chartTip2,
        l10n.chartTip3,
        l10n.chartTip4,
      ];

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.bgSurface.withOpacity(0.55),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: AppColors.gradientMid.withOpacity(0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l10n.tipsForBestResults, style: AppTextStyles.heading3),
          const SizedBox(height: 16),
          for (final tip in _tips)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '•',
                    style: AppTextStyles.bodyMedium.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      tip,
                      style: AppTextStyles.bodyMedium.copyWith(
                        color: AppColors.textSecondary,
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

/// نافذة سفلية لاختيار مصدر الصورة: كاميرا أو معرض الصور
/// (نفس نمط [MarketPickerSheet] المشتركة)
class _ImageSourceSheet extends StatelessWidget {
  const _ImageSourceSheet({
    required this.onPickCamera,
    required this.onPickGallery,
  });

  final VoidCallback onPickCamera;
  final VoidCallback onPickGallery;

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
          border: Border.all(color: AppColors.gradientMid, width: 1.4),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
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
            Text(l10n.selectImageSource, style: AppTextStyles.heading3),
            const SizedBox(height: 8),
            _ImageSourceTile(
              icon: Icons.photo_camera_outlined,
              label: l10n.takePhoto,
              onTap: onPickCamera,
            ),
            _ImageSourceTile(
              icon: Icons.photo_library_outlined,
              label: l10n.chooseFromGalleryImage,
              onTap: onPickGallery,
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}

/// صف واحد داخل [_ImageSourceSheet]
class _ImageSourceTile extends StatelessWidget {
  const _ImageSourceTile({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 14),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppColors.accentCyan.withOpacity(0.15),
                shape: BoxShape.circle,
              ),
              child: Icon(icon, size: 18, color: AppColors.accentCyan),
            ),
            const SizedBox(width: 14),
            Text(
              label,
              style: AppTextStyles.bodyMedium.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════
// Dashed Border Painter - رسّام الحدود المتقطّعة
// ═══════════════════════════════════════════════════════════

/// يرسم حدود مستطيل بزوايا دائرية بشكل متقطّع (dashed)
/// حول الكرت الفاضي — Flutter ما بيدعم هيك حدود جاهزة
class _DashedBorderPainter extends CustomPainter {
  const _DashedBorderPainter({
    required this.color,
    this.radius = 24,
    this.strokeWidth = 1.4,
    this.dashWidth = 6,
    this.gapWidth = 5,
  });

  final Color color;
  final double radius;
  final double strokeWidth;
  final double dashWidth;
  final double gapWidth;

  @override
  void paint(Canvas canvas, Size size) {
    final rrect = RRect.fromRectAndRadius(
      Rect.fromLTWH(0, 0, size.width, size.height),
      Radius.circular(radius),
    );
    final path = Path()..addRRect(rrect);
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth;

    for (final metric in path.computeMetrics()) {
      var distance = 0.0;
      while (distance < metric.length) {
        final next = (distance + dashWidth).clamp(0.0, metric.length);
        canvas.drawPath(metric.extractPath(distance, next), paint);
        distance = next + gapWidth;
      }
    }
  }

  @override
  bool shouldRepaint(covariant _DashedBorderPainter old) =>
      old.color != color || old.radius != radius;
}
