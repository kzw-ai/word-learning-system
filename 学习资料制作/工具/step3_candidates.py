"""第 3 步　候选清单：词典义项、教材例句、搭配（论文 5.3.2–5.3.5，附录 H、K、L、M、N）。

用法：学习资料制作/.venv/bin/python 学习资料制作/工具/step3_candidates.py 第01批
产出：2_加工结果/候选清单/第01批/<词>.md（给人看）与 <词>.json（给第 4 步用）

- 例句（附录 H、K、L、M）：教材语料按「。？！」切句；结巴分词后目标词是其中一个词的句子才算（只是包含这几个字不算，
  如「想」在「理想」里）。句子复杂度 = 各词复杂度之和（查不到的词按 0），按复杂度、再按四至六级词个数升序排，列前 20 句。
  默认词典切不出目标词时，临时把它加入分词词典再找一次，清单里注明。
- 搭配（附录 N）：先列分级阅读库，再列维基库；搭配词限一至三级，按互信息降序，各列前 20 条。
- 词典：CC-CEDICT 里这个词和每个字的全部读音与义项。
"""
import collections
import json
import re
import sys

import jieba

import common
import step2_confusables
import step4_semantic_tasks

TOP = 20
# 只学四级义项的「得」「等」（step4_semantic_tasks.HSK4_ENTRY）：教材里多是低级义项，前 20 句可能一句四级义项都没有
# （「等」105 句候选，前 20 句全是 wait），放宽到 60 句
TOP_HSK4_ENTRY = 60

# 句首杂质（教材录入、切句时混进来的）：对话的说话人「王静：」、上一句落下的右引号「”」、题号「2黄色代表……」。
# 去掉以后句子本身常常是好例句（「朋友：她去年秋天出生的，刚过完一岁生日。」），不去掉就被大模型当成片段判掉
# （作者同意，2026-10-29；作者论文词库的例句也有带说话人的）。宁可少删，不误删：
# - 说话人只认课文里当说话人出现过至少 3 次的标签（小丽、王静、同事、高老师……）；「我决定：」「国家规定：」这类
#   只出现一两次的是句子内容，不去；以说话动作结尾的（罗伟说：、我想：）不去。标签里有目标词也去
#   （「记者：请问您怎么看？」没有用「记者」造句，去掉后正文里没有目标词，下面按分词就筛掉了）
# - 数字只去明确的题号：带分隔符的（「2、」「2.」），或者紧跟着正文（「6如果你……」）；后面是单位、量词、
#   标点的是句子的一部分（「20世纪」「3天后」「8:00」「20~30人」「2.5倍」），不去。五位以上的数字串是录入杂质
SPEAKER = re.compile(r'^([一-龥A-Za-z·]{1,4})[：:]')
SPEECH_VERBS = ('说', '想', '是', '道', '问', '答', '写', '认为')
SPEAKER_MIN = 3
STRAY_CLOSE = re.compile(r'^[”’」』）)]+')
DIGITS = re.compile(r'^[0-9０-９]+')
NUMBER_UNITS = set('年月日号点时分秒岁世纪万千百亿元块角个位名次倍层米斤克件本张只条辆家所门期届级度多余来后前半'
                   '天周遍趟口声步种样些成折项份篇句段页课题道行排组对双台部'
                   '公厘毫美英欧节场首封座棵朵盒袋匹群代楼路班室类人至到')


def speaker_labels(sentences):
    """课文里当说话人出现过至少 SPEAKER_MIN 次的标签"""
    head = re.compile(r'^[”’」』）)]*[0-9０-９]*([一-龥A-Za-z·]{1,4})[：:]')
    counts = collections.Counter(m.group(1) for _, s in sentences if (m := head.match(s)))
    return {k for k, n in counts.items() if n >= SPEAKER_MIN and not k.endswith(SPEECH_VERBS)}


def strip_number(t):
    m = DIGITS.match(t)
    if not m:
        return t
    rest = t[m.end():]
    if not rest:
        return t
    if len(m.group()) >= 5:  # 「13797915397002000“那妻子的字条……」
        return re.sub(r'^[0-9０-９\-]+', '', t)
    if rest[0] in '、' or (rest[0] in '.．' and not rest[1:2].isdigit()):
        return rest[1:]
    if ('一' <= rest[0] <= '鿿' or rest[0] in '“"') and rest[0] not in NUMBER_UNITS:
        return rest
    return t


def clean_start(s, word, speakers):
    while True:
        t = strip_number(STRAY_CLOSE.sub('', s, count=1))
        m = SPEAKER.match(t)
        if m and m.group(1) in speakers:
            t = t[m.end():]
        t = t.lstrip()
        if not t:
            return s
        if t == s:
            return t
        s = t


# 默认分词、加入词典都切不出目标词时的最后一招：拆开粘在一起的「数词、指示词、程度副词 + 目标词」（一座、这场、很帅）
# 和「目标词 + 方位词、补语」（桥上、留下、入口处）。只在一句都找不到时用，不影响找得到例句的词
GLUED_BEFORE = set('一二三四五六七八九十两几这那每哪半很真太好挺更最0123456789')
GLUED_AFTER = {'上', '里', '下', '在', '给', '着', '了', '过', '到', '起', '处'}


def split_glued(tokens, word):
    out = []
    for t in tokens:
        if t != word and t.endswith(word) and all(ch in GLUED_BEFORE for ch in t[:-len(word)]):
            out += [t[:-len(word)], word]
        elif t != word and t.startswith(word) and t[len(word):] in GLUED_AFTER:
            out += [word, t[len(word):]]
        else:
            out.append(t)
    return out


def sentences_with(word, sentences, complexity, levels, speakers=frozenset()):
    def find(split=False):
        found, seen = [], set()
        for book, s in sentences:
            if word not in s:
                continue
            s = clean_start(s, word, speakers)
            if s in seen:
                continue
            tokens = common.tokenize(s)
            if split:
                tokens = split_glued(tokens, word)
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
    if not found:
        found, note = find(split=True), '分词把目标词和前后的字连在一起（一座、很帅、桥上），拆开后再找'
    found.sort(key=lambda c: (c['complexity'], len(c['hsk4_6_words'])))
    return found, note


def main(batch):
    words = step2_confusables.words_from_args([batch])
    levels = common.hsk_levels()
    complexity = common.word_complexity()
    dictionary = common.cedict()
    sentences = [(book, s) for book, text in common.textbook_texts() for s in common.split_sentences(text) if s.strip()]
    speakers = speaker_labels(sentences)
    edu, wiki = common.load_collocation_rows()
    outdir = common.OUT / '候选清单' / batch
    outdir.mkdir(parents=True, exist_ok=True)
    for word in words:
        found, note = sentences_with(word, sentences, complexity, levels, speakers)
        top = TOP_HSK4_ENTRY if word in step4_semantic_tasks.HSK4_ENTRY else TOP
        data = {
            'word': word,
            'hsk_level': levels.get(word),
            'confusables': step2_confusables.selected(word),
            'cedict_word': dictionary.get(word, []),
            'cedict_chars': {ch: dictionary.get(ch, []) for ch in word},
            'textbook_sentences_total': len(found),
            'sentence_note': note,
            'sentences': found[:top],
            'collocations_edu': common.collocations_for(word, edu, levels)[:TOP],
            'collocations_wiki': common.collocations_for(word, wiki, levels)[:TOP],
        }
        (outdir / f'{word}.json').write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')

        md = [f'# {word}（HSK {data["hsk_level"] or "表外"} 级）', '']
        md += [f'易混淆词：{"、".join(data["confusables"]) or "无"}', '', '## CC-CEDICT', '']
        md += [f"- [{e['pinyin']}] " + ' / '.join(e['senses']) for e in data['cedict_word']] or ['- （词典未收）']
        for ch, es in data['cedict_chars'].items():
            md += [f"- 字「{ch}」[{e['pinyin']}] " + ' / '.join(e['senses'][:8]) for e in es[:4]]
        md += ['', f"## 教材例句（共 {len(found)} 句，按句子复杂度取前 {top}）" + (f"　※ {note}" if note else ''), '']
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
