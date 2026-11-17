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

export default function WordLearning() {
  const { userId } = useLearningContext();
  const { session, hydrated, restored, updateSession } = useLearningSession();
  const { word, loading, error } = useWordData({ initialWordId: session.wordId ?? undefined });
  const singleChar = isSingleCharacter(word);
  const { previous, next, goTo } = useLearningNavigation('word', { skipCharacter: singleChar });

  const tracking = useComprehensiveTracking({
    userId,
    wordId: session.wordId ?? 1,
    moduleType: 'word',
    sessionType: session.reviewMode ? 'review' : 'learning',
    initialLevel: session.vksLevel ?? undefined,
    recommendationId: session.recommendationId ?? undefined,
    ready: hydrated && restored,
  });

  useEffect(() => {
    updateSession({ module: 'word' });
  }, [updateSession]);

  useEffect(() => {
    if (word) updateSession({ wordId: word.id, word: word.hanzi });
  }, [word, updateSession]);

  const handleNavigate = (direction: 'previous' | 'next') => {
    const target = direction === 'previous' ? previous : next;
    if (!target) return;
    tracking.trackEvent('module_navigate', 'word', { direction, to: target.key });
    goTo(target.key);
  };

  const body =
    loading ? (
      <Text style={styles.muted}>Loading the word…</Text>
    ) : error || !word ? (
      <Text style={styles.error}>Couldn’t load the word. Please try again later.</Text>
    ) : (
      <>
        <View style={styles.card}>
          <Text style={styles.wordHanzi}>{word.hanzi}</Text>
          <View style={styles.pinyinRow}>
            <Text style={styles.wordPinyin}>{word.pinyin}</Text>
            <AudioPlayer text={word.hanzi} audioUrl={word.audio || undefined} language="zh-CN" />
          </View>
          <Text style={styles.wordDef}>{word.definition}</Text>
        </View>
        {!singleChar && word.characters.length > 0 && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Characters</Text>
            {word.characters.map((c, i) => (
              <View key={i} style={styles.charRow}>
                <Text style={styles.charHanzi}>{c.character}</Text>
                <View style={styles.charInfo}>
                  <Text style={styles.charPinyin}>{c.pinyin}</Text>
                  <Text style={styles.charDef}>{c.definition}</Text>
                </View>
                <AudioPlayer text={c.character} audioUrl={c.audio || undefined} language="zh-CN" />
              </View>
            ))}
          </View>
        )}
      </>
    );

  const footer = (
    <Pressable style={styles.continueBtn} onPress={() => handleNavigate('next')}>
      <Text style={styles.continueText}>CONTINUE</Text>
    </Pressable>
  );

  return (
    <LearningScreen
      title="Word"
      module="word"
      entry={session.entryModule}
      skipCharacter={singleChar}
      previous={previous}
      next={next}
      onPrevious={() => handleNavigate('previous')}
      onNext={() => handleNavigate('next')}
      onStepSelect={key => {
        tracking.trackEvent('step_progress', 'word', { key });
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
    padding: spacing.xl,
    gap: spacing.sm,
  },
  muted: { fontSize: fontSize.body, color: colors.textFaint, textAlign: 'center', marginTop: spacing['2xl'] },
  error: { fontSize: fontSize.body, color: colors.dangerText, textAlign: 'center', marginTop: spacing['2xl'] },
  wordHanzi: { fontSize: fontSize['2xl'], fontWeight: '800', color: colors.text },
  wordPinyin: { fontSize: fontSize.lg, fontWeight: '600', color: colors.primary },
  pinyinRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  wordDef: { fontSize: fontSize.body, color: colors.textMuted, lineHeight: 22 },
  cardTitle: { fontSize: fontSize.base, fontWeight: '700', color: colors.textStrong, marginBottom: spacing.sm },
  charRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.lg, paddingVertical: spacing.sm },
  charHanzi: { fontSize: fontSize['2xl'], fontWeight: '800', color: colors.text, width: 40, textAlign: 'center' },
  charInfo: { flex: 1, gap: 2 },
  charPinyin: { fontSize: fontSize.body, fontWeight: '600', color: colors.primaryDark },
  charDef: { fontSize: fontSize.body, color: colors.textMuted },
  continueBtn: {
    minHeight: buttonHeight.xl,
    borderRadius: radius.xl,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  continueText: { fontSize: fontSize.base, fontWeight: '700', color: colors.white, letterSpacing: 1 },
});
