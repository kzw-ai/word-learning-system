// 源文件：components/learning/StepProgress.tsx（网页版）。RN 版：Tailwind → StyleSheet + theme。
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { colors, fontSize } from '@/theme';

const STEPS = [
  { key: 'character', label: 'Chars' },
  { key: 'word', label: 'Word' },
  { key: 'collocation', label: 'Phrases' },
  { key: 'sentence', label: 'Sentence' },
  { key: 'exercise', label: 'Practice' },
] as const;

interface StepProgressProps {
  /** 当前所在步骤 */
  current: string;
  /** 本轮从哪一步进入，之前的步骤显示为「跳过」 */
  entry?: string | null;
  /** 单字词跳过字页 */
  skipCharacter?: boolean;
  /** 点一格跳到那一步 */
  onSelect?: (key: string) => void;
}

export default function StepProgress({ current, entry, skipCharacter = false, onSelect }: StepProgressProps) {
  const currentIndex = STEPS.findIndex(step => step.key === current);
  const entryIndex = Math.max(0, STEPS.findIndex(step => step.key === entry));
  const startIndex = Math.min(entryIndex, Math.max(currentIndex, 0));

  return (
    <View style={styles.row} accessibilityLabel="Learning steps">
      {STEPS.map((step, index) => {
        const skipped = index < startIndex || (skipCharacter && step.key === 'character');
        const done = !skipped && index >= startIndex && index < currentIndex;
        const active = index === currentIndex;
        const state = active ? 'current' : done ? 'done' : skipped ? 'skipped' : 'not started';

        const labelColor = active
          ? colors.primaryDeep
          : done
            ? colors.primary
            : skipped
              ? colors.textFaint
              : colors.textMuted;
        const labelWeight = active || done || !skipped ? '600' : '400';
        const barColor = active ? colors.primary : done ? '#a5b4fc' : skipped ? '#f1f5f9' : '#e2e8f0';

        const content = (
          <>
            <Text style={[styles.label, { color: labelColor, fontWeight: labelWeight }]}>{step.label}</Text>
            <View style={[styles.bar, { backgroundColor: barColor }]} />
          </>
        );

        const selectable = onSelect && !active && !(skipCharacter && step.key === 'character');
        return (
          <View key={step.key} style={styles.step}>
            {selectable ? (
              <Pressable
                style={styles.stepBox}
                onPress={() => onSelect(step.key)}
                accessibilityLabel={`${step.label}: ${state}. Go to this step`}
              >
                {content}
              </Pressable>
            ) : (
              <View style={styles.stepBox} accessibilityLabel={`${step.label}: ${state}`}>
                {content}
              </View>
            )}
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', gap: 4 },
  step: { flex: 1 },
  stepBox: {
    minHeight: 36,
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    borderRadius: 8,
  },
  label: { fontSize: fontSize.body, lineHeight: 20 },
  bar: { height: 4, width: '100%', borderRadius: 999 },
});
