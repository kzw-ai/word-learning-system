"""第 3 步　候选清单：词典义项、教材例句、搭配（论文 5.3.2–5.3.5，附录 H、K、L、M、N）。

用法：学习资料制作/.venv/bin/python 学习资料制作/工具/step3_candidates.py 第01批
产出：2_加工结果/候选清单/第01批/<词>.md（给人看）与 <词>.json（给第 4 步用）

- 例句（附录 H、K、L、M）：教材语料按「。？！」切句；结巴分词后目标词是其中一个词的句子才算（只是包含这几个字不算，
  如「想」在「理想」里）。句子复杂度 = 各词复杂度之和（查不到的词按 0），按复杂度、再按四至六级词个数升序排，列前 20 句。
  默认词典切不出目标词时，临时把它加入分词词典再找一次，清单里注明。
- 搭配（附录 N）：先列分级阅读库，再列维基库；搭配词限一至三级，按互信息降序，各列前 20 条。
- 词典：CC-CEDICT 里这个词和每个字的全部读音与义项。
"""
import json
import re
import sys

import jieba

import common
import step2_confusables

TOP = 20

# 句首杂质（教材录入、切句时混进来的）：对话的说话人「王静：」、上一句落下的右引号「”」、题号「2黄色代表……」。
# 去掉以后句子本身常常是好例句（「朋友：她去年秋天出生的，刚过完一岁生日。」），不去掉就被大模型当成片段判掉
# （作者同意，2026-10-29）。「我想：」「朋友说：」这类冒号前是说话动作的不去；冒号前含目标词的不去
SPEAKER = re.compile(r'^([一-龥A-Za-z·]{1,4})[：:]')
SPEECH_VERBS = ('说', '想', '是', '道', '问', '答', '写', '认为')
STRAY_CLOSE = re.compile(r'^[”’」』）)]+')
LEADING_NUMBER = re.compile(r'^[0-9０-９]+[、.．]?')
# 数字后面是这些字时，数字是句子的一部分（「20世纪」「28岁」「800万」「16点」），不去
NUMBER_UNITS = set('年月日号点时分秒岁世纪万千百亿元块角个位名次倍层米斤克件本张只条辆家所门期届级度%％多余来后前半')


def clean_start(s, word):
    while True:
        t = STRAY_CLOSE.sub('', s, count=1)
        m = LEADING_NUMBER.match(t)
        if m and m.end() < len(t) and t[m.end()] not in NUMBER_UNITS and not t[m.end()].isdigit():
            t = t[m.end():]
        m = SPEAKER.match(t)
        if m and not m.group(1).endswith(SPEECH_VERBS) and word not in m.group(1):
            t = t[m.end():]
        t = t.lstrip()
        if not t:
            return s
        if t == s:
            return t
        s = t


def sentences_with(word, sentences, complexity, levels):
    def find():
        found, seen = [], set()
        for book, s in sentences:
            if word not in s:
                continue
            s = clean_start(s, word)
            if s in seen:
                continue
            tokens = common.tokenize(s)
            if word not in tokens:
                continue
            seen.add(s)
            others = [t for t in common.without_punctuation(tokens) if t != word]
            found.append({
                'sentence': s, 'book': book, 'tokens': tokens,
                'complexity': round(common.sentence_complexity(tokens, complexity), 4),
                'hsk4_6_words': [t for t in others if levels.get(t, 0) >= 4],
                'not_in_hsk_list': sorted({t for t in others if t not in levels}),
            })
        return found

    found, note = find(), ''
    if not found:
        jieba.add_word(word)
        found, note = find(), '默认词典切不出这个词，已临时加入分词词典'
    found.sort(key=lambda c: (c['complexity'], len(c['hsk4_6_words'])))
    return found, note


def main(batch):
    words = step2_confusables.words_from_args([batch])
    levels = common.hsk_levels()
    complexity = common.word_complexity()
    dictionary = common.cedict()
    sentences = [(book, s) for book, text in common.textbook_texts() for s in common.split_sentences(text) if s.strip()]
    edu, wiki = common.load_collocation_rows()
    outdir = common.OUT / '候选清单' / batch
    outdir.mkdir(parents=True, exist_ok=True)
    for word in words:
        found, note = sentences_with(word, sentences, complexity, levels)
        data = {
            'word': word,
            'hsk_level': levels.get(word),
            'confusables': step2_confusables.selected(word),
            'cedict_word': dictionary.get(word, []),
            'cedict_chars': {ch: dictionary.get(ch, []) for ch in word},
            'textbook_sentences_total': len(found),
            'sentence_note': note,
            'sentences': found[:TOP],
            'collocations_edu': common.collocations_for(word, edu, levels)[:TOP],
            'collocations_wiki': common.collocations_for(word, wiki, levels)[:TOP],
        }
        (outdir / f'{word}.json').write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')

        md = [f'# {word}（HSK {data["hsk_level"] or "表外"} 级）', '']
        md += [f'易混淆词：{"、".join(data["confusables"]) or "无"}', '', '## CC-CEDICT', '']
        md += [f"- [{e['pinyin']}] " + ' / '.join(e['senses']) for e in data['cedict_word']] or ['- （词典未收）']
        for ch, es in data['cedict_chars'].items():
            md += [f"- 字「{ch}」[{e['pinyin']}] " + ' / '.join(e['senses'][:8]) for e in es[:4]]
        md += ['', f"## 教材例句（共 {len(found)} 句，按句子复杂度取前 {TOP}）" + (f"　※ {note}" if note else ''), '']
        md += [f"{i}. {c['sentence']}　复杂度 {c['complexity']}｜四至六级：{'、'.join(c['hsk4_6_words']) or '无'}"
               f"｜表外：{'、'.join(c['not_in_hsk_list']) or '无'}｜{c['book']}" for i, c in enumerate(data['sentences'], 1)]
        for key, label in (('collocations_edu', '分级阅读库'), ('collocations_wiki', '维基库')):
            md += ['', f'## 搭配（{label}，搭配词一至三级，按互信息）', '']
            md += [f"{i}. {c['collocation']}（{c['other']} {c['level']} 级，{c['type']}）互信息 {c['mi']:.2f}，频次 {c['freq']}"
                   for i, c in enumerate(data[key], 1)] or ['- 无']
        (outdir / f'{word}.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
        print(f"{word}：教材例句 {len(found)} 句{'（' + note + '）' if note else ''}，搭配 分级阅读库 {len(data['collocations_edu'])} / 维基库 {len(data['collocations_wiki'])}", flush=True)


if __name__ == '__main__':
    main(sys.argv[1])
