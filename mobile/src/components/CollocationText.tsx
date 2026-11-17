// 源文件：components/CollocationText.tsx（网页版）
import { Fragment, type ReactNode } from 'react';
import { StyleSheet, Text, type TextStyle } from 'react-native';
import { colors } from '@/theme';

const LEVEL_MARK = /（([^）]*)）/;

/**
 * 渲染一条搭配：目标词就地高亮，「（三级）」这类等级标注显示为它原本位置上的小标签。
 * 目标词在等级标注之前时（「重视 文化（三级）」）也只显示一次。
 */
export default function CollocationText({ text, target, style }: { text: string; target: string; style?: TextStyle }) {
  // split 带捕获组：偶数位是正文，奇数位是等级
  const pieces = text.split(LEVEL_MARK);
  const hasTarget = Boolean(target) && text.includes(target);
  const nodes: ReactNode[] = [];

  pieces.forEach((piece, i) => {
    if (i % 2 === 1) {
      nodes.push(
        <Text key={`level-${i}`} style={styles.level}>
          {` (${piece}) `}
        </Text>
      );
      return;
    }
    const chunks = hasTarget ? piece.split(target) : [piece];
    chunks.forEach((chunk, j) => {
      if (j > 0) {
        nodes.push(
          <Text key={`target-${i}-${j}`} style={styles.target}>
            {target}
          </Text>
        );
      }
      if (chunk.trim()) nodes.push(<Fragment key={`text-${i}-${j}`}>{chunk.trim()}</Fragment>);
    });
  });

  // 少数搭配的原文里不含目标词，沿用网页版的做法补在末尾
  if (!hasTarget && target) {
    nodes.push(
      <Text key="target-tail" style={styles.target}>
        {target}
      </Text>
    );
  }

  return <Text style={style}>{nodes}</Text>;
}

const styles = StyleSheet.create({
  target: { color: colors.primary, fontWeight: '800' },
  level: { fontSize: 14, fontWeight: '500', color: colors.primaryDark, backgroundColor: colors.primaryBg },
});
