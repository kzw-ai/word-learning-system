"""分批：把还没做的四级词排进第 02 批及以后，写出各批的 词表.txt（制作流程 第 1 步）。

- 每批约 10 个目标词。论文 5.2 节「每次学习安排相当的高频词、中频词、低频词」：三档各自均匀摊到每一批，
  档内按加权词频从高到低，所以高频词先做。
- 跳过：已写进某一批词表的词、论文词库（words_extended.db）里已有材料的词。
- 入选的易混淆词（第 2 步）排在它的目标词后面，单独学习（论文 2.2.4）；已在前面出现过或词库里已有的不再加。

用法：学习资料制作/.venv/bin/python 学习资料制作/工具/plan_batches.py          # 只打印计划
      学习资料制作/.venv/bin/python 学习资料制作/工具/plan_batches.py --write  # 写出词表.txt，已有的批次不动
要先对这些词跑完第 2 步；有词没有第 2 步结果时只报出来，不写。
"""
import collections
import csv
import math
import re
import sqlite3
import sys

import common
import step2_confusables

PER_BATCH = 10
TIERS = ('高频', '中频', '低频')
DB = common.W.parent / 'words_extended.db'


def db_words():
    """论文词库里的词（按 character.id 的顺序拼字，同导入脚本）"""
    chars = {}
    with sqlite3.connect(DB) as conn:
        for word_id, ch in conn.execute('SELECT word_id, character FROM character ORDER BY word_id, id'):
            chars.setdefault(word_id, []).append(ch)
    return {''.join(cs) for cs in chars.values()}


def existing_batches():
    """{批号: [词]}：3_审核 下已写好词表的批次"""
    out = {}
    for path in sorted(common.REVIEW.glob('第*批/词表.txt')):
        m = re.fullmatch(r'第(\d+)批', path.parent.name)
        if m:
            out[int(m.group(1))] = step2_confusables.words_from_args([path.parent.name])
    return out


def plan():
    """返回 (新批次 [(批名, [(词, 注释)])], 缺第 2 步结果的词)"""
    rows = list(csv.DictReader(open(common.OUT / '四级词加权词频分档.csv', encoding='utf-8-sig')))
    done = existing_batches()
    seen = db_words() | {w for words in done.values() for w in words}
    todo = [r for r in rows if r['word'] not in seen]
    n_batches = math.ceil(len(todo) / PER_BATCH)
    batches = [[] for _ in range(n_batches)]
    for tier in TIERS:
        words = [r for r in todo if r['tier'] == tier]  # 词频表已按加权词频排好
        for k, r in enumerate(words):
            batches[int((k + 0.5) * n_batches / len(words))].append((r['word'], tier))
    seen |= {r['word'] for r in todo}

    analysed = {r['target'] for r in csv.DictReader(open(step2_confusables.RESULT, encoding='utf-8'))} \
        if step2_confusables.RESULT.exists() else set()
    missing = [r['word'] for r in todo if r['word'] not in analysed]
    levels = common.hsk_levels()
    first = max(done, default=0) + 1
    out = []
    for i, targets in enumerate(batches):
        lines = []
        for word, tier in targets:
            lines.append((word, tier))
            for c in step2_confusables.selected(word):
                if c not in seen:
                    seen.add(c)
                    lines.append((c, f'{word}的易混淆词（{common.LEVEL_NAMES[levels[c] - 1]}级）'))
        out.append((f'第{first + i:02d}批', lines))
    return out, missing


def write(batches):
    for name, lines in batches:
        path = common.REVIEW / name / '词表.txt'
        path.parent.mkdir(parents=True, exist_ok=True)
        text = [f'# {name[:1]} {name[1:-1]} 批（# 后面是注释）。易混淆词排在目标词之后，单独学习（论文 2.2.4）。']
        text += [f'{w}{" " * max(1, 7 - 2 * len(w))}# {note}' for w, note in lines]
        path.write_text('\n'.join(text) + '\n', encoding='utf-8')


if __name__ == '__main__':
    batches, missing = plan()
    for name, lines in batches:
        tiers = collections.Counter(note for _, note in lines if note in TIERS)
        print(f"{name}（{'、'.join(f'{t}{tiers[t]}' for t in TIERS)}）：{' '.join(w for w, _ in lines)}")
    extra = sum(note not in TIERS for _, lines in batches for _, note in lines)
    print(f'共 {len(batches)} 批，目标词 {sum(len(l) for _, l in batches) - extra} 个，易混淆词 {extra} 个')
    if missing:
        print(f'⚠️ 还有 {len(missing)} 个词没跑第 2 步，先跑完再写：{" ".join(missing[:20])}{" …" if len(missing) > 20 else ""}')
    elif '--write' in sys.argv:
        write(batches)
        print('已写出词表.txt')
