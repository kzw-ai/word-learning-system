// 源文件：src/lib/reviewTime.ts（网页版）。纯逻辑，改动需与网页版同步。
// 注意：Hermes 的 Intl 行为与浏览器可能不同，显示格式等真机验证后再定。
// 后端给的复习时间是 SQLite 的 UTC 字符串（'2026-10-31 08:15:00'），按学习者本地时间显示
export const formatReviewTime = (utc: string): string => {
  const date = new Date(`${utc.trim().replace(' ', 'T')}Z`);
  if (Number.isNaN(date.getTime())) return 'soon';
  const time = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const today = new Date();
  const tomorrow = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1);
  if (date.toDateString() === today.toDateString()) return `today at ${time}`;
  if (date.toDateString() === tomorrow.toDateString()) return `tomorrow at ${time}`;
  return `on ${date.toLocaleDateString([], { month: 'short', day: 'numeric' })} at ${time}`;
};
