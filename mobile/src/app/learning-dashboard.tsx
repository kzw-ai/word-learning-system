// 源文件：pages/learning-dashboard.tsx（网页版）。RN 版：跳转用 router.replace。
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, BackHandler, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { authenticatedFetch, sendRecommendationFeedback } from '@/lib/authClient';
import type { DashboardData, Recommendation } from '@/lib/types';
import { formatReviewTime } from '@/lib/reviewTime';
import { useLearningContext } from '@/context/LearningContext';
import { useLearningSession } from '@/context/LearningSessionContext';
import { colors, fontSize, radius, buttonHeight, spacing } from '@/theme';

const MODULE_ROUTES: Record<string, string> = {
  character: '/character-learning',
  word: '/word-learning',
  collocation: '/collocation-learning',
  sentence: '/sentence-learning',
  exercise: '/exercise',
  urgent_review: '/exercise',
  scheduled_review: '/exercise',
  new_learning: '/word-learning',
};

const MODULE_LABELS: Record<string, string> = {
  character: 'Characters',
  word: 'Word',
  collocation: 'Collocations',
  sentence: 'Sentences',
  exercise: 'Practice',
  urgent_review: 'Urgent review',
  scheduled_review: 'Scheduled review',
  new_learning: 'New word',
};

const TYPE_LABELS: Record<string, string> = {
  urgent_review: 'Urgent review',
  scheduled_review: 'Review due',
  new_learning: 'New word',
  all_caught_up: 'All caught up',
  system_default: 'Suggested',
};

export default function LearningDashboard() {
  const { userId } = useLearningContext();
  const { updateSession } = useLearningSession();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);

  const fetchDashboardData = async () => {
    try {
      const response = await authenticatedFetch(`/api/analytics/user/${userId}/dashboard`);
      const result = await response.json();
      if (response.ok && result.success) {
        setDashboardData(result.data);
      }
    } catch {
      /* 看板数据取不到不阻塞推荐 */
    }
  };

  const fetchRecommendation = async () => {
    try {
      setLoading(true);
      const response = await authenticatedFetch(`/api/adaptive/recommendation/${userId}`);
      const result = await response.json();
      if (response.ok && result.success) {
        setRecommendation(result.data);
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
    if (!userId) return;
    fetchDashboardData();
    fetchRecommendation();
  }, [userId]);

  // 安卓返回键回首页
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      router.replace('/');
      return true;
    });
    return () => sub.remove();
  }, []);

  const startRecommendedLearning = () => {
    if (!recommendation?.word_id) return;
    // 新词先做 VKS 自评，入口页沿用这条推荐的词
    if (recommendation.type === 'new_learning') {
      updateSession({
        wordId: recommendation.word_id,
        word: recommendation.word,
        module: null,
        entryModule: null,
        vksLevel: undefined,
        recommendationId: recommendation.recommendationId ?? null,
        reviewMode: null,
        lastUpdated: new Date().toISOString(),
      });
      router.replace('/word-learning-entrance');
      return;
    }

    sendRecommendationFeedback(userId, recommendation.recommendationId, true, `${recommendation.recommended_module}:${recommendation.word_id}`);
    updateSession({
      wordId: recommendation.word_id,
      word: recommendation.word,
      module: recommendation.recommended_module,
      entryModule: recommendation.recommended_module,
      vksLevel: undefined,
      recommendationId: recommendation.recommendationId ?? null,
      reviewMode: null,
      lastUpdated: new Date().toISOString(),
    });
    const route = MODULE_ROUTES[recommendation.recommended_module ?? ''] || MODULE_ROUTES[recommendation.type] || '/word-learning';
    router.replace(route as any);
  };

  const overall = dashboardData?.overallProgress;
  const hskLevel = overall?.hskLevel ?? 4;
  const levelProgress = overall?.levels?.[String(hskLevel)];
  const levelWords = levelProgress?.words ?? overall?.totalWords ?? 0;
  const levelStudied = levelProgress?.studied ?? overall?.studiedWords ?? 0;

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Text style={styles.title}>Dashboard</Text>
      </View>

      <ScrollView style={styles.content} contentContainerStyle={styles.contentInner}>
        {loading && !recommendation && (
          <View style={styles.card}>
            <ActivityIndicator color={colors.primary} />
            <Text style={styles.muted}>Loading your progress…</Text>
          </View>
        )}

        {error && !recommendation && (
          <View style={styles.errorCard}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}

        {/* 暂时没有任务 */}
        {recommendation && !recommendation.word_id && (
          <View style={styles.card}>
            <Text style={styles.caughtUpTitle}>You’re all caught up</Text>
            <Text style={styles.caughtUpText}>
              {recommendation.next_review_at
                ? `Your next review is ${formatReviewTime(recommendation.next_review_at)}.`
                : 'There are no new words to learn right now.'}
            </Text>
          </View>
        )}

        {/* 智能推荐卡片 */}
        {recommendation?.word_id && (
          <View style={styles.recommendCard}>
            <View style={styles.recommendTop}>
              <View style={styles.recommendInfo}>
                <View style={styles.typeBadge}>
                  <Text style={styles.typeBadgeText}>{TYPE_LABELS[recommendation.type] ?? recommendation.type}</Text>
                </View>
                <Text style={styles.reason}>{recommendation.reason}</Text>
              </View>
              <View style={styles.wordBox}>
                <Text style={styles.wordBoxText}>{recommendation.word}</Text>
              </View>
            </View>

            <View style={styles.metaRow}>
              <Text style={styles.metaText}>
                {recommendation.type === 'new_learning'
                  ? 'Self-check'
                  : MODULE_LABELS[recommendation.recommended_module || recommendation.type]}
              </Text>
              <Text style={styles.metaSep}>|</Text>
              <Text style={styles.metaText}>about {Math.floor(recommendation.estimated_time / 60)} min</Text>
            </View>

            <Pressable style={styles.primaryBtn} onPress={startRecommendedLearning}>
              <Text style={styles.primaryBtnText}>Start now</Text>
            </Pressable>
          </View>
        )}

        {/* 今日统计 */}
        {dashboardData && (
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Today</Text>
            <View style={styles.statGrid}>
              <View style={styles.statCell}>
                <Text style={styles.statValue}>{dashboardData.todayStats.wordsReviewed}</Text>
                <Text style={styles.statLabel}>Words studied</Text>
              </View>
              <View style={styles.statCell}>
                <Text style={styles.statValue}>{dashboardData.todayStats.exercisesCompleted}</Text>
                <Text style={styles.statLabel}>Exercises</Text>
              </View>
              <View style={styles.statCell}>
                <Text style={styles.statValue}>{dashboardData.todayStats.studyTimeMinutes}</Text>
                <Text style={styles.statLabel}>Minutes</Text>
              </View>
              <View style={styles.statCell}>
                <Text style={styles.statValue}>{(dashboardData.todayStats.averageAccuracy * 100).toFixed(0)}%</Text>
                <Text style={styles.statLabel}>Accuracy</Text>
              </View>
            </View>
          </View>
        )}

        {/* 整体进度 */}
        {dashboardData && (
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Overall</Text>
            <View style={styles.progressBlock}>
              <View style={styles.progressRow}>
                <Text style={styles.progressLabel}>HSK {hskLevel} words learned</Text>
                <Text style={styles.progressValue}>
                  {levelStudied} <Text style={styles.progressTotal}>/ {levelWords}</Text>
                </Text>
              </View>
              <View style={styles.progressTrack}>
                <View style={[styles.progressFill, { width: `${levelWords ? (levelStudied / levelWords) * 100 : 0}%`, backgroundColor: '#6366f1' }]} />
              </View>
            </View>
            <View style={styles.progressBlock}>
              <View style={styles.progressRow}>
                <Text style={styles.progressLabel}>Average mastery</Text>
                <Text style={[styles.progressValue, { color: colors.success }]}>
                  {(dashboardData.overallProgress.averageMastery * 100).toFixed(1)}%
                </Text>
              </View>
              <View style={styles.progressTrack}>
                <View style={[styles.progressFill, { width: `${dashboardData.overallProgress.averageMastery * 100}%`, backgroundColor: '#34d399' }]} />
              </View>
            </View>
          </View>
        )}

        {/* 快捷操作 */}
        <View style={styles.shortcuts}>
          <Pressable
            style={styles.shortcut}
            onPress={() => {
              sendRecommendationFeedback(userId, recommendation?.recommendationId, false, 'today-review');
              router.replace('/today-review');
            }}
          >
            <View style={[styles.shortcutIcon, { backgroundColor: colors.primaryBg }]}>
              <Text style={[styles.shortcutIconText, { color: colors.primary }]}>⏱</Text>
            </View>
            <Text style={styles.shortcutLabel}>Today’s review</Text>
            {dashboardData && dashboardData.dueReviews > 0 && (
              <View style={styles.shortcutBadge}>
                <Text style={styles.shortcutBadgeText}>{dashboardData.dueReviews > 99 ? '99+' : dashboardData.dueReviews}</Text>
              </View>
            )}
          </Pressable>
          <Pressable
            style={styles.shortcut}
            onPress={() => {
              sendRecommendationFeedback(userId, recommendation?.recommendationId, false, 'word-learning-entrance');
              router.replace('/word-learning-entrance');
            }}
          >
            <View style={[styles.shortcutIcon, { backgroundColor: '#f3e8ff' }]}>
              <Text style={[styles.shortcutIconText, { color: '#7c3aed' }]}>📖</Text>
            </View>
            <Text style={styles.shortcutLabel}>Start learning</Text>
          </Pressable>
        </View>
      </ScrollView>

      <View style={styles.footer}>
        <Pressable style={styles.backBtn} onPress={() => router.replace('/')}>
          <Text style={styles.backBtnText}>Back to home</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bgStart },
  header: { paddingHorizontal: spacing.xl, paddingVertical: spacing.md },
  title: { fontSize: fontSize['2xl'], fontWeight: '800', color: colors.text },
  content: { flex: 1 },
  contentInner: { paddingHorizontal: spacing.xl, paddingVertical: spacing.md, gap: spacing.lg },
  card: {
    backgroundColor: colors.white, borderRadius: radius['3xl'], borderWidth: 1, borderColor: colors.primaryBorder,
    padding: spacing.xl, gap: spacing.md, alignItems: 'center',
  },
  muted: { fontSize: fontSize.base, color: colors.textFaint, textAlign: 'center' },
  errorCard: {
    backgroundColor: colors.dangerBg, borderRadius: radius.xl, borderWidth: 1, borderColor: colors.dangerBorder,
    padding: spacing.lg,
  },
  errorText: { fontSize: fontSize.base, color: colors.dangerText, textAlign: 'center' },
  caughtUpTitle: { fontSize: fontSize.lg, fontWeight: '700', color: colors.text },
  caughtUpText: { fontSize: fontSize.base, color: colors.textMuted, textAlign: 'center' },
  recommendCard: {
    backgroundColor: colors.white, borderRadius: radius['3xl'], borderWidth: 1, borderColor: colors.primaryBorder,
    padding: spacing.xl, gap: spacing.md,
  },
  recommendTop: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.lg },
  recommendInfo: { flex: 1, gap: spacing.sm },
  typeBadge: {
    alignSelf: 'flex-start', paddingHorizontal: spacing.md, paddingVertical: 4,
    borderRadius: 999, backgroundColor: colors.primaryBg,
  },
  typeBadgeText: { fontSize: fontSize.body, fontWeight: '600', color: colors.primaryDark },
  reason: { fontSize: fontSize.body, color: colors.textMuted, lineHeight: 20 },
  wordBox: {
    paddingHorizontal: spacing.lg, paddingVertical: spacing.sm, borderRadius: radius.xl,
    backgroundColor: colors.primaryBg, borderWidth: 1, borderColor: colors.primaryBorder,
  },
  wordBoxText: { fontSize: fontSize['2xl'], fontWeight: '800', color: colors.text },
  metaRow: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.sm,
    paddingVertical: spacing.sm, paddingHorizontal: spacing.md, borderRadius: radius.xl,
    backgroundColor: colors.bgEnd, borderWidth: 1, borderColor: colors.border,
  },
  metaText: { fontSize: fontSize.body, fontWeight: '600', color: colors.textStrong },
  metaSep: { color: colors.borderStrong },
  primaryBtn: {
    minHeight: buttonHeight.xl, borderRadius: radius.xl, backgroundColor: colors.primary,
    alignItems: 'center', justifyContent: 'center',
  },
  primaryBtnText: { fontSize: fontSize.base, fontWeight: '700', color: colors.white, letterSpacing: 1 },
  sectionTitle: { fontSize: fontSize.lg, fontWeight: '700', color: colors.text },
  statGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md },
  statCell: {
    flexBasis: '47%', flexGrow: 1, alignItems: 'center',
    padding: spacing.md, borderRadius: radius.xl, backgroundColor: colors.bgEnd, borderWidth: 1, borderColor: colors.border,
  },
  statValue: { fontSize: fontSize['2xl'], fontWeight: '800', color: colors.text },
  statLabel: { fontSize: fontSize.body, color: colors.textMuted },
  progressBlock: { gap: spacing.sm },
  progressRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' },
  progressLabel: { fontSize: fontSize.base, color: colors.textMuted },
  progressValue: { fontSize: fontSize.lg, fontWeight: '700', color: colors.text },
  progressTotal: { fontSize: fontSize.body, fontWeight: '400', color: colors.textFaint },
  progressTrack: { height: 8, borderRadius: 999, backgroundColor: colors.primaryBg, overflow: 'hidden' },
  progressFill: { height: 8, borderRadius: 999 },
  shortcuts: { flexDirection: 'row', gap: spacing.lg, marginBottom: spacing.md },
  shortcut: {
    flex: 1, alignItems: 'center', gap: spacing.sm,
    padding: spacing.lg, borderRadius: radius['3xl'], backgroundColor: colors.white, borderWidth: 1, borderColor: colors.border,
  },
  shortcutIcon: { padding: spacing.md, borderRadius: radius.xl },
  shortcutIconText: { fontSize: fontSize.xl },
  shortcutLabel: { fontSize: fontSize.base, fontWeight: '700', color: colors.text, textAlign: 'center' },
  shortcutBadge: {
    position: 'absolute', top: spacing.sm, right: spacing.sm,
    minWidth: 24, height: 24, borderRadius: 12, backgroundColor: colors.danger,
    alignItems: 'center', justifyContent: 'center', paddingHorizontal: 6,
  },
  shortcutBadgeText: { fontSize: fontSize.body, fontWeight: '700', color: colors.white },
  footer: {
    paddingHorizontal: spacing.xl, paddingVertical: spacing.sm,
    backgroundColor: colors.bgEnd, borderTopWidth: 1, borderTopColor: colors.border,
  },
  backBtn: { minHeight: buttonHeight.lg, alignItems: 'center', justifyContent: 'center' },
  backBtnText: { fontSize: fontSize.body, fontWeight: '600', color: colors.textMuted },
});
