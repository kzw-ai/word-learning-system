// 源文件：pages/confusable-words.tsx（网页版）。RN 版：跳转用 router.replace，音频 M8 补。
import { router, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, BackHandler, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Crypto from 'expo-crypto';
import { authenticatedFetch, authenticatedPost } from '@/lib/authClient';
import type { ConfusablePair, ContrastQuestion } from '@/lib/types';
import { afterWordRoute, useLearningSession } from '@/context/LearningSessionContext';
import { useLearningContext } from '@/context/LearningContext';
import { useTimeTracking } from '@/hooks/useTimeTracking';
import { colors, fontSize, radius, buttonHeight, spacing } from '@/theme';

// 辨析页的英文讲解比学习页长，两次操作之间最多算 180 秒有效时长
const CONTRAST_IDLE_CAP_SECONDS = 180;

type SaveState = 'saving' | 'saved' | 'failed' | 'stale';

// 每次作答一个编号，重试沿用同一个，后端据此去重
const newAttemptId = () => Crypto.randomUUID();

/** 辨析题：每题选一次，选完即把题号和所选答案交给后端判分记录（不计入论文表 4.2 的复习次数）。 */
function ContrastQuiz({ pair }: { pair: ConfusablePair }) {
  const questions: ContrastQuestion[] = pair.questions ?? [];
  const [picked, setPicked] = useState<Record<number, string>>({});
  const [saved, setSaved] = useState<Record<number, SaveState>>({});
  // 后端判分结果（对错与正确答案），以它为准；没返回之前先按本地答案显示
  const [judged, setJudged] = useState<Record<number, { ok: boolean; answer: string }>>({});
  const shownAt = useRef(Date.now());
  const elapsed = useRef<Record<number, number>>({});
  const attempts = useRef<Record<number, string>>({});

  useEffect(() => {
    setPicked({});
    setSaved({});
    setJudged({});
    elapsed.current = {};
    attempts.current = {};
    shownAt.current = Date.now();
  }, [pair.id]);

  if (questions.length === 0) return null;

  const save = async (index: number, option: string) => {
    setSaved(prev => ({ ...prev, [index]: 'saving' }));
    try {
      const resp = await authenticatedPost('/api/confusable/exercise/record', {
        pair_id: pair.id,
        question_index: index,
        question_version: questions[index].version,
        user_answer: option,
        response_time: elapsed.current[index],
        attempt_id: attempts.current[index],
      });
      const result = await resp.json().catch(() => null);
      if (resp.status === 409) {
        setSaved(prev => ({ ...prev, [index]: 'stale' }));
        return;
      }
      const ok = resp.ok && result?.success;
      setSaved(prev => ({ ...prev, [index]: ok ? 'saved' : 'failed' }));
      if (ok && typeof result.is_correct === 'boolean') {
        const answer = typeof result.correct_answer === 'string' ? result.correct_answer : questions[index].correct_answer;
        setJudged(prev => ({ ...prev, [index]: { ok: result.is_correct, answer } }));
      }
    } catch {
      setSaved(prev => ({ ...prev, [index]: 'failed' }));
    }
  };

  const choose = (index: number, option: string) => {
    if (picked[index]) return;
    setPicked(prev => ({ ...prev, [index]: option }));
    elapsed.current[index] = (Date.now() - shownAt.current) / 1000;
    attempts.current[index] = newAttemptId();
    shownAt.current = Date.now();
    void save(index, option);
  };

  const answerOf = (i: number) => judged[i]?.answer ?? questions[i].correct_answer;
  const isRight = (i: number) => judged[i]?.ok ?? picked[i] === answerOf(i);
  const allSaved = questions.every((_, i) => saved[i] === 'saved');
  const anyStale = questions.some((_, i) => saved[i] === 'stale');
  const correct = questions.filter((_, i) => isRight(i)).length;

  return (
    <View style={styles.quizCard}>
      <Text style={styles.quizTitle}>✏️ Check yourself</Text>
      <Text style={styles.quizHint}>Choose the word that fits each sentence.</Text>
      {questions.map((q, i) => {
        const choice = picked[i];
        return (
          <View key={i} style={styles.quizQuestion}>
            <Text style={styles.quizStem}>{q.stem}</Text>
            <View style={styles.quizOptions}>
              {q.options.map(option => {
                const state = !choice || saved[i] === 'stale' ? 'idle'
                  : option === answerOf(i) ? 'right'
                  : option === choice ? 'wrong' : 'idle';
                return (
                  <Pressable
                    key={option}
                    style={[
                      styles.quizOption,
                      state === 'right' && styles.quizOptionRight,
                      state === 'wrong' && styles.quizOptionWrong,
                    ]}
                    disabled={!!choice}
                    onPress={() => choose(i, option)}
                  >
                    <Text style={[styles.quizOptionText, state === 'right' && styles.quizOptionTextRight, state === 'wrong' && styles.quizOptionTextWrong]}>
                      {option}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
            {choice && saved[i] !== 'stale' && (
              <Text style={[styles.quizResult, isRight(i) ? styles.textCorrect : styles.textWrong]}>
                {isRight(i) ? 'Correct.' : `Not quite: the answer is ${answerOf(i)}.`}
              </Text>
            )}
            {choice && saved[i] !== 'stale' && q.explanation ? (
              <Text style={styles.quizExplanation}>{q.explanation}</Text>
            ) : null}
            {saved[i] === 'stale' && (
              <Text style={styles.textWarning}>This question has been updated. Please reload the page.</Text>
            )}
            {saved[i] === 'failed' && (
              <View style={styles.quizFailRow}>
                <Text style={styles.textWarning}>Your answer wasn’t saved.</Text>
                <Pressable style={styles.retryBtn} onPress={() => save(i, choice)}>
                  <Text style={styles.retryBtnText}>Retry</Text>
                </Pressable>
              </View>
            )}
          </View>
        );
      })}
      {allSaved && (
        <Text style={styles.quizScore}>
          {correct} / {questions.length} correct
          {correct < questions.length ? '. This pair will come back next time you practise these words.' : '. Well done!'}
        </Text>
      )}
      {anyStale && (
        <Text style={styles.textWarning}>Some questions have been updated. Please reload the page to try them again.</Text>
      )}
    </View>
  );
}

export default function ConfusableWordsPage() {
  const { session } = useLearningSession();
  const { userId } = useLearningContext();
  const { pair: pairParam, from: fromParam, revisit: revisitParam } = useLocalSearchParams<{ pair?: string; from?: string; revisit?: string }>();
  const [pairs, setPairs] = useState<ConfusablePair[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAnswer, setShowAnswer] = useState(false);
  const fromExercise = fromParam === 'exercise';
  const revisit = revisitParam === '1';
  const loadSeq = useRef(0);

  const loadConfusablePairs = useCallback(async () => {
    const seq = ++loadSeq.current;
    const stale = () => seq !== loadSeq.current;
    try {
      setLoading(true);
      const response = await authenticatedFetch('/api/confusable/pairs?limit=20');
      const data = await response.json();
      if (stale()) return;

      if (data.success) {
        // 从练习带入的那一对不一定在列表的前 20 对里：单独取来放在最前面
        const pairId = Number(pairParam);
        let list: ConfusablePair[] = data.pairs;
        if (pairId && !list.some(p => p.id === pairId)) {
          const resp = await authenticatedFetch(`/api/confusable/pair/${pairId}`);
          const single = await resp.json().catch(() => null);
          if (stale()) return;
          if (!resp.ok || !single?.success) {
            setError('Could not load this pair of words.');
            return;
          }
          list = [single.pair, ...list];
        }
        setError(null);
        // 列表和定位一起设（同一次渲染）：先渲染列表首项的话，停留时长会给没看的那一对记一个会话
        const idx = pairId ? list.findIndex(p => p.id === pairId) : -1;
        setPairs(list);
        setCurrentIndex(Math.max(idx, 0));
        setShowAnswer(idx >= 0 && revisit);
      } else {
        setError(data.error || 'Failed to load');
      }
    } catch {
      if (stale()) return;
      setError('Network error. Please try again later.');
    } finally {
      if (!stale()) setLoading(false);
    }
  }, [pairParam, revisit]);

  useEffect(() => {
    loadConfusablePairs();
  }, [loadConfusablePairs]);

  const currentPair = pairs[currentIndex];

  // 停留时长：每对按目标词（word1）记一个学习会话，模块记作 contrast；不计入论文表 4.2 的复习。
  // 换到另一对时结束上一个会话，目标词相同的两对也分开记（sessionKey）。
  const { trackEvent } = useTimeTracking({
    userId,
    wordId: currentPair?.word1.id ?? 0,
    sessionKey: currentPair?.id,
    moduleType: 'contrast',
    sessionType: session.reviewMode ? 'review' : 'learning',
    idleCapSeconds: CONTRAST_IDLE_CAP_SECONDS,
    ready: !!currentPair && !loading && !error,
  });

  useEffect(() => {
    if (currentPair) trackEvent('contrast_pair', String(currentPair.id), { revisit });
  }, [currentPair, trackEvent, revisit]);

  // 安卓返回键回上一页（学习流程中回主页）
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      router.replace('/');
      return true;
    });
    return () => sub.remove();
  }, []);

  const showComparison = () => {
    setShowAnswer(true);
    if (currentPair) trackEvent('contrast_expand', String(currentPair.id));
  };

  const handleNext = () => {
    if (currentIndex < pairs.length - 1) {
      setCurrentIndex(currentIndex + 1);
      setShowAnswer(false);
    }
  };

  const handlePrevious = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
      setShowAnswer(false);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.center}>
        <ActivityIndicator color={colors.primary} />
        <Text style={styles.muted}>Loading easily confused words…</Text>
      </SafeAreaView>
    );
  }

  if (error) {
    return (
      <SafeAreaView style={styles.center}>
        <Text style={styles.error}>{error}</Text>
        <Pressable style={styles.primaryBtn} onPress={loadConfusablePairs}>
          <Text style={styles.primaryBtnText}>Retry</Text>
        </Pressable>
      </SafeAreaView>
    );
  }

  if (!currentPair) {
    return (
      <SafeAreaView style={styles.center}>
        <Text style={styles.muted}>No easily confused words yet</Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Pressable style={styles.headerBtn} onPress={() => router.replace('/')}>
          <Text style={styles.headerBtnText}>← Back</Text>
        </Pressable>
        <Text style={styles.title}>Easily confused</Text>
        <View style={styles.headerSpacer} />
      </View>
      {pairs.length > 0 && (
        <Text style={styles.counter}>Pair {currentIndex + 1} of {pairs.length}</Text>
      )}

      <ScrollView style={styles.content} contentContainerStyle={styles.contentInner}>
        {/* 词对比较 */}
        <View style={styles.compareRow}>
          <View style={[styles.wordCard, styles.wordCardLeft]}>
            <Text style={styles.wordHanziLeft}>{currentPair.word1.hanzi ?? currentPair.word1.pinyin}</Text>
            {currentPair.word1.hanzi && <Text style={styles.wordPinyin}>{currentPair.word1.pinyin}</Text>}
            <Text style={styles.wordDef}>{currentPair.word1.definition}</Text>
          </View>
          <View style={[styles.wordCard, styles.wordCardRight]}>
            <Text style={styles.wordHanziRight}>{currentPair.word2.hanzi ?? currentPair.word2.pinyin}</Text>
            {currentPair.word2.hanzi && <Text style={styles.wordPinyin}>{currentPair.word2.pinyin}</Text>}
            <Text style={styles.wordDef}>{currentPair.word2.definition}</Text>
          </View>
        </View>

        {/* 混淆原因 */}
        <View style={[styles.card, styles.reasonCard]}>
          <Text style={styles.sectionTitleAmber}>💡 Why they get mixed up</Text>
          <Text style={styles.bodyText}>{currentPair.reason}</Text>
        </View>

        {/* 显示答案按钮 */}
        {!showAnswer && (
          <Pressable style={styles.primaryBtn} onPress={showComparison}>
            <Text style={styles.primaryBtnText}>See the full comparison</Text>
          </Pressable>
        )}

        {/* 详细辨析 */}
        {showAnswer && (
          <>
            <View style={styles.card}>
              <Text style={styles.sectionTitle}>📖 The difference</Text>
              <Text style={styles.bodyText}>{currentPair.difference}</Text>
            </View>

            {currentPair.examples ? (
              <View style={[styles.card, styles.exampleCard]}>
                <Text style={styles.sectionTitleGreen}>✏️ Example sentences</Text>
                <Text style={styles.bodyText}>{currentPair.examples}</Text>
              </View>
            ) : null}

            {currentPair.tips ? (
              <View style={[styles.card, styles.tipCard]}>
                <Text style={styles.sectionTitleIndigo}>💡 Memory tip</Text>
                <Text style={styles.bodyText}>{currentPair.tips}</Text>
              </View>
            ) : null}

            <ContrastQuiz pair={currentPair} />
          </>
        )}

        {/* 难度标识 */}
        <Text style={styles.difficulty}>
          Difficulty {'★'.repeat(currentPair.difficulty_level)}
        </Text>
      </ScrollView>

      {/* Navigation */}
      {pairs.length > 0 && (
        <View style={styles.footer}>
          {fromExercise && (
            <Pressable
              style={showAnswer ? styles.primaryBtn : styles.doneBtn}
              onPress={() => router.replace(afterWordRoute(session) as any)}
            >
              <Text style={showAnswer ? styles.primaryBtnText : styles.doneBtnText}>
                {session.reviewMode ? 'Done · continue reviewing' : 'Done · see my progress'}
              </Text>
            </Pressable>
          )}
          <View style={styles.navRow}>
            <Pressable
              style={[styles.navBtn, currentIndex === 0 && styles.navBtnDisabled]}
              onPress={handlePrevious}
              disabled={currentIndex === 0}
            >
              <Text style={styles.navBtnText}>← Previous pair</Text>
            </Pressable>
            <Pressable
              style={[styles.navBtn, currentIndex === pairs.length - 1 && styles.navBtnDisabled]}
              onPress={handleNext}
              disabled={currentIndex === pairs.length - 1}
            >
              <Text style={styles.navBtnText}>Next pair →</Text>
            </Pressable>
          </View>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bgStart },
  center: { flex: 1, backgroundColor: colors.bgStart, alignItems: 'center', justifyContent: 'center', gap: spacing.md, paddingHorizontal: spacing.xl },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: spacing.xl, paddingVertical: spacing.md },
  headerBtn: {
    minHeight: buttonHeight.min, paddingHorizontal: spacing.md, borderRadius: radius.lg,
    backgroundColor: colors.white, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center',
  },
  headerBtnText: { fontSize: fontSize.body, fontWeight: '600', color: colors.primaryDark },
  title: { fontSize: fontSize.xl, fontWeight: '800', color: colors.text },
  headerSpacer: { width: 76 },
  counter: { fontSize: fontSize.body, fontWeight: '600', color: colors.textMuted, textAlign: 'center', marginBottom: spacing.sm },
  content: { flex: 1 },
  contentInner: { paddingHorizontal: spacing.xl, paddingBottom: spacing.lg, gap: spacing.md },
  compareRow: { flexDirection: 'row', gap: spacing.md },
  wordCard: { flex: 1, padding: spacing.lg, borderRadius: radius.xl, borderWidth: 1, gap: spacing.xs },
  wordCardLeft: { backgroundColor: colors.white, borderLeftWidth: 4, borderLeftColor: colors.primary, borderColor: colors.border },
  wordCardRight: { backgroundColor: colors.white, borderLeftWidth: 4, borderLeftColor: '#34d399', borderColor: colors.border },
  wordHanziLeft: { fontSize: fontSize.xl, fontWeight: '800', color: colors.primaryDark },
  wordHanziRight: { fontSize: fontSize.xl, fontWeight: '800', color: '#047857' },
  wordPinyin: { fontSize: fontSize.body, color: colors.textFaint },
  wordDef: { fontSize: fontSize.body, color: colors.textMuted, lineHeight: 20 },
  card: { backgroundColor: colors.white, borderRadius: radius.xl, borderWidth: 1, borderColor: colors.border, padding: spacing.lg, gap: spacing.sm },
  reasonCard: { backgroundColor: '#fffbeb', borderColor: '#fde68a' },
  exampleCard: { backgroundColor: '#ecfdf5', borderColor: '#a7f3d0' },
  tipCard: { backgroundColor: colors.primaryBg, borderColor: colors.primaryBorder },
  sectionTitle: { fontSize: fontSize.body, fontWeight: '700', color: colors.textStrong },
  sectionTitleAmber: { fontSize: fontSize.body, fontWeight: '700', color: colors.amberText },
  sectionTitleGreen: { fontSize: fontSize.body, fontWeight: '700', color: colors.success },
  sectionTitleIndigo: { fontSize: fontSize.body, fontWeight: '700', color: colors.primaryDeep },
  bodyText: { fontSize: fontSize.body, color: colors.textStrong, lineHeight: 22 },
  quizCard: { backgroundColor: colors.white, borderRadius: radius.xl, borderWidth: 1, borderColor: colors.border, padding: spacing.lg, gap: spacing.md },
  quizTitle: { fontSize: fontSize.body, fontWeight: '600', color: colors.textStrong },
  quizHint: { fontSize: fontSize.body, color: colors.textFaint },
  quizQuestion: { gap: spacing.sm },
  quizStem: { fontSize: fontSize.base, color: colors.text, lineHeight: 24 },
  quizOptions: { flexDirection: 'row', gap: spacing.sm },
  quizOption: {
    flex: 1, minHeight: buttonHeight.lg, borderRadius: radius.xl, borderWidth: 2, borderColor: colors.primaryBorder,
    backgroundColor: colors.white, alignItems: 'center', justifyContent: 'center', paddingHorizontal: spacing.md,
  },
  quizOptionRight: { borderColor: colors.success, backgroundColor: colors.successBg },
  quizOptionWrong: { borderColor: colors.danger, backgroundColor: colors.dangerBg },
  quizOptionText: { fontSize: fontSize.lg, fontWeight: '700', color: colors.text },
  quizOptionTextRight: { color: colors.success },
  quizOptionTextWrong: { color: colors.dangerText },
  quizResult: { fontSize: fontSize.body, fontWeight: '600' },
  textCorrect: { color: colors.success },
  textWrong: { color: colors.dangerText },
  quizExplanation: { fontSize: fontSize.body, color: colors.textMuted, lineHeight: 20 },
  textWarning: { fontSize: fontSize.body, color: colors.warning },
  quizFailRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  retryBtn: { minHeight: buttonHeight.min, paddingHorizontal: spacing.md, borderRadius: radius.lg, backgroundColor: colors.primaryBg, alignItems: 'center', justifyContent: 'center' },
  retryBtnText: { fontSize: fontSize.body, fontWeight: '600', color: colors.primaryDark },
  quizScore: { fontSize: fontSize.body, fontWeight: '600', color: colors.textStrong },
  difficulty: { fontSize: fontSize.body, color: colors.textMuted, textAlign: 'center' },
  footer: {
    paddingHorizontal: spacing.xl, paddingVertical: spacing.md,
    backgroundColor: colors.bgEnd, borderTopWidth: 1, borderTopColor: colors.border, gap: spacing.sm,
  },
  primaryBtn: { minHeight: buttonHeight.xl, borderRadius: radius.xl, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' },
  primaryBtnText: { fontSize: fontSize.base, fontWeight: '700', color: colors.white, letterSpacing: 1 },
  doneBtn: { minHeight: buttonHeight.xl, borderRadius: radius.xl, backgroundColor: colors.white, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' },
  doneBtnText: { fontSize: fontSize.base, fontWeight: '600', color: colors.primaryDark },
  navRow: { flexDirection: 'row', gap: spacing.md },
  navBtn: {
    flex: 1, minHeight: buttonHeight.lg, borderRadius: radius.xl, backgroundColor: colors.white, borderWidth: 1, borderColor: colors.border,
    alignItems: 'center', justifyContent: 'center',
  },
  navBtnDisabled: { opacity: 0.4 },
  navBtnText: { fontSize: fontSize.body, fontWeight: '600', color: colors.textStrong },
  muted: { fontSize: fontSize.body, color: colors.textFaint, textAlign: 'center' },
  error: { fontSize: fontSize.body, color: colors.dangerText, textAlign: 'center', marginBottom: spacing.md },
});
