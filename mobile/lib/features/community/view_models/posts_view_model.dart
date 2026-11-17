import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/shell/shell_tab.dart';
import '../../../core/data/low_data_mode.dart';
import '../../../core/data/network_status.dart';
import '../../../providers/locale_provider.dart';
import '../data/posts_repository.dart';
import '../models/post.dart';

/// الطلب ما انبعت لأنو الجهاز بدون اتصال (تحميل، نشر، إعجاب، حذف، بلاغ)
final class PostsOfflineException implements Exception {
  const PostsOfflineException();
}

/// ViewModel قسم Posts بتبويب Community.
///
/// - تبديل اللغة بيعيد التحميل؛ سحب للتحديث مرتين ورا بعض: الأقدم بينرمى.
/// - الإعجاب متفائل (بيتبدّل فورًا) وبيرجع لو فشل؛ ضغطة تانية والطلب الأول
///   لسّا ماشي بتنتجاهل.
/// - الحذف متفائل + Undo. البلاغ مرة وحدة لكل منشور.
/// - بدون اتصال: ما في طلب بينبعت ([PostsOfflineException])؛ أول تحميل بدون
///   اتصال بيطلع حالة "offline"، وبيرجع يحمّل لحالو لما يرجع الاتصال.
class PostsViewModel extends AsyncNotifier<List<Post>> {
  var _generation = 0;
  final Set<String> _liking = {};
  final Set<String> _reporting = {};
  bool _creating = false;

  PostsRepository get _repo => ref.read(postsRepositoryProvider);

  @override
  Future<List<Post>> build() async {
    final language = ref.watch(localeProvider.select((l) => l.languageCode));
    final repo = ref.watch(postsRepositoryProvider);
    // H5b: بالـ Low data mode بيستنّى لحد ما تبويب Community يبيّن
    reloadWhenBackOnline(
      ref,
      tab: ShellTab.community,
      needed: () => state.error is PostsOfflineException,
      reload: ref.invalidateSelf,
    );
    _generation++;
    _requireOnline();
    return repo.posts(languageCode: language);
  }

  void _requireOnline() {
    if (ref.read(networkStatusProvider) == NetworkStatus.offline) throw const PostsOfflineException();
  }

  Future<void> refresh() async {
    _requireOnline();
    final generation = ++_generation;
    final posts = await _repo.posts(languageCode: ref.read(localeProvider).languageCode);
    if (generation == _generation) state = AsyncData(posts);
  }

  bool get isCreating => _creating;

  /// false = فاضي / أطول من الحد / في نشر جاري. بدون اتصال: [PostsOfflineException].
  /// أي فشل تاني بيوصل للمنادي (الـ sheet بيعرضه وبيخلّي النص).
  Future<bool> create(String body, {String? symbol}) async {
    final trimmed = body.trim();
    if (_creating || trimmed.isEmpty || trimmed.length > kPostMaxLength) return false;
    _requireOnline();
    _creating = true;
    try {
      final post = await _repo.create(body: trimmed, symbol: symbol);
      state = AsyncData([post, ...?state.valueOrNull]);
      return true;
    } finally {
      _creating = false;
    }
  }

  Future<void> toggleLike(String postId) async {
    final post = _find(postId);
    if (post == null || _liking.contains(postId)) return;
    _requireOnline();
    _liking.add(postId);
    final liked = !post.likedByMe;
    _replace(post.copyWith(likedByMe: liked, likesCount: (post.likesCount + (liked ? 1 : -1)).clamp(0, 1 << 31)));
    try {
      final result = liked ? await _repo.like(postId) : await _repo.unlike(postId);
      final current = _find(postId);
      if (current != null) _replace(current.copyWith(likedByMe: result.liked, likesCount: result.likesCount));
    } catch (_) {
      final current = _find(postId);
      if (current != null) _replace(current.copyWith(likedByMe: post.likedByMe, likesCount: post.likesCount));
      rethrow;
    } finally {
      _liking.remove(postId);
    }
  }

  /// بيرجّع المنشور ومكانه للـ Undo (null لو مش موجود أو مش إلك)
  Future<(Post, int)?> remove(String postId) async {
    final current = state.valueOrNull ?? const <Post>[];
    final index = current.indexWhere((p) => p.id == postId);
    if (index < 0 || !current[index].isOwn) return null;
    _requireOnline();
    final removed = current[index];
    state = AsyncData([...current]..removeAt(index));
    try {
      await _repo.delete(postId);
      return (removed, index);
    } catch (_) {
      state = AsyncData(current);
      rethrow;
    }
  }

  Future<void> undoRemove((Post, int) removed) async {
    final (post, index) = removed;
    await _repo.restore(post.id);
    final current = [...?state.valueOrNull]..removeWhere((p) => p.id == post.id);
    current.insert(index.clamp(0, current.length), post);
    state = AsyncData(current);
  }

  /// بلاغ عن منشور غيرك. false = منشورك / بلّغت قبل / في بلاغ جاري.
  Future<bool> report(String postId, ReportReason reason) async {
    final post = _find(postId);
    if (post == null || post.isOwn || post.reportedByMe || !_reporting.add(postId)) return false;
    try {
      _requireOnline();
      await _repo.report(postId, reason);
      final current = _find(postId);
      if (current != null) _replace(current.copyWith(reportedByMe: true));
      return true;
    } finally {
      _reporting.remove(postId);
    }
  }

  /// عدد التعليقات بعد إضافة / حذف من sheet التعليقات
  void setCommentsCount(String postId, int count) {
    final post = _find(postId);
    if (post != null) _replace(post.copyWith(commentsCount: count));
  }

  Post? _find(String id) {
    for (final p in state.valueOrNull ?? const <Post>[]) {
      if (p.id == id) return p;
    }
    return null;
  }

  void _replace(Post post) {
    final current = state.valueOrNull;
    if (current == null) return;
    state = AsyncData([for (final p in current) p.id == post.id ? post : p]);
  }
}

final postsViewModelProvider = AsyncNotifierProvider<PostsViewModel, List<Post>>(PostsViewModel.new);
