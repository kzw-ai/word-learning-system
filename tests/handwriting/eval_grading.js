// 手写判分（src/lib/handwriting.ts）的评估：用标准笔画模拟真人书写——每一笔随机转一点、缩放一点、挪一点、
// 加点抖动，起笔离上一笔收笔近时一定概率连成一笔（连笔）——量两个数：
//   写对的字判对的比例（越高越好）、写成形近字也判对的比例（越低越好；「己/已」「未/末」这类本来就分不开）。
// 用法：node tests/handwriting/eval_grading.js [旧版 handwriting.ts 的路径，对比用]
//   环境变量：N 每个字写几遍（默认 15）；JOIN 连笔概率（默认 0.5）；ROT/SC/SH/NO 旋转度数、缩放、平移、抖动；SHOW=1 列出误判的字对
// 2026-10-31 加连笔处理时的结果（N=15, JOIN=0.5，随机抽样，各次差一两个百分点）：改前判对约 40%、形近字误判约 23%；改后判对约 98%、形近字误判约 38%
const ts = require('typescript');
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
const load_module = (file) => {
  const out = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2019 } }).outputText;
  const m = { exports: {} };
  new Function('module', 'exports', 'require', out)(m, m.exports, require);
  return m.exports;
};
const VERSIONS = { current: load_module(path.join(ROOT, 'src/lib/handwriting.ts')) };
if (process.argv[2]) VERSIONS.compare = load_module(process.argv[2]);

const DATA = path.join(ROOT, 'public/hanzi-data');
const load = ch => { try { return JSON.parse(fs.readFileSync(`${DATA}/${ch}.json`)); } catch { return null; } };
let seed = 7; const rand = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
const gauss = () => Math.sqrt(-2 * Math.log(rand() + 1e-12)) * Math.cos(2 * Math.PI * rand());
const LEVEL = { rot: +(process.env.ROT || 8), scale: +(process.env.SC || 0.15), shift: +(process.env.SH || 40), noise: +(process.env.NO || 8), join: +(process.env.JOIN || 0.5) };
function vary(strokes) {
  const out = strokes.map(s => {
    const cx = s.reduce((a, p) => a + p[0], 0) / s.length, cy = s.reduce((a, p) => a + p[1], 0) / s.length;
    const r = (rand() * 2 - 1) * LEVEL.rot * Math.PI / 180, k = 1 + (rand() * 2 - 1) * LEVEL.scale;
    const dx = (rand() * 2 - 1) * LEVEL.shift, dy = (rand() * 2 - 1) * LEVEL.shift;
    return s.map(([x, y]) => {
      const X = (x - cx) * k, Y = (y - cy) * k;
      return [cx + X * Math.cos(r) - Y * Math.sin(r) + dx + gauss() * LEVEL.noise, cy + X * Math.sin(r) + Y * Math.cos(r) + dy + gauss() * LEVEL.noise];
    });
  });
  // natural joins: next stroke starts near where this one ended
  const joined = [out[0]];
  for (let i = 1; i < out.length; i++) {
    const prev = joined[joined.length - 1], e = prev[prev.length - 1], st = out[i][0];
    if (Math.hypot(e[0] - st[0], e[1] - st[1]) < 300 && rand() < LEVEL.join) joined[joined.length - 1] = [...prev, ...out[i]];
    else joined.push(out[i]);
  }
  return joined;
}
const words = '学父傅师很租脏页象印羽球点优习字写觉家宝冬安定实客室害寒容宿完察富寄宣守官宜宫密寸对导封将尊'.split('');
const confusable = ['大太','太大','人入','入人','己已','已己','日目','目日','王玉','玉王','土士','士土','未末','末未','天夫','夫天','白百','百白','自目','目自','田由','由田','午牛','牛午','千干','干千','刀力','力刀','买卖','卖买','师帅','帅师','很根','根很','租组','组租','傅博','父文','文父','页贝','贝页','优忧','忧优','点店','木本','本木','乌鸟','鸟乌','今令','令今','住往','往住','问间','间问','清请','请清','休体','体休','找我','我找','早旱','旱早','儿几','几儿','厂广','广厂','王主','主王','学字','字学','学觉','觉学','宝实','实宝','完元','安字','字安'];
const N = +(process.env.N || 15);
for (const [file, hw] of Object.entries(VERSIONS)) {
  let ok = 0, tot = 0, fp = 0, fpt = 0; const fpPairs = {};
  for (const ch of words) { const d = load(ch); if (!d) continue; const s = hw.targetStrokes(d);
    for (let i = 0; i < N; i++) { tot++; if (hw.gradeHandwriting(vary(s), d).correct) ok++; } }
  for (const [a, b] of confusable) { const da = load(a), db = load(b); if (!da || !db) continue; const s = hw.targetStrokes(da);
    for (let i = 0; i < N; i++) { fpt++; if (hw.gradeHandwriting(vary(s), db).correct) { fp++; fpPairs[a + '→' + b] = (fpPairs[a + '→' + b] || 0) + 1; } } }
  console.log(`${file}: right char accepted ${ok}/${tot} (${(100 * ok / tot).toFixed(0)}%) | wrong similar char accepted ${fp}/${fpt} (${(100 * fp / fpt).toFixed(0)}%)`);
  if (process.env.SHOW) console.log(Object.entries(fpPairs).sort((a, b) => b[1] - a[1]).map(([k, v]) => k + v).join(' '));
}
