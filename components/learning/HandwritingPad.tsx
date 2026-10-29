import React, { useCallback, useEffect, useRef } from 'react';
import type { Stroke } from '@/src/lib/handwriting';

interface HandwritingPadProps {
  /** 已写下的笔画（父组件持有，CHECK 时拿去判分） */
  strokes: Stroke[];
  onChange: (strokes: Stroke[]) => void;
  disabled?: boolean;
  /** 答完后边框颜色：对 / 错 */
  result?: 'correct' | 'wrong' | null;
}

const SIZE = 240;

/**
 * 填字题的手写格（论文 3.2 节）：田字格里用手指或鼠标写，不限笔顺。只记录笔画坐标，
 * 判分见 src/lib/handwriting.ts。格子里不显示答案字的轮廓。
 */
export default function HandwritingPad({ strokes, onChange, disabled = false, result = null }: HandwritingPadProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const current = useRef<Stroke | null>(null);
  const strokesRef = useRef(strokes);
  strokesRef.current = strokes;

  const draw = useCallback((all: Stroke[]) => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;
    const ratio = window.devicePixelRatio || 1;
    if (canvas.width !== SIZE * ratio) {
      canvas.width = SIZE * ratio;
      canvas.height = SIZE * ratio;
    }
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, SIZE, SIZE);
    ctx.strokeStyle = '#1f2937';
    ctx.lineWidth = 9;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    for (const stroke of all) {
      if (stroke.length === 0) continue;
      ctx.beginPath();
      ctx.moveTo(stroke[0][0], stroke[0][1]);
      if (stroke.length === 1) ctx.lineTo(stroke[0][0] + 0.1, stroke[0][1]);
      for (const [x, y] of stroke.slice(1)) ctx.lineTo(x, y);
      ctx.stroke();
    }
  }, []);

  useEffect(() => {
    draw(strokes);
  }, [strokes, draw]);

  const point = (event: React.PointerEvent<HTMLCanvasElement>): [number, number] => {
    const rect = event.currentTarget.getBoundingClientRect();
    return [((event.clientX - rect.left) / rect.width) * SIZE, ((event.clientY - rect.top) / rect.height) * SIZE];
  };

  const onPointerDown = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (disabled) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    current.current = [point(event)];
    draw([...strokesRef.current, current.current]);
  };

  const onPointerMove = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!current.current) return;
    current.current.push(point(event));
    draw([...strokesRef.current, current.current]);
  };

  const finishStroke = () => {
    if (!current.current) return;
    const stroke = current.current;
    current.current = null;
    onChange([...strokesRef.current, stroke]);
  };

  const border = result === 'correct' ? 'border-emerald-600' : result === 'wrong' ? 'border-red-500' : 'border-indigo-200';

  return (
    <div className={`relative rounded-2xl border-2 bg-white/90 ${border}`} style={{ width: SIZE, height: SIZE }}>
      {/* 田字格 */}
      <svg className="absolute inset-0 pointer-events-none" width={SIZE} height={SIZE} aria-hidden="true">
        <line x1="0" y1={SIZE / 2} x2={SIZE} y2={SIZE / 2} stroke="#e0e7ff" strokeWidth="1.5" strokeDasharray="6 6" />
        <line x1={SIZE / 2} y1="0" x2={SIZE / 2} y2={SIZE} stroke="#e0e7ff" strokeWidth="1.5" strokeDasharray="6 6" />
      </svg>
      <canvas
        ref={canvasRef}
        width={SIZE}
        height={SIZE}
        style={{ width: SIZE, height: SIZE, touchAction: 'none' }}
        className="relative rounded-2xl"
        aria-label="Handwriting area: write the missing character here"
        role="img"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={finishStroke}
        onPointerCancel={finishStroke}
        onPointerLeave={finishStroke}
      />
    </div>
  );
}
