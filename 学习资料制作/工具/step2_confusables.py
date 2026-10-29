"""第 2 步　易混淆词（论文 5.3.1，附录 G）。

用法：学习资料制作/.venv/bin/python 学习资料制作/工具/step2_confusables.py 第01批
      （读 3_审核/第01批/词表.txt，跳过注释里写着「易混淆词」的行；也可以直接跟词：... step2_confusables.py 原因 考虑）
产出：2_加工结果/易混淆词.csv（每个词一组，重复运行会替换这个词原来的结果）
      2_加工结果/易混淆词报告/<词>.md（给人看：每个混淆词的次数、占比，和学习者写错的原句）

1. 按网页「下载」的方式取回含目标词的标注语料，存为 1_源数据/HSK动态作文语料库/下载的语料/目标词.csv。
   已下载过的词直接用本地文件，不再请求网站。
2. 附录 G：筛出含「目标词{CC」的句子（每句只取第一处，同 str.extract），取出花括号里的词。
3. 统计次数与占比。入选：目标词偏误 ≥ 10 次（论文 5.3.1）、占比 > 20%，且易混淆词是一至三级词（论文：学习者已经学过），
   或是另一个四级词（作者 2026-10-29 加：两个词都在系统里学，各自学完后再辨析，如「经历 → 经验」66%）。
   五级以上、词表外的不选（学习者还没学过）；写成目标词本身的（「而{CC而}」，标注造成）不算。
   目标词另有一至三级条目时（「得」助词二级、助动词四级；「等」）不自动入选：语料不分义项，
   统计到的多是低级义项的偏误（「过得{CC的}很开心」是结构助词，不是四级的「得 děi」）。作者确定这类词不做辨析（2026-10-29）。
"""
import collections
import csv
import re
import sys

import common
import hsk_client

RAW = common.HSK_CORPUS / '下载的语料'
RESULT = common.OUT / '易混淆词.csv'
REPORT = common.OUT / '易混淆词报告'
FIELDS = ['target', 'sentences', 'target_errors', 'confused_with', 'times', 'share', 'hsk_level', 'selected']


def no_data(word):
    """网站补试过仍回答「没有匹配到数据」的词，下载目录里有一个空的 <词>.无数据 文件：按 0 句语料处理，
    没有易混淆词，学习材料照做（如「打折」「登机牌」，作文语料里没人写过）"""
    if not (RAW / f'{word}.无数据').exists():
        return False
    if (RAW / f'{word}.csv').exists():
        raise SystemExit(f'「{word}」既有下载的语料又有 .无数据 标记：补下了语料就删掉 {word}.无数据')
    return True


def corpus_file(word):
    path = RAW / f'{word}.csv'
    if not path.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        path.write_bytes(hsk_client.download_keyword(word))
    return path


def errors_of(word):
    """[(学习者写成的词, 语料行)]：该用 word 的地方学习者写成了别的词的句子（每句只取第一处，同附录 G）。只读本地文件。

    「检索原句」是改正后的句子，标注写作「正确的词{CC学习者写的词}」，如「继续{CC续继}」是学习者把「继续」写成了「续继」。
    """
    if no_data(word):
        return [], []
    rows = list(csv.DictReader(open(corpus_file(word), encoding='utf-8-sig')))
    pattern = re.compile(re.escape(word) + r'\{CC\d*([一-龥]+)\[?[A-Z]*\]?\}')
    return rows, [(m.group(1), r) for r in rows if (m := pattern.search(r['检索原句']))]


def error_sentences(word, other, limit=15):
    """该用 word、学习者却写成 other 的原句（标注原样保留），给大模型分析混淆点用，不进学习内容。"""
    return [r['检索原句'] for w, r in errors_of(word)[1] if w == other][:limit]


def mixed_senses(word, levels):
    """四级词另有一至三级条目（hsk_levels 取最低等级）：语料统计混着低级义项"""
    return levels.get(word, 4) < 4


def qualifies(word, other, total, n, levels):
    """目标词是四级词（且没有更低的条目），偏误 ≥ 10、占比 > 20%，易混淆词是一至四级的另一个词"""
    lv = levels.get(other)
    return (levels.get(word) == 4 and total >= 10 and n / total > 0.2 and lv is not None and lv <= 4 and other != word
            and not mixed_senses(word, levels))


def analyse(word, levels):
    rows, found = errors_of(word)
    counts = collections.Counter(w for w, _ in found)
    write_report(word, len(rows), found, counts, levels)
    total = sum(counts.values())
    out = []
    for w, n in counts.most_common():
        lv = levels.get(w)
        chosen = qualifies(word, w, total, n, levels)
        out.append({'target': word, 'sentences': len(rows), 'target_errors': total, 'confused_with': w, 'times': n,
                    'share': round(n / total, 4), 'hsk_level': lv or '', 'selected': 'yes' if chosen else ''})
    if not out:
        out.append({'target': word, 'sentences': len(rows), 'target_errors': 0, 'confused_with': '', 'times': 0,
                    'share': 0, 'hsk_level': '', 'selected': ''})
    return out


def write_report(word, n_sentences, found, counts, levels):
    """给人看的报告：每个混淆词的次数、占比、等级，以及学习者写错的原句（标注原样保留）。"""
    total = sum(counts.values())
    md = [f'# {word}　易混淆词', '',
          f'语料 {n_sentences} 句，其中「{word}{{CC…}}」{total} 处：该用「{word}」的地方，学习者写成了花括号里的词（原句是改正后的句子）。',
          '入选标准：偏误 ≥ 10 处、占比 > 20%、一至四级词。下面每节是「学习者写成的词」，列出原句。', '']
    if mixed_senses(word, levels):
        md += [f'⚠️ 「{word}」在词表里另有{levels[word]}级条目，语料不分义项，下面的偏误多半属于低级义项，'
               '所以不入选（作者确定这类词不做辨析）。', '']
    for w, n in counts.most_common():
        lv = levels.get(w)
        chosen = qualifies(word, w, total, n, levels)
        md += [f"## {w}　{n} 处，{n / total:.0%}，{f'{lv} 级' if lv else '不在词表'}{'　✅ 入选' if chosen else ''}", '']
        md += [f"- {r['检索原句']}　（{r['国籍']}，{r['作文题目']}）" for c, r in found if c == w]
        md.append('')
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / f'{word}.md').write_text('\n'.join(md), encoding='utf-8')


def selected_rows():
    """易混淆词.csv 里入选的行。按现行规则用统计数字重新判定，不用文件里存的 selected 列：
    规则改过以后，旧的统计结果不会把已经不该入选的词（如「得 → 的」）带进后面的步骤。"""
    if not RESULT.exists():
        return []
    levels = common.hsk_levels()
    return [r for r in csv.DictReader(open(RESULT, encoding='utf-8')) if r['confused_with']
            and qualifies(r['target'], r['confused_with'], int(r['target_errors']), int(r['times']), levels)]


def selected(word):
    """入选的易混淆词，按占比从高到低"""
    rows = [r for r in selected_rows() if r['target'] == word]
    return [r['confused_with'] for r in sorted(rows, key=lambda r: -float(r['share']))]


# 词表注释里写着它的词：论文词库已有学习材料，只为易混淆词辨析走第 3–5 步（出辨析题要用它的例句），
# 第 6 步不做翻译检查，第 7 步不放进学习材料
PAIR_ONLY = '只做辨析'


def batch_notes(batch):
    """3_审核/<批>/词表.txt → {词: 注释}，按词表顺序"""
    path = common.REVIEW / batch / '词表.txt'
    if not path.exists():
        raise SystemExit(f'找不到 {path}：请先写好这一批的词表')
    notes, words = {}, []
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        word, _, note = line.partition('#')
        word = word.strip()
        if word:
            words.append(word)
            notes[word] = note.strip()
    if dup := [w for w, n in collections.Counter(words).items() if n > 1]:
        raise SystemExit(f'{path} 里有重复的词：{"、".join(dup)}')
    return notes


def home_batches():
    """词 → 它第一次出现的批次（按批号）。易混淆词只在这一批做，第 3–5 步的产出都在这一批"""
    home = {}
    for path in sorted(common.REVIEW.glob('第*批/词表.txt')):
        if re.fullmatch(r'第\d+批', path.parent.name):
            for word in batch_notes(path.parent.name):
                home.setdefault(word, path.parent.name)
    return home


def pair_only_words(batch):
    return {w for w, note in batch_notes(batch).items() if PAIR_ONLY in note}


def words_from_args(args, skip_confusables=False):
    """批次名（如「第01批」）→ 3_审核/<批>/词表.txt 里的词；也可以直接给词。
    skip_confusables：跳过注释里写着「易混淆词」的行。"""
    if len(args) == 1 and re.fullmatch(r'第\d+批', args[0]):
        return [w for w, note in batch_notes(args[0]).items() if not (skip_confusables and '易混淆词' in note)]
    return args


def main(words):
    levels = common.hsk_levels()
    old = list(csv.DictReader(open(RESULT, encoding='utf-8'))) if RESULT.exists() else []
    keep = [r for r in old if r['target'] not in words]
    new = []
    for word in words:
        rows = analyse(word, levels)
        new += rows
        picked = [f"{r['confused_with']}（{r['times']}/{r['target_errors']}，{r['share']:.0%}，{r['hsk_level']} 级）" for r in rows if r['selected']]
        top = [f"{r['confused_with']} {r['times']}次 {r['share']:.0%} {r['hsk_level'] or '表外'}级" for r in rows[:3] if r['confused_with']]
        print(f"{word}：语料 {rows[0]['sentences']} 句，偏误 {rows[0]['target_errors']} 处 → 入选 {'、'.join(picked) or '无'}；前三：{'; '.join(top) or '无'}", flush=True)
    with open(RESULT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(keep + new)


if __name__ == '__main__':
    main(words_from_args(sys.argv[1:], skip_confusables=True))
