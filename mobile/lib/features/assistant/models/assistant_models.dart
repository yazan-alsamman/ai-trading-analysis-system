import 'package:flutter/foundation.dart';

import '../../markets/models/market_models.dart';
import '../../risk/models/risk_limits.dart';
import '../../signals/models/opportunity.dart';
import 'chart_analysis.dart';

/// نوع الجواب (عقد الويب `ReplyKind`) - بيحدد عنوان بطاقة الجواب
enum ReplyKind { explain, invalidate, risk, chart, unknown }

/// شو بيعرف المساعد وقت السؤال - بس يلي بالتطبيق، والمستخدم شايفه بالشريحة
@immutable
final class AssistantContext {
  const AssistantContext({this.instrument, this.lastPrice, this.read, required this.limits});

  final Instrument? instrument;
  final double? lastPrice;
  final ModelRead? read;
  final RiskLimits limits;
}

/// جواب المساعد كما رجع من المصدر
@immutable
final class AssistantAnswer {
  const AssistantAnswer({required this.kind, required this.text, this.chart, this.simulated = true});

  final ReplyKind kind;
  final String text;
  /// تحليل صورة شارت (الاتجاه والمستويات من الاستراتيجية المحفوظة)
  final ChartAnalysisReply? chart;

  /// مبني على بيانات محاكاة (أو مساعد قواعد، مش نموذج لغوي)
  final bool simulated;
}

/// رسالة بالمحادثة
@immutable
sealed class ChatMessage {
  const ChatMessage({required this.id, required this.createdAt});

  final String id;
  final DateTime createdAt;
}

final class UserText extends ChatMessage {
  const UserText({required super.id, required super.createdAt, required this.text});

  final String text;
}

final class UserImage extends ChatMessage {
  const UserImage({required super.id, required super.createdAt, required this.path});

  final String path;
}

final class AssistantReply extends ChatMessage {
  const AssistantReply({required super.id, required super.createdAt, required this.answer, this.symbol});

  final AssistantAnswer answer;

  /// الأداة يلي كانت بالسياق وقت الجواب
  final String? symbol;
}
