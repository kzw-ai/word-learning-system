#!/usr/bin/env node
/**
 * E2E 冒烟测试：页面渲染 + 页面跳转
 *
 * 用系统 Chrome（无头）加载每个页面，捕获 JS 运行时异常、
 * console 错误和失败的网络请求；并真实点击首页入口和
 * 学习链路的前后导航按钮，验证路由跳转正确。
 *
 * 前置条件（两个服务都在运行）：
 *   python3 app_phase.py     # 后端 :5004
 *   npm run build && npm start  # 前端 :3000
 *
 * 运行: npm run test:e2e
 * 环境变量: BASE_URL（默认 http://localhost:3000）、CHROME_PATH
 */

const puppeteer = require('puppeteer-core');

const BASE = (process.env.BASE_URL || 'http://localhost:3000').replace(/\/$/, '');
const CHROME =
  process.env.CHROME_PATH ||
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

const ROUTES = [
  '/', '/character-learning', '/collocation-learning', '/confusable-words',
  '/exercise', '/learning-dashboard',
  '/learning-stats', '/login', '/phase-demo', '/register', '/sentence-learning',
  '/system-status', '/time-tracking-demo', '/today-review', '/word-learning',
  '/word-learning-entrance',
];

// system-status 页的职责就是探测其他端口的服务，未启动的服务会产生
// 预期内的连接失败——不算错误
const EXPECTED_ERROR_PATTERNS = {
  '/system-status': [/ERR_CONNECTION_REFUSED/, /localhost:500[12]/],
};

// 首页各入口的 router.push 目标（对应 pages/index.tsx；
// 今日复习/易混词辨析已融入主流程，不再是首页入口）
const HOME_NAV_TARGETS = [
  '/word-learning-entrance', '/learning-dashboard',
  '/learning-stats', '/login', '/system-status',
];

// 学习链路页面（每页顶部有 ← / → 导航按钮）
const CHAIN_PAGES = [
  '/character-learning', '/word-learning', '/collocation-learning',
  '/sentence-learning', '/exercise',
];

let failures = 0;

function pass(msg) {
  console.log(`  ✓ ${msg}`);
}

function fail(msg, details = []) {
  failures += 1;
  console.log(`  ✗ ${msg}`);
  details.forEach((d) => console.log(`      ${String(d).slice(0, 160)}`));
}

async function checkServerUp() {
  try {
    const resp = await fetch(BASE + '/');
    return resp.ok;
  } catch {
    return false;
  }
}

async function testPageRendering(browser) {
  console.log('\n== 页面渲染（含运行时错误捕获）==');
  for (const route of ROUTES) {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', (err) => errors.push(`JS异常: ${err.message.split('\n')[0]}`));
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(`console.error: ${msg.text()}`);
    });
    page.on('requestfailed', (req) =>
      errors.push(`请求失败: ${req.url()} ${req.failure()?.errorText || ''}`)
    );

    try {
      await page.goto(BASE + route, { waitUntil: 'networkidle2', timeout: 20000 });
      await new Promise((r) => setTimeout(r, 1200));
      const bodyText = await page.evaluate(() => document.body.innerText.trim());

      const expected = EXPECTED_ERROR_PATTERNS[route] || [];
      const realErrors = errors.filter((e) => !expected.some((p) => p.test(e)));

      if (bodyText.length < 20) {
        fail(`${route} 页面内容为空`, [bodyText]);
      } else if (realErrors.length > 0) {
        fail(`${route} 有运行时错误`, [...new Set(realErrors)]);
      } else {
        pass(route);
      }
    } catch (e) {
      fail(`${route} 加载失败`, [e.message.split('\n')[0]]);
    }
    await page.close();
  }
}

async function testReturningUserHydration(browser) {
  console.log('\n== 老用户回访（localStorage 有历史数据时的水合）==');
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (err) => errors.push(err.message.split('\n')[0]));

  // 先访问 dashboard 让上下文写入 localStorage，再访问 entrance
  await page.goto(BASE + '/learning-dashboard', { waitUntil: 'networkidle2', timeout: 20000 });
  await new Promise((r) => setTimeout(r, 1200));
  errors.length = 0;
  await page.goto(BASE + '/word-learning-entrance', { waitUntil: 'networkidle2', timeout: 20000 });
  await new Promise((r) => setTimeout(r, 1200));

  const hydrationErrors = errors.filter((e) => /Minified React error #4(18|23|25)/.test(e));
  if (hydrationErrors.length > 0) {
    fail('word-learning-entrance 回访时出现水合错误', hydrationErrors);
  } else {
    pass('带历史 localStorage 回访无水合错误');
  }
  await page.close();
}

async function testNavigation(browser) {
  console.log('\n== 页面跳转 ==');
  const page = await browser.newPage();

  for (const target of HOME_NAV_TARGETS) {
    try {
      await page.goto(BASE + '/', { waitUntil: 'networkidle2', timeout: 20000 });
      await page.evaluate((t) => window.next.router.push(t), target);
      await new Promise((r) => setTimeout(r, 1000));
      const landed = new URL(page.url()).pathname;
      if (landed === target) {
        pass(`首页 → ${target}`);
      } else {
        fail(`首页 → ${target} 实际落在 ${landed}`);
      }
    } catch (e) {
      fail(`首页 → ${target} 跳转异常`, [e.message.split('\n')[0]]);
    }
  }

  for (const route of CHAIN_PAGES) {
    let buttons = [];
    try {
      await page.goto(BASE + route, { waitUntil: 'networkidle2', timeout: 20000 });
      await new Promise((r) => setTimeout(r, 600));
      buttons = await page.evaluate(() =>
        [...document.querySelectorAll('button, [role="button"], a, div[class*="cursor-pointer"]')]
          .map((el) => (el.innerText || '').trim().slice(0, 20))
          .filter((t) => t.includes('←') || t.includes('→'))
      );
    } catch (e) {
      fail(`${route} 加载失败，跳过导航检查`, [e.message.split('\n')[0]]);
      continue;
    }
    if (buttons.length === 0) {
      fail(`${route} 未找到 ←/→ 导航按钮`);
      continue;
    }
    for (const text of buttons) {
      try {
        await page.goto(BASE + route, { waitUntil: 'networkidle2', timeout: 20000 });
        await new Promise((r) => setTimeout(r, 400));
        await page.evaluate((t) => {
          const els = [...document.querySelectorAll('button, [role="button"], a, div[class*="cursor-pointer"]')];
          const el = els.find((e) => (e.innerText || '').trim().slice(0, 20) === t);
          if (el) el.click();
        }, text);
        await new Promise((r) => setTimeout(r, 1000));
        const landed = new URL(page.url()).pathname;
        if (landed !== route) {
          pass(`${route} [${text}] → ${landed}`);
        } else {
          fail(`${route} [${text}] 点击后未跳转`);
        }
      } catch (e) {
        fail(`${route} [${text}] 点击异常`, [e.message.split('\n')[0]]);
      }
    }
  }
  await page.close();
}

(async () => {
  if (!(await checkServerUp())) {
    console.error(`✗ 前端服务不可用: ${BASE}`);
    console.error('  请先启动: python3 app_phase.py 和 npm run build && npm start');
    process.exit(2);
  }

  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new' });
  try {
    await testPageRendering(browser);
    await testReturningUserHydration(browser);
    await testNavigation(browser);
  } finally {
    await browser.close();
  }

  console.log(failures === 0 ? '\n✅ E2E 冒烟测试全部通过' : `\n❌ ${failures} 项失败`);
  process.exit(failures === 0 ? 0 : 1);
})();
