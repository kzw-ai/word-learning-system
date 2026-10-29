import { useEffect, useRef, useState } from 'react';

export type SwipeDirection = 'previous' | 'next';

// 从离屏幕左右边缘这么近的地方开始的滑动不算：iPhone Safari 从边缘滑是浏览器的返回 / 前进
const EDGE_PX = 30;
// 横向至少滑这么远、且明显比竖向多，才算翻页；上下滚动和轻微拖动不算
const MIN_DISTANCE_PX = 60;
const HORIZONTAL_RATIO = 1.5;
const MAX_DURATION_MS = 800;
// 这些元素里的滑动和按键交给元素自己（输入框里移动光标、选文字等）
const IGNORE = 'input, textarea, select, [contenteditable="true"], [data-no-swipe]';

const DIRECTION_KEY = 'learning-slide-direction';

const ignored = (target: EventTarget | null) => target instanceof Element && target.closest(IGNORE) !== null;

/** 记下这次翻页的方向，下一页挂载时据此播放滑入动画（useSlideIn） */
export const rememberSlideDirection = (direction: SwipeDirection) => {
  try {
    sessionStorage.setItem(DIRECTION_KEY, direction);
  } catch {
    /* 存不了就不播放动画 */
  }
};

/**
 * 学习页的左右滑动和键盘翻页：左滑 / → 到下一步，右滑 / ← 回上一步。
 * 只用在字、词、搭配、例句四个学习页；练习页不用，免得还没作答就被滑走。
 */
export const useSwipeNavigation = (onNavigate: (direction: SwipeDirection) => void, enabled = true) => {
  const handler = useRef(onNavigate);
  handler.current = onNavigate;

  useEffect(() => {
    if (!enabled) return;
    let start: { x: number; y: number; time: number } | null = null;

    const go = (direction: SwipeDirection) => handler.current(direction);

    const onTouchStart = (event: TouchEvent) => {
      start = null;
      if (event.touches.length !== 1 || ignored(event.target)) return;
      const touch = event.touches[0];
      if (touch.clientX < EDGE_PX || touch.clientX > window.innerWidth - EDGE_PX) return;
      start = { x: touch.clientX, y: touch.clientY, time: Date.now() };
    };

    const onTouchEnd = (event: TouchEvent) => {
      if (!start) return;
      const touch = event.changedTouches[0];
      const dx = touch.clientX - start.x;
      const dy = touch.clientY - start.y;
      const quick = Date.now() - start.time <= MAX_DURATION_MS;
      start = null;
      if (!quick || Math.abs(dx) < MIN_DISTANCE_PX || Math.abs(dx) < HORIZONTAL_RATIO * Math.abs(dy)) return;
      // 拖着选文字时不翻页
      if (window.getSelection()?.toString()) return;
      go(dx < 0 ? 'next' : 'previous');
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || ignored(event.target)) return;
      if (event.key === 'ArrowRight') go('next');
      else if (event.key === 'ArrowLeft') go('previous');
    };

    window.addEventListener('touchstart', onTouchStart, { passive: true });
    window.addEventListener('touchend', onTouchEnd, { passive: true });
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('touchstart', onTouchStart);
      window.removeEventListener('touchend', onTouchEnd);
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [enabled]);
};

/** 这一页挂载时的滑入动画 class：从下一步翻过来从右侧滑入，回到上一步从左侧滑入；直接打开的页面不播放 */
export const useSlideIn = () => {
  const [className, setClassName] = useState('');
  useEffect(() => {
    try {
      const direction = sessionStorage.getItem(DIRECTION_KEY);
      sessionStorage.removeItem(DIRECTION_KEY);
      if (direction === 'next' || direction === 'previous') {
        setClassName(`learning-slide-${direction}`);
      }
    } catch {
      /* 读不了就不播放动画 */
    }
  }, []);
  return className;
};
