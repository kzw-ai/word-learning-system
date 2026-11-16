import { splitGap, DEFAULT_IDLE_CAP_SECONDS } from '../activeTime';

describe('splitGap', () => {
  it('间隔小于上限时全算有效', () => {
    expect(splitGap(50000, 90000)).toEqual({ activeMs: 50000, idleMs: 0 });
  });

  it('间隔超过上限时拆出 idle', () => {
    expect(splitGap(120000, 90000)).toEqual({ activeMs: 90000, idleMs: 30000 });
  });

  it('负间隔按 0 处理', () => {
    expect(splitGap(-1000, 90000)).toEqual({ activeMs: 0, idleMs: 0 });
  });

  it('默认上限为 90 秒', () => {
    expect(DEFAULT_IDLE_CAP_SECONDS).toBe(90);
  });
});
