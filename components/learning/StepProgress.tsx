import React, { useEffect, useState } from 'react';
import { safeGetItem, safeSetItem } from '@/src/lib/guestIdentity';

// 五个标签要在 375px 宽的屏幕上排成一行：用短标签，各页标题仍用全称
const STEPS = [
  { key: 'character', label: 'Chars' },
  { key: 'word', label: 'Word' },
  { key: 'collocation', label: 'Phrases' },
  { key: 'sentence', label: 'Sentence' },
  { key: 'exercise', label: 'Practice' },
] as const;

// 第一次见到自评或复习跳过的步骤时，进度条下面说一句怎么回事；只说一次，之后不再占注意力。
// 不说具体理由（自评选了什么、上次哪类题错了）：每个词都解释一遍太啰嗦，学习者只要知道浅色是跳过、能点开。
// 记在本机浏览器里，和新手引导一样；换设备最多再看到一次
const HINT_SEEN_KEY = 'learningSystem.skippedStepsHintSeen';
let hintSeenInMemory = false;

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
  /** 点一格跳到那一步（不必按顺序左右滑）；不传时只显示位置。当前这一步和单字词的「Chars」（没有这一页）不能点 */
  onSelect?: (key: string) => void;
}

/**
 * 学习链路的步骤进度：字 → 词 → 搭配 → 例句 → 练习。传了 onSelect 时每一格都能点，直接跳到那一步
 * （包括自评后跳过的步骤，想回头看也行）；上一步、下一步按钮和左右滑动照旧。
 *
 * 每一步占等宽的一格、标签一直显示，状态只改颜色：左右滑动换页时标签和进度条都不挪位置
 * （以前已完成的步骤收成对勾、当前步骤放大成胶囊，每换一页整行都在动）。
 * 单字词也是五格、「Chars」按跳过显示：以前单字词去掉这一格，页面先按五格画、词的数据到了再变四格，换页时跳一下。
 *
 * 跳过的步骤用细字、浅色横条，不划线：划线读起来像「错了、作废」，练习页答错的选项也是划线。
 * 跳过的在当前步骤左边、还没到的在右边，靠位置就分得开；还没到的用深一档的灰，字色都不低于对比度 4.5。
 */
export default function StepProgress({ current, entry, skipCharacter = false, onSelect }: StepProgressProps) {
  const currentIndex = STEPS.findIndex(step => step.key === current);
  const entryIndex = Math.max(0, STEPS.findIndex(step => step.key === entry));
  // 当前步骤在入口之前（例如从后面的步骤点了「上一步」）时，按当前步骤为起点
  const startIndex = Math.min(entryIndex, Math.max(currentIndex, 0));
  // 单字词的「Chars」不算：那是没有这一页，不是跳过，也点不开。
  // 提示里直接点名跳过的步骤：说「浅色的」分不清，还没到的步骤也是灰的
  const skippedLabels = STEPS.slice(0, startIndex)
    .filter(step => !(skipCharacter && step.key === 'character'))
    .map(step => step.label);
  const hasSkipped = skippedLabels.length > 0 && Boolean(onSelect);

  const [showHint, setShowHint] = useState(false);
  useEffect(() => {
    if (!hasSkipped || hintSeenInMemory || safeGetItem(HINT_SEEN_KEY) === '1') return;
    hintSeenInMemory = true;
    safeSetItem(HINT_SEEN_KEY, '1');
    setShowHint(true);
  }, [hasSkipped]);

  return (
    <>
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
          <li key={step.key} aria-current={active ? 'step' : undefined}>
            {(() => {
              const label = (
                <>
                  <span
                    className={`text-sm leading-5 whitespace-nowrap ${
                      active
                        ? 'font-bold text-indigo-800'
                        : done
                          ? 'font-semibold text-indigo-600'
                          : skipped
                            ? 'font-normal text-slate-500'
                            : 'font-semibold text-slate-600'
                    }`}
                    aria-hidden="true"
                  >
                    {step.label}
                  </span>
                  <span
                    className={`h-1 w-full rounded-full ${
                      active ? 'bg-indigo-600' : done ? 'bg-indigo-300' : skipped ? 'bg-slate-100' : 'bg-slate-200'
                    }`}
                    aria-hidden="true"
                  />
                </>
              );
              // 整格都是按钮，至少 36px 高，手指点得准；按下时底色稍深
              const selectable = onSelect && !active && !(skipCharacter && step.key === 'character');
              return selectable ? (
                <button
                  type="button"
                  onClick={() => onSelect(step.key)}
                  className="w-full min-h-9 flex flex-col items-center justify-center gap-1 rounded-lg hover:bg-white/60 active:bg-indigo-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
                  aria-label={`${step.label}: ${state}. Go to this step`}
                >
                  {label}
                </button>
              ) : (
                <div className="w-full min-h-9 flex flex-col items-center justify-center gap-1" aria-label={`${step.label}: ${state}`}>
                  {label}
                </div>
              );
            })()}
          </li>
        );
      })}
    </ol>
    {showHint && (
      <p className="mt-1 text-center text-sm text-slate-600 text-balance">
        Skipped this time: {skippedLabels.join(', ')}. Tap {skippedLabels.length === 1 ? 'it' : 'one'} to look anyway.
      </p>
    )}
    </>
  );
}
