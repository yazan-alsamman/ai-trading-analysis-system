import 'package:flutter/material.dart';

import '../../../core/theme/theme_context.dart';
import '../../../l10n/app_localizations.dart';
import '../models/market_models.dart';

/// شارة حالة تدفّق الأسعار: نقطة + كلمة (مش اللون لحالو)
class FeedStatusPill extends StatelessWidget {
  const FeedStatusPill({super.key, required this.status});

  static const double _dot = 6;

  final FeedStatus status;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context)!;
    final (String word, Color color) = switch (status) {
      FeedStatus.live => (l10n.feedLive, c.accent),
      FeedStatus.connecting => (l10n.feedConnecting, c.fg3),
      FeedStatus.delayed => (l10n.feedDelayed, c.warning),
      FeedStatus.stale => (l10n.feedStale, c.warning),
      FeedStatus.marketClosed => (l10n.feedMarketClosed, c.fg3),
      FeedStatus.offline => (l10n.feedOffline, c.warning),
      FeedStatus.error => (l10n.feedError, c.danger),
    };
    return Semantics(
      container: true,
      label: l10n.feedStatusLabel(word),
      excludeSemantics: true,
      child: DecoratedBox(
        decoration: BoxDecoration(
          borderRadius: AppRadii.pillAll,
          border: Border.all(color: c.hairline),
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xs, vertical: AppSpacing.xxs / 2),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: _dot,
                height: _dot,
                decoration: BoxDecoration(color: color, shape: BoxShape.circle),
              ),
              const SizedBox(width: AppSpacing.xxs),
              Text(word, style: context.textTheme.labelSmall!.copyWith(color: c.fg2)),
            ],
          ),
        ),
      ),
    );
  }
}
