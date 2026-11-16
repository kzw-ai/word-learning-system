// 源文件：utils/activeTime.ts（网页版）。纯逻辑，改动需与网页版同步。
// 有效学习时长：两次操作之间的间隔，最多算一个上限。上限以内全部算有效，超出部分算离开。

/** 学习页（字、词、搭配、例句）：几行字加一个发音 */
export const DEFAULT_IDLE_CAP_SECONDS = 90;

/** 一段间隔里算作有效、算作离开的毫秒数 */
export function splitGap(gapMs: number, capMs: number): { activeMs: number; idleMs: number } {
  const gap = Math.max(0, gapMs);
  return { activeMs: Math.min(gap, capMs), idleMs: Math.max(0, gap - capMs) };
}
