import { useEffect } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import LearningScreen from '@/components/LearningScreen';
import AudioPlayer from '@/components/AudioPlayer';
import { useWordData } from '@/hooks/useWordData';
import { useLearningContext } from '@/context/LearningContext';
import { useLearningSession } from '@/context/LearningSessionContext';
import { isSingleCharacter, useLearningNavigation } from '@/hooks/useLearningNavigation';
import { useComprehensiveTracking } from '@/hooks/useTimeTracking';
import { colors, fontSize, radius, buttonHeight, spacing } from '@/theme';

export default function SentenceLearning() {
  const { userId } = useLearningContext();
  const { session, hydrated, restored, updateSession } = useLearningSession();
  const { word, loading, error } = useWordData({ initialWordId: session.wordId ?? undefined });
  const singleChar = isSingleCharacter(word);
  const { previous, next, goTo } = useLearningNavigation('sentence', { skipCharacter: singleChar });

  const tracking = useComprehensiveTracking({
    userId,
    wordId: session.wordId ?? 1,
    moduleType: 'sentence',
    sessionType: session.reviewMode ? 'review' : 'learning',
    initialLevel: session.vksLevel ?? undefined,
    recommendationId: session.recommendationId ?? undefined,
    ready: hydrated && restored,
  });

  useEffect(() => {
    updateSession({ module: 'sentence' });
  }, [updateSession]);

  const handleNavigate = (direction: 'previous' | 'next') => {
    const target = direction === 'previous' ? previous : next;
    if (!target) return;
    tracking.trackEvent('module_navigate', 'sentence', { direction, to: target.key });
    goTo(target.key);
  };

  const body =
    loading ? (
      <Text style={styles.muted}>Loading sentences…</Text>
    ) : error || !word ? (
      <Text style={styles.error}>Couldn’t load the word. Please try again later.</Text>
    ) : word.examples.length === 0 ? (
      <Text style={styles.muted}>No example sentences for this word.</Text>
    ) : (
      <>
        <Text style={styles.intro}>See this word in sentences.</Text>
        {word.examples.map((e, i) => (
          <View key={i} style={styles.card}>
            <View style={styles.sentenceRow}>
              <Text style={styles.sentence}>{e.sentence}</Text>
              <AudioPlayer text={e.sentence} audioUrl={e.audio || undefined} language="zh-CN" />
            </View>
            {e.pinyin ? <Text style={styles.pinyin}>{e.pinyin}</Text> : null}
            {e.translation ? <Text style={styles.translation}>{e.translation}</Text> : null}
          </View>
        ))}
      </>
    );

  const footer = (
    <Pressable style={styles.continueBtn} onPress={() => handleNavigate('next')}>
      <Text style={styles.continueText}>CONTINUE</Text>
    </Pressable>
  );

  return (
    <LearningScreen
      title="Sentences"
      module="sentence"
      entry={session.entryModule}
      skipCharacter={singleChar}
      previous={previous}
      next={next}
      onPrevious={() => handleNavigate('previous')}
      onNext={() => handleNavigate('next')}
      onStepSelect={key => {
        tracking.trackEvent('step_progress', 'sentence', { key });
        goTo(key);
      }}
      footer={footer}
    >
      {body}
    </LearningScreen>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.white,
    borderRadius: radius.xl,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  intro: { fontSize: fontSize.base, fontWeight: '600', color: colors.textStrong },
  muted: { fontSize: fontSize.body, color: colors.textFaint, textAlign: 'center', marginTop: spacing['2xl'] },
  error: { fontSize: fontSize.body, color: colors.dangerText, textAlign: 'center', marginTop: spacing['2xl'] },
  sentence: { fontSize: fontSize.lg, fontWeight: '700', color: colors.text, lineHeight: 26, flex: 1 },
  sentenceRow: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
  pinyin: { fontSize: fontSize.body, color: colors.primaryDark, lineHeight: 20 },
  translation: { fontSize: fontSize.body, color: colors.textMuted, lineHeight: 22 },
  continueBtn: {
    minHeight: buttonHeight.xl,
    borderRadius: radius.xl,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  continueText: { fontSize: fontSize.base, fontWeight: '700', color: colors.white, letterSpacing: 1 },
});
