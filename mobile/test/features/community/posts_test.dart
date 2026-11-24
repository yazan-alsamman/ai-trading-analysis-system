// اختبارات Community → Posts: الـ mapper، القائمة (نفس الشكل للكل)، "New post"
// (حدّ الأحرف، الأداة الاختيارية، معطّل وهو فاضي، بدون اتصال)، الإعجاب
// المتفائل مع الرجوع، التعليقات بنفس sheet الأخبار، حذف منشورك مع Undo،
// البلاغ، حالة بدون اتصال، سباق الضغطة المزدوجة، والعربي بخط كبير.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:trading_app/core/data/json.dart';
import 'package:trading_app/core/data/network_status.dart';
import 'package:trading_app/core/theme/theme_mode_provider.dart';
import 'package:trading_app/core/widgets/app_illustration.dart';
import 'package:trading_app/features/auth/auth_state.dart';
import 'package:trading_app/features/community/data/posts_repository.dart';
import 'package:trading_app/features/community/models/post.dart';
import 'package:trading_app/features/community/view_models/posts_view_model.dart';
import 'package:trading_app/features/community/views/community_screen.dart';
import 'package:trading_app/features/community/widgets/post_card.dart';
import 'package:trading_app/features/markets/views/market_screen.dart';
import 'package:trading_app/models/user_model.dart';

import '../../helpers/test_app.dart';

Future<ProviderContainer> openPosts(
  WidgetTester tester, {
  String locale = 'en',
  String theme = 'light',
  double height = 812,
  List<Override> overrides = const [],
}) async {
  usePhoneSize(tester, height: height);
  await tester.pumpWidget(await testScope(
    const TestApp(home: CommunityScreen()),
    locale: locale,
    prefs: {themeModeStorageKey: theme},
    overrides: overrides,
  ));
  await settleMocks(tester);
  await tester.tap(find.text(locale == 'en' ? 'Posts' : 'المنشورات'));
  await tester.pumpAndSettle();
  return ProviderScope.containerOf(tester.element(find.byType(CommunityScreen)));
}

Finder get sheetField => find.descendant(of: find.byType(BottomSheet), matching: find.byType(TextField));
Finder get postButton => find.widgetWithText(FilledButton, 'Post');

Future<void> openComposer(WidgetTester tester) async {
  await tester.tap(find.widgetWithText(FloatingActionButton, 'New post'));
  await tester.pumpAndSettle();
}

Future<void> share(WidgetTester tester, String text, {String? symbol}) async {
  await openComposer(tester);
  await tester.enterText(sheetField, text);
  await tester.pump();
  if (symbol != null) {
    await tester.tap(find.descendant(of: find.byType(BottomSheet), matching: find.text(symbol)));
    await tester.pump();
  }
  await tester.ensureVisible(postButton);
  await tester.tap(postButton);
  await tester.pumpAndSettle();
}

class _EmptyPosts extends SimulatedPostsRepository {
  _EmptyPosts() : super(author: () => 'You');

  @override
  Future<List<Post>> posts({required String languageCode}) async => const [];
}

class _FailingPosts extends SimulatedPostsRepository {
  _FailingPosts() : super(author: () => 'You');

  @override
  Future<List<Post>> posts({required String languageCode}) async => throw StateError('down');
}

class _StartsOffline extends NetworkStatusViewModel {
  @override
  NetworkStatus build() => NetworkStatus.offline;
}

/// مستودع بيوقف كل طلب لحد ما [gate] يكتمل، وبيعدّ الطلبات (سباق الضغطة المزدوجة)
class _GatedPosts extends SimulatedPostsRepository {
  _GatedPosts() : super(author: () => 'You', clock: () => kTestNow);

  Completer<void>? gate;
  var likeCalls = 0;
  var createCalls = 0;

  Future<void> _pass() async {
    if (gate case final g?) await g.future;
  }

  @override
  Future<LikeState> like(String postId) async {
    likeCalls++;
    await _pass();
    return super.like(postId);
  }

  @override
  Future<Post> create({required String body, String? symbol}) async {
    createCalls++;
    await _pass();
    return super.create(body: body, symbol: symbol);
  }

  @override
  Future<void> report(String postId, ReportReason reason) async {
    await _pass();
    return super.report(postId, reason);
  }
}

class _FailingLikes extends SimulatedPostsRepository {
  _FailingLikes() : super(author: () => 'You', clock: () => kTestNow);

  @override
  Future<LikeState> like(String postId) async => throw StateError('down');
}

void main() {
  group('payload', () {
    Map<String, Object?> row({String status = 'published', String? symbol = 'XAU/USD', String role = 'trader'}) => {
          'id': 'p1',
          'author': {'id': 'u1', 'display_name': 'Lina', 'role': role},
          'title': 'Gold',
          'body': 'Gold holds.',
          'instrument': symbol == null ? null : {'id': 'i1', 'symbol': symbol},
          'status': status,
          'comments_count': 2,
          'likes_count': 5,
          'liked_by_me': true,
          'can_edit': false,
          'created_at': '2026-10-21T12:00:00Z',
        };

    test('PostRead → Post (the author role is ignored: every post looks the same)', () {
      final post = postFromJson(Json(row()))!;
      expect(post.authorName, 'Lina');
      expect(post.symbol, 'XAU/USD');
      expect((post.likesCount, post.likedByMe, post.commentsCount), (5, true, 2));
    });

    test('hidden / deleted posts are dropped; other asset classes lose the chip', () {
      expect(postFromJson(Json(row(status: 'hidden'))), isNull);
      expect(postFromJson(Json(row(status: 'deleted'))), isNull);
      expect(postFromJson(Json(row(symbol: 'BTC/USD')))!.symbol, isNull);
      expect(postFromJson(Json(row(role: 'expert'))), isNotNull);
      expect(postFromJson(const Json({'id': 'x', 'body': ' '})), isNull);
    });

    test('the API title is the first line, at most 140 characters', () {
      expect(postTitleFrom('Gold holds\nmore detail'), 'Gold holds');
      expect(postTitleFrom('a' * 200).length, 140);
    });
  });

  for (final theme in ['light', 'dark']) {
    testWidgets('Posts lists everyone’s posts the same way, with no badge ($theme)', (tester) async {
      await openPosts(tester, theme: theme, height: 3000);
      expect(find.byType(PostCard), findsNWidgets(5));
      expect(find.text('Simulated'), findsOneWidget);
      expect(find.text('Lina Haddad'), findsOneWidget);
      // ما في شارات دور: كل المنشورات شكلها واحد
      expect(find.descendant(of: find.byType(PostCard), matching: find.byIcon(Icons.verified_outlined)), findsNothing);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('three sections, and "New post" only on Posts', (tester) async {
    usePhoneSize(tester);
    await tester.pumpWidget(await testScope(const TestApp(home: CommunityScreen())));
    await settleMocks(tester);
    final segmented = tester.widget<SegmentedButton<CommunitySection>>(find.byType(SegmentedButton<CommunitySection>));
    expect(segmented.segments.map((s) => s.value), CommunitySection.values);
    expect(find.byType(FloatingActionButton), findsNothing);
    await tester.tap(find.text('Posts'));
    await tester.pumpAndSettle();
    expect(find.widgetWithText(FloatingActionButton, 'New post'), findsOneWidget);
    await tester.tap(find.text('Experts'));
    await tester.pumpAndSettle();
    expect(find.byType(FloatingActionButton), findsNothing);
  });

  group('New post', () {
    testWidgets('disabled while empty or blank; the limit is enforced', (tester) async {
      await openPosts(tester);
      await openComposer(tester);
      expect(tester.widget<FilledButton>(postButton).onPressed, isNull);
      await tester.enterText(sheetField, '   ');
      await tester.pump();
      expect(tester.widget<FilledButton>(postButton).onPressed, isNull);
      await tester.enterText(sheetField, 'a' * (kPostMaxLength + 100));
      await tester.pump();
      expect(tester.widget<TextField>(sheetField).controller!.text.length, kPostMaxLength);
      expect(find.text('$kPostMaxLength/$kPostMaxLength'), findsOneWidget);
      expect(tester.widget<FilledButton>(postButton).onPressed, isNotNull);
    });

    testWidgets('sharing with an instrument puts it on top, with a confirmation', (tester) async {
      await openPosts(tester);
      await share(tester, 'Watching the gold close.', symbol: 'XAU/USD');
      expect(find.byType(BottomSheet), findsNothing);
      expect(find.text('Post shared'), findsOneWidget);
      final first = find.byType(PostCard).first;
      expect(find.descendant(of: first, matching: find.text('Watching the gold close.')), findsOneWidget);
      expect(find.descendant(of: first, matching: find.text('You')), findsOneWidget);
      expect(find.descendant(of: first, matching: find.text('XAU/USD')), findsOneWidget);
    });

    testWidgets('any signed-in user sees "New post", can post, and the post has no badge', (tester) async {
      for (final role in UserRole.values) {
        await tester.pumpWidget(const SizedBox());
        await openPosts(tester, overrides: [
          authStateProvider.overrideWithValue(SignedIn(
            UserModel(id: 'u', email: 'maya@example.com', displayName: 'Maya Nasser', role: role),
          )),
        ]);
        expect(find.widgetWithText(FloatingActionButton, 'New post'), findsOneWidget, reason: role.name);
        await openComposer(tester);
        expect(find.text('Posting as Maya Nasser'), findsOneWidget);
        await tester.enterText(sheetField, 'Idea from ${role.name}');
        await tester.pump();
        await tester.tap(postButton);
        await tester.pumpAndSettle();
        final first = find.byType(PostCard).first;
        expect(find.descendant(of: first, matching: find.text('Idea from ${role.name}')), findsOneWidget);
        expect(find.descendant(of: first, matching: find.byIcon(Icons.verified_outlined)), findsNothing);
      }
    });

    testWidgets('offline: nothing is sent, the text stays and an inline message explains why', (tester) async {
      final container = await openPosts(tester);
      container.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      await share(tester, 'Offline idea');
      expect(find.text('You’re offline. Your post was not sent.'), findsOneWidget);
      expect(tester.widget<TextField>(sheetField).controller!.text, 'Offline idea');
      expect(container.read(postsViewModelProvider).value, hasLength(5));
    });
  });

  testWidgets('like toggles at once, with a readable label and state', (tester) async {
    final semantics = tester.ensureSemantics();
    await openPosts(tester);
    expect(find.bySemanticsLabel('Like, 24'), findsOneWidget);
    await tester.tap(find.bySemanticsLabel('Like, 24'));
    await tester.pumpAndSettle();
    expect(find.bySemanticsLabel('Like, 25'), findsOneWidget);
    expect(tester.getSemantics(find.bySemanticsLabel('Like, 25')), isSemantics(isToggled: true, isButton: true));
    await tester.tap(find.bySemanticsLabel('Like, 25'));
    await tester.pumpAndSettle();
    expect(find.bySemanticsLabel('Like, 24'), findsOneWidget);
    semantics.dispose();
  });

  testWidgets('a failed like rolls back and says so', (tester) async {
    final container = await openPosts(tester, overrides: [postsRepositoryProvider.overrideWithValue(_FailingLikes())]);
    final first = container.read(postsViewModelProvider).value!.first;
    await tester.tap(find.byIcon(Icons.favorite_border_rounded).first);
    await tester.pumpAndSettle();
    expect(find.text('That didn’t work. Try again.'), findsOneWidget);
    final after = container.read(postsViewModelProvider).value!.first;
    expect((after.likedByMe, after.likesCount), (first.likedByMe, first.likesCount));
  });

  testWidgets('comments open in the shared sheet with no badges; counts follow', (tester) async {
    final container = await openPosts(tester);
    await tester.tap(find.bySemanticsLabel('Comments · 3').first);
    await tester.pumpAndSettle();
    final sheet = find.byType(BottomSheet);
    expect(find.descendant(of: sheet, matching: find.text('Comments · 3')), findsOneWidget);
    expect(find.descendant(of: sheet, matching: find.text('Omar Saleh')), findsOneWidget);
    expect(find.descendant(of: sheet, matching: find.byIcon(Icons.verified_outlined)), findsNothing);
    await tester.enterText(find.widgetWithText(TextField, 'Add a comment'), 'Same here.');
    await tester.pump();
    await tester.tap(find.byTooltip('Post comment'));
    await tester.pumpAndSettle();
    expect(find.descendant(of: sheet, matching: find.text('Comments · 4')), findsOneWidget);
    expect(container.read(postsViewModelProvider).value!.first.commentsCount, 4);
  });

  testWidgets('only your posts can be deleted, with Undo', (tester) async {
    await openPosts(tester);
    // منشور غيرك: بلاغ بس، بدون حذف
    await tester.tap(find.byTooltip('Post options').first);
    await tester.pumpAndSettle();
    expect(find.text('Delete post'), findsNothing);
    expect(find.text('Report post'), findsOneWidget);
    await tester.tapAt(Offset.zero);
    await tester.pumpAndSettle();

    await share(tester, 'Mine to delete');
    await tester.tap(find.byTooltip('Post options').first);
    await tester.pumpAndSettle();
    expect(find.text('Report post'), findsNothing);
    await tester.tap(find.text('Delete post'));
    await tester.pumpAndSettle();
    expect(find.text('Mine to delete'), findsNothing);
    expect(find.text('Post deleted'), findsOneWidget);
    await tester.tap(find.text('Undo'));
    await tester.pumpAndSettle();
    expect(find.text('Mine to delete'), findsOneWidget);
  });

  testWidgets('report someone else’s post: pick a reason, sent once, then shown as Reported', (tester) async {
    final repo = SimulatedPostsRepository(clock: () => kTestNow, author: () => 'You');
    await openPosts(tester, overrides: [postsRepositoryProvider.overrideWithValue(repo)]);
    await tester.tap(find.byTooltip('Post options').first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Report post'));
    await tester.pumpAndSettle();
    final send = find.widgetWithText(FilledButton, 'Send report');
    expect(tester.widget<FilledButton>(send).onPressed, isNull);
    await tester.tap(find.text('Misleading, or promises profits'));
    await tester.pump();
    await tester.tap(send);
    await tester.pumpAndSettle();
    expect(find.text('Thanks. A moderator will review this post.'), findsOneWidget);
    expect(repo.reports, [
      {'target_type': 'post', 'target_id': 'post-gold-breakout', 'reason': 'misleading or promises profits'},
    ]);
    await tester.tap(find.byTooltip('Post options').first);
    await tester.pumpAndSettle();
    final reported = tester.widget<PopupMenuItem<VoidCallback>>(
      find.ancestor(of: find.text('Reported'), matching: find.byType(PopupMenuItem<VoidCallback>)),
    );
    expect(reported.enabled, isFalse);
  });

  group('offline', () {
    testWidgets('first load offline shows the offline state, then loads when back online', (tester) async {
      await openPosts(tester, overrides: [networkStatusProvider.overrideWith(_StartsOffline.new)]);
      expect(find.text('You’re offline'), findsOneWidget);
      expect(find.byType(AppIllustration), findsOneWidget);
      expect(find.byType(PostCard), findsNothing);
      final container = ProviderScope.containerOf(tester.element(find.byType(CommunityScreen)));
      container.read(networkStatusProvider.notifier).set(NetworkStatus.online);
      await tester.pumpAndSettle();
      expect(find.byType(PostCard), findsWidgets);
    });

    testWidgets('actions offline: nothing is sent, the list stays, a snackbar says why', (tester) async {
      final container = await openPosts(tester);
      container.read(networkStatusProvider.notifier).set(NetworkStatus.offline);
      await tester.pump();
      await tester.tap(find.bySemanticsLabel('Like, 24'));
      await tester.pumpAndSettle();
      expect(find.text('You’re offline. Try again when you’re connected.'), findsOneWidget);
      expect(container.read(postsViewModelProvider).value!.first.likedByMe, isFalse);
      expect(find.byType(PostCard), findsWidgets);
    });
  });

  group('double-tap races', () {
    test('repository: like and unlike are idempotent', () async {
      final repo = SimulatedPostsRepository(clock: () => kTestNow, author: () => 'You');
      expect((await repo.like('post-gold-breakout')).likesCount, 25);
      expect((await repo.like('post-gold-breakout')).likesCount, 25);
      expect((await repo.unlike('post-gold-breakout')).likesCount, 24);
      expect((await repo.unlike('post-gold-breakout')).likesCount, 24);
    });

    testWidgets('view model: two likes, two posts or two reports at once send one request each', (tester) async {
      final repo = _GatedPosts();
      final container = await openPosts(tester, overrides: [postsRepositoryProvider.overrideWithValue(repo)]);
      final vm = container.read(postsViewModelProvider.notifier);

      repo.gate = Completer<void>();
      final likes = [vm.toggleLike('post-gold-breakout'), vm.toggleLike('post-gold-breakout')];
      final posts = [vm.create('One'), vm.create('Two')];
      final reports = [
        vm.report('post-eurusd-range', ReportReason.spam),
        vm.report('post-eurusd-range', ReportReason.spam),
      ];
      repo.gate!.complete();
      await Future.wait(likes);
      expect(await Future.wait(posts), [true, false]);
      expect(await Future.wait(reports), [true, false]);

      expect((repo.likeCalls, repo.createCalls, repo.reports.length), (1, 1, 1));
      final list = container.read(postsViewModelProvider).value!;
      expect(list.where((p) => p.isOwn), hasLength(1));
      final gold = list.firstWhere((p) => p.id == 'post-gold-breakout');
      expect((gold.likedByMe, gold.likesCount), (true, 25));
    });

    testWidgets('composer: tapping Post twice shares once', (tester) async {
      final repo = _GatedPosts();
      final container = await openPosts(tester, overrides: [postsRepositoryProvider.overrideWithValue(repo)]);
      repo.gate = Completer<void>();
      await openComposer(tester);
      await tester.enterText(sheetField, 'Only once');
      await tester.pump();
      await tester.tap(postButton);
      await tester.pump();
      // وهو عم ينشر الزر بيعرض مؤشّر بدل الكلمة - منضغط عالزر نفسه
      await tester.tap(find.descendant(of: find.byType(BottomSheet), matching: find.byType(FilledButton)),
          warnIfMissed: false);
      await tester.pump();
      repo.gate!.complete();
      await tester.pumpAndSettle();
      expect(repo.createCalls, 1);
      expect(container.read(postsViewModelProvider).value!.where((p) => p.body == 'Only once'), hasLength(1));
      expect(find.text('Post shared'), findsOneWidget);
    });
  });

  testWidgets('the instrument chip opens its Market screen', (tester) async {
    await openPosts(tester);
    await tester.tap(find.descendant(of: find.byType(PostCard).first, matching: find.text('XAU/USD')));
    await tester.pumpAndSettle();
    expect(find.byType(MarketScreen), findsOneWidget);
  });

  testWidgets('empty: illustration and a way to write the first post', (tester) async {
    await openPosts(tester, overrides: [postsRepositoryProvider.overrideWithValue(_EmptyPosts())]);
    expect(find.text('No posts yet'), findsOneWidget);
    expect(find.byType(AppIllustration), findsOneWidget);
    expect(find.widgetWithText(OutlinedButton, 'New post'), findsOneWidget);
  });

  testWidgets('load failure shows an error with retry', (tester) async {
    await openPosts(tester, overrides: [postsRepositoryProvider.overrideWithValue(_FailingPosts())]);
    expect(find.text('Posts could not be loaded.'), findsOneWidget);
    expect(find.text('Try again'), findsOneWidget);
  });

  testWidgets('Arabic + dark + largest font: list, segments and composer fit', (tester) async {
    useLargeText(tester);
    await openPosts(tester, locale: 'ar', theme: 'dark');
    expect(find.text('لينا حداد'), findsOneWidget);
    expect(Directionality.of(tester.element(find.byType(CommunityScreen))), TextDirection.rtl);
    await tester.drag(find.byType(PostCard).first, const Offset(0, -3000));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FloatingActionButton, 'منشور جديد'));
    await tester.pumpAndSettle();
    expect(find.text('منشور جديد'), findsWidgets);
    expect(tester.takeException(), isNull);
  });
}
