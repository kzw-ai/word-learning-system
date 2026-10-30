"""手机兼容性测试：在一台手机上用真实触摸走一遍学新词：看板「Start now」→ 自评 → 左右滑动切换学习步骤 →
例句发音 → 练习选择题 → 手写填字。用法、前置准备见 docs/core/测试文档.md「手机兼容性测试」。

  python3 tests/mobile/walk.py ios <模拟器 UDID> <名字>     # safaridriver 端口取 WD_PORT，默认 4723
  python3 tests/mobile/walk.py android [名字]               # 需要装了 playwright 的 Python
"""
import json
import os
import re
import sys
import time
from pathlib import Path

from drivers import AndroidDriver, IOSDriver

ROOT = Path(__file__).resolve().parents[2]
HANZI = ROOT / 'public' / 'hanzi-data'

# 找到元素、滚到屏幕中间、记在 window 上。文字按 textContent 比（innerText 会被 text-transform 改成大写），
# 取最里层匹配的元素；收起的 Recap 里的不算
FIND_JS = """(kind, query) => {
  const usable = e => !e.closest('details:not([open])') && e.getBoundingClientRect().width > 0;
  let el;
  if (kind === 'css') {
    el = [...document.querySelectorAll(query)].filter(usable).pop();
  } else {
    const re = new RegExp(query);
    const hits = [...document.querySelectorAll('button, a, label, [role=button], span, p, div, h1, h2, h3')]
      .filter(e => usable(e) && re.test(e.textContent.replace(/\\s+/g, ' ').trim()));
    el = hits.find(h => !hits.some(o => o !== h && h.contains(o)));
  }
  if (!el) return false;
  el.scrollIntoView({block: 'center'});
  window.__mobileTarget = el;
  return true;
}"""
TARGET_CENTRE_JS = """() => { const r = window.__mobileTarget.getBoundingClientRect();
  return [r.left + r.width / 2, r.top + r.height / 2, r.left, r.top, r.width]; }"""
# 新手引导：动画期间安卓 uiautomator 导不出界面，直接在页面里点
ONBOARDING_JS = """() => { const b = [...document.querySelectorAll('button')]
  .find(b => ['Next', 'Get started'].includes(b.textContent.trim()));
  if (b) { b.click(); return true; } return false; }"""


class Walk:
    def __init__(self, driver, name):
        self.d, self.name = driver, name
        self.results = []

    def check(self, label, ok, detail=''):
        self.results.append(ok)
        print(f"{self.name}: {'PASS' if ok else 'FAIL'} {label} {detail}".rstrip(), flush=True)

    def shot(self, step):
        self.d.shot(f'{self.name}-{step}')

    def path(self):
        return self.d.eval('() => location.pathname')

    def body(self):
        return self.d.eval('() => document.body.innerText')

    def locate(self, kind, query, timeout=10):
        end = time.time() + timeout
        while time.time() < end:
            if self.d.eval(FIND_JS, kind, query):
                time.sleep(0.4)
                return self.d.eval(TARGET_CENTRE_JS)
            time.sleep(0.5)
        raise RuntimeError(f'not on page: {query}')

    def tap(self, kind, query, wait=1.5):
        x, y, *_ = self.locate(kind, query)
        self.d.tap(x, y)
        time.sleep(wait)

    def swipe(self, direction):
        w, h = self.d.eval('() => [innerWidth, innerHeight]')
        a, b = (w * 0.8, w * 0.2) if direction == 'left' else (w * 0.2, w * 0.8)
        self.d.swipe(a, h * 0.55, b, h * 0.55)
        time.sleep(1.8)

    def audio_requests(self):
        return self.d.eval("() => performance.getEntriesByType('resource').filter(e => e.name.includes('/api/audio/')).length")

    def run(self):
        d = self.d
        d.goto('/')
        time.sleep(2)
        d.eval("() => { localStorage.clear(); sessionStorage.clear(); document.cookie = 'guest_id=; Max-Age=0; path=/'; }")
        d.goto('/')
        time.sleep(3)
        for _ in range(4):
            if not d.eval(ONBOARDING_JS):
                break
            time.sleep(1)
        self.shot('01-home')

        d.goto('/learning-dashboard')
        self.locate('text', r'^Start now$')
        self.shot('02-dashboard')
        self.tap('text', r'^Start now$', 2.5)
        word_id = d.eval("() => new URLSearchParams(location.search).get('wordId')")
        word = (re.search(r'How well do you know (.+?)\?', self.body()) or [None, ''])[1]
        self.check('dashboard Start now -> self-check', self.path() == '/word-learning-entrance' and bool(word),
                   f'{self.path()} word={word}')
        self.shot('03-self-check')

        self.tap('text', r'^I have never seen this word\.$', 0.8)
        self.tap('text', r'^CONTINUE$', 3)
        steps = ['/word-learning', '/collocation-learning', '/sentence-learning', '/exercise']
        if len(word) > 1:
            steps.insert(0, '/character-learning')
        self.check('never seen -> first learning step', self.path() == steps[0], self.path())
        self.shot('04-first-step')
        self.swipe('left')
        self.check('swipe left -> next step', self.path() == steps[1], self.path())
        self.swipe('right')
        self.check('swipe right -> previous step', self.path() == steps[0], self.path())
        for _ in range(len(steps)):
            if self.path() == '/sentence-learning':
                break
            self.swipe('left')
        self.check('swipe left through to sentences', self.path() == '/sentence-learning', self.path())
        self.shot('05-sentences')

        before = self.audio_requests()
        self.tap('css', 'button[title="Play audio"]', 2.5)
        self.check('example audio plays', self.audio_requests() > before)
        self.swipe('left')
        self.check('swipe left -> practice', self.path() == '/exercise', self.path())
        time.sleep(1)

        questions = d.eval("(id) => fetch(`/api/learning/word/${id}/exercises?limit=5`).then(r => r.json()).then(r => r.data.questions)",
                           word_id)
        fill = None
        for q in questions:
            if q['type'] == 'fill_word':
                fill = q
                break
            self.tap('text', r'^(\w\. )?' + re.escape(q['correctAnswer']) + '$', 0.8)
            self.tap('text', r'^CHECK$', 1.5)
            self.check(f"{q['type']} question answered", 'Excellent' in self.body())
            self.tap('text', r'^CONTINUE$', 1.5)
        if not fill:
            self.check('fill-in question present', False, str([q['type'] for q in questions]))
            return

        char = fill['correctAnswer']
        _, _, left, top, size = self.locate('css', 'canvas[aria-label^="Handwriting area"]')
        self.shot('06-fill-in')
        scroll = d.eval('() => document.scrollingElement.scrollTop')
        medians = json.loads((HANZI / f'{char}.json').read_text())['medians']
        k = size / 240 * 200 / 1024  # hanzi-writer-data 是 1024 见方、y 轴朝上；四周留 1/12 的边
        d.write([[(left + size / 12 + x * k, top + size / 12 + (900 - y) * k) for x, y in m] for m in medians])
        time.sleep(0.8)
        self.check('page does not move while writing',
                   self.path() == '/exercise' and d.eval('() => document.scrollingElement.scrollTop') == scroll)
        self.shot('07-written')
        self.tap('text', r'^CHECK$', 3)
        self.check(f'handwritten {char} graded correct', 'Excellent' in self.body())
        self.check('stroke-order animation shown',
                   d.eval('(c) => document.querySelectorAll(`[aria-label="How to write ${c}"] svg`).length', char) == 1)
        self.shot('08-feedback')


def main():
    platform, *rest = sys.argv[1:]
    out = Path(os.environ.get('MOBILE_OUT', ROOT / '.review' / 'mobile'))
    out.mkdir(parents=True, exist_ok=True)
    base = os.environ.get('BASE_URL', 'http://localhost:3100')
    if platform == 'ios':
        udid, name = rest
        driver = IOSDriver(udid, os.environ.get('WD_PORT', '4723'), base, str(out))
    else:
        name = rest[0] if rest else 'android'
        driver = AndroidDriver(base, str(out))
    walk = Walk(driver, name)
    ok = True
    try:
        walk.run()
    except Exception as e:
        ok = False
        walk.shot('zz-error')
        print(f'{name}: ERROR {e!r} at {walk.path()}', flush=True)
    finally:
        driver.close()
    ok = ok and all(walk.results)
    print(f'{name}: {sum(walk.results)}/{len(walk.results)} passed' + ('' if ok else ' (FAILED)'), flush=True)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
