import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/shell/widgets/back_to_home_button.dart';
import '../../../core/theme/theme_context.dart';
import '../../../core/widgets/feedback_states.dart';
import '../../../core/widgets/motion.dart';
import '../../../core/widgets/segment_label.dart';
import '../../../core/widgets/source_tag.dart';
import '../../../l10n/app_localizations.dart';
import '../../news/widgets/news_section.dart';
import '../data/experts_repository.dart';
import '../widgets/expert_card.dart';
import '../widgets/posts_section.dart';

enum CommunitySection { news, posts, experts }

/// تبويب Community: شريط News · Posts · Experts تحت الرأس.
///
/// News: مزاج السوق + الأخبار بنبرتها وتعليقاتها. Posts: منشورات كل
/// الأعضاء (زر "New post" عائم بهالقسم بس). Experts: الخبراء (اشتراك محاكى
/// + محادثة للمشتركين). كل قسم بيحتفظ بالسكرول تبعو لما تبدّل بينهم.
class CommunityScreen extends StatefulWidget {
  const CommunityScreen({super.key});

  @override
  State<CommunityScreen> createState() => _CommunityScreenState();
}

class _CommunityScreenState extends State<CommunityScreen> {
  CommunitySection _section = CommunitySection.news;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final gutter = AppSpacing.gutter(context);
    final c = context.colors;
    // بخط كبير جدًا الأيقونات بتطلع من الشريط وبتضل الكلمات (3 أقسام بعرض الهاتف)
    final icons = MediaQuery.textScalerOf(context).scale(1) <= 1.3;
    final posts = _section == CommunitySection.posts;

    ButtonSegment<CommunitySection> segment(CommunitySection value, IconData icon, String label) => ButtonSegment(
          value: value,
          icon: icons ? Icon(icon) : null,
          // سطر واحد دايمًا: بالخط الكبير الكلمة بتصغر لتساع (ما بتلتف ولا بتنقص)
          label: SegmentLabel(label),
        );

    return Scaffold(
      floatingActionButton: posts
          ? FloatingActionButton.extended(
              onPressed: () => composePost(context),
              backgroundColor: c.primaryAction,
              foregroundColor: c.onPrimaryAction,
              icon: const Icon(Icons.edit_outlined),
              label: Text(l10n.newPost),
            )
          : null,
      body: SafeArea(
        bottom: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TabHeader(title: l10n.navCommunity),
            Padding(
              padding: EdgeInsets.fromLTRB(gutter, 0, gutter, AppSpacing.sm),
              child: SegmentedButton<CommunitySection>(
                showSelectedIcon: false,
                segments: [
                  segment(CommunitySection.news, Icons.newspaper_rounded, l10n.communityNews),
                  segment(CommunitySection.posts, Icons.forum_outlined, l10n.communityPosts),
                  segment(CommunitySection.experts, Icons.support_agent_rounded, l10n.toolExperts),
                ],
                selected: {_section},
                onSelectionChanged: (selection) {
                  AppHaptics.selection();
                  setState(() => _section = selection.first);
                },
              ),
            ),
            Expanded(
              child: IndexedStack(
                index: _section.index,
                children: const [
                  NewsSection(),
                  PostsSection(),
                  _ExpertsList(),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// قائمة الخبراء: مقدّمة قصيرة + بطاقات، مع تحميل / فاضي / خطأ وسحب للتحديث
class _ExpertsList extends ConsumerWidget {
  const _ExpertsList();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final text = context.textTheme;
    final gutter = AppSpacing.gutter(context);
    final experts = ref.watch(expertsProvider);

    Widget scroll(List<Widget> children) => RefreshIndicator(
          onRefresh: () => ref.refresh(expertsProvider.future),
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: EdgeInsets.fromLTRB(gutter, AppSpacing.xs, gutter, AppSpacing.xxl),
            children: children,
          ),
        );

    final intro = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(l10n.expertsIntro, style: text.bodyMedium),
        const SizedBox(height: AppSpacing.xs),
        const SourceTag(SourceKind.demo),
      ],
    );

    return experts.when(
      loading: () => scroll([
        intro,
        const SizedBox(height: AppSpacing.md),
        LoadingRegion(
          child: Column(children: [
            for (var i = 0; i < 2; i++) ...[
              if (i > 0) const SizedBox(height: AppSpacing.md),
              const Skeleton(height: AppSpacing.huge * 4, radius: AppRadii.card),
            ],
          ]),
        ),
      ]),
      error: (_, __) => scroll([ErrorState(onRetry: () => ref.invalidate(expertsProvider))]),
      data: (list) => list.isEmpty
          ? scroll([intro, EmptyState(icon: Icons.support_agent_rounded, title: l10n.expertsEmpty)])
          : scroll([
              intro,
              for (final (i, expert) in list.indexed) ...[
                const SizedBox(height: AppSpacing.md),
                FadeRise(index: i, child: ExpertCard(expert: expert)),
              ],
            ]),
    );
  }
}
