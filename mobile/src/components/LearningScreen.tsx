import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import StepProgress from './StepProgress';
import { colors, fontSize, buttonHeight, radius, spacing } from '@/theme';

interface LearningScreenProps {
  title: string;
  module: string;
  entry?: string | null;
  skipCharacter?: boolean;
  previous?: { label: string } | null;
  next?: { label: string } | null;
  onPrevious?: () => void;
  onNext?: () => void;
  onStepSelect?: (key: string) => void;
  children: React.ReactNode;
  footer: React.ReactNode;
}

/** 学习链路（字/词/搭配/例句）的共用骨架：顶栏 + 步骤进度 + 滚动内容 + 底部按钮。 */
export default function LearningScreen({
  title,
  module,
  entry,
  skipCharacter = false,
  previous,
  next,
  onPrevious,
  onNext,
  onStepSelect,
  children,
  footer,
}: LearningScreenProps) {
  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Pressable
          style={[styles.navBtn, !previous && styles.navBtnDisabled]}
          onPress={onPrevious}
          disabled={!previous}
        >
          <Text style={styles.navText}>← {previous ? previous.label : 'Back'}</Text>
        </Pressable>
        <Text style={styles.title}>{title}</Text>
        <Pressable
          style={[styles.navBtn, !next && styles.navBtnDisabled]}
          onPress={onNext}
          disabled={!next}
        >
          <Text style={styles.navText}>{next ? `${next.label} →` : 'Finish →'}</Text>
        </Pressable>
      </View>

      <View style={styles.steps}>
        <StepProgress current={module} entry={entry} skipCharacter={skipCharacter} onSelect={onStepSelect} />
      </View>

      <ScrollView style={styles.content} contentContainerStyle={styles.contentInner}>
        {children}
      </ScrollView>

      <View style={styles.footer}>{footer}</View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bgStart },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  navBtn: {
    minHeight: buttonHeight.min,
    paddingHorizontal: spacing.md,
    borderRadius: radius.lg,
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  navBtnDisabled: { opacity: 0.4 },
  navText: { fontSize: fontSize.body, fontWeight: '600', color: colors.primaryDark },
  title: { fontSize: fontSize.xl, fontWeight: '800', color: colors.text },
  steps: { paddingHorizontal: spacing.xl, marginTop: spacing.md },
  content: { flex: 1 },
  contentInner: { paddingHorizontal: spacing.xl, paddingVertical: spacing.lg, gap: spacing.lg },
  footer: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
    backgroundColor: colors.bgEnd,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
});
