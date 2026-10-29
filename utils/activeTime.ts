/**
 * 有效学习时长：两次操作（触屏、滑动、滚动、鼠标、键盘）之间的间隔，最多算一个上限。
 *
 * 读内容、想、听发音都不会产生操作，很多页面只有一个 Continue 按钮，所以不能把「没操作」当成离开；
 * 但页面开着、人走开了的时候，间隔会很长。上限以内全部算有效时长，超出的部分当作离开，另记一条
 * idle_gap 事件（离开从何时起、多长），以后可以按真实数据重新定上限再算。总时长照记不变。
 */

/** 学习页（字、词、搭配、例句）：几行字加一个发音 */
export const DEFAULT_IDLE_CAP_SECONDS = 90;

/** 一段间隔里算作有效、算作离开的毫秒数 */
export function splitGap(gapMs: number, capMs: number): { activeMs: number; idleMs: number } {
  const gap = Math.max(0, gapMs);
  return { activeMs: Math.min(gap, capMs), idleMs: Math.max(0, gap - capMs) };
}
