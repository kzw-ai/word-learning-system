// 源文件：pages/today-review.tsx（网页版）。RN 版：跳转用 router.replace。
import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, BackHandler, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { authenticatedFetch } from '@/lib/authClient';
import type { ReviewItem } from '@/lib/types';
import { useLearningContext } from '@/context/LearningContext';
import { reviewedToday, useLearningSession } from '@/context/LearningSessionContext';
import { colors, fontSize, radius, buttonHeight, spacing } from '@/theme';

const REVIEW_TYPE_LABELS: Record<string, string> = {
  definition: 'meaning',
  collocation: 'collocations',
  // 窄屏不折行，用连字符
  fill_word: 'fill\u2011in',
};

const MODULE_ROUTES: Record<string, string> = {
  character: '/character-learning',
  word: '/word-learning',
  collocation: '/collocation-learning',
  sentence: '/sentence-learning',
  exercise: '/exercise',
};

const MODULE_LABELS: Record<string, string> = {
  character: 'Characters',
  word: 'Word',
  collocation: 'Collocations',
  sentence: 'Sentences',
  exercise: 'Practice',
};

export default function TodayReview() {
  const { userId } = useLearningContext();
  const { session, hydrated, updateSession } = useLearningSession();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dueReviews, setReviews] = useState<ReviewItem[]>([]);
  // 列表是哪个用户的：切换用户后，旧用户的（空）列表不能触发对新用户的清理
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const currentUserRef = useRef(userId);
  currentUserRef.current = userId;
  // 点了开始复习、正在跳走：不能在跳走前据列表判定「复习做完了」而清掉复习模式
  const leavingRef = useRef(false);
  // 隐藏今天已经复习完的词（当天有效；中途退出的词不隐藏）
  const reviewed = reviewedToday(session);
  const reviews = dueReviews.filter(r => !reviewed.includes(r.word_id));

  const fetchDueReviews = async () => {
    const requestUser = userId;
    if (!requestUser) return;
    try {
      setLoading(true);
      setLoadedFor(null);
      setReviews([]);
      // limit 取足：前端还要再滤掉今天复习过的词，后端只给前 N 个的话，排在后面的到期词会被挡住
      const response = await authenticatedFetch(`/api/review/user/${requestUser}/due?limit=200`);
      const result = await response.json();
      if (currentUserRef.current !== requestUser) return;
      if (response.ok && result.success) {
        setReviews(result.data);
        setLoadedFor(requestUser);
      } else {
        setError(result.error || 'The service is unavailable');
      }
    } catch {
      setError('Couldn’t connect. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDueReviews();
  }, [userId]);

  // 安卓返回键离开本轮复习、回首页
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      updateSession({ reviewMode: null });
      router.replace('/');
      return true;
    });
    return () => sub.remove();
  }, [updateSession]);

  // 复习清空后退出复习模式，之后学完的词照常去学习看板。只退出模式、保留今天的已复习记录。
  useEffect(() => {
    if (hydrated && loadedFor === userId && reviews.length === 0 && session.reviewMode && !leavingRef.current) {
      updateSession({ reviewMode: null });
    }
  }, [hydrated, loadedFor, userId, reviews.length, session.reviewMode, updateSession]);

  const startReview = (review: ReviewItem) => {
    leavingRef.current = true;
    updateSession({
      wordId: review.word_id,
      word: review.word,
      module: review.recommended_module,
      entryModule: review.recommended_module,
      vksLevel: undefined,
      recommendationId: null,
      reviewMode: true,
      lastUpdated: new Date().toISOString(),
    });
    const route = MODULE_ROUTES[review.recommended_module] || '/word-learning';
    router.replace(route as any);
  };

  const leaveReview = () => {
    updateSession({ reviewMode: null });
    router.replace('/');
  };

  const masteryColor = (level: number) =>
    level >= 0.8 ? colors.success : level >= 0.6 ? '#1d4ed8' : level >= 0.4 ? colors.warning : colors.dangerText;
  const masteryBar = (level: number) =>
    level >= 0.8 ? '#34d399' : level >= 0.6 ? '#60a5fa' : level >= 0.4 ? '#fbbf24' : '#fb7185';

  if (loading) {
    return (
      <SafeAreaView style={styles.center}>
        <ActivityIndicator color={colors.primary} />
        <Text style={styles.muted}>Loading reviews…</Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Pressable style={styles.headerBtn} onPress={leaveReview}>
          <Text style={styles.headerBtnText}>← Home</Text>
        </Pressable>
        <Text style={styles.title}>Review</Text>
        <View style={styles.dueBadge}>
          <Text style={styles.dueBadgeText}>{reviews.length} due</Text>
        </View>
      </View>

      <ScrollView style={styles.content} contentContainerStyle={styles.contentInner}>
        {error && (
          <View style={styles.errorCard}>
            <Text style={styles.errorText}>{error}</Text>
            <Pressable style={styles.reloadBtn} onPress={fetchDueReviews}>
              <Text style={styles.reloadBtnText}>Reload</Text>
            </Pressable>
          </View>
        )}

        {!error && reviews.length === 0 && (
          <View style={styles.doneCard}>
            <Text style={styles.doneTitle}>All reviews done</Text>
            <Text style={styles.doneText}>You’ve completed all your reviews for today.</Text>
            <Pressable style={styles.primaryBtn} onPress={() => router.replace('/word-learning-entrance')}>
              <Text style={styles.primaryBtnText}>Learn a new word</Text>
            </Pressable>
          </View>
        )}

        {!error && reviews.length > 1 && (
          <Text style={styles.hint}>
            {"Start at the top — these are the words you're most likely to forget."}
          </Text>
        )}

        {reviews.map((review, index) => (
          <Pressable key={`${review.word_id}-${index}`} style={styles.card} onPress={() => startReview(review)}>
            <View style={styles.cardHeader}>
              <Text style={styles.wordText}>
                {review.word}
                {review.pinyin && review.pinyin !== review.word ? (
                  <Text style={styles.pinyin}>  {review.pinyin}</Text>
                ) : null}
              </Text>
            </View>
            <Text style={styles.reviewedCount}>
              Reviewed {review.review_count ?? 0} {(review.review_count ?? 0) === 1 ? 'time' : 'times'}
            </Text>
            {review.reviews_remaining !== undefined && (
              <Text style={styles.remaining}>
                {review.reviews_remaining > 0
                  ? `${review.reviews_remaining} more ${review.reviews_remaining === 1 ? 'review' : 'reviews'} · ${(review.review_types ?? []).map(t => REVIEW_TYPE_LABELS[t] ?? t).join(', ')}`
                  : 'Mastered · keeping it fresh'}
              </Text>
            )}

            <View style={styles.masteryRow}>
              <Text style={styles.masteryLabel}>Mastery</Text>
              <Text style={[styles.masteryValue, { color: masteryColor(review.mastery_level) }]}>
                {(review.mastery_level * 100).toFixed(0)}%
              </Text>
            </View>
            <View style={styles.masteryTrack}>
              <View style={[styles.masteryFill, { width: `${review.mastery_level * 100}%`, backgroundColor: masteryBar(review.mastery_level) }]} />
            </View>

            {review.days_overdue > 0 && (
              <Text style={styles.overdue}>
                {review.days_overdue} {review.days_overdue === 1 ? 'day' : 'days'} overdue
              </Text>
            )}

            <View style={styles.cardFooter}>
              <Text style={styles.moduleLabel}>{MODULE_LABELS[review.recommended_module] ?? 'Word'}</Text>
              <Pressable style={styles.reviewBtn} onPress={() => startReview(review)}>
                <Text style={styles.reviewBtnText}>Review</Text>
              </Pressable>
            </View>
          </Pressable>
        ))}
      </ScrollView>

      {reviews.length > 0 && (
        <View style={styles.footer}>
          <Pressable style={styles.primaryBtn} onPress={() => reviews[0] && startReview(reviews[0])}>
            <Text style={styles.primaryBtnText}>
              {session.reviewMode ? `Continue review (${reviews.length} left)` : 'Start first review'}
            </Text>
          </Pressable>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bgStart },
  center: { flex: 1, backgroundColor: colors.bgStart, alignItems: 'center', justifyContent: 'center', gap: spacing.md },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: spacing.xl, paddingVertical: spacing.md,
  },
  headerBtn: {
    minHeight: buttonHeight.min, paddingHorizontal: spacing.md, borderRadius: radius.lg,
    backgroundColor: colors.white, borderWidth: 1, borderColor: colors.border,
    alignItems: 'center', justifyContent: 'center',
  },
  headerBtnText: { fontSize: fontSize.body, fontWeight: '600', color: colors.primaryDark },
  title: { fontSize: fontSize.xl, fontWeight: '800', color: colors.text },
  dueBadge: {
    minHeight: buttonHeight.min, paddingHorizontal: spacing.md, borderRadius: radius.lg,
    backgroundColor: colors.primaryBg, borderWidth: 1, borderColor: colors.primaryBorder,
    alignItems: 'center', justifyContent: 'center',
  },
  dueBadgeText: { fontSize: fontSize.body, fontWeight: '600', color: colors.primaryDark },
  content: { flex: 1 },
  contentInner: { paddingHorizontal: spacing.xl, paddingVertical: spacing.md, gap: spacing.md },
  errorCard: {
    backgroundColor: colors.dangerBg, borderRadius: radius.xl, borderWidth: 1, borderColor: colors.dangerBorder,
    padding: spacing.lg, alignItems: 'center', gap: spacing.md,
  },
  errorText: { fontSize: fontSize.base, color: colors.dangerText, textAlign: 'center' },
  reloadBtn: {
    minHeight: buttonHeight.lg, paddingHorizontal: spacing.lg, borderRadius: radius.xl,
    backgroundColor: colors.danger, alignItems: 'center', justifyContent: 'center', alignSelf: 'stretch',
  },
  reloadBtnText: { fontSize: fontSize.base, fontWeight: '700', color: colors.white },
  doneCard: {
    backgroundColor: colors.white, borderRadius: radius['3xl'], borderWidth: 1, borderColor: colors.primaryBorder,
    padding: spacing.xl, alignItems: 'center', gap: spacing.sm,
  },
  doneTitle: { fontSize: fontSize['2xl'], fontWeight: '800', color: colors.text },
  doneText: { fontSize: fontSize.base, color: colors.textMuted, textAlign: 'center', marginBottom: spacing.md },
  hint: { fontSize: fontSize.body, color: colors.textMuted },
  card: {
    backgroundColor: colors.white, borderRadius: radius.xl, borderWidth: 1, borderColor: colors.border,
    padding: spacing.lg, gap: spacing.xs,
  },
  cardHeader: { flexDirection: 'row', alignItems: 'baseline' },
  wordText: { fontSize: fontSize.xl, fontWeight: '800', color: colors.text },
  pinyin: { fontSize: fontSize.body, fontWeight: '400', color: colors.textMuted },
  reviewedCount: { fontSize: fontSize.body, color: colors.textMuted },
  remaining: { fontSize: fontSize.body, color: colors.primaryDark },
  masteryRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: spacing.xs },
  masteryLabel: { fontSize: fontSize.body, color: colors.textFaint },
  masteryValue: { fontSize: fontSize.body, fontWeight: '700' },
  masteryTrack: { height: 8, borderRadius: 999, backgroundColor: colors.primaryBg, overflow: 'hidden' },
  masteryFill: { height: 8, borderRadius: 999 },
  overdue: { fontSize: fontSize.body, fontWeight: '600', color: colors.dangerText, marginTop: spacing.xs },
  cardFooter: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    borderTopWidth: 1, borderTopColor: colors.border, paddingTop: spacing.md, marginTop: spacing.sm,
  },
  moduleLabel: { fontSize: fontSize.body, fontWeight: '500', color: colors.textMuted },
  reviewBtn: {
    minHeight: buttonHeight.min, paddingHorizontal: spacing.lg, borderRadius: radius.lg,
    backgroundColor: colors.primaryBg, borderWidth: 1, borderColor: colors.primaryBorder,
    alignItems: 'center', justifyContent: 'center',
  },
  reviewBtnText: { fontSize: fontSize.body, fontWeight: '600', color: colors.primaryDark },
  footer: {
    paddingHorizontal: spacing.xl, paddingVertical: spacing.md,
    backgroundColor: colors.bgEnd, borderTopWidth: 1, borderTopColor: colors.border,
  },
  primaryBtn: {
    minHeight: buttonHeight.xl, borderRadius: radius.xl, backgroundColor: colors.primary,
    alignItems: 'center', justifyContent: 'center',
  },
  primaryBtnText: { fontSize: fontSize.base, fontWeight: '700', color: colors.white, letterSpacing: 1 },
  muted: { fontSize: fontSize.body, color: colors.textFaint },
});
