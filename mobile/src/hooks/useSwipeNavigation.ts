// 源文件：src/hooks/useSwipeNavigation.ts（网页版）。RN 版：react-native-gesture-handler 的 Pan 手势。
// 阈值和网页版一致：横向至少 60dp、横向 > 1.5 × 竖向、单指；竖滑失败交给 ScrollView 滚动。
import { useRef } from 'react';
import { Gesture } from 'react-native-gesture-handler';

export type SwipeDirection = 'previous' | 'next';

const MIN_DISTANCE = 60;
const HORIZONTAL_RATIO = 1.5;

/**
 * 学习页左右滑动：左滑 → 下一步，右滑 ← 上一步。
 * 只用在字/词/搭配/例句四个学习页（练习页不用，免得还没作答就被滑走）。
 * 返回的 Pan 手势用 GestureDetector 包住整个学习页。
 */
export function useSwipeNavigation(onNavigate: (direction: SwipeDirection) => void) {
  const handler = useRef(onNavigate);
  handler.current = onNavigate;

  const pan = Gesture.Pan()
    .maxPointers(1)
    // 横向先动一点就接管手势；竖向一动就失败，把滚动交给内层 ScrollView
    .activeOffsetX([-20, 20])
    .failOffsetY([-20, 20])
    // 回调在 JS 线程运行：swipe 只是触发导航，不需要 worklet；在 worklet 里访问 useRef 会崩溃
    .runOnJS(true)
    .onEnd(e => {
      const dx = e.translationX;
      const dy = e.translationY;
      if (Math.abs(dx) < MIN_DISTANCE || Math.abs(dx) < HORIZONTAL_RATIO * Math.abs(dy)) return;
      handler.current(dx < 0 ? 'next' : 'previous');
    });

  return pan;
}
