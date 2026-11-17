import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, BackHandler, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { fetchWordExercises } from '@/lib/apiClient';
import { parseFillHint, completeSentence } from '@/lib/fillHint';
import { gradeHandwriting, type Stroke } from '@/lib/handwriting';
import { loadCharacterData } from '@/lib/strokeData';
import type { ExerciseQuestionPayload } from '@/lib/types';
import HandwritingPad, { HandwritingThumb } from '@/components/HandwritingPad';
import StrokeOrderAnimation from '@/components/StrokeOrderAnimation';
import { useLearningContext } from '@/context/LearningContext';
import { afterWordRoute, useLearningSession } from '@/context/LearningSessionContext';
import { useComprehensiveTracking } from '@/hooks/useTimeTracking';
import { useWordData } from '@/hooks/useWordData';
import { colors, fontSize, radius, buttonHeight, spacing } from '@/theme';

const DEFAULT_WORD_ID = 1;
const DEFAULT_WORD_NAME = '发生';

type ExerciseQuestion = ExerciseQuestionPayload;

/** 归一化作答后再比对：去首尾空白、全角转半角、英文统一小写。 */
const normaliseAnswer = (value: string): string =>
  value
    .trim()
    .replace(/[！-～]/g, ch => String.fromCharCode(ch.charCodeAt(0) - 0xfee0))
    .replace(/　/g, ' ')
    .toLowerCase();

const getQuestionTitle = (q: ExerciseQuestion) => {
  switch (q.type) {
    case 'definition':
      return 'Choose the word that matches the meaning.';
    case 'collocation':
      return q.gloss ? 'Choose the word that makes this phrase.' : 'Choose the word that fits the blank.';
    case 'choose_word':
      return 'Choose the right word.';
    case 'fill_word':
      return 'Write the missing character of the word you just learned.';
    default:
      return 'Practice';
  }
};

export default function Exercise() {
  const { userId } = useLearningContext();
  const { session, hydrated, restored, updateSession } = useLearningSession();
  const wordId = session.wordId ?? DEFAULT_WORD_ID;
  const wordLabel = session.word ?? DEFAULT_WORD_NAME;
  const { word } = useWordData({ initialWordId: wordId });

  // 安卓返回键回首页（同 LearningScreen）
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      router.replace('/');
      return true;
    });
    return () => sub.remove();
  }, []);

  const [questions, setQuestions] = useState<ExerciseQuestion[]>([]);
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState('');
  const [fillAnswer, setFillAnswer] = useState('');
  const [fillMode, setFillMode] = useState<'write' | 'type'>('write');
  const [handStrokes, setHandStrokes] = useState<Stroke[]>([]);
  const [writing, setWriting] = useState(false);
  const [showFeedback, setShowFeedback] = useState(false);
  const [isCorrect, setIsCorrect] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const current = questions[index] ?? null;
  const fillHint = current?.type === 'fill_word' ? parseFillHint(current.question) : null;
  const isFill = current?.type === 'fill_word';
  const isWriting = isFill && fillMode === 'write';

  const tracking = useComprehensiveTracking({
    userId,
    wordId,
    moduleType: 'exercise',
    sessionType: 'exercise',
    initialLevel: session.wordId === wordId ? session.vksLevel ?? undefined : undefined,
    recommendationId: session.wordId === wordId ? session.recommendationId ?? undefined : undefined,
    ready: hydrated && restored && questions.length > 0,
  });

  useEffect(() => {
    if (!hydrated) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchWordExercises(wordId, { limit: 5, options: 4 })
      .then(data => {
        if (cancelled) return;
        setQuestions(data.questions);
        updateSession({ wordId: data.wordId, word: data.word ?? wordLabel, module: 'exercise' });
      })
      .catch(err => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load the exercises');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [hydrated, wordId]);

  // 切题时重置作答状态并计时
  useEffect(() => {
    if (!questions.length) return;
    setSelected('');
    setFillAnswer('');
    setHandStrokes([]);
    setShowFeedback(false);
    setIsCorrect(false);
    tracking.exerciseTimer.startTimer();
  }, [index, questions.length]);

  const hasAnswer = isFill ? (isWriting ? handStrokes.length > 0 : fillAnswer.trim().length > 0) : selected.length > 0;

  const handleSubmit = async () => {
    if (!current || !hasAnswer) return;
    const startTime = tracking.exerciseTimer.startTime;
    const endTime = new Date();

    let correct = false;
    let userAnswer = '';
    let handwriting: ReturnType<typeof gradeHandwriting> | null = null;

    if (isFill) {
      if (isWriting) {
        // 手写：按笔画和答案字的标准笔画配对判分（不限笔顺）
        const data = await loadCharacterData(current.correctAnswer).catch(() => null);
        if (!data) {
          // 取不到笔画数据：回退打字作答
          setFillMode('type');
          return;
        }
        handwriting = gradeHandwriting(handStrokes, data);
        const alsoCorrect = current.options ?? [];
        for (const alt of alsoCorrect) {
          if (handwriting.correct) break;
          const altData = await loadCharacterData(alt).catch(() => null);
          const altResult = altData && gradeHandwriting(handStrokes, altData);
          if (altResult?.correct) handwriting = altResult;
        }
        correct = handwriting.correct;
        userAnswer = correct
          ? current.correctAnswer
          : `[handwriting ${handwriting.matched}/${handwriting.expected} strokes, ${handwriting.extra} extra]`;
      } else {
        userAnswer = fillAnswer.trim();
        const alsoCorrect = current.options ?? [];
        correct = [current.correctAnswer, ...alsoCorrect].some(a => normaliseAnswer(userAnswer) === normaliseAnswer(a));
      }
    } else {
      userAnswer = selected;
      correct = selected === current.correctAnswer;
    }

    tracking.exerciseTimer.submitAnswer();
    await tracking.trackExercise({
      questionId: current.id,
      questionType: current.type,
      questionContent: current.question,
      userAnswer,
      correctAnswer: current.correctAnswer,
      isCorrect: correct,
      startTime: startTime ?? new Date(),
      endTime,
      hesitationCount: tracking.exerciseTimer.hesitationCount,
      confidenceLevel: tracking.exerciseTimer.hesitationCount === 0 ? 5 : Math.max(1, 5 - tracking.exerciseTimer.hesitationCount),
      attemptCount: 1,
    });

    setIsCorrect(correct);
    setShowFeedback(true);
    tracking.trackEvent('exercise_submit', 'exercise', { questionId: current.id, isCorrect: correct });
  };

  const handleContinue = async () => {
    if (index < questions.length - 1) {
      setIndex(index + 1);
    } else {
      await tracking.endSession(true);
      // 学完去学习看板；复习模式回今日复习
      router.replace(afterWordRoute(session) as any);
    }
  };

  const handleDone = () => {
    router.replace(afterWordRoute(session) as any);
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.center}>
        <ActivityIndicator color={colors.primary} />
        <Text style={styles.muted}>Loading the exercises…</Text>
      </SafeAreaView>
    );
  }

  if (error) {
    return (
      <SafeAreaView style={styles.center}>
        <Text style={styles.error}>❌ {error}</Text>
        <Pressable style={styles.primaryBtn} onPress={() => router.back()}>
          <Text style={styles.primaryBtnText}>Back</Text>
        </Pressable>
      </SafeAreaView>
    );
  }

  if (!current) {
    return (
      <SafeAreaView style={styles.center}>
        <Text style={styles.muted}>No exercises available</Text>
        <Pressable style={styles.primaryBtn} onPress={handleDone}>
          <Text style={styles.primaryBtnText}>Back to home</Text>
        </Pressable>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Practice</Text>
        <Text style={styles.counter}>
          {index + 1} / {questions.length}
        </Text>
      </View>

      <ScrollView style={styles.content} contentContainerStyle={styles.contentInner} keyboardShouldPersistTaps="handled" scrollEnabled={!writing}>
        <View style={styles.card}>
          <Text style={styles.questionTitle}>{getQuestionTitle(current)}</Text>
          <Text style={styles.questionStem}>{fillHint ? fillHint.stem : current.question}</Text>
          {current.type === 'collocation' && current.gloss ? (
            <Text style={styles.gloss}>{current.gloss}</Text>
          ) : null}
          {fillHint?.hint ? (
            <Text style={styles.hint}>
              Hint: the pinyin {fillHint.initialOnly ? 'starts with' : 'is'}{' '}
              <Text style={styles.hintStrong}>“{fillHint.hint}”</Text>
            </Text>
          ) : null}
        </View>

        {isFill && isWriting ? (
          <View style={styles.writeArea}>
            {!showFeedback && (
              <>
                <HandwritingPad
                  strokes={handStrokes}
                  onChange={setHandStrokes}
                  disabled={showFeedback}
                  result={showFeedback ? (isCorrect ? 'correct' : 'wrong') : null}
                  onWritingChange={setWriting}
                />
                <View style={styles.writeTools}>
                  <Pressable style={styles.toolBtn} onPress={() => setHandStrokes(handStrokes.slice(0, -1))} disabled={handStrokes.length === 0}>
                    <Text style={styles.toolText}>Undo</Text>
                  </Pressable>
                  <Pressable style={styles.toolBtn} onPress={() => setHandStrokes([])} disabled={handStrokes.length === 0}>
                    <Text style={styles.toolText}>Clear</Text>
                  </Pressable>
                  <Pressable style={[styles.toolBtn, styles.toolBtnPrimary]} onPress={() => setFillMode('type')}>
                    <Text style={[styles.toolText, styles.toolTextPrimary]}>Type instead</Text>
                  </Pressable>
                </View>
              </>
            )}
          </View>
        ) : isFill ? (
          <View style={styles.writeArea}>
            {!showFeedback && (
              <>
                <TextInput
                  style={[styles.fillInput, showFeedback && (isCorrect ? styles.inputCorrect : styles.inputWrong)]}
                  value={fillAnswer}
                  onChangeText={setFillAnswer}
                  editable={!showFeedback}
                  placeholder="Type here"
                  autoCapitalize="none"
                  autoCorrect={false}
                  returnKeyType="done"
                  onSubmitEditing={handleSubmit}
                />
                <Pressable style={[styles.toolBtn, styles.toolBtnPrimary, styles.toolBtnCenter]} onPress={() => setFillMode('write')}>
                  <Text style={[styles.toolText, styles.toolTextPrimary]}>Write instead</Text>
                </Pressable>
              </>
            )}
          </View>
        ) : (
          <View style={styles.options}>
            {current.options.map((option, i) => {
              const letter = String.fromCharCode(65 + i);
              const isSelected = selected === option;
              const showCorrect = showFeedback && option === current.correctAnswer;
              const showWrong = showFeedback && isSelected && option !== current.correctAnswer;
              const faded = showFeedback && !showCorrect && !isSelected;
              return (
                <Pressable
                  key={i}
                  style={[
                    styles.option,
                    isSelected && !showFeedback && styles.optionSelected,
                    showCorrect && styles.optionCorrect,
                    showWrong && styles.optionWrong,
                    faded && styles.optionFaded,
                  ]}
                  onPress={() => !showFeedback && setSelected(option)}
                  disabled={showFeedback}
                >
                  <Text style={[styles.optionLetter, showCorrect && styles.optionTextLight]}>{letter}.</Text>
                  <Text style={[styles.optionText, showCorrect && styles.optionTextLight]}>{option}</Text>
                  {showCorrect && <Text style={styles.optionTextLight}>✓</Text>}
                  {showWrong && <Text style={styles.optionTextLight}>✗</Text>}
                </Pressable>
              );
            })}
          </View>
        )}

        {showFeedback && (
          <View style={[styles.feedback, isCorrect ? styles.feedbackCorrect : styles.feedbackWrong]}>
            <Text style={[styles.feedbackTitle, isCorrect ? styles.textCorrect : styles.textWrong]}>
              {isCorrect ? '✓ Excellent!' : '✗ Incorrect'}
            </Text>
            {!isCorrect && (
              <Text style={styles.feedbackAnswer}>
                Correct answer: {isFill ? current.correctAnswer : `${String.fromCharCode(65 + current.options.indexOf(current.correctAnswer))}. ${current.correctAnswer}`}
              </Text>
            )}
            {isFill && fillHint && (
              <Text style={styles.feedbackSentence}>{completeSentence(fillHint.stem, current.correctAnswer)}</Text>
            )}
            {/* 字 + 拼音 + 释义（网页版反馈卡同款；释义题的题干就是这句释义，不重复） */}
            {word && (
              <Text style={styles.feedbackWordInfo}>
                <Text style={styles.feedbackWordLabel}>{wordLabel}</Text> {word.pinyin}
                {current.type !== 'definition' && (
                  <Text style={styles.feedbackWordDef}> · {word.definition}</Text>
                )}
              </Text>
            )}
            {/* 填字题：自己写的字和标准写法（笔顺动画）并排对照 */}
            {isFill && (
              <View style={styles.compareRow}>
                {isWriting && handStrokes.length > 0 && (
                  <View style={styles.compareItem}>
                    <HandwritingThumb strokes={handStrokes} size={88} result={isCorrect ? 'correct' : 'wrong'} />
                    <Text style={styles.compareLabel}>Your writing</Text>
                  </View>
                )}
                <View style={styles.compareItem}>
                  <StrokeOrderAnimation character={current.correctAnswer} size={88} />
                </View>
              </View>
            )}
          </View>
        )}
      </ScrollView>

      <View style={styles.footer}>
        {!showFeedback ? (
          <Pressable
            style={[styles.primaryBtn, !hasAnswer && styles.primaryBtnDisabled]}
            onPress={handleSubmit}
            disabled={!hasAnswer}
          >
            <Text style={styles.primaryBtnText}>CHECK</Text>
          </Pressable>
        ) : (
          <Pressable style={styles.primaryBtn} onPress={handleContinue}>
            <Text style={styles.primaryBtnText}>CONTINUE</Text>
          </Pressable>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bgStart },
  center: {
    flex: 1,
    backgroundColor: colors.bgStart,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.md,
    paddingHorizontal: spacing.xl,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.lg,
  },
  headerTitle: { fontSize: fontSize.xl, fontWeight: '800', color: colors.text },
  counter: { fontSize: fontSize.body, fontWeight: '600', color: colors.textFaint },
  content: { flex: 1 },
  contentInner: { paddingHorizontal: spacing.xl, paddingBottom: spacing.xl, gap: spacing.lg },
  card: {
    backgroundColor: colors.white,
    borderRadius: radius.xl,
    borderWidth: 1,
    borderColor: colors.primaryBorder,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  questionTitle: { fontSize: fontSize.body, fontWeight: '600', color: colors.primary },
  questionStem: { fontSize: fontSize.lg, fontWeight: '700', color: colors.text, lineHeight: 26 },
  gloss: { fontSize: fontSize.body, color: colors.textMuted },
  hint: { fontSize: fontSize.body, color: colors.textMuted },
  hintStrong: { fontWeight: '700', color: colors.primaryDark },
  options: { gap: spacing.md },
  option: {
    minHeight: buttonHeight.lg,
    borderRadius: radius.xl,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.white,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  optionSelected: { backgroundColor: colors.primaryBg, borderColor: colors.primary },
  optionCorrect: { backgroundColor: colors.success, borderColor: colors.success },
  optionWrong: { backgroundColor: colors.dangerBg, borderColor: colors.danger },
  optionFaded: { opacity: 0.5 },
  optionLetter: { fontSize: fontSize.base, fontWeight: '700', color: colors.primary },
  optionText: { flex: 1, fontSize: fontSize.base, fontWeight: '600', color: colors.text },
  optionTextLight: { color: colors.white },
  writeArea: { alignItems: 'center', gap: spacing.md },
  writeTools: { flexDirection: 'row', gap: spacing.sm },
  toolBtn: {
    minHeight: buttonHeight.min,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.white,
    alignItems: 'center',
    justifyContent: 'center',
  },
  toolBtnPrimary: { backgroundColor: colors.primaryBg, borderColor: colors.primaryBorder },
  toolBtnCenter: { alignSelf: 'center' },
  toolText: { fontSize: fontSize.body, fontWeight: '600', color: colors.textStrong },
  toolTextPrimary: { color: colors.primaryDark },
  fillInput: {
    minHeight: 64,
    width: 200,
    borderRadius: radius.xl,
    borderWidth: 2,
    borderColor: colors.primaryBorder,
    backgroundColor: colors.white,
    textAlign: 'center',
    fontSize: fontSize['3xl'],
    fontWeight: '700',
    color: colors.text,
  },
  inputCorrect: { borderColor: colors.success, backgroundColor: colors.successBg, color: colors.success },
  inputWrong: { borderColor: colors.danger, backgroundColor: colors.dangerBg, color: colors.dangerText },
  feedback: { borderRadius: radius.xl, padding: spacing.lg, gap: spacing.sm },
  feedbackCorrect: { backgroundColor: colors.successBg, borderWidth: 1, borderColor: colors.successBorder },
  feedbackWrong: { backgroundColor: colors.dangerBg, borderWidth: 1, borderColor: colors.dangerBorder },
  feedbackTitle: { fontSize: fontSize.lg, fontWeight: '800' },
  textCorrect: { color: colors.success },
  textWrong: { color: colors.dangerText },
  feedbackAnswer: { fontSize: fontSize.base, fontWeight: '700', color: colors.dangerText },
  feedbackSentence: { fontSize: fontSize.base, fontWeight: '600', color: colors.textStrong },
  feedbackWordInfo: { fontSize: fontSize.base, fontWeight: '500', color: colors.textStrong },
  feedbackWordLabel: { fontWeight: '700', color: colors.primaryDark },
  feedbackWordDef: { color: colors.textMuted },
  compareRow: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.lg, marginTop: spacing.sm },
  compareItem: { alignItems: 'center', gap: spacing.xs },
  compareLabel: { fontSize: fontSize.body, fontWeight: '500', color: colors.textStrong },
  footer: {
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    backgroundColor: colors.bgEnd,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  primaryBtn: {
    minHeight: buttonHeight.xl,
    borderRadius: radius.xl,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryBtnDisabled: { backgroundColor: colors.border },
  primaryBtnText: { fontSize: fontSize.base, fontWeight: '700', color: colors.white, letterSpacing: 1 },
  muted: { fontSize: fontSize.body, color: colors.textFaint },
  error: { fontSize: fontSize.body, color: colors.dangerText, textAlign: 'center' },
});
