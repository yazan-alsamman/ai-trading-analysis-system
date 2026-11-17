import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/data/network_status.dart';
import '../../../core/theme/theme_context.dart';
import '../models/market_models.dart';
import 'feed_status_pill.dart';
import 'last_updated_line.dart';

/// H5b: نفس سطر الـ Home وشاشة السوق (H5a) لباقي الشاشات: شارة Offline (بدون
/// اتصال) أو Stale (المصدر فشل) + "Last updated" (+ "Old data" بعد 24 ساعة).
/// [updatedAt] null = البيانات حيّة → ولا شي.
class SavedDataStatus extends ConsumerWidget {
  const SavedDataStatus(
      {super.key, required this.updatedAt, this.padding = const EdgeInsets.only(bottom: AppSpacing.sm)});

  final DateTime? updatedAt;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final at = updatedAt;
    final offline = ref.watch(networkStatusProvider) == NetworkStatus.offline;
    final Widget child = at == null
        ? const SizedBox(width: double.infinity)
        : Padding(
            padding: padding,
            child: Wrap(
              spacing: AppSpacing.xs,
              runSpacing: AppSpacing.xxs,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                FeedStatusPill(status: offline ? FeedStatus.offline : FeedStatus.stale),
                LastUpdatedLine(updatedAt: at),
              ],
            ),
          );
    // تقليل الحركة: بدون AnimatedSize (بمدة صفر بيعيد تعليم حالو أثناء الـ layout)
    if (context.reduceMotion) return child;
    return AnimatedSize(
      duration: AppMotion.base,
      curve: AppMotion.out,
      alignment: AlignmentDirectional.topStart,
      child: child,
    );
  }
}
