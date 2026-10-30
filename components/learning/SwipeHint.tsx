import React, { useEffect, useState } from 'react';
import { ChevronsLeft } from 'lucide-react';

const SEEN_KEY = 'learning-swipe-hint-seen';
const VISIBLE_MS = 4000;

/**
 * 第一次进学习页时提示一次可以左滑翻页（只在触屏设备上），几秒后消失，之后不再出现。
 * 电脑上用 ← → 键翻页，不提示。
 */
export default function SwipeHint() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      if (localStorage.getItem(SEEN_KEY) || !window.matchMedia('(pointer: coarse)').matches) return;
      localStorage.setItem(SEEN_KEY, '1');
    } catch {
      return;
    }
    setVisible(true);
    const timer = window.setTimeout(() => setVisible(false), VISIBLE_MS);
    return () => window.clearTimeout(timer);
  }, []);

  if (!visible) return null;
  return (
    <p className="flex items-center justify-center gap-1 text-sm text-slate-600 mb-2" role="status">
      <ChevronsLeft size={16} aria-hidden="true" />
      Swipe left for the next step
    </p>
  );
}
