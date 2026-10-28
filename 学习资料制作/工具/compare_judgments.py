"""对比两份语义判断（用来校准大模型：同一批词，Claude Code 的判断 vs DeepSeek 的判断）。

用法：学习资料制作/.venv/bin/python 学习资料制作/工具/compare_judgments.py 第01批 claude-code deepseek-flash
产出：2_加工结果/判断/第01批/对比.claude-code.deepseek-flash.md

义项编号和释义措辞两边可能不同，所以先按例句、搭配的归属把两边的义项对应起来，再比较归属是否一致。
"""
import collections
import json
import sys

import common
import step2_confusables
import step5_select


def load(outdir, word, source):
    path = outdir / f'{word}.判断.{source}.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def sense_label(answer, sid):
    if sid is None:
        return '不用'
    for s in answer.get('senses', []):
        if s.get('id') == sid:
            return f"{s.get('pos', '')} {s.get('definition', '')}".strip()
    return f'（未知义项 {sid}）'


def align(a, b):
    """把 b 的义项对应到 a 的义项：看两边都判为可用的例句和搭配，b 的每个义项对应它最常落到的 a 的义项。"""
    pairs = collections.Counter()
    for key in ('sentence_senses', 'collocation_senses'):
        for k, sa in a[key].items():
            sb = b[key].get(k)
            if sa is not None and sb is not None:
                pairs[(sb, sa)] += 1
    mapping = {}
    for (sb, sa), _ in pairs.most_common():
        mapping.setdefault(sb, sa)
    return mapping


def merges(a, b, name_a, name_b):
    """一方分开、另一方合并的义项。"""
    lines = []
    for x, y, nx, ny in ((a, b, name_a, name_b), (b, a, name_b, name_a)):
        groups = collections.defaultdict(list)
        for sy, sx in align(x, y).items():
            groups[sx].append(sy)
        for sx, sys_ in groups.items():
            if len(sys_) > 1:
                lines.append(f"- {ny} 分成 {len(sys_)} 个义项（{'｜'.join(sense_label(y, i) for i in sys_)}），"
                             f"{nx} 合为一个（{sense_label(x, sx)}）")
    return lines


def compare(task, a, b, name_a, name_b):
    lines, stats = [], {}
    mapping = align(a, b)
    lines += merges(a, b, name_a, name_b)
    lines.append(f"义项　{name_a}：" + '｜'.join(sense_label(a, s['id']) for s in a['senses']))
    lines.append(f"义项　{name_b}：" + '｜'.join(sense_label(b, s['id']) for s in b['senses']))
    multi = len(a['senses']) > 1 or len(b['senses']) > 1
    for kind, items, key in (('例句', task['sentences'], 'sentence_senses'), ('搭配', task['collocations'], 'collocation_senses')):
        usable_same = sense_diff = 0
        diffs = []
        for k, text in items.items():
            sa, sb = a[key].get(k), b[key].get(k)
            if (sa is None) == (sb is None):
                usable_same += 1
                if sa is not None and multi and mapping.get(sb) != sa:
                    sense_diff += 1
                    diffs.append(f"- {k} {text}　{name_a}：{sense_label(a, sa)}；{name_b}：{sense_label(b, sb)}")
            else:
                note_a = a.get('sentence_notes', {}).get(k, '') if kind == '例句' else ''
                note_b = b.get('sentence_notes', {}).get(k, '') if kind == '例句' else ''
                diffs.append(f"- {k} {text}　{name_a}：{sense_label(a, sa)}{'（' + note_a + '）' if note_a else ''}；"
                             f"{name_b}：{sense_label(b, sb)}{'（' + note_b + '）' if note_b else ''}")
        stats[kind] = (usable_same, len(items), sense_diff)
        lines.append(f"\n{kind}：能否使用一致 {usable_same}/{len(items)}" + (f"，义项归属不同 {sense_diff} 条" if multi else ''))
        lines += diffs
    chars_a = {c['character']: c for c in a.get('characters', [])}
    for c in b.get('characters', []):
        ca = chars_a.get(c['character'], {})
        if ca.get('pinyin') != c.get('pinyin'):
            lines.append(f"\n字「{c['character']}」读音不同：{name_a} {ca.get('pinyin')}；{name_b} {c.get('pinyin')}")
    return lines, stats


def final_picks(word, candidates, judgment, pool):
    r = step5_select.select(word, candidates, judgment, pool)
    examples = [s['example']['sentence'] for s in r['senses'] if s['example']]
    collocations = [c['collocation'] for s in r['senses'] for c in s['collocations']]
    return [f"{s['pos']} {s['definition']}" for s in r['senses']], examples, collocations, [s['id'] for s in r['senses']]


def main(batch, name_a, name_b):
    outdir = common.OUT / '判断' / batch
    pool = common.hsk1_to_3()
    md = [f'# 语义判断对比：{name_a} vs {name_b}（{batch}）', '']
    total = {'例句': [0, 0], '搭配': [0, 0]}
    final = {'例句': [0, 0], '搭配': [0, 0]}
    for word in step2_confusables.words_from_args([batch]):
        a, b = load(outdir, word, name_a), load(outdir, word, name_b)
        if not a or not b:
            md += [f'## {word}', '', f"缺少 {name_a if not a else name_b} 的判断", '']
            continue
        task = json.loads((outdir / f'{word}.任务.json').read_text(encoding='utf-8'))
        lines, stats = compare(task, a, b, name_a, name_b)
        candidates = json.loads((common.OUT / '候选清单' / batch / f'{word}.json').read_text(encoding='utf-8'))
        pa, pb = final_picks(word, candidates, a, pool), final_picks(word, candidates, b, pool)
        head = ['第 5 步最终选择：']
        for label, i in (('义项', 0), ('例句', 1), ('搭配', 2)):
            if label != '义项':
                final[label][0] += len(set(pa[i]) & set(pb[i]))
                final[label][1] += len(pa[i])
            same = [align(a, b).get(sid) for sid in pb[3]] == pa[3] if label == '义项' else pa[i] == pb[i]
            mark = '' if same else '　← 不同'
            head.append(f"- {label}　{name_a}：{'｜'.join(pa[i]) or '无'}；{name_b}：{'｜'.join(pb[i]) or '无'}{mark}")
        lines = head + [''] + lines
        for kind, (same, n, _) in stats.items():
            total[kind][0] += same
            total[kind][1] += n
        md += [f'## {word}', ''] + lines + ['']
    summary = ('最终选出的' + '、'.join(f'{k}相同 {s}/{n}' for k, (s, n) in final.items() if n) + '；逐条判断：'
               + '；'.join(f'{k}能否使用一致 {s}/{n}（{s / n:.0%}）' for k, (s, n) in total.items() if n))
    md.insert(2, f'总计：{summary}\n')
    out = outdir / f'对比.{name_a}.{name_b}.md'
    out.write_text('\n'.join(md) + '\n', encoding='utf-8')
    print(summary)
    print(out)


if __name__ == '__main__':
    main(*sys.argv[1:4])
