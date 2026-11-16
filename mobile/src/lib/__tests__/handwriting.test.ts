import { resample, normalise, strokeCost, targetStrokes, gradeHandwriting, type CharacterData, type Stroke } from '../handwriting';

describe('resample', () => {
  it('单点笔画重复 n 次', () => {
    expect(resample([[0, 0]], 4)).toEqual([[0, 0], [0, 0], [0, 0], [0, 0]]);
  });

  it('直线等距取点', () => {
    const s = resample([[0, 0], [10, 0], [20, 0]], 3);
    expect(s).toHaveLength(3);
    expect(s[0]).toEqual([0, 0]);
    expect(s[2]).toEqual([20, 0]);
    expect(s[1][0]).toBeCloseTo(10);
  });
});

describe('normalise', () => {
  it('按外框归一到 0–1 并居中', () => {
    const s = normalise([[[0, 0], [10, 0]]]);
    expect(s[0][0][0]).toBeCloseTo(0);
    expect(s[0][1][0]).toBeCloseTo(1);
    // 宽度 10、高度 0，size 取 10，y 居中到 0.5
    expect(s[0][0][1]).toBeCloseTo(0.5);
  });
});

describe('strokeCost', () => {
  it('正反方向取小，反向笔画偏差为 0', () => {
    const a: Stroke = [[0, 0], [1, 0]];
    const b: Stroke = [[1, 0], [0, 0]];
    expect(strokeCost(a, b)).toBeCloseTo(0);
  });
});

describe('targetStrokes', () => {
  it('y 轴翻转（900 - y）', () => {
    const d: CharacterData = { strokes: [''], medians: [[[100, 800], [200, 850]]] };
    expect(targetStrokes(d)).toEqual([[[100, 100], [200, 50]]]);
  });
});

describe('gradeHandwriting', () => {
  // 一横：单笔，沿基线 800 从左到右
  const heng: CharacterData = {
    strokes: [''],
    medians: [[[50, 800], [500, 800], [950, 800]]],
  };

  it('空笔画判错', () => {
    const r = gradeHandwriting([], heng);
    expect(r.correct).toBe(false);
    expect(r.expected).toBe(1);
    expect(r.matched).toBe(0);
  });

  it('标准笔画判对', () => {
    const drawn = targetStrokes(heng);
    const r = gradeHandwriting(drawn, heng);
    expect(r.correct).toBe(true);
    expect(r.matched).toBe(1);
  });

  it('写成别的笔画判错', () => {
    const shu: Stroke[] = [[[450, 100], [450, 500], [450, 900]]];
    const r = gradeHandwriting(shu, heng);
    expect(r.correct).toBe(false);
  });
});
