import React, { useEffect, useRef } from 'react';
import { RotateCcw } from 'lucide-react';
import { loadCharacterData } from '@/src/lib/handwriting';

interface StrokeOrderAnimationProps {
  character: string;
  size?: number;
}

/** 答完填字题后演示这个字的标准写法和笔顺（Hanzi Writer），可以再看一遍 */
export default function StrokeOrderAnimation({ character, size = 110 }: StrokeOrderAnimationProps) {
  const target = useRef<HTMLDivElement>(null);
  const writer = useRef<{ animateCharacter: () => void } | null>(null);

  useEffect(() => {
    let cancelled = false;
    const el = target.current;
    if (!el) return;
    import('hanzi-writer').then(({ default: HanziWriter }) => {
      if (cancelled) return;
      el.innerHTML = '';
      const created = HanziWriter.create(el, character, {
        width: size,
        height: size,
        padding: 6,
        showOutline: true,
        strokeAnimationSpeed: 1.4,
        delayBetweenStrokes: 120,
        charDataLoader: (char: string, onLoad: (data: never) => void, onError: (err?: unknown) => void) => {
          loadCharacterData(char).then(data => onLoad(data as never)).catch(onError);
        },
      });
      writer.current = created;
      created.animateCharacter();
    }).catch(() => {
      /* 没有笔画数据或组件加载失败：不显示演示 */
    });
    return () => {
      cancelled = true;
      el.innerHTML = '';
      writer.current = null;
    };
  }, [character, size]);

  // 动画在上、Replay 在下：反馈卡里和学习者写的字并排放
  return (
    <div className="flex flex-col items-center gap-1">
      <div ref={target} className="rounded-xl bg-white border-2 border-slate-200" style={{ width: size, height: size }} aria-label={`How to write ${character}`} />
      <button
        type="button"
        onClick={() => writer.current?.animateCharacter()}
        className="h-9 px-3 inline-flex items-center gap-1 rounded-lg text-sm font-medium text-slate-700 hover:bg-white/60"
      >
        <RotateCcw size={14} aria-hidden="true" /> Replay
      </button>
    </div>
  );
}
