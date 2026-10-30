import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ClipboardCheck, Layers, CalendarClock, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { safeGetItem, safeSetItem } from '@/src/lib/guestIdentity';

/**
 * 新用户引导：第一次打开首页时说明怎么学。三步对应论文的学习流程：
 * VKS 自评定入口 → 字、词、搭配、例句、练习逐步学 → 按复习计划回来复习。
 */

const SEEN_KEY = 'learningSystem.onboardingSeen';

const STEPS = [
  {
    icon: ClipboardCheck,
    title: 'Start with a quick self-check',
    body: 'Each new word begins with one question: how well do you know it? Your answer decides where you start, so you never redo what you already know.',
  },
  {
    icon: Layers,
    title: 'Learn it step by step',
    body: 'Characters → word → collocations → example sentences → practice. You see the parts first, then use the whole word.',
  },
  {
    icon: CalendarClock,
    title: 'Come back to review',
    body: 'Each word comes back a few times over the next two weeks, then less often. Open the app and Today’s review shows what is due.',
  },
] as const;

// localStorage 不可用（隐私模式、禁用站点数据）时写不进去：至少在这次打开期间记住已关闭
let seenInMemory = false;

/** 本设备是否已看过引导 */
export const onboardingSeen = () => seenInMemory || safeGetItem(SEEN_KEY) === '1';

const FOCUSABLE = 'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

export function Onboarding({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [index, setIndex] = useState(0);
  const primaryRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  // 打开前焦点所在的元素（如「How it works」），关闭后把焦点还给它
  const returnFocusRef = useRef<Element | null>(null);

  // 关掉即记为看过（跳过也算），之后不再自动弹出
  const close = useCallback(() => {
    seenInMemory = true;
    safeSetItem(SEEN_KEY, '1');
    onClose();
  }, [onClose]);

  useEffect(() => {
    if (open) {
      returnFocusRef.current = document.activeElement;
    } else if (returnFocusRef.current instanceof HTMLElement && returnFocusRef.current.isConnected) {
      returnFocusRef.current.focus();
      returnFocusRef.current = null;
    }
  }, [open]);

  // 每次打开都从第一步开始。单独成一个 effect：下面的键盘监听随 close 重挂，
  // 父组件每次渲染都会传入新的 onClose，放在一起会把用户翻到的页数重置
  useEffect(() => {
    if (open) setIndex(0);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        close();
        return;
      }
      // Tab 只在弹层里循环，不跳到背后的页面
      if (event.key === 'Tab' && dialogRef.current) {
        const items = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE));
        if (!items.length) return;
        const first = items[0];
        const last = items[items.length - 1];
        const inside = dialogRef.current.contains(document.activeElement);
        if (event.shiftKey && (document.activeElement === first || !inside)) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && (document.activeElement === last || !inside)) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, close]);

  // 打开和翻页时把焦点放到主按钮上，键盘用户可以直接回车往下走
  useEffect(() => {
    if (open) primaryRef.current?.focus();
  }, [open, index]);

  if (!open) return null;

  const step = STEPS[index];
  const Icon = step.icon;
  const last = index === STEPS.length - 1;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-gray-900/40 backdrop-blur-sm">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="onboarding-title"
        className="w-full max-w-[430px] bg-white rounded-t-3xl sm:rounded-3xl shadow-2xl px-6 pt-6 pb-[calc(env(safe-area-inset-bottom)+1.5rem)]"
      >
        <div className="flex items-center justify-between mb-5">
          <span className="text-sm font-semibold text-indigo-700">
            {index + 1} / {STEPS.length}
          </span>
          <button
            type="button"
            onClick={close}
            className="h-9 px-3 -mr-3 inline-flex items-center gap-1 text-sm font-medium text-gray-600 hover:text-gray-800"
          >
            Skip <X size={16} aria-hidden="true" />
          </button>
        </div>

        <div className="w-14 h-14 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mb-4">
          <Icon size={28} aria-hidden="true" />
        </div>
        <h2 id="onboarding-title" className="text-2xl font-bold text-gray-900 mb-2">
          {step.title}
        </h2>
        <p className="text-base text-gray-700 leading-relaxed mb-6">{step.body}</p>

        <div className="flex items-center justify-center gap-2 mb-6" aria-hidden="true">
          {STEPS.map((s, i) => (
            <span
              key={s.title}
              className={`h-2 rounded-full transition-all ${i === index ? 'w-6 bg-indigo-600' : 'w-2 bg-gray-300'}`}
            />
          ))}
        </div>

        <div className="flex gap-3">
          {index > 0 && (
            <Button variant="outline" className="h-11 flex-1 text-base rounded-xl border-slate-200 text-slate-700 focus-visible:ring-2 focus-visible:ring-indigo-300 focus-visible:ring-offset-2" onClick={() => setIndex(index - 1)}>
              Back
            </Button>
          )}
          <Button
            ref={primaryRef}
            // 打开时焦点放在这里（键盘、读屏用户），焦点框用淡色，不显得像一圈黑边
            className="h-11 flex-1 text-base font-semibold rounded-xl border-none bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white focus-visible:ring-2 focus-visible:ring-indigo-300 focus-visible:ring-offset-2"
            onClick={() => (last ? close() : setIndex(index + 1))}
          >
            {last ? 'Get started' : 'Next'}
          </Button>
        </div>
      </div>
    </div>
  );
}
