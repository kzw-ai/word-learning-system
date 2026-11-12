"""手机上走一遍选等级（三级词 / 四级词）：新访客在首页选 HSK 3 → 开始学第一个词（三级高频第一个「自己」）→
回首页，顶栏的等级按钮打开菜单（菜单不出屏）→ 换成 HSK 4 → 进度卡跟着换，刷新后等级还在。
用法同 walk.py，也可以 tests/mobile/run_all.sh level 三台同时跑。

  python3 tests/mobile/level.py ios <模拟器 UDID> <名字>
  python3 tests/mobile/level.py android [名字]
"""
import os
import sys
import time
from pathlib import Path

from drivers import AndroidDriver, IOSDriver
from walk import ONBOARDING_JS, ROOT, Walk

H1_JS = "() => document.querySelector('h1')?.innerText.trim() || ''"
# 菜单的左右边缘是否都在屏幕里
MENU_INSIDE_JS = """() => { const m = document.querySelector('[role=menu]'); if (!m) return null;
  const r = m.getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth; }"""
BADGE_JS = "() => document.querySelector('button[aria-haspopup=menu]')?.innerText.trim() || ''"


class LevelWalk(Walk):
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
        self.check('new visitor sees HSK 4 by default', d.eval(H1_JS) == 'Learn the 600 HSK 4 words', d.eval(H1_JS))
        self.shot('l1-new-hsk4')

        self.tap('text', r'^HSK 3 · 300 words$', 1.5)
        self.check('choosing HSK 3 changes the title', d.eval(H1_JS) == 'Learn the 300 HSK 3 words', d.eval(H1_JS))
        self.shot('l2-new-hsk3')

        self.tap('text', r'^Start my first word', 3)
        word = d.eval("() => document.querySelector('[data-target-word]')?.innerText.trim() || ''")
        self.check('first word is the top HSK 3 word', self.path() == '/word-learning-entrance' and word == '自己',
                   f'{self.path()} word={word}')
        self.shot('l3-self-check')
        self.tap('text', r'^I have never seen this word\.$', 0.8)
        self.tap('text', r'^CONTINUE$', 3)

        d.goto('/')
        time.sleep(3)
        self.check('returning learner sees the HSK 3 badge', d.eval(BADGE_JS) == 'HSK 3', d.eval(BADGE_JS))
        self.shot('l4-returning-hsk3')
        self.tap('css', 'button[aria-haspopup=menu]', 1)
        self.check('level menu stays on screen', d.eval(MENU_INSIDE_JS) is True, str(d.eval(MENU_INSIDE_JS)))
        self.shot('l5-menu')
        self.tap('text', r'^HSK 4 words$', 2)
        self.check('switching shows HSK 4 progress', d.eval(BADGE_JS) == 'HSK 4' and '/ 600' in self.body(),
                   d.eval(BADGE_JS))
        self.shot('l6-returning-hsk4')
        d.goto('/')
        time.sleep(3)
        self.check('level is kept after reload', d.eval(BADGE_JS) == 'HSK 4', d.eval(BADGE_JS))


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
    walk = LevelWalk(driver, name)
    ok = True
    try:
        walk.run()
    except Exception as e:
        ok = False
        walk.shot('zz-level-error')
        print(f'{name}: ERROR {e!r} at {walk.path()}', flush=True)
    finally:
        driver.close()
    ok = ok and all(walk.results)
    print(f'{name}: {sum(walk.results)}/{len(walk.results)} passed' + ('' if ok else ' (FAILED)'), flush=True)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
