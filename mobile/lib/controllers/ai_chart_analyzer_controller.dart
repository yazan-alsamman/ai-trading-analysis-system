import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:image_picker/image_picker.dart';
import '../l10n/app_localizations.dart';
import '../models/chart_analysis_model.dart';

// ═══════════════════════════════════════════════════════════
// AI Chart Analyzer Controller - متحكم شاشة تحليل الشارت
// ═══════════════════════════════════════════════════════════

/// متحكم إدارة حالة شاشة AI Chart Analyzer
///
/// مسؤوليات هذا الكلاس:
/// - فتح مصدر الصورة (كاميرا / معرض) عبر [ImagePicker]
/// - التحقق من نوع وحجم الصورة المختارة قبل قبولها
/// - إدارة حالة التحليل (idle / analyzing / success / failure)
/// - توليد نتيجة التحليل (حاليًا محاكاة، لحين ربط API حقيقي)
///
/// ⚠️ IMPORTANT: الواجهة (View) لا تتواصل مع ImagePicker أو أي خدمة
/// مباشرة، كل شي بيمر من هون، بنفس نمط [AuthController]
///
/// ⚠️ [l10n] يُلتقط لحظة إنشاء المتحكم (لحظة فتح الشاشة) ويُستخدم
/// لرسائل الخطأ ونتيجة التحليل التجريبية - نفس ملاحظة [AiChatController].
final class AiChartAnalyzerController extends ChangeNotifier {
  AiChartAnalyzerController({required AppLocalizations l10n, ImagePicker? picker})
      : _l10n = l10n,
        _picker = picker ?? ImagePicker();

  final AppLocalizations _l10n;
  final ImagePicker _picker;

  // ═══════════════════════════════════════════════════════════
  // Constraints - قيود قبول الصورة
  // ═══════════════════════════════════════════════════════════

  /// أقصى حجم مسموح للصورة (10MB)
  static const int maxFileSizeBytes = 10 * 1024 * 1024;

  /// الامتدادات المسموحة
  static const List<String> allowedExtensions = ['png', 'jpg', 'jpeg'];

  // ═══════════════════════════════════════════════════════════
  // Private State - الحالة الخاصة
  // ═══════════════════════════════════════════════════════════

  File? _selectedImage;
  ChartAnalysisStatus _status = ChartAnalysisStatus.idle;
  ChartAnalysisResultModel? _result;
  String? _errorMessage;

  // ═══════════════════════════════════════════════════════════
  // Public Getters - القيم العامة (للقراءة فقط)
  // ═══════════════════════════════════════════════════════════

  /// الصورة المختارة حاليًا (null لو ما في صورة بعد)
  File? get selectedImage => _selectedImage;

  /// حالة عملية التحليل الحالية
  ChartAnalysisStatus get status => _status;

  /// نتيجة آخر تحليل ناجح (null قبل التحليل)
  ChartAnalysisResultModel? get result => _result;

  /// رسالة الخطأ الحالية إن وجدت
  String? get errorMessage => _errorMessage;

  // ═══════════════════════════════════════════════════════════
  // Public Actions - العمليات العامة
  // ═══════════════════════════════════════════════════════════

  /// اختيار صورة من معرض الصور
  Future<void> pickImageFromGallery() => _pickImage(ImageSource.gallery);

  /// التقاط صورة جديدة بالكاميرا
  Future<void> pickImageFromCamera() => _pickImage(ImageSource.camera);

  /// بدء تحليل الصورة المختارة حاليًا
  Future<void> analyzeChart() async {
    if (_selectedImage == null || _status.isAnalyzing) return;

    _status = ChartAnalysisStatus.analyzing;
    _errorMessage = null;
    notifyListeners();

    // TODO: استبدال هذا بـ API call حقيقي عبر ChartAnalysisService
    // (رفع الصورة والحصول على تحليل فعلي من نموذج AI)
    await Future.delayed(const Duration(seconds: 2));

    _result = _mockResult();
    _status = ChartAnalysisStatus.success;
    notifyListeners();
  }

  /// إعادة الشاشة لحالتها الأولية، لتحليل شارت جديد من الصفر
  void reset() {
    _selectedImage = null;
    _result = null;
    _errorMessage = null;
    _status = ChartAnalysisStatus.idle;
    notifyListeners();
  }

  // ═══════════════════════════════════════════════════════════
  // Private Helper Methods - دوال مساعدة خاصة
  // ═══════════════════════════════════════════════════════════

  Future<void> _pickImage(ImageSource source) async {
    try {
      final picked = await _picker.pickImage(source: source, imageQuality: 90);
      if (picked == null) return; // المستخدم لغى الاختيار، ما منغيّر شي

      if (!_isExtensionAllowed(picked.path)) {
        _setError(_l10n.invalidImageTypeError);
        return;
      }

      final file = File(picked.path);
      final sizeBytes = await file.length();
      if (sizeBytes > maxFileSizeBytes) {
        _setError(_l10n.imageTooLargeError);
        return;
      }

      _selectedImage = file;
      _result = null;
      _errorMessage = null;
      _status = ChartAnalysisStatus.idle;
      notifyListeners();
    } catch (_) {
      _setError(_l10n.imageOpenError);
    }
  }

  bool _isExtensionAllowed(String path) {
    final dotIndex = path.lastIndexOf('.');
    if (dotIndex == -1) return false;
    final ext = path.substring(dotIndex + 1).toLowerCase();
    return allowedExtensions.contains(ext);
  }

  void _setError(String message) {
    _errorMessage = message;
    _status = ChartAnalysisStatus.failure;
    notifyListeners();
  }

  /// توليد نتيجة تحليل تجريبية (بديل مؤقت لحين ربط نموذج AI حقيقي)
  ChartAnalysisResultModel _mockResult() {
    return ChartAnalysisResultModel(
      trend: ChartTrend.bullish,
      confidencePercent: 78,
      summary: _l10n.chartMockSummary,
      keyLevels: [
        _l10n.chartMockSupport,
        _l10n.chartMockResistance,
        _l10n.chartMockTarget,
      ],
    );
  }
}
