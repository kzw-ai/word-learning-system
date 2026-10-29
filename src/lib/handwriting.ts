// 填字题的手写判分（论文 3.2 节：学习者手写，系统判断对错）。
// 不用 Hanzi Writer 自带的测验：它要求严格按笔顺一笔一笔写，中级学习者不一定按标准笔顺写，会一直卡住。
// 这里按「字写出来了、笔画大体对」判：学习者写下的每一笔和答案字的标准笔画（hanzi-writer-data 的笔画中线
// medians）逐一配对，不看先后、不看正着写还是反着写，大小和位置按各自的外框归一。
// 写成别的字时笔画对不上，判错。

export type Point = [number, number];
export type Stroke = Point[];

export interface CharacterData {
  strokes: string[];
  medians: Point[][];
}

export interface HandwritingResult {
  correct: boolean;
  /** 标准笔画数、配上的笔画数、多写（没配上）的笔画数 */
  expected: number;
  matched: number;
  extra: number;
  /** 配上的笔画的平均偏差（以外框边长为 1） */
  meanCost: number;
}

const SAMPLES = 16;
// 一笔算「对上」的最大偏差；整字平均偏差上限。以外框边长为 1，经验值，见 tests/handwriting 的样例
const MATCH_COST = 0.2;
const MEAN_COST = 0.13;

const dist = (a: Point, b: Point) => Math.hypot(a[0] - b[0], a[1] - b[1]);

/** 沿笔画按长度等距取 n 个点；一个点的笔画（点击）重复这个点 */
export const resample = (stroke: Stroke, n = SAMPLES): Stroke => {
  if (stroke.length === 0) return [];
  if (stroke.length === 1) return Array.from({ length: n }, () => stroke[0]);
  const lengths = [0];
  for (let i = 1; i < stroke.length; i += 1) lengths.push(lengths[i - 1] + dist(stroke[i - 1], stroke[i]));
  const total = lengths[lengths.length - 1];
  if (total === 0) return Array.from({ length: n }, () => stroke[0]);
  const out: Stroke = [];
  let j = 1;
  for (let k = 0; k < n; k += 1) {
    const target = (total * k) / (n - 1);
    while (j < stroke.length - 1 && lengths[j] < target) j += 1;
    const span = lengths[j] - lengths[j - 1] || 1;
    const t = Math.min(1, Math.max(0, (target - lengths[j - 1]) / span));
    out.push([
      stroke[j - 1][0] + (stroke[j][0] - stroke[j - 1][0]) * t,
      stroke[j - 1][1] + (stroke[j][1] - stroke[j - 1][1]) * t,
    ]);
  }
  return out;
};

/** 所有笔画一起按外框归一到 0–1（保持长宽比，居中），写大写小、偏一点都不影响 */
export const normalise = (strokes: Stroke[]): Stroke[] => {
  const all = strokes.flat();
  if (all.length === 0) return strokes;
  const xs = all.map(p => p[0]);
  const ys = all.map(p => p[1]);
  const minX = Math.min(...xs);
  const minY = Math.min(...ys);
  const w = Math.max(...xs) - minX;
  const h = Math.max(...ys) - minY;
  const size = Math.max(w, h) || 1;
  const offX = (size - w) / 2;
  const offY = (size - h) / 2;
  return strokes.map(s => s.map(([x, y]) => [(x - minX + offX) / size, (y - minY + offY) / size] as Point));
};

/** 两笔的偏差：等距取点后的平均点距，正着、反着取小的（笔画方向不限） */
export const strokeCost = (a: Stroke, b: Stroke) => {
  const forward = a.reduce((sum, p, i) => sum + dist(p, b[i]), 0) / a.length;
  const backward = a.reduce((sum, p, i) => sum + dist(p, b[b.length - 1 - i]), 0) / a.length;
  return Math.min(forward, backward);
};

/** hanzi-writer-data 的坐标：1024 见方，y 轴朝上（基线在 900）。换成 y 朝下，和屏幕一致 */
export const targetStrokes = (data: CharacterData): Stroke[] =>
  data.medians.map(m => m.map(([x, y]) => [x, 900 - y] as Point));

export const gradeHandwriting = (drawn: Stroke[], data: CharacterData): HandwritingResult => {
  const target = normalise(targetStrokes(data)).map(s => resample(s));
  const user = normalise(drawn.filter(s => s.length > 0)).map(s => resample(s));
  const expected = target.length;
  if (user.length === 0) return { correct: false, expected, matched: 0, extra: 0, meanCost: 1 };

  // 所有（写的笔, 标准笔）按偏差从小到大配对，每笔只用一次
  const pairs: { u: number; t: number; cost: number }[] = [];
  user.forEach((u, ui) => target.forEach((t, ti) => pairs.push({ u: ui, t: ti, cost: strokeCost(u, t) })));
  pairs.sort((a, b) => a.cost - b.cost);
  const usedU = new Set<number>();
  const usedT = new Set<number>();
  const costs: number[] = [];
  for (const { u, t, cost } of pairs) {
    if (cost > MATCH_COST) break;
    if (usedU.has(u) || usedT.has(t)) continue;
    usedU.add(u);
    usedT.add(t);
    costs.push(cost);
  }
  const matched = costs.length;
  const extra = user.length - matched;
  const meanCost = matched ? costs.reduce((a, b) => a + b, 0) / matched : 1;
  // 宽松：笔画多的字允许一两笔对不上（连笔、把一笔写成两笔、漏一笔）；漏写和多写合起来算。
  // 笔画少的字不放宽，否则「一」写成「十」、「大」写成「太」也算对
  const allowed = expected >= 11 ? 2 : expected >= 6 ? 1 : 0;
  const correct = (expected - matched) + extra <= allowed && meanCost <= MEAN_COST;
  return { correct, expected, matched, extra, meanCost };
};

const cache = new Map<string, Promise<CharacterData>>();

/** 按字取笔画数据（构建时复制到 public/hanzi-data/，见 scripts/copy_hanzi_data.js） */
export const loadCharacterData = (char: string): Promise<CharacterData> => {
  if (!cache.has(char)) {
    const request = fetch(`/hanzi-data/${encodeURIComponent(char)}.json`).then(resp => {
      if (!resp.ok) throw new Error(`no stroke data for ${char}`);
      return resp.json() as Promise<CharacterData>;
    });
    request.catch(() => cache.delete(char));
    cache.set(char, request);
  }
  return cache.get(char)!;
};
