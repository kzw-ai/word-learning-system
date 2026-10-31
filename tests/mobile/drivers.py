"""手机兼容性测试的设备驱动：iOS 模拟器里的 Safari（safaridriver，W3C WebDriver）和安卓模拟器里的 Chrome
（DevTools 协议读页面 + adb 发系统触摸事件）。两边接口一样，坐标都是网页的 CSS 像素，点按、滑动、手写都是真实触摸。"""
import json
import os
import re
import subprocess
import time
import urllib.request

ADB = os.environ.get('ADB', os.path.expanduser('~/Library/Android/sdk/platform-tools/adb'))


def adb(*args, check=True):
    return subprocess.run([ADB, *args], capture_output=True, text=True, check=check).stdout


class IOSDriver:
    def __init__(self, udid, port, base, out):
        self.udid, self.base, self.out = udid, base, out
        self.wd = f'http://localhost:{port}'
        caps = {'browserName': 'Safari', 'platformName': 'iOS', 'safari:useSimulator': True, 'safari:deviceUDID': udid}
        self.sid = self._call('POST', '/session', {'capabilities': {'alwaysMatch': caps}})['sessionId']

    def _call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.wd + path, method=method, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.load(resp)['value']

    def _session(self, method, path, body=None):
        return self._call(method, f'/session/{self.sid}{path}', body)

    def eval(self, fn, *args):
        return self._session('POST', '/execute/sync', {'script': f'return ({fn}).apply(null, arguments)', 'args': list(args)})

    def goto(self, path):
        self._session('POST', '/url', {'url': self.base + path})

    def _touch(self, strokes, step_ms):
        for pts in strokes:
            acts = [{'type': 'pointerMove', 'duration': 0, 'x': round(pts[0][0]), 'y': round(pts[0][1])},
                    {'type': 'pointerDown', 'button': 0}]
            acts += [{'type': 'pointerMove', 'duration': step_ms, 'x': round(x), 'y': round(y)} for x, y in pts[1:]]
            if len(pts) == 1:
                acts.append({'type': 'pause', 'duration': 80})
            acts.append({'type': 'pointerUp', 'button': 0})
            self._session('POST', '/actions', {'actions': [
                {'type': 'pointer', 'id': 'finger', 'parameters': {'pointerType': 'touch'}, 'actions': acts}]})
            self._session('DELETE', '/actions')

    def tap(self, x, y):
        # 不用 WebDriver 的「点击元素」：safaridriver 在 iOS 上只发 touchstart、不发 touchend，click 不会触发
        self._touch([[(x, y)]], 0)

    def swipe(self, x1, y1, x2, y2):
        self._touch([[(x1 + (x2 - x1) * k / 8, y1 + (y2 - y1) * k / 8) for k in range(9)]], 20)

    def write(self, strokes):
        self._touch(strokes, 25)


    def shot(self, name):
        path = f'{self.out}/{name}.png'
        subprocess.run(['xcrun', 'simctl', 'io', self.udid, 'screenshot', path], capture_output=True)
        return path

    def close(self):
        self._session('DELETE', '')


class AndroidDriver:
    def __init__(self, base, out, cdp_port=9333):
        from playwright.sync_api import sync_playwright
        self.base, self.out = base, out
        self._origin = None
        # 每次开一个带标记的新标签页，再按网址认出它：Chrome 会留着旧标签页，而且它们都报告自己「可见」
        marker = f'{base}/?mobile_walk={int(time.time())}'
        adb('shell', 'am', 'start', '-a', 'android.intent.action.VIEW', '-d', marker, 'com.android.chrome')
        self._pw = sync_playwright().start()
        for _ in range(10):
            time.sleep(1.5)
            browser = self._pw.chromium.connect_over_cdp(f'http://localhost:{cdp_port}')
            pages = [p for c in browser.contexts for p in c.pages if p.url == marker]
            if pages:
                self.page = pages[0]
                return
            browser.close()
        raise RuntimeError(f'Chrome tab not found: {marker}')

    def eval(self, fn, *args):
        return self.page.evaluate(f'(args) => ({fn}).apply(null, args)', list(args))

    def goto(self, path):
        self.page.goto(self.base + path)

    def _screen_origin(self):
        """网页左上角在屏幕上的位置。连上 DevTools 后网页节点没有文字标签，按类名找；
        动画进行中 uiautomator 导不出界面，取不到就沿用上一次的位置（网页位置很少变）。"""
        for _ in range(5):
            adb('shell', 'uiautomator', 'dump', '/sdcard/ui.xml', check=False)
            xml = adb('shell', 'cat', '/sdcard/ui.xml', check=False)
            m = re.search(r'class="android\.webkit\.WebView"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml)
            if m:
                x1, _, _, y2 = map(int, m.groups())
                inner, dpr = self.page.evaluate('[innerHeight, devicePixelRatio]')
                self._origin = x1, y2 - inner * dpr, dpr
                return self._origin
            time.sleep(0.8)
        if self._origin:
            return self._origin
        raise RuntimeError('Chrome web view not found on screen')

    def _to_screen(self, pts, origin=None):
        ox, oy, dpr = origin or self._screen_origin()
        return [(str(int(ox + x * dpr)), str(int(oy + y * dpr))) for x, y in pts]

    def tap(self, x, y):
        adb('shell', 'input', 'tap', *self._to_screen([(x, y)])[0])

    def swipe(self, x1, y1, x2, y2):
        (a, b), (c, d) = self._to_screen([(x1, y1), (x2, y2)])
        adb('shell', 'input', 'swipe', a, b, c, d, '250')

    def write(self, strokes):
        origin = self._screen_origin()
        for pts in strokes:
            sx = self._to_screen(pts, origin)
            adb('shell', 'input', 'motionevent', 'DOWN', *sx[0])
            for p in sx[1:]:
                adb('shell', 'input', 'motionevent', 'MOVE', *p)
            adb('shell', 'input', 'motionevent', 'UP', *sx[-1])


    def shot(self, name):
        path = f'{self.out}/{name}.png'
        with open(path, 'wb') as f:
            f.write(subprocess.run([ADB, 'exec-out', 'screencap', '-p'], capture_output=True, check=True).stdout)
        return path

    def close(self):
        # 关掉这次开的标签页：不关的话每跑一次多一个，2026-10-31 积到 53 个，作者在模拟器上看到一堆旧页面
        try:
            self.page.close()
        except Exception:
            pass
        self._pw.stop()
