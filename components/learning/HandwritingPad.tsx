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
    // 像素缓冲按实际显示大小定（各屏幕上框的大小不同），笔画坐标仍按 SIZE 画
    const ratio = (window.devicePixelRatio || 1) * ((canvas.clientWidth || SIZE) / SIZE);
    if (canvas.width !== Math.round(SIZE * ratio)) {
      canvas.width = Math.round(SIZE * ratio);
      canvas.height = Math.round(SIZE * ratio);
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
    // 显示尺寸：矮屏（iPhone SE 这类）上小一号，高屏手机上大一号；笔画坐标始终按 SIZE 记录（point() 按实际显示大小换算）
    <div className={`relative rounded-2xl border-2 bg-white w-[240px] h-[240px] short:w-[196px] short:h-[196px] roomy:w-[280px] roomy:h-[280px] ${border}`}>
      {/* 田字格 */}
      <svg className="absolute inset-0 pointer-events-none w-full h-full" viewBox={`0 0 ${SIZE} ${SIZE}`} aria-hidden="true">
        <line x1="0" y1={SIZE / 2} x2={SIZE} y2={SIZE / 2} stroke="#e0e7ff" strokeWidth="1.5" strokeDasharray="6 6" />
        <line x1={SIZE / 2} y1="0" x2={SIZE / 2} y2={SIZE} stroke="#e0e7ff" strokeWidth="1.5" strokeDasharray="6 6" />
      </svg>
      <canvas
        ref={canvasRef}
        width={SIZE}
        height={SIZE}
        style={{ width: '100%', height: '100%', touchAction: 'none' }}
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

/** 答完以后把学习者写的字缩小显示（和手写格同一套坐标、同样的田字格），和标准写法并排对照 */
export function HandwritingThumb({ strokes, size, result }: { strokes: Stroke[]; size: number; result: 'correct' | 'wrong' }) {
  const path = (stroke: Stroke) => stroke.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      className={`rounded-xl bg-white border-2 ${result === 'correct' ? 'border-emerald-600' : 'border-rose-500'}`}
      role="img"
      aria-label="Your writing"
    >
      <line x1="0" y1={SIZE / 2} x2={SIZE} y2={SIZE / 2} stroke="#e0e7ff" strokeWidth="2" strokeDasharray="8 8" />
      <line x1={SIZE / 2} y1="0" x2={SIZE / 2} y2={SIZE} stroke="#e0e7ff" strokeWidth="2" strokeDasharray="8 8" />
      {strokes.map((stroke, i) =>
        stroke.length === 1 ? (
          <circle key={i} cx={stroke[0][0]} cy={stroke[0][1]} r={4.5} fill="#1f2937" />
        ) : (
          <path key={i} d={path(stroke)} stroke="#1f2937" strokeWidth={9} fill="none" strokeLinecap="round" strokeLinejoin="round" />
        )
      )}
    </svg>
  );
}
