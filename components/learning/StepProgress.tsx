import React from 'react';
import { Check } from 'lucide-react';

const STEPS = [
  { key: 'character', label: '字' },
  { key: 'word', label: '词' },
  { key: 'collocation', label: '搭配' },
  { key: 'sentence', label: '例句' },
  { key: 'exercise', label: '练习' },
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
    <ol className="flex items-center gap-1" aria-label="学习步骤">
      {STEPS.map((step, index) => {
        const skipped = index < startIndex;
        const done = index >= startIndex && index < currentIndex;
        const active = index === currentIndex;
        const state = active ? '当前' : done ? '已完成' : skipped ? '已跳过' : '未开始';
        return (
          <li
            key={step.key}
            className={index === 0 ? 'flex items-center shrink-0' : 'flex items-center gap-1 flex-1 min-w-0'}
            aria-current={active ? 'step' : undefined}
          >
            {index > 0 && (
              <span
                className={`h-px flex-1 ${index > startIndex && index <= currentIndex ? 'bg-indigo-400' : 'bg-gray-300'}`}
                aria-hidden="true"
              />
            )}
            <span
              className={`inline-flex items-center gap-0.5 rounded-full px-2 h-7 text-sm font-semibold whitespace-nowrap shrink-0 ${
                active
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : done
                    ? 'bg-indigo-100 text-indigo-700'
                    : skipped
                      ? 'text-gray-500 line-through decoration-gray-400'
                      : 'bg-white/60 text-gray-600'
              }`}
              aria-label={`${step.label}：${state}`}
            >
              {done && <Check size={12} strokeWidth={3} aria-hidden="true" />}
              {step.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
