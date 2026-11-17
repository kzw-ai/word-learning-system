import { useEffect } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import LearningScreen from '@/components/LearningScreen';
import StrokeOrderAnimation from '@/components/StrokeOrderAnimation';
import AudioPlayer from '@/components/AudioPlayer';
import { useWordData } from '@/hooks/useWordData';
import { useLearningContext } from '@/context/LearningContext';
import { useLearningSession } from '@/context/LearningSessionContext';
import { isSingleCharacter, useLearningNavigation } from '@/hooks/useLearningNavigation';
import { useComprehensiveTracking } from '@/hooks/useTimeTracking';
import { colors, fontSize, radius, buttonHeight, spacing } from '@/theme';

export default function CharacterLearning() {
  const { userId } = useLearningContext();
  const { session, hydrated, restored, updateSession } = useLearningSession();
  const { word, loading, error } = useWordData({ initialWordId: session.wordId ?? undefined });
  const singleChar = isSingleCharacter(word);
  const { previous, next, goTo } = useLearningNavigation('character', { skipCharacter: singleChar });

  const tracking = useComprehensiveTracking({
    userId,
    wordId: session.wordId ?? 1,
    moduleType: 'character',
    sessionType: session.reviewMode ? 'review' : 'learning',
    initialLevel: session.vksLevel ?? undefined,
    recommendationId: session.recommendationId ?? undefined,
    ready: hydrated && restored,
  });

  useEffect(() => {
    updateSession({ module: 'character' });
  }, [updateSession]);

  const handleNavigate = (direction: 'previous' | 'next') => {
    const target = direction === 'previous' ? previous : next;
    if (!target) return;
    tracking.trackEvent('module_navigate', 'character', { direction, to: target.key });
    goTo(target.key);
  };

  const body =
    loading ? (
      <Text style={styles.muted}>Loading characters…</Text>
    ) : error || !word ? (
      <Text style={styles.error}>Couldn’t load the word. Please try again later.</Text>
    ) : (
      <>
        <Text style={styles.intro}>Watch how to write each character.</Text>
        {word.characters.map((c, i) => (
          <View key={i} style={styles.card}>
            <StrokeOrderAnimation character={c.character} size={150} />
            <View style={styles.charHanziRow}>
              <Text style={styles.charHanzi}>{c.character}</Text>
              <AudioPlayer text={c.character} audioUrl={c.audio || undefined} language="zh-CN" />
            </View>
            <Text style={styles.charPinyin}>{c.pinyin}</Text>
            <Text style={styles.charDef}>{c.definition}</Text>
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
      title="Characters"
      module="character"
      entry={session.entryModule}
      skipCharacter={singleChar}
      previous={previous}
      next={next}
      onPrevious={() => handleNavigate('previous')}
      onNext={() => handleNavigate('next')}
      onStepSelect={key => {
        tracking.trackEvent('step_progress', 'character', { key });
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
    borderRadius: radius['3xl'],
    borderWidth: 1,
    borderColor: colors.primaryBorder,
    padding: spacing.lg,
    alignItems: 'center',
    gap: spacing.sm,
  },
  intro: { fontSize: fontSize.base, fontWeight: '600', color: colors.textStrong },
  muted: { fontSize: fontSize.body, color: colors.textFaint, textAlign: 'center', marginTop: spacing['2xl'] },
  error: { fontSize: fontSize.body, color: colors.dangerText, textAlign: 'center', marginTop: spacing['2xl'] },
  charHanzi: { fontSize: fontSize['2xl'], fontWeight: '800', color: colors.text },
  charHanziRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  charPinyin: { fontSize: fontSize.base, fontWeight: '600', color: colors.primary },
  charDef: { fontSize: fontSize.body, color: colors.textMuted, lineHeight: 22, textAlign: 'center' },
  continueBtn: {
    minHeight: buttonHeight.xl,
    borderRadius: radius.xl,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  continueText: { fontSize: fontSize.base, fontWeight: '700', color: colors.white, letterSpacing: 1 },
});
