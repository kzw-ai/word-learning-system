#!/usr/bin/env node
// 扫描学习资料提取所有唯一汉字，从 public/hanzi-data/ 复制子集到 mobile/assets/hanzi-data/，
// 生成 mobile/src/lib/hanziIndex.ts（char → require 静态索引）。
// 与网页版 scripts/copy_hanzi_data.js 同源：笔画数据按文鼎公众许可（Arphic Public License）分发。
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..'); // word-app-rn 根
const MOBILE = path.resolve(__dirname, '..'); // mobile/
const SRC_DIRS = [
  path.join(ROOT, 'data/learning_materials/hsk3'),
  path.join(ROOT, 'data/learning_materials/hsk4'),
];
const HANZI_SRC = path.join(ROOT, 'public/hanzi-data');
const DEST = path.join(MOBILE, 'assets/hanzi-data');
const INDEX = path.join(MOBILE, 'src/lib/hanziIndex.ts');

const chars = new Set();

for (const dir of SRC_DIRS) {
  if (!fs.existsSync(dir)) continue;
  for (const name of fs.readdirSync(dir)) {
    if (!name.endsWith('.json')) continue;
    try {
      const data = JSON.parse(fs.readFileSync(path.join(dir, name), 'utf8'));
      const words = Array.isArray(data) ? data : data.words || [];
      for (const w of words) {
        if (typeof w.hanzi === 'string') for (const ch of w.hanzi) chars.add(ch);
        if (Array.isArray(w.characters)) {
          for (const c of w.characters) {
            if (c && typeof c.character === 'string') for (const ch of c.character) chars.add(ch);
          }
        }
      }
    } catch (e) {
      console.warn('跳过', name, e.message);
    }
  }
}

fs.mkdirSync(DEST, { recursive: true });
let copied = 0;
const bundled = [];
for (const ch of chars) {
  const src = path.join(HANZI_SRC, `${ch}.json`);
  if (!fs.existsSync(src)) continue;
  const target = path.join(DEST, `${ch}.json`);
  if (!fs.existsSync(target)) {
    fs.copyFileSync(src, target);
    copied += 1;
  }
  bundled.push(ch);
}

bundled.sort();
const lines = bundled.map(ch => `  '${ch}': require('../../assets/hanzi-data/${ch}.json'),`);
const content = `// 自动生成，勿手改。由 scripts/build_hanzi_subset.js 生成。
import type { CharacterData } from './handwriting';

export const bundledHanzi: Record<string, CharacterData> = {
${lines.join('\n')}
};
`;
fs.writeFileSync(INDEX, content);

console.log(`hanzi 子集：${bundled.length} 个字（本次新增复制 ${copied} 个），索引写入 mobile/src/lib/hanziIndex.ts`);
