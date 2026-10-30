"""版面检查：在一台手机上走一遍学习者会看到的页面和主要状态（新手引导、答错、打字和键盘、Recap 展开、
第二个词的汉字页、登录注册……），每一步截图，并自动量出常见的版面问题。量不出「好不好看」，截图要人看。

  python3 tests/mobile/audit.py ios <模拟器 UDID> <名字>
  python3 tests/mobile/audit.py android [名字]
  python3 tests/mobile/audit.py report            # 把各台的结果汇总成 .review/layout/报告.md

截图和每台的结果在 .review/layout/（MOBILE_OUT 可改）。前置准备同 walk.py，见 docs/core/测试文档.md。
"""
import json
import os
import re
import sys
import time
from pathlib import Path

from drivers import AndroidDriver, IOSDriver
from walk import ONBOARDING_JS, ROOT, Walk

OUT = Path(os.environ.get('MOBILE_OUT', ROOT / '.review' / 'layout'))

# 每一步量的东西：横向溢出、文字超出屏幕、字号 < 14px、点按目标 < 36px、被截断的文字、
# 被别的元素盖住的文字（取文字中心点上最上层的元素）、各滚动区域还藏着多少内容
MEASURE_JS = r"""() => {
  const vw = innerWidth, vh = innerHeight;
  const shown = e => { const cs = getComputedStyle(e), r = e.getBoundingClientRect();
    return cs.display !== 'none' && cs.visibility !== 'hidden' && +cs.opacity > 0.05 && r.width > 0 && r.height > 0; };
  const onScreen = r => r.bottom > 0 && r.top < vh && r.right > 0 && r.left < vw;
  const label = e => (e.innerText || e.getAttribute('aria-label') || e.getAttribute('placeholder') || e.tagName)
    .replace(/\s+/g, ' ').trim().slice(0, 40);
  const ownText = e => [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
  const texts = [...document.querySelectorAll('body *')].filter(e => ownText(e) && shown(e) && onScreen(e.getBoundingClientRect()));
  const uniq = a => [...new Set(a)];
  const se = document.scrollingElement;
  return {
    path: location.pathname, viewport: [vw, vh],
    overflowX: Math.max(0, se.scrollWidth - vw),
    offscreenText: uniq(texts.filter(e => { const r = e.getBoundingClientRect(); return r.right > vw + 1 || r.left < -1; }).map(label)),
    smallText: uniq(texts.filter(e => parseFloat(getComputedStyle(e).fontSize) < 14)
      .map(e => `${label(e)} (${getComputedStyle(e).fontSize})`)),
    smallTargets: uniq([...document.querySelectorAll('button, a, [role=button], [role=radio], input, select, textarea')]
      .filter(e => shown(e) && onScreen(e.getBoundingClientRect()) && !getComputedStyle(e).clip.startsWith('rect(0'))
      .filter(e => { const r = e.getBoundingClientRect(); return r.height < 36 || r.width < 36; })
      .map(e => { const r = e.getBoundingClientRect(); return `${label(e)} (${Math.round(r.width)}×${Math.round(r.height)})`; })),
    clippedText: uniq(texts.filter(e => e.scrollWidth > e.clientWidth + 1 && ['hidden', 'clip'].includes(getComputedStyle(e).overflowX)).map(label)),
    coveredText: uniq(texts.filter(e => { const r = e.getBoundingClientRect();
      const x = Math.min(Math.max(r.left + r.width / 2, 1), vw - 1), y = Math.min(Math.max(r.top + r.height / 2, 1), vh - 1);
      const top = document.elementFromPoint(x, y); return top && !e.contains(top) && !top.contains(e); }).map(label)),
    hiddenByScroll: [se, ...document.querySelectorAll('body *')].filter(e => e === se
        ? e.scrollHeight > e.clientHeight + 1
        : ['auto', 'scroll'].includes(getComputedStyle(e).overflowY) && e.scrollHeight > e.clientHeight + 1 && shown(e))
      .map(e => ({area: e === se ? 'page' : String(e.className).slice(0, 50), px: e.scrollHeight - e.clientHeight})),
  };
}"""
# 美学指标：文字对比度（WCAG：正文 4.5、大字 3）、大块空白（相邻内容之间空出 15% 屏高以上）、左边缘差 1–6px 的没对齐、
# 一屏的字号 / 字重 / 文字颜色种数、抢眼的主按钮个数、最大的字是谁
AESTHETIC_JS = r"""() => {
  const vw = innerWidth, vh = innerHeight;
  const shown = e => { const cs = getComputedStyle(e), r = e.getBoundingClientRect();
    return cs.display !== 'none' && cs.visibility !== 'hidden' && +cs.opacity > 0.05 && r.width > 0 && r.height > 0; };
  const onScreen = r => r.bottom > 0 && r.top < vh && r.right > 0 && r.left < vw;
  const label = e => (e.innerText || e.getAttribute('aria-label') || e.tagName).replace(/\s+/g, ' ').trim().slice(0, 30);
  const ownText = e => [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
  const texts = [...document.querySelectorAll('body *')].filter(e => ownText(e) && shown(e) && onScreen(e.getBoundingClientRect()));
  const parse = c => { const m = (c || '').match(/rgba?\(([^)]+)\)/); if (!m) return null;
    const v = m[1].split(/[\s,\/]+/).filter(Boolean).map(Number); return [v[0], v[1], v[2], v.length > 3 ? v[3] : 1]; };
  const over = (top, base) => base.map((b, i) => top[i] * top[3] + b * (1 - top[3]));
  const background = e => {
    const layers = [];
    for (let n = e; n; n = n.parentElement) {
      const cs = getComputedStyle(n);
      const c = parse(cs.backgroundColor);
      if (c && c[3] > 0) { layers.push(c); if (c[3] >= 1) break; }
      const stops = (cs.backgroundImage.match(/rgba?\([^)]+\)/g) || []).map(parse);
      if (stops.length) { const avg = [0, 1, 2, 3].map(i => stops.reduce((s, x) => s + x[i], 0) / stops.length); layers.push(avg); if (avg[3] >= 1) break; }
    }
    return layers.reverse().reduce((base, l) => over(l, base), [255, 255, 255]);
  };
  const opacity = e => { let o = 1; for (let n = e; n; n = n.parentElement) o *= +getComputedStyle(n).opacity; return o; };
  const lum = c => { const [r, g, b] = c.map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const lowContrast = [];
  for (const e of texts) {
    if (e.closest(':disabled, [aria-disabled=true], [aria-hidden=true]')) continue;  // WCAG 不要求禁用控件和纯装饰
    const cs = getComputedStyle(e), bg = background(e), fg = parse(cs.color);
    if (!fg || cs.backgroundClip === 'text' || cs.webkitBackgroundClip === 'text') continue;  // 渐变字量不准，跳过
    const text = over([...fg.slice(0, 3), fg[3] * opacity(e)], bg);
    const size = parseFloat(cs.fontSize), large = size >= 24 || (size >= 18.66 && +cs.fontWeight >= 700);
    const ratio = contrast(text, bg);
    if (ratio < (large ? 3 : 4.5)) lowContrast.push(`${label(e)} ${ratio.toFixed(2)}`);
  }
  const blocks = [...document.querySelectorAll('body *')].filter(e => shown(e) && onScreen(e.getBoundingClientRect())
      && (ownText(e) || ['BUTTON', 'INPUT', 'IMG', 'CANVAS', 'svg', 'TEXTAREA'].includes(e.tagName)))
    .map(e => e.getBoundingClientRect()).map(r => [Math.max(0, r.top), Math.min(vh, r.bottom)]).sort((a, b) => a[0] - b[0]);
  const merged = [];
  for (const [t, b] of blocks) { const last = merged[merged.length - 1]; if (last && t <= last[1]) last[1] = Math.max(last[1], b); else merged.push([t, b]); }
  // 吸在屏幕底部的按钮栏：它上方的空档是「内容在上、工具栏在下」的固有空档，单独记，不算失衡
  const bars = [...document.querySelectorAll('body *')].filter(e => ['sticky', 'fixed'].includes(getComputedStyle(e).position) && shown(e))
    .map(e => e.getBoundingClientRect()).filter(r => r.bottom >= vh - 60 && r.height < vh * 0.3);
  const barTop = bars.length ? Math.min(...bars.map(r => r.top)) : Infinity;
  const gaps = [], toolbarGaps = [];
  for (let i = 1; i < merged.length; i++) {
    const g = merged[i][0] - merged[i - 1][1];
    if (g <= vh * 0.15) continue;
    (merged[i][0] >= barTop - 2 ? toolbarGaps : gaps).push(`${Math.round(g)}px（${Math.round(merged[i - 1][1])}–${Math.round(merged[i][0])}）`);
  }
  // 对齐只看正文里左对齐的文字：按钮里、居中的文字本来就不和正文左边对齐
  const prose = texts.filter(e => !e.closest('button, a, [role=button], label, summary') && ['start', 'left'].includes(getComputedStyle(e).textAlign)
    && !['center'].includes(getComputedStyle(e.parentElement).justifyContent)
    && !(getComputedStyle(e.parentElement).display.includes('flex') && getComputedStyle(e.parentElement).flexDirection === 'column'
         && getComputedStyle(e.parentElement).alignItems === 'center'));
  const byEdge = new Map();
  for (const e of prose) { const x = Math.round(e.getBoundingClientRect().left); if (x < vw * 0.3 && !byEdge.has(x)) byEdge.set(x, label(e)); }
  const edges = [...byEdge.keys()].sort((a, b) => a - b);
  const misaligned = edges.filter((x, i) => i && x - edges[i - 1] >= 1 && x - edges[i - 1] <= 6)
    .map(x => { const p = edges[edges.indexOf(x) - 1]; return `${p}「${byEdge.get(p)}」/${x}「${byEdge.get(x)}」`; });
  const styles = texts.map(e => getComputedStyle(e));
  const sizes = [...new Set(styles.map(s => s.fontSize))], weights = [...new Set(styles.map(s => s.fontWeight))];
  const colors = [...new Set(styles.map(s => s.color))];
  const primary = [...document.querySelectorAll('button, a')].filter(e => shown(e) && !e.disabled && onScreen(e.getBoundingClientRect())).filter(e => {
    const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
    return r.width >= vw * 0.5 && r.height >= 40 && (cs.backgroundImage.includes('gradient') || (parse(cs.backgroundColor) || [0, 0, 0, 0])[3] > 0.9
      && Math.max(...parse(cs.backgroundColor).slice(0, 3)) - Math.min(...parse(cs.backgroundColor).slice(0, 3)) > 60); }).map(label);
  const biggest = texts.reduce((m, e) => parseFloat(getComputedStyle(e).fontSize) > (m ? parseFloat(getComputedStyle(m).fontSize) : 0) ? e : m, null);
  return {lowContrast, bigGaps: gaps, toolbarGaps, bottomEmpty: Math.round(vh - (merged.length ? merged[merged.length - 1][1] : 0)),
          misaligned, fontSizes: sizes, fontWeights: weights, textColors: colors.length, primaryButtons: primary,
          biggestText: biggest ? `${label(biggest)} (${getComputedStyle(biggest).fontSize})` : ''};
}"""
SCROLL_JS ="""(toBottom) => { [document.scrollingElement, ...document.querySelectorAll('body *')]
  .filter(e => e.scrollHeight > e.clientHeight + 1).forEach(e => { e.scrollTop = toBottom ? e.scrollHeight : 0; }); }"""
BLUR_JS = '() => document.activeElement && document.activeElement.blur()'


class Audit(Walk):
    def __init__(self, driver, name):
        super().__init__(driver, name)
        self.records = []

    def capture(self, step, note=''):
        time.sleep(0.8)
        m = self.d.eval(MEASURE_JS)
        m['aesthetics'] = self.d.eval(AESTHETIC_JS)
        m.update(step=step, note=note, shots=[f'{self.name}-{step}.png'])
        self.shot(step)
        # 还有超过 40px 的内容要滚动才看得到：滚到底再截一张，再滚回去
        if any(s['px'] > 40 for s in m['hiddenByScroll']):
            self.d.eval(SCROLL_JS, True)
            time.sleep(0.8)
            self.shot(f'{step}-bottom')
            m['shots'].append(f'{self.name}-{step}-bottom.png')
            self.d.eval(SCROLL_JS, False)
            time.sleep(0.4)
        self.records.append(m)
        print(f'{self.name}: {step} {m["path"]}', flush=True)

    def segment(self, label, fn):
        """一段出错不影响后面几段：记下错误和当时的截图，接着走"""
        try:
            fn()
        except Exception as e:
            print(f'{self.name}: ERROR in {label}: {e!r}', flush=True)
            self.records.append({'step': f'error-{label}', 'error': repr(e), 'path': self.path(), 'shots': []})
            try:
                self.capture(f'error-{label}', f'出错：{e!r}')
            except Exception:
                pass

    def wrong_option(self, right):
        """页面上还能点的（没被划掉的）选项里，挑一个错的"""
        return self.d.eval("""(right) => [...document.querySelectorAll('button')].filter(b => !b.disabled)
          .map(b => b.querySelectorAll('span span'))
          .filter(s => s.length >= 2 && /^[A-Z]\\.$/.test(s[0].textContent.trim())).map(s => s[1].textContent.trim())
          .find(t => t !== right)""", right)

    def answer(self, text):
        self.tap('text', r'^(\w\. )?' + re.escape(text) + '$', 0.8)
        self.tap('text', r'^CHECK$', 1.8)

    def first_word(self):
        d = self.d
        d.goto('/learning-dashboard')
        self.locate('text', r'^Start now$')
        self.capture('03-dashboard', '新访客的看板')
        self.tap('text', r'^Start now$', 2.5)
        self.word_id = d.eval("() => new URLSearchParams(location.search).get('wordId')")
        self.tap('text', r'^I know what it means, but not which words go with it\.$', 0.8)
        self.capture('04-self-check', '自评页，选中一项')
        self.tap('text', r'^I have never seen this word\.$', 0.8)
        self.tap('text', r'^CONTINUE$', 3)
        self.capture('05-first-step', '自评选「没见过」后的第一步（单字词是词语页）')
        self.swipe('left')
        self.capture('06-collocations', '搭配页')
        while self.path() != '/sentence-learning':
            self.swipe('left')
        self.capture('07-sentences', '例句页')
        self.tap('text', r'^Recap:', 1.2)
        self.capture('07b-sentences-recap', '例句页，展开 Recap')
        self.swipe('left')
        time.sleep(1)

    def exercises(self):
        d = self.d
        questions = d.eval("(id) => fetch(`/api/learning/word/${id}/exercises?limit=5`).then(r => r.json()).then(r => r.data.questions)",
                           self.word_id)
        shown_right = False
        for i, q in enumerate(questions):
            if q['type'] == 'fill_word':
                self.capture('10-fill-handwriting', '填字题，手写')
                self.tap('text', r'^Type instead$', 1)
                self.tap('css', 'input[placeholder="Type here"]', 1.5)
                self.capture('11-fill-typing-keyboard', '填字题改打字，点输入框（安卓弹键盘；iOS 模拟器默认接硬件键盘，不弹）')
                # 只为截「答错」的样子：直接在页面里填值并发出 React 认的 input 事件（打字本身由 e2e 旅程测试覆盖；
                # 各平台的打字通道在模拟器上不稳：iOS WebDriver 发字不生效，安卓输入法首次会弹手写笔教程）
                d.eval("""(v) => { const el = document.querySelector('input[data-fill-input]');
                  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v);
                  el.dispatchEvent(new Event('input', {bubbles: true})); }""", 'x')
                d.eval(BLUR_JS)
                time.sleep(0.8)
                self.tap('text', r'^CHECK$', 1.8)
                self.capture('12-fill-wrong', '填字题答错')
            elif i == 0:
                self.capture('08-question', f'选择题（{q["type"]}）')
                # 第一次选错先不揭晓，划掉再选；再错才揭晓。干扰项每次请求都重新随机，从页面上还能点的选项里挑错的
                self.answer(self.wrong_option(q['correctAnswer']))
                self.capture('09-choice-again', '选择题第一次选错：划掉，再选一次')
                self.answer(self.wrong_option(q['correctAnswer']))
                self.capture('09-choice-wrong', '选择题第二次还错：揭晓答案')
            else:
                self.answer(q['correctAnswer'])
                if not shown_right:
                    self.capture('09b-choice-right', '选择题答对')
                    shown_right = True
            self.tap('text', r'^CONTINUE$', 2.5)
        # 第一次答错的题在一轮最后再考一次（Once more）：答对
        fill = next((q['correctAnswer'] for q in questions if q['type'] == 'fill_word'), None)
        for k in range(len(questions)):
            if 'Once more' not in self.body():
                break
            if k == 0:
                self.capture('12b-once-more', '一轮最后再考答错过的题')
            if d.eval("() => !!document.querySelector('input[data-fill-input]')"):
                d.eval("""(v) => { const el = document.querySelector('input[data-fill-input]');
                  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v);
                  el.dispatchEvent(new Event('input', {bubbles: true})); }""", fill)
                d.eval(BLUR_JS)
                self.tap('text', r'^CHECK$', 1.8)
            else:
                right = next(q['correctAnswer'] for q in questions if q['type'] != 'fill_word'
                             and q['correctAnswer'] in self.body() and q['question'][:6] in self.body())
                self.answer(right)
            self.tap('text', r'^CONTINUE$', 2.5)
        time.sleep(1.5)
        self.capture('13-after-word', '一个词的练习做完之后')

    def second_word(self):
        d = self.d
        d.goto('/learning-dashboard')
        self.locate('text', r'^Start now$')
        self.capture('14-dashboard-after-one', '学完一个词后的看板')
        self.tap('text', r'^Start now$', 2.5)
        self.tap('text', r'^I have never seen this word\.$', 0.8)
        self.tap('text', r'^CONTINUE$', 3)
        self.capture('15-word2-first-step', '第二个词，自评「没见过」后的第一步（多字词是汉字页）')
        self.tap('text', r'^Recap:', 1.2) if self.d.eval(
            "() => [...document.querySelectorAll('summary')].some(s => s.textContent.startsWith('Recap'))") else None

    def other_pages(self):
        d = self.d
        for step, path, note in [('16-today-review', '/today-review', '今日复习'), ('17-learning-stats', '/learning-stats', '学习统计'),
                                 ('18-login', '/login', '登录'), ('19-register', '/register', '注册')]:
            d.goto(path)
            time.sleep(2.5)
            self.capture(step, note)
        d.goto('/login')
        time.sleep(2)
        self.tap('css', 'input', 1.5)
        self.capture('18b-login-keyboard', '登录，点输入框')
        d.eval(BLUR_JS)

    def run(self):
        d = self.d
        d.goto('/')
        time.sleep(2)
        d.eval("() => { localStorage.clear(); sessionStorage.clear(); document.cookie = 'guest_id=; Max-Age=0; path=/'; }")
        d.goto('/')
        time.sleep(3)
        self.capture('01-onboarding', '新手引导第 1 步')
        for _ in range(4):
            if not d.eval(ONBOARDING_JS):
                break
            time.sleep(1)
        self.capture('02-home', '首页')
        self.segment('first-word', self.first_word)
        self.segment('exercises', self.exercises)
        self.segment('second-word', self.second_word)
        self.segment('other-pages', self.other_pages)


def report():
    """各台的结果 → 一份 Markdown：每一步三台截图并排，下面列自动量出的问题"""
    runs = {p.stem: json.loads(p.read_text()) for p in sorted(OUT.glob('*.json'))}
    steps = []
    for recs in runs.values():
        for r in recs:
            if r['step'] not in steps:
                steps.append(r['step'])
    steps.sort()
    labels = {'overflowX': '横向溢出(px)', 'offscreenText': '文字超出屏幕', 'smallText': '字号 < 14px',
              'smallTargets': '点按目标 < 36px', 'clippedText': '文字被截断', 'coveredText': '文字被盖住'}
    lines = ['# 版面检查', '', f'设备：{"、".join(runs)}。截图下面是脚本自动量出的问题；「好不好看」要看截图。', '']
    for step in steps:
        recs = {name: next((r for r in recs if r['step'] == step), None) for name, recs in runs.items()}
        note = next((r.get('note') for r in recs.values() if r and r.get('note')), '')
        lines += [f'## {step} {note}', '', '<table><tr>']
        for name, r in recs.items():
            imgs = ''.join(f'<img src="{s}" width="200"> ' for s in (r or {}).get('shots', []))
            lines.append(f'<td valign="top"><b>{name}</b> <code>{(r or {}).get("path", "")}</code><br>{imgs or "（没走到）"}</td>')
        lines += ['</tr></table>', '']
        for name, r in recs.items():
            if not r:
                continue
            found = [f'{labels[k]}：{r[k] if k == "overflowX" else "；".join(r[k])}' for k in labels if r.get(k)]
            found += [f'要滚动：{s["area"] or "?"} 藏了 {s["px"]}px' for s in r.get('hiddenByScroll', [])]
            a = r.get('aesthetics') or {}
            if a.get('lowContrast'):
                found.append('对比度不足：' + '；'.join(a['lowContrast']))
            if a.get('bigGaps'):
                found.append('大块空白：' + '；'.join(a['bigGaps']))
            if a.get('misaligned'):
                found.append('左边缘差几像素没对齐：' + '；'.join(a['misaligned']))
            if len(a.get('fontSizes', [])) > 5:
                found.append(f'字号 {len(a["fontSizes"])} 种：' + ' '.join(a['fontSizes']))
            if a.get('textColors', 0) > 6:
                found.append(f'文字颜色 {a["textColors"]} 种')
            if len(a.get('primaryButtons', [])) > 1:
                found.append('抢眼的主按钮不止一个：' + '；'.join(a['primaryButtons']))
            if r.get('error'):
                found.insert(0, f'出错：{r["error"]}')
            if found:
                lines.append(f'- **{name}**：' + ' ／ '.join(found))
        lines.append('')
    (OUT / '报告.md').write_text('\n'.join(lines))
    print(OUT / '报告.md')


def main():
    platform, *rest = sys.argv[1:]
    if platform == 'report':
        report()
        return
    OUT.mkdir(parents=True, exist_ok=True)
    base = os.environ.get('BASE_URL', 'http://localhost:3100')
    if platform == 'ios':
        udid, name = rest
        driver = IOSDriver(udid, os.environ.get('WD_PORT', '4723'), base, str(OUT))
    else:
        name = rest[0] if rest else 'android'
        driver = AndroidDriver(base, str(OUT))
    audit = Audit(driver, name)
    try:
        audit.run()
    finally:
        (OUT / f'{name}.json').write_text(json.dumps(audit.records, ensure_ascii=False, indent=1))
        driver.close()


if __name__ == '__main__':
    main()
