#!/usr/bin/env node
// 把 hanzi-writer-data 的笔画数据（每个字一个 JSON）复制到 public/hanzi-data/，填字题手写判分和
// 答后笔顺演示从这里按字取（src/lib/handwriting.ts、components/learning/HandwritingPad.tsx）。
// 在 npm run build 之前自动运行（package.json 的 prebuild）；目录不提交到仓库。
// 数据按文鼎公众许可（Arphic Public License）分发，许可文件一并复制。
const fs = require('fs');
const path = require('path');

const src = path.dirname(require.resolve('hanzi-writer-data/package.json'));
const dest = path.join(__dirname, '..', 'public', 'hanzi-data');
fs.mkdirSync(dest, { recursive: true });

let copied = 0;
for (const name of fs.readdirSync(src)) {
  if (!name.endsWith('.json') || name === 'package.json') continue;
  const target = path.join(dest, name);
  if (!fs.existsSync(target)) {
    fs.copyFileSync(path.join(src, name), target);
    copied += 1;
  }
}
fs.copyFileSync(path.join(src, 'ARPHICPL.TXT'), path.join(dest, 'ARPHICPL.TXT'));
console.log(`hanzi-data: ${copied} new characters copied to public/hanzi-data`);
