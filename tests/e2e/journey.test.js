#!/usr/bin/env node
/**
 * E2E 学习旅程测试：完整走一遍主学习流程
 *   入口 VKS（推荐词）→ 字学习 → 练习（含手写题）→ 易混淆词辨析 → 学习分析
 *
 * 前置条件与 smoke.test.js 相同（前端 :3000 + 后端 :5004）；环境变量 BASE_URL 同 smoke.test.js。
 * 运行: npm run test:e2e:journey
 */
const puppeteer = require('puppeteer-core');

const BASE = (process.env.BASE_URL || 'http://localhost:3000').replace(/\/$/, '');

(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: 'new',
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 430, height: 932, deviceScaleFactor: 2 });
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message.split('\n')[0]));

  // 用全新用户，保证走 new_learning 路径
  await page.goto(BASE + '/', { waitUntil: 'networkidle2' });
  await page.evaluate(() => {
    localStorage.setItem('learningSystem.userId', 'journey_tester');
  });

  // 1. 入口页：VKS 问题应显示推荐词（非硬编码发生也可能恰好是；记录它）
  await page.goto(BASE + '/word-learning-entrance', { waitUntil: 'networkidle2' });
  await new Promise((r) => setTimeout(r, 2500));
  const question = await page.evaluate(() => document.querySelector('[data-target-word]')?.innerText);
  console.log('1. 自评的词:', question);

  // 2. 选择 A（没见过）→ CONTINUE → 应进入字学习
  await page.evaluate(() => {
    const labels = [...document.querySelectorAll('label')];
    labels.find((l) => l.innerText.includes('never seen'))?.click();
  });
  await new Promise((r) => setTimeout(r, 600));
  await page.evaluate(() => {
    [...document.querySelectorAll('button')].find((b) => b.innerText.trim() === 'CONTINUE')?.click();
  });
  await new Promise((r) => setTimeout(r, 3000));
  console.log('2. CONTINUE 后落在:', new URL(page.url()).pathname);

  // 3. 字学习页应显示推荐词（读大标题汉字）
  const bigWord = await page.evaluate(() => {
    const el = document.querySelector('h1, .text-6xl, [class*="text-5xl"], [class*="text-4xl"]');
    return document.body.innerText.slice(0, 80).replace(/\n/g, ' ');
  });
  console.log('3. 字学习页内容片段:', bigWord);

  // 4. 直接去练习页（模拟走完链路），完成一题后看完成路由
  //    为快速验证辨析衔接，直接设置 session 词为「变化」(有辨析对)
  const bianhuaId = await page.evaluate(async () => {
    const resp = await fetch('/words');
    const words = await resp.json();
    return words.find((w) => w.hanzi === '变化')?.id;
  });
  console.log('4. 变化 word_id =', bianhuaId);
  await page.evaluate((id) => {
    localStorage.setItem(
      'learningSession:journey_tester',
      JSON.stringify({ wordId: id, word: '变化', module: 'exercise', vksLevel: 'A', lastUpdated: new Date().toISOString() })
    );
  }, bianhuaId);

  await page.goto(BASE + '/exercise', { waitUntil: 'networkidle2' });
  await new Promise((r) => setTimeout(r, 2500));

  // 逐题作答直到完成（最多 10 轮）
  for (let i = 0; i < 24; i++) {
    if (new URL(page.url()).pathname !== '/exercise') break;
    // 若在答题态：作答并提交
    const state = await page.evaluate(() => {
      const feedbackBtn = [...document.querySelectorAll('button')]
        .find((b) => b.hasAttribute('data-feedback-continue'));
      if (feedbackBtn) { feedbackBtn.click(); return 'feedback-continue'; }
      const optionBtn = [...document.querySelectorAll('button')]
        .find((b) => /^[A-D]\.\s/.test(b.innerText.trim()) && !b.disabled);
      if (optionBtn) { optionBtn.click(); return 'answered'; }
      if (document.querySelector('[data-fill-input]')) return 'fill';
      // 填字题默认手写：这个测试改用打字作答（手写判分另有测试）
      const typeInstead = [...document.querySelectorAll('button')].find((b) => b.innerText.trim() === 'Type instead');
      if (typeInstead) { typeInstead.click(); return 'switched'; }
      return 'answered';
    });
    if (state === 'fill') {
      // 填词题是输入框：输入一个字后回车提交
      await page.type('[data-fill-input]', '化');
      await page.keyboard.press('Enter');
    }
    await new Promise((r) => setTimeout(r, 500));
    if (state === 'answered') {
      // 作答前的提交按钮叫 CHECK
      await page.evaluate(() => {
        [...document.querySelectorAll('button')]
          .find((b) => /^(CHECK|CONTINUE)$/.test(b.innerText.trim()) && !b.disabled)?.click();
      });
    }
    await new Promise((r) => setTimeout(r, 1500));
  }
  const afterExercise = new URL(page.url());
  console.log('5. 练习完成后落在:', afterExercise.pathname + afterExercise.search);

  // 6. 若在辨析页，验证定位与主线出口
  if (afterExercise.pathname === '/confusable-words') {
    await new Promise((r) => setTimeout(r, 1500));
    const pairText = await page.evaluate(() => document.body.innerText.slice(0, 120).replace(/\n/g, ' '));
    console.log('6. 辨析页内容:', pairText);
    await page.evaluate(() => {
      [...document.querySelectorAll('button')].find((b) => b.innerText.includes('Done ·'))?.click();
    });
    await new Promise((r) => setTimeout(r, 1500));
    console.log('7. 完成辨析后落在:', new URL(page.url()).pathname);
  }

  const finalPath = new URL(page.url()).pathname;
  console.log('页面 JS 错误:', errors.length ? errors : '无');
  await browser.close();
  const ok = errors.length === 0 && finalPath === '/learning-dashboard';
  console.log(ok ? '\n✅ 学习旅程测试通过' : `\n❌ 学习旅程测试失败（最终页面 ${finalPath}，错误 ${errors.length} 个）`);
  process.exit(ok ? 0 : 1);
})();
