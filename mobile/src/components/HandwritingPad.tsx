// 源文件：components/learning/HandwritingPad.tsx（网页版，canvas + PointerEvent）。
// RN 版：react-native-svg + PanResponder 手势采集，坐标仍按 240 见方记录（判分见 handwriting.ts）。
import React, { useCallback, useRef, useState } from 'react';
import { PanResponder, StyleSheet, View, type LayoutChangeEvent } from 'react-native';
import Svg, { Circle, Line, Path } from 'react-native-svg';
import type { Point, Stroke } from '@/lib/handwriting';
import { colors, radius } from '@/theme';

const SIZE = 240;
const LINE_WIDTH = 9;

interface HandwritingPadProps {
  /** 已写下的笔画（父组件持有，CHECK 时拿去判分） */
  strokes: Stroke[];
  onChange: (strokes: Stroke[]) => void;
  disabled?: boolean;
  /** 答完后边框颜色：对 / 错 */
  result?: 'correct' | 'wrong' | null;
}

const strokePath = (stroke: Stroke) =>
  stroke.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');

export default function HandwritingPad({ strokes, onChange, disabled = false, result = null }: HandwritingPadProps) {
  const [currentStroke, setCurrentStroke] = useState<Stroke | null>(null);
  const strokesRef = useRef(strokes);
  strokesRef.current = strokes;
  const currentStrokeRef = useRef<Stroke | null>(null);
  currentStrokeRef.current = currentStroke;
  const sizeRef = useRef(SIZE);

  const onLayout = useCallback((e: LayoutChangeEvent) => {
    sizeRef.current = e.nativeEvent.layout.width || SIZE;
  }, []);

  const toPoint = useCallback((x: number, y: number): Point => {
    return [(x / sizeRef.current) * SIZE, (y / sizeRef.current) * SIZE];
  }, []);

  const finishStroke = useCallback(
    (stroke: Stroke | null) => {
      if (stroke && stroke.length > 0) onChange([...strokesRef.current, stroke]);
      setCurrentStroke(null);
    },
    [onChange]
  );

  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => !disabled,
      onMoveShouldSetPanResponder: () => !disabled,
      onPanResponderGrant: evt => {
        const { locationX, locationY } = evt.nativeEvent;
        setCurrentStroke([toPoint(locationX, locationY)]);
      },
      onPanResponderMove: evt => {
        const { locationX, locationY } = evt.nativeEvent;
        const p = toPoint(locationX, locationY);
        setCurrentStroke(prev => {
          if (!prev) return [p];
          const last = prev[prev.length - 1];
          // 太近的点跳过，减少冗余坐标
          if (Math.hypot(p[0] - last[0], p[1] - last[1]) < 1.5) return prev;
          return [...prev, p];
        });
      },
      onPanResponderRelease: () => {
        finishStroke(currentStrokeRef.current);
      },
      onPanResponderTerminate: () => {
        finishStroke(currentStrokeRef.current);
      },
    })
  ).current;

  const allStrokes = currentStroke ? [...strokes, currentStroke] : strokes;
  const borderColor = result === 'correct' ? colors.success : result === 'wrong' ? colors.danger : colors.primaryBorder;

  return (
    <View
      style={[styles.pad, { borderColor }]}
      onLayout={onLayout}
      {...panResponder.panHandlers}
      accessibilityLabel="Handwriting area: write the missing character here"
    >
      <Svg width="100%" height="100%" viewBox={`0 0 ${SIZE} ${SIZE}`}>
        <Line x1={SIZE / 2} y1={0} x2={SIZE / 2} y2={SIZE} stroke="#e0e7ff" strokeWidth={1.5} strokeDasharray="6 6" />
        <Line x1={0} y1={SIZE / 2} x2={SIZE} y2={SIZE / 2} stroke="#e0e7ff" strokeWidth={1.5} strokeDasharray="6 6" />
        {allStrokes.map((stroke, i) =>
          stroke.length === 1 ? (
            <Circle key={i} cx={stroke[0][0]} cy={stroke[0][1]} r={4.5} fill="#1f2937" />
          ) : (
            <Path
              key={i}
              d={strokePath(stroke)}
              stroke="#1f2937"
              strokeWidth={LINE_WIDTH}
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )
        )}
      </Svg>
    </View>
  );
}

/** 答完以后把学习者写的字缩小显示（和手写格同一套坐标），和标准写法并排对照 */
export function HandwritingThumb({ strokes, size, result }: { strokes: Stroke[]; size: number; result: 'correct' | 'wrong' }) {
  const borderColor = result === 'correct' ? colors.success : colors.danger;
  return (
    <View style={{ width: size, height: size }}>
      <Svg width={size} height={size} viewBox={`0 0 ${SIZE} ${SIZE}`} style={[styles.thumb, { borderColor }]}>
        <Line x1={SIZE / 2} y1={0} x2={SIZE / 2} y2={SIZE} stroke="#e0e7ff" strokeWidth={2} strokeDasharray="8 8" />
        <Line x1={0} y1={SIZE / 2} x2={SIZE} y2={SIZE / 2} stroke="#e0e7ff" strokeWidth={2} strokeDasharray="8 8" />
        {strokes.map((stroke, i) =>
          stroke.length === 1 ? (
            <Circle key={i} cx={stroke[0][0]} cy={stroke[0][1]} r={4.5} fill="#1f2937" />
          ) : (
            <Path
              key={i}
              d={strokePath(stroke)}
              stroke="#1f2937"
              strokeWidth={9}
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )
        )}
      </Svg>
    </View>
  );
}

const styles = StyleSheet.create({
  pad: {
    width: 240,
    height: 240,
    borderRadius: radius.xl,
    borderWidth: 2,
    backgroundColor: colors.white,
    alignSelf: 'center',
  },
  thumb: {
    borderRadius: radius.lg,
    borderWidth: 2,
    backgroundColor: colors.white,
  },
});
