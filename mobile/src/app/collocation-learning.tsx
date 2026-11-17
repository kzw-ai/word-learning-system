import { useEffect } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import LearningScreen from '@/components/LearningScreen';
import AudioPlayer from '@/components/AudioPlayer';
import CollocationText from '@/components/CollocationText';
import { useWordData } from '@/hooks/useWordData';
import { useLearningContext } from '@/context/LearningContext';
import { useLearningSession } from '@/context/LearningSessionContext';
import { isSingleCharacter, useLearningNavigation } from '@/hooks/useLearningNavigation';
import { useComprehensiveTracking } from '@/hooks/useTimeTracking';
import { colors, fontSize, radius, buttonHeight, spacing } from '@/theme';

export default function CollocationLearning() {
  const { userId } = useLearningContext();
  const { session, hydrated, restored, updateSession } = useLearningSession();
  const { word, loading, error } = useWordData({ initialWordId: session.wordId ?? undefined });
  const singleChar = isSingleCharacter(word);
  const { previous, next, goTo } = useLearningNavigation('collocation', { skipCharacter: singleChar });

  const tracking = useComprehensiveTracking({
    userId,
    wordId: session.wordId ?? 1,
    moduleType: 'collocation',
    sessionType: session.reviewMode ? 'review' : 'learning',
    initialLevel: session.vksLevel ?? undefined,
    recommendationId: session.recommendationId ?? undefined,
    ready: hydrated && restored,
  });

  useEffect(() => {
    updateSession({ module: 'collocation' });
  }, [updateSession]);

  const handleNavigate = (direction: 'previous' | 'next') => {
    const target = direction === 'previous' ? previous : next;
    if (!target) return;
    tracking.trackEvent('module_navigate', 'collocation', { direction, to: target.key });
    goTo(target.key);
  };

  const body =
    loading ? (
      <Text style={styles.muted}>Loading collocations…</Text>
    ) : error || !word ? (
      <Text style={styles.error}>Couldn’t load the word. Please try again later.</Text>
    ) : word.collocations.length === 0 ? (
      <Text style={styles.muted}>No collocations for this word.</Text>
    ) : (
      <>
        <Text style={styles.intro}>Which words go with this word?</Text>
        {word.collocations.map((c, i) => (
          <View key={i} style={styles.card}>
            <View style={styles.collocationRow}>
              <CollocationText text={c.collocation} target={word.hanzi || word.pinyin} style={styles.collocation} />
              <AudioPlayer text={c.collocation.replace(/（[^）]*）/g, '')} audioUrl={c.audio || undefined} language="zh-CN" />
            </View>
            <Text style={styles.translation}>{c.translation}</Text>
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
      title="Collocations"
      module="collocation"
      entry={session.entryModule}
      skipCharacter={singleChar}
      previous={previous}
      next={next}
      onPrevious={() => handleNavigate('previous')}
      onNext={() => handleNavigate('next')}
      onStepSelect={key => {
        tracking.trackEvent('step_progress', 'collocation', { key });
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
    gap: spacing.xs,
  },
  intro: { fontSize: fontSize.base, fontWeight: '600', color: colors.textStrong },
  muted: { fontSize: fontSize.body, color: colors.textFaint, textAlign: 'center', marginTop: spacing['2xl'] },
  error: { fontSize: fontSize.body, color: colors.dangerText, textAlign: 'center', marginTop: spacing['2xl'] },
  collocation: { fontSize: fontSize.lg, fontWeight: '700', color: colors.text, flex: 1 },
  collocationRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
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
