"""第 1 步　选词与分档（论文 5.3.1，附录 A、D、E、F）。

用法：学习资料制作/.venv/bin/python 学习资料制作/工具/step1_frequency.py
产出：2_加工结果/四级词加权词频分档.csv、2_加工结果/HSK2012等级表.csv

1. 附录 A：四级词及其 BCC Global 词频——直接用作者整理好的
   「新HSK四级词汇词频排序（参照BCC语料库.xlsx」（就是附录 A 的输出）。词的范围以汉办四级词表为准：
   Excel 里混进了 22 个一至二级词（「了、不、到」等），排除；四级词「倍」不在 Excel 里，BCC 词频记 0。
2. 附录 D：清洗合并后的教材语料用结巴分词（默认词典），统计词频。
3. 附录 E：四级词表左连接教材词频。
4. 附录 F：空值填 0，两列分别最小–最大规范化，总分 = 0.3 × BCC + 0.7 × 教材，降序排名。
   第 1–200 名高频、201–400 名中频、401 名以后低频（论文脚注 6）。
"""
import collections
import csv
import re

import openpyxl

import common


def main():
    levels = common.hsk_levels()
    common.OUT.mkdir(parents=True, exist_ok=True)
    with open(common.OUT / 'HSK2012等级表.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['word', 'level'])
        for word, lv in sorted(levels.items(), key=lambda x: (x[1], x[0])):
            w.writerow([word, lv])

    if common.TARGET_LEVEL == 4:
        # 附录 A 的输出：作者整理的四级词 BCC 词频。词的范围以汉办四级词表为准（左连接），
        # Excel 里混进的一至二级词（如「了、不、到」）不算，四级词在 Excel 里没有的，BCC 词频记 0。
        rows = [r for r in openpyxl.load_workbook(common.BCC_HSK4, read_only=True).worksheets[0].iter_rows(min_row=2, values_only=True)
                if r and r[0] and isinstance(r[1], (int, float))]
        bcc_of = {re.sub(r'（.*?）', '', str(r[0])).strip(): r[1] for r in rows}
        target_words = common.hsk_grade4_words()
        source = '作者 Excel'
    else:
        # 三级词没有作者整理的 Global 词频，用 BCC 多领域总表（算例句难度用的同一份；与 Global 的四级词排名相关 0.91）
        bcc_of = common.bcc_counts()
        target_words = common.hsk_target_words()
        source = 'BCC 多领域总表'
    grade4 = [(w, w, bcc_of.get(w, 0)) for w in target_words]
    extra = [w for w in bcc_of if w not in set(target_words)] if common.TARGET_LEVEL == 4 else []
    missing = [w for w in target_words if w not in bcc_of]

    # 附录 D：教材词频
    counts = collections.Counter()
    for _, text in common.textbook_texts():
        counts.update(common.tokenize(text))

    # 附录 E、F
    bcc = [f for _, _, f in grade4]
    tb = [counts.get(word, 0) for _, word, _ in grade4]

    def minmax(xs):
        lo, hi = min(xs), max(xs)
        return [(x - lo) / (hi - lo) if hi > lo else 0.0 for x in xs]

    scored = [(0.3 * b + 0.7 * t, label, word, raw_bcc, raw_tb)
              for (label, word, raw_bcc), b, t, raw_tb in zip(grade4, minmax(bcc), minmax(tb), tb)]
    scored.sort(key=lambda x: -x[0])
    # 论文脚注 6：600 个四级词按 200、400 名分三档；别的等级按词数三等分
    n = len(scored)
    cut1, cut2 = (200, 400) if common.TARGET_LEVEL == 4 else (round(n / 3), round(2 * n / 3))
    with open(common.TIERS_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['rank', 'word', 'label', 'tier', 'last_freq', 'bcc_freq', 'textbook_freq'])
        for i, (score, label, word, raw_bcc, raw_tb) in enumerate(scored, 1):
            tier = '高频' if i <= cut1 else '中频' if i <= cut2 else '低频'
            w.writerow([i, word, label, tier, round(score, 5), raw_bcc, raw_tb])
    print(f'{common.LEVEL_CN}级词 {len(scored)} 个（汉办词表），教材里出现过 {sum(1 for x in tb if x)} 个；HSK 等级表 {len(levels)} 词；'
          f'分档：前 {cut1} 名高频、前 {cut2} 名中频')
    if extra:
        print(f'作者 Excel 里不是四级、已排除的 {len(extra)} 个：{"、".join(extra)}')
    print(f'{source}里没有、BCC 词频记 0 的 {len(missing)} 个：{"、".join(missing)}')


if __name__ == '__main__':
    main()
