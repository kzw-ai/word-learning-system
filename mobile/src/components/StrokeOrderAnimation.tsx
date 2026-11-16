// 用 react-native-svg 的 Mask 复刻 hanzi-writer 的笔顺动画：
// 底层画完整字形轮廓（strokes 实心填充），遮罩层按笔顺逐笔画出中线（medians 连线成粗线，
// strokeDashoffset 动画从全长到 0），字形轮廓只在已画出的中线覆盖区域可见 → 逐笔显露。
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Animated, Pressable, StyleSheet, Text, View } from 'react-native';
import Svg, { Defs, G, Mask, Path } from 'react-native-svg';
import { loadCharacterData } from '@/lib/strokeData';
import type { CharacterData, Point } from '@/lib/handwriting';
import { colors, fontSize, radius } from '@/theme';

const AnimatedPath = Animated.createAnimatedComponent(Path);
const COORD = 1024;
// hanzi-writer-data 的 medians 和 strokes 都是 y 轴朝上（基线 900），SVG 是 y 轴朝下。
// 不要单独翻转 medians（那样会和 strokes 对不上、字形颠倒），而是把两者放进同一个
// transform 里统一翻转：scale(1,-1) 翻 y，translate(0,900) 把翻转后坐标平移回 0–1024。
const FLIP = 'translate(0, 900) scale(1, -1)';
// 中线宽度：遮罩可见区域的粗细（够宽才能遮住字形轮廓的笔划）
const STROKE_WIDTH = 130;

const toPolyline = (points: Point[]): string =>
  points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');

const polylineLen = (points: Point[]): number =>
  points.reduce(
    (sum, p, i) => (i === 0 ? 0 : sum + Math.hypot(p[0] - points[i - 1][0], p[1] - points[i - 1][1])),
    0
  );

interface StrokeOrderAnimationProps {
  character: string;
  size?: number;
}

export default function StrokeOrderAnimation({ character, size = 110 }: StrokeOrderAnimationProps) {
  const [data, setData] = useState<CharacterData | null>(null);
  const progressRef = useRef<Animated.Value[]>([]);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    loadCharacterData(character)
      .then(d => {
        if (!cancelled) setData(d);
      })
      .catch(() => {
        if (!cancelled) setData(null);
      });
    return () => {
      cancelled = true;
    };
  }, [character]);

  const play = useCallback(() => {
    if (!data) return;
    progressRef.current.forEach(p => p.setValue(0));
    const anims = progressRef.current.map(p =>
      Animated.timing(p, { toValue: 1, duration: 700, useNativeDriver: false })
    );
    Animated.stagger(220, anims).start();
  }, [data]);

  useEffect(() => {
    if (data) {
      progressRef.current = data.medians.map(() => new Animated.Value(0));
      play();
    }
  }, [data, play]);

  if (!data) {
    return (
      <View
        style={[
          styles.placeholder,
          { width: size, height: size, borderRadius: radius.lg },
        ]}
      />
    );
  }

  // medians 与 strokes 共用同一套 y 轴朝上的坐标，统一由 FLIP transform 翻转
  const medians = data.medians;

  return (
    <View style={styles.wrap}>
      <View style={[styles.frame, { width: size, height: size }]}>
        <Svg width={size} height={size} viewBox={`0 0 ${COORD} ${COORD}`}>
          <Defs>
            <Mask id={`mask-${character}`}>
              <G transform={FLIP}>
                {medians.map((points, i) => {
                const len = polylineLen(points) || 1;
                const progress = progressRef.current[i];
                const dashOffset = progress
                  ? progress.interpolate({ inputRange: [0, 1], outputRange: [len, 0] })
                  : len;
                return (
                  <AnimatedPath
                    key={i}
                    d={toPolyline(points)}
                    stroke="white"
                    strokeWidth={STROKE_WIDTH}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    fill="none"
                    strokeDasharray={[len, len]}
                    strokeDashoffset={dashOffset}
                  />
                );
                })}
              </G>
            </Mask>
          </Defs>
          {/* 字形轮廓（实心），被中线 mask 遮罩，逐笔显露；轮廓与中线用同一个 transform 翻转 */}
          <G mask={`url(#mask-${character})`}>
            <G transform={FLIP}>
              {data.strokes.map((d, i) => (
                <Path key={i} d={d} fill="#1f2937" />
              ))}
            </G>
          </G>
        </Svg>
      </View>
      <Pressable style={styles.replay} onPress={play} accessibilityLabel="Replay animation">
        <Text style={styles.replayText}>Replay</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: 'center', gap: 4 },
  placeholder: { backgroundColor: colors.white, borderWidth: 2, borderColor: colors.border },
  frame: {
    backgroundColor: colors.white,
    borderWidth: 2,
    borderColor: colors.border,
    borderRadius: radius.lg,
    overflow: 'hidden',
  },
  replay: {
    minHeight: 36,
    paddingHorizontal: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  replayText: { fontSize: fontSize.body, fontWeight: '600', color: colors.textMuted },
});
