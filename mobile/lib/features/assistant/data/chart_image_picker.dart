import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../models/chart_analysis.dart';

/// مصدر الصورة (كاميرا / معرض)
enum ChartImageSource { camera, gallery }

/// ليش انرفضت الصورة
enum ChartImageProblem { type, size, unreadable }

/// نتيجة اختيار صورة الشارت
sealed class ChartPick {
  const ChartPick();
}

/// صورة صالحة: [bytes] هي يلي رح تنبعت (والبصمة منها)
final class ChartPicked extends ChartPick {
  const ChartPicked(this.path, this.bytes);

  final String path;
  final Uint8List bytes;
}

final class ChartPickCancelled extends ChartPick {
  const ChartPickCancelled();
}

final class ChartPickRejected extends ChartPick {
  const ChartPickRejected(this.problem);

  final ChartImageProblem problem;
}

/// أقصى حجم للصورة (10 MB)
const int kChartImageMaxBytes = 10 * 1024 * 1024;

/// التحقق من محتوى الصورة (مش الامتداد بس): فاضية / مقطوعة = unreadable،
/// أكبر من 10 MB = size، صورة بصيغة تانية (GIF، WebP، HEIC، BMP) = type،
/// لا PNG ولا JPG ولا صيغة معروفة = unreadable. null = صالحة.
ChartImageProblem? validateChartImage(Uint8List bytes) {
  if (bytes.length > kChartImageMaxBytes) return ChartImageProblem.size;
  if (bytes.length < 8) return ChartImageProblem.unreadable;
  if (isPng(bytes) || isJpeg(bytes)) return null;
  return _otherImage(bytes) ? ChartImageProblem.type : ChartImageProblem.unreadable;
}

bool _otherImage(Uint8List b) {
  String ascii(int from, int to) => String.fromCharCodes(b.sublist(from, to));
  if (ascii(0, 4) == 'GIF8') return true;
  if (b[0] == 0x42 && b[1] == 0x4D) return true; // BMP
  if (b.length >= 12 && ascii(0, 4) == 'RIFF' && ascii(8, 12) == 'WEBP') return true;
  if (b.length >= 12 && ascii(4, 8) == 'ftyp') return true; // HEIC / HEIF / AVIF
  return false;
}

/// اختيار صورة الشارت + التحقق منها (PNG / JPG، ≤ 10MB، مقروءة) - الـ ViewModel
/// ما بيلمس image_picker مباشرة، فبالاختبارات منبدّل هاد الـ provider بس.
class ChartImagePicker {
  ChartImagePicker({ImagePicker? picker}) : _picker = picker ?? ImagePicker();

  final ImagePicker _picker;

  static const int maxFileSizeBytes = kChartImageMaxBytes;
  static const List<String> allowedExtensions = ['png', 'jpg', 'jpeg'];

  Future<ChartPick> pick(ChartImageSource source) async {
    try {
      final picked = await _picker.pickImage(
        source: source == ChartImageSource.camera ? ImageSource.camera : ImageSource.gallery,
        // 2048 بيكفي لقراءة الشارت، وبيخفّف الذاكرة والرفع لاحقًا
        maxWidth: 2048,
        maxHeight: 2048,
        imageQuality: 90,
      );
      if (picked == null) return const ChartPickCancelled();
      final dot = picked.path.lastIndexOf('.');
      final ext = dot < 0 ? '' : picked.path.substring(dot + 1).toLowerCase();
      if (!allowedExtensions.contains(ext)) return const ChartPickRejected(ChartImageProblem.type);
      // الحجم قبل القراءة: ما منحمّل ملف كبير بالذاكرة
      if (await File(picked.path).length() > maxFileSizeBytes) {
        return const ChartPickRejected(ChartImageProblem.size);
      }
      final bytes = await picked.readAsBytes();
      if (validateChartImage(bytes) case final problem?) return ChartPickRejected(problem);
      return ChartPicked(picked.path, bytes);
    } catch (_) {
      return const ChartPickRejected(ChartImageProblem.unreadable);
    }
  }
}

final chartImagePickerProvider = Provider<ChartImagePicker>((ref) => ChartImagePicker());
