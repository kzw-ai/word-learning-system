"""第 3 步　候选清单：词典义项、教材例句、搭配（论文 5.3.2–5.3.5，附录 H、K、L、M、N）。

用法：学习资料制作/.venv/bin/python 学习资料制作/工具/step3_candidates.py 第01批
产出：2_加工结果/候选清单/第01批/<词>.md（给人看）与 <词>.json（给第 4 步用）

- 例句（附录 H、K、L、M）：教材语料按「。？！」切句；结巴分词后目标词是其中一个词的句子才算（只是包含这几个字不算，
  如「想」在「理想」里）。句子复杂度 = 各词复杂度之和（查不到的词按 0），按复杂度、再按四至六级词个数升序排，列前 20 句。
  默认词典切不出目标词时，临时把它加入分词词典再找一次，清单里注明。
- 搭配（附录 N）：先列教材库，再列维基库；搭配词限一至三级，按互信息降序，各列前 20 条。
- 词典：CC-CEDICT 里这个词和每个字的全部读音与义项。
"""
import json
import sys

import jieba

import common
import step2_confusables

TOP = 20


def sentences_with(word, sentences, complexity, levels):
    def find():
        found, seen = [], set()
        for book, s in sentences:
            if word not in s or s in seen:
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
        for key, label in (('collocations_edu', '教材库'), ('collocations_wiki', '维基库')):
            md += ['', f'## 搭配（{label}，搭配词一至三级，按互信息）', '']
            md += [f"{i}. {c['collocation']}（{c['other']} {c['level']} 级，{c['type']}）互信息 {c['mi']:.2f}，频次 {c['freq']}"
                   for i, c in enumerate(data[key], 1)] or ['- 无']
        (outdir / f'{word}.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
        print(f"{word}：教材例句 {len(found)} 句{'（' + note + '）' if note else ''}，搭配 教材库 {len(data['collocations_edu'])} / 维基库 {len(data['collocations_wiki'])}", flush=True)


if __name__ == '__main__':
    main(sys.argv[1])
