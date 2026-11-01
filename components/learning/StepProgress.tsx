import React from 'react';

// 五个标签要在 375px 宽的屏幕上排成一行：用短标签，各页标题仍用全称
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
  /** 单字词跳过字页：「Chars」这一格显示为跳过（格子照留，五格不变） */
  skipCharacter?: boolean;
}

/**
 * 学习链路的步骤进度：字 → 词 → 搭配 → 例句 → 练习。只用于显示位置，不可点击——
 * 跳转仍由页面顶部的上一步 / 下一步按钮负责。
 *
 * 每一步占等宽的一格、标签一直显示，状态只改颜色：左右滑动换页时标签和进度条都不挪位置
 * （以前已完成的步骤收成对勾、当前步骤放大成胶囊，每换一页整行都在动）。
 * 单字词也是五格、「Chars」划掉：以前单字词去掉这一格，页面先按五格画、词的数据到了再变四格，换页时跳一下。
 */
export default function StepProgress({ current, entry, skipCharacter = false }: StepProgressProps) {
  const currentIndex = STEPS.findIndex(step => step.key === current);
  const entryIndex = Math.max(0, STEPS.findIndex(step => step.key === entry));
  // 当前步骤在入口之前（例如从后面的步骤点了「上一步」）时，按当前步骤为起点
  const startIndex = Math.min(entryIndex, Math.max(currentIndex, 0));

  return (
    <ol
      className="grid grid-cols-5 gap-1"
      aria-label="Learning steps"
    >
      {STEPS.map((step, index) => {
        const skipped = index < startIndex || (skipCharacter && step.key === 'character');
        const done = !skipped && index >= startIndex && index < currentIndex;
        const active = index === currentIndex;
        const state = active ? 'current' : done ? 'done' : skipped ? 'skipped' : 'not started';
        return (
          <li
            key={step.key}
            className="flex flex-col items-center gap-1"
            aria-current={active ? 'step' : undefined}
            aria-label={`${step.label}: ${state}`}
          >
            <span
              className={`text-sm leading-5 whitespace-nowrap ${
                active
                  ? 'font-bold text-indigo-800'
                  : done
                    ? 'font-semibold text-indigo-600'
                    : skipped
                      ? 'font-semibold text-slate-500 line-through decoration-slate-400'
                      : 'font-semibold text-slate-500'
              }`}
              aria-hidden="true"
            >
              {step.label}
            </span>
            <span
              className={`h-1 w-full rounded-full ${
                active ? 'bg-indigo-600' : done ? 'bg-indigo-300' : 'bg-slate-200'
              }`}
              aria-hidden="true"
            />
          </li>
        );
      })}
    </ol>
  );
}
