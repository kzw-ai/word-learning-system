import { router } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { saveHskLevel } from '@/lib/apiClient';
import { useLearningContext } from '@/context/LearningContext';
import { useLearningSession } from '@/context/LearningSessionContext';
import { colors, fontSize, radius, buttonHeight, spacing } from '@/theme';

type Level = 3 | 4;

const LEVELS: { level: Level; words: number; example: { chars: string; pinyin: string; meaning: string } }[] = [
  { level: 3, words: 300, example: { chars: '礼物', pinyin: 'lǐwù', meaning: 'gift; present' } },
  { level: 4, words: 600, example: { chars: '师傅', pinyin: 'shīfu', meaning: 'master; qualified worker' } },
];

export default function HomeScreen() {
  const { userId } = useLearningContext();
  const { hydrated, session } = useLearningSession();
  const [level, setLevel] = useState<Level>(4);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);

  const levelInfo = LEVELS.find(l => l.level === level)!;
  const returning = Boolean(session.wordId);

  const chooseLevel = (next: Level) => {
    setLevel(next);
    setError(false);
  };

  const handleStart = async () => {
    if (!userId) return;
    setSaving(true);
    setError(false);
    try {
      await saveHskLevel(userId, level);
      router.push('/word-learning-entrance');
    } catch {
      setError(true);
    } finally {
      setSaving(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.appName}>Word Learning</Text>
        </View>

        <View style={styles.hero}>
          <Text style={styles.title}>
            {returning ? 'Welcome back' : `Learn the ${levelInfo.words} HSK ${level} words`}
          </Text>
          <Text style={styles.subtitle}>
            {returning
              ? 'Continue learning HSK words.'
              : 'Characters, the word, its phrases and sentences, then practice.'}
          </Text>
        </View>

        {error && (
          <Text style={styles.error} role="alert">
            Couldn’t save your level. Check your connection and try again.
          </Text>
        )}

        <View style={styles.levelBlock}>
          <Text style={styles.sectionLabel}>Your level</Text>
          <View style={styles.levelRow}>
            {LEVELS.map(({ level: l, words }) => {
              const active = level === l;
              return (
                <Pressable
                  key={l}
                  style={[styles.levelBtn, active && styles.levelBtnActive]}
                  onPress={() => chooseLevel(l)}
                  accessibilityRole="radio"
                  accessibilityState={{ selected: active }}
                >
                  <Text style={[styles.levelTitle, active && styles.levelTitleActive]}>HSK {l}</Text>
                  <Text style={[styles.levelWords, active && styles.levelWordsActive]}> · {words} words</Text>
                </Pressable>
              );
            })}
          </View>
        </View>

        <Pressable
          style={[styles.startBtn, (saving || !hydrated) && styles.startBtnDisabled]}
          onPress={handleStart}
          disabled={saving || !hydrated}
        >
          {saving ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.startText}>{returning ? 'Continue learning' : 'Start my first word'}</Text>
          )}
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bgStart },
  container: { flex: 1, paddingHorizontal: 20, paddingVertical: spacing.lg, gap: spacing.lg },
  header: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  appName: { fontSize: fontSize.base, fontWeight: '800', color: colors.text },
  hero: { gap: spacing.xs },
  title: { fontSize: fontSize['2xl'], fontWeight: '800', color: colors.text, lineHeight: 32 },
  subtitle: { fontSize: fontSize.body, color: colors.textMuted },
  error: { fontSize: fontSize.body, color: colors.dangerText },
  levelBlock: { gap: spacing.sm },
  sectionLabel: { fontSize: fontSize.body, fontWeight: '600', color: colors.textMuted },
  levelRow: { flexDirection: 'row', gap: spacing.sm },
  levelBtn: {
    flex: 1,
    minHeight: buttonHeight.lg,
    borderRadius: radius.xl,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.white,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  levelBtnActive: {
    backgroundColor: colors.primaryBg,
    borderColor: colors.primary,
  },
  levelTitle: { fontSize: fontSize.base, fontWeight: '700', color: colors.text },
  levelTitleActive: { color: colors.primaryDeep },
  levelWords: { fontSize: fontSize.body, fontWeight: '500', color: colors.textMuted },
  levelWordsActive: { color: colors.primaryDeep },
  startBtn: {
    marginTop: 'auto',
    minHeight: buttonHeight.xl,
    borderRadius: radius.xl,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  startBtnDisabled: { backgroundColor: colors.border },
  startText: { fontSize: fontSize.base, fontWeight: '700', color: colors.white, letterSpacing: 1 },
});
