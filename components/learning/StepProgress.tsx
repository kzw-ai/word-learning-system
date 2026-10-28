import React from 'react';
import { Check } from 'lucide-react';

// 五个标签要在 390px 宽的屏幕上排成一行：用短标签，各页标题仍用全称
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
  /**
   * 本轮从哪一步进入（VKS 自评或复习推荐决定）。之前的步骤显示为「跳过」，
   * 未知时按从第一步开始处理
   */
  entry?: string | null;
}

/**
 * 学习链路的步骤进度：字 → 词 → 搭配 → 例句 → 练习。只用于显示位置，不可点击——
 * 跳转仍由页面顶部的上一步 / 下一步按钮负责。
 */
export default function StepProgress({ current, entry }: StepProgressProps) {
  const currentIndex = STEPS.findIndex(step => step.key === current);
  const entryIndex = Math.max(0, STEPS.findIndex(step => step.key === entry));
  // 当前步骤在入口之前（例如从后面的步骤点了「上一步」）时，按当前步骤为起点
  const startIndex = Math.min(entryIndex, Math.max(currentIndex, 0));

  return (
    <ol className="flex items-center gap-0.5" aria-label="Learning steps">
      {STEPS.map((step, index) => {
        const skipped = index < startIndex;
        const done = index >= startIndex && index < currentIndex;
        const active = index === currentIndex;
        const state = active ? 'current' : done ? 'done' : skipped ? 'skipped' : 'not started';
        return (
          <li
            key={step.key}
            // flex-auto：按标签实际宽度分配，剩下的给连接线。flex-1 会平均分，标签宽时溢出
            className={index === 0 ? 'flex items-center shrink-0' : 'flex items-center gap-0.5 flex-auto'}
            aria-current={active ? 'step' : undefined}
          >
            {index > 0 && (
              <span
                className={`h-px flex-1 ${index > startIndex && index <= currentIndex ? 'bg-indigo-400' : 'bg-gray-300'}`}
                aria-hidden="true"
              />
            )}
            {/* 已完成的步骤只留对勾：英文标签比中文宽，五个都带字在 390px 宽的屏幕上排不下 */}
            <span
              className={`inline-flex items-center justify-center rounded-full h-7 text-sm font-semibold whitespace-nowrap shrink-0 ${
                active
                  ? 'px-1.5 bg-indigo-600 text-white shadow-sm'
                  : done
                    ? 'w-7 bg-indigo-100 text-indigo-700'
                    : skipped
                      ? 'px-1 text-gray-500 line-through decoration-gray-400'
                      : 'px-1 bg-white/60 text-gray-600'
              }`}
              aria-label={`${step.label}: ${state}`}
              title={done ? step.label : undefined}
            >
              {done ? <Check size={14} strokeWidth={3} aria-hidden="true" /> : step.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
