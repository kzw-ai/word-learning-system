import { parseFillHint, completeSentence } from '../fillHint';

describe('parseFillHint', () => {
  it('无括号提示时原样返回', () => {
    expect(parseFillHint('你好世界')).toEqual({ stem: '你好世界', hint: null, initialOnly: false });
  });

  it('声母提示（不带声调、短）标记 initialOnly', () => {
    const r = parseFillHint('我不明白，为什么 ( d ) 有人叫我“奶奶”？');
    expect(r.stem).toBe('我不明白，为什么 ( ) 有人叫我“奶奶”？');
    expect(r.hint).toBe('d');
    expect(r.initialOnly).toBe(true);
  });

  it('完整拼音提示标记非 initialOnly', () => {
    const r = parseFillHint('这是 (yīn) 的字');
    expect(r.hint).toBe('yīn');
    expect(r.initialOnly).toBe(false);
  });
});

describe('completeSentence', () => {
  it('把答案填回空位并去掉两边空格', () => {
    expect(completeSentence('为什么 ( ) 有人', '都')).toBe('为什么都有人');
  });
});
