import { router, useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { authenticatedFetch, sendRecommendationFeedback } from '@/lib/authClient';
import { useLearningContext } from '@/context/LearningContext';
import { useLearningSession } from '@/context/LearningSessionContext';
import { useComprehensiveTracking } from '@/hooks/useTimeTracking';
import { colors, fontSize, radius, buttonHeight, spacing } from '@/theme';

const DEFAULT_WORD_ID = 1;
const DEFAULT_WORD_NAME = '发生';

const learningOptions = [
  { value: 'A', module: 'character', path: '/character-learning', label: 'Characters', text: 'I have never seen this word.' },
  { value: 'B', module: 'word', path: '/word-learning', label: 'Word', text: "I don't know what it means." },
  { value: 'C', module: 'collocation', path: '/collocation-learning', label: 'Collocations', text: 'I know what it means, but not which words go with it.' },
  { value: 'D', module: 'sentence', path: '/sentence-learning', label: 'Sentences', text: "I know which words go with it, but I can't use it in a sentence yet." },
  { value: 'E', module: 'exercise', path: '/exercise', label: 'Practice', text: 'I can use it in a sentence.' },
];

export default function WordLearningEntrance() {
  const { userId } = useLearningContext();
  const { session, updateSession } = useLearningSession();
  const [targetWord, setTargetWord] = useState<{ id: number; word: string; recommendationId?: number } | null>(null);
  const [settled, setSettled] = useState(false);
  const [selected, setSelected] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // 页面重新获得焦点时复位「提交中」状态：防止上一轮 setSubmitting(true) 后跳转未完成，
  // 回来时按钮一直转圈、发不出请求（网页版换页整页重载，RN 不会）。
  useFocusEffect(
    useCallback(() => {
      setSubmitting(false);
    }, [])
  );

  const askedWordId = targetWord?.id ?? DEFAULT_WORD_ID;

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    const context = encodeURIComponent(JSON.stringify({ new_only: true }));
    authenticatedFetch(`/api/adaptive/recommendation/${userId}?context=${context}`, { cache: 'no-cache' })
      .then(resp => resp.json())
      .then(result => {
        if (cancelled || !result.success || !result.data) return;
        const { word_id, word, recommendationId } = result.data;
        if (word_id && word) setTargetWord({ id: word_id, word, recommendationId });
      })
      .catch(() => {
        /* 拉取失败保持默认词，不阻塞流程 */
      })
      .finally(() => {
        if (!cancelled) setSettled(true);
      });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  useEffect(() => {
    setSelected(session.wordId === askedWordId ? session.vksLevel ?? '' : '');
  }, [askedWordId, session.wordId, session.vksLevel]);

  const tracking = useComprehensiveTracking({
    userId,
    wordId: askedWordId,
    moduleType: 'entrance',
    sessionType: 'learning',
    ready: settled && Boolean(targetWord),
  });

  const handleContinue = async () => {
    if (!selected || !targetWord) return;
    const opt = learningOptions.find(o => o.value === selected);
    if (!opt) return;
    setSubmitting(true);

    const resolvedWordId = targetWord.id;
    const resolvedWord = targetWord.word;
    // 单字词拆不出字：选 A 的也从词页开始（档位仍记 A）
    const singleChar = Array.from(resolvedWord).length === 1;
    const resolvedModule = singleChar && opt.module === 'character' ? 'word' : opt.module;
    const resolvedPath = singleChar && opt.module === 'character' ? '/word-learning' : opt.path;
    const recommendationId = targetWord.recommendationId ?? null;

    tracking.trackEvent('vks_test_complete', 'entrance', {
      selectedLevel: selected,
      resolvedModule,
      recommendationId,
      userId,
    });
    tracking.updateConfig({ wordId: resolvedWordId, moduleType: resolvedModule });
    sendRecommendationFeedback(userId, recommendationId, true, `${resolvedModule}:${resolvedWordId}`);

    updateSession({
      wordId: resolvedWordId,
      word: resolvedWord,
      module: resolvedModule,
      entryModule: resolvedModule,
      vksLevel: selected,
      recommendationId,
      reviewMode: null,
      lastUpdated: new Date().toISOString(),
    });

    await tracking.endSession(true);
    // replace 而不是 push：自评页是学习流程的入口，选完就替换成学习步骤，
    // 返回时回首页而不是卡在自评页（旧页面若留在栈里，提交中状态不会复位）。
    router.replace(resolvedPath as any);
  };

  const displayWord = targetWord?.word ?? DEFAULT_WORD_NAME;

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Self-check</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardLabel}>New word</Text>
          <View style={styles.wordBox}>
            <Text style={styles.wordText}>{displayWord}</Text>
          </View>
          <Text style={styles.question}>How well do you know this word?</Text>
        </View>

        <View style={styles.options}>
          {learningOptions.map((option, index) => {
            const active = selected === option.value;
            return (
              <Pressable
                key={option.value}
                style={[styles.option, active && styles.optionActive]}
                onPress={() => setSelected(option.value)}
                accessibilityRole="radio"
                accessibilityState={{ selected: active }}
              >
                <View style={[styles.optionBadge, active && styles.optionBadgeActive]}>
                  <Text style={[styles.optionBadgeText, active && styles.optionBadgeTextActive]}>{index + 1}</Text>
                </View>
                <Text style={[styles.optionText, active && styles.optionTextActive]}>{option.text}</Text>
              </Pressable>
            );
          })}
        </View>

        <Pressable
          style={[styles.continueBtn, (!selected || submitting) && styles.continueBtnDisabled]}
          onPress={handleContinue}
          disabled={!selected || submitting}
        >
          {submitting ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.continueText}>CONTINUE</Text>
          )}
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bgStart },
  container: { flex: 1, paddingHorizontal: 20, paddingVertical: spacing.lg, gap: spacing.lg },
  header: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center' },
  headerTitle: { fontSize: fontSize.xl, fontWeight: '800', color: colors.text },
  card: {
    backgroundColor: colors.white,
    borderRadius: radius['3xl'],
    borderWidth: 1,
    borderColor: colors.primaryBorder,
    padding: spacing.xl,
    alignItems: 'center',
    gap: spacing.md,
  },
  cardLabel: { fontSize: fontSize.body, fontWeight: '600', color: colors.primary },
  wordBox: {
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.sm,
    borderRadius: radius.xl,
    backgroundColor: colors.primaryBg,
    borderWidth: 1,
    borderColor: colors.primaryBorder,
  },
  wordText: { fontSize: fontSize['3xl'], fontWeight: '800', color: colors.text },
  question: { fontSize: fontSize.base, fontWeight: '600', color: colors.textStrong },
  options: { gap: spacing.sm },
  option: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderRadius: radius.xl,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.white,
    minHeight: buttonHeight.lg,
  },
  optionActive: {
    backgroundColor: colors.primaryBg,
    borderColor: colors.primary,
  },
  optionBadge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#f1f5f9',
    alignItems: 'center',
    justifyContent: 'center',
  },
  optionBadgeActive: { backgroundColor: colors.primary },
  optionBadgeText: { fontSize: fontSize.body, fontWeight: '700', color: colors.textMuted },
  optionBadgeTextActive: { color: colors.white },
  optionText: { flex: 1, fontSize: fontSize.body, fontWeight: '500', color: colors.textStrong, lineHeight: 20 },
  optionTextActive: { color: colors.primaryDeep, fontWeight: '600' },
  continueBtn: {
    marginTop: 'auto',
    minHeight: buttonHeight.xl,
    borderRadius: radius.xl,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  continueBtnDisabled: { backgroundColor: colors.border },
  continueText: { fontSize: fontSize.base, fontWeight: '700', color: colors.white, letterSpacing: 1 },
});
