import React from 'react';

interface CollocationTextProps {
  /** 数据库里的原始搭配，如「容易（三级）发生」「重视 文化（三级）」 */
  text: string;
  /** 要高亮的目标词 */
  target: string;
}

const LEVEL_MARK = /（([^）]*)）/;

/**
 * 渲染一条搭配：目标词就地高亮，「（三级）」这类等级标注显示为它原本位置上的小标签。
 *
 * 此前三个学习页各自按「前缀（等级）后缀」拆分后再把目标词追加到末尾，
 * 目标词在等级标注之前时（「重视 文化（三级）」）会显示两遍：「重视 文化 (三级) 重视」。
 */
export default function CollocationText({ text, target }: CollocationTextProps) {
  // split 带捕获组：偶数位是正文，奇数位是等级
  const pieces = text.split(LEVEL_MARK);
  const hasTarget = Boolean(target) && text.includes(target);
  const nodes: React.ReactNode[] = [];

  pieces.forEach((piece, i) => {
    if (i % 2 === 1) {
      nodes.push(
        <span key={`level-${i}`} className="text-base text-indigo-700 bg-indigo-50 px-1.5 rounded">
          ({piece})
        </span>
      );
      return;
    }
    const chunks = hasTarget ? piece.split(target) : [piece];
    chunks.forEach((chunk, j) => {
      if (j > 0) {
        nodes.push(
          <span key={`target-${i}-${j}`} className="text-indigo-600 font-bold">{target}</span>
        );
      }
      if (chunk.trim()) {
        nodes.push(<span key={`text-${i}-${j}`}>{chunk.trim()}</span>);
      }
    });
  });

  // 少数搭配的原文里不含目标词，沿用原先的做法补在末尾
  if (!hasTarget && target) {
    nodes.push(<span key="target-tail" className="text-indigo-600 font-bold">{target}</span>);
  }

  return <>{nodes}</>;
}
