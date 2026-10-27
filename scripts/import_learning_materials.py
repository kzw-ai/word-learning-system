#!/usr/bin/env python3
"""把 data/learning_materials/*.json（PPT 解析产物）导入 words_extended.db。

每个词在课件里有多张递进的 slide（对应 VKS 不同入口）：
- 含字分解的 slide → 提取单字（字、拼音、词性、释义）
- 不含字分解、以词性开头的 slide → 提取词义
- 含 Collocation: 的 slide → 提取搭配（含频级标注）与英译
- Sentence: 段 → 提取例句（汉字句 + 逐词拼音 + 英译）

用法:
    python3 scripts/import_learning_materials.py            # 导入
    python3 scripts/import_learning_materials.py --report   # 只看解析质量报告，不写库
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / 'data' / 'learning_materials'
DB_PATH = PROJECT_ROOT / 'words_extended.db'

POS_WORDS = {
    'NOUN', 'VERB', 'ADJECTIVE', 'ADVERB', 'PRONOUN', 'PREPOSITION',
    'CONJUNCTION', 'INTERJECTION', 'NUMERAL', 'MEASURE', 'PARTICLE',
    'AUXILIARY', 'IDIOM',
}
POS_ABBREV = {
    'NOUN': 'n.', 'VERB': 'v.', 'ADJECTIVE': 'adj.', 'ADVERB': 'adv.',
    'PRONOUN': 'pron.', 'PREPOSITION': 'prep.', 'CONJUNCTION': 'conj.',
    'INTERJECTION': 'interj.', 'NUMERAL': 'num.', 'MEASURE': 'm.',
    'PARTICLE': 'part.', 'AUXILIARY': 'aux.', 'IDIOM': 'idiom',
}
# ---- 拼音工具（清洗脚本 clean_materials.py 也用） ----
TONE_MARKS = 'āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ'
_TONELESS = str.maketrans(TONE_MARKS, 'aaaaeeeeiiiioooouuuuüüüü')
_INITIALS = ('zh', 'ch', 'sh', 'b', 'p', 'm', 'f', 'd', 't', 'n', 'l', 'g',
             'k', 'h', 'j', 'q', 'x', 'r', 'z', 'c', 's', 'y', 'w', '')
_FINALS = {
    'a', 'o', 'e', 'ai', 'ei', 'ao', 'ou', 'an', 'en', 'ang', 'eng', 'ong', 'er',
    'i', 'ia', 'ie', 'iao', 'iu', 'ian', 'in', 'iang', 'ing', 'iong',
    'u', 'ua', 'uo', 'uai', 'ui', 'uan', 'un', 'uang', 'ueng', 'ue',
    'ü', 'üe', 'üan', 'ün',
}


def strip_tones(text: str) -> str:
    return text.translate(_TONELESS)


def is_pinyin_syllable(text: str) -> bool:
    """单个拼音音节（声调可有可无）：声母 + 韵母，宽松校验，足以区分音节边界"""
    plain = strip_tones(text.lower())
    return any(plain.startswith(ini) and plain[len(ini):] in _FINALS for ini in _INITIALS)


def split_word_pinyin(pinyin: str, count: int) -> list[str] | None:
    """把整词拼音切成 count 个音节，如 ('fāngmiàn', 2) -> ['fāng', 'miàn']。

    只在切法唯一时返回；有歧义或切不出时返回 None，宁可留空也不猜。
    声调符号与对应元音一一替换，长度不变，所以切分位置可直接用在原串上。
    """
    raw = re.sub(r"[\s'’]", '', pinyin or '')
    if not raw or count < 1:
        return None
    plain = strip_tones(raw.lower())
    solutions: list[list[str]] = []

    def walk(start: int, parts: list[str]) -> None:
        if len(solutions) > 1:
            return
        if len(parts) == count:
            if start == len(plain):
                solutions.append(parts)
            return
        for end in range(start + 1, min(len(plain), start + 6) + 1):
            if is_pinyin_syllable(plain[start:end]):
                walk(end, parts + [raw[start:end]])

    walk(0, [])
    return solutions[0] if len(solutions) == 1 else None


def split_pinyin_prefix(line: str) -> tuple[str, str] | None:
    """行首是带声调的拼音音节、后面还有内容时拆开：
    'hòu NOUN climate' -> ('hòu', 'NOUN climate')；'diǎn place; point' -> ('diǎn', 'place; point')。
    PPT 里单字的拼音和词性释义常挤在同一行。"""
    m = re.match(r'^(\S+)\s+(\S.*)$', (line or '').strip())
    if not m:
        return None
    token, rest = m.groups()
    if not re.search(f'[{TONE_MARKS}]', token) or not is_pinyin_syllable(token):
        return None
    return token, rest.strip()


NOISE_LINES = {"['", "’]", '[', ']', "'", '"', '’', '‘', '"]', '["', '【', '】'}


def has_chinese(text: str) -> bool:
    return any('一' <= ch <= '鿿' for ch in text)


def is_noise(line: str) -> bool:
    if line in NOISE_LINES:
        return True
    lower = line.lower()
    return lower.startswith('click') or lower == 'to the next page'


def clean_lines(text: str) -> list[str]:
    lines = []
    for ln in text.splitlines():
        ln = ln.strip().lstrip('【】').strip()
        if ln and not is_noise(ln):
            lines.append(ln)
    return lines


def leading_pos(line: str) -> str | None:
    """行首若是词性标记则返回该词性"""
    first = re.split(r'\s+', line, 1)[0].upper()
    return first if first in POS_WORDS else None


def format_definition(blocks: list[tuple[str, str]]) -> str:
    """[(POS, meaning)] -> 'v. change; vary' / 'n. change 或多词性拼接'"""
    parts = []
    for pos, meaning in blocks:
        abbrev = POS_ABBREV.get(pos, pos.lower())
        parts.append(f'{abbrev} {meaning}'.strip() if meaning else abbrev)
    return '; '.join(parts)


def parse_pos_blocks(lines: list[str]) -> list[tuple[str, str]]:
    """把若干行解析为 [(POS, meaning)]，词性行后可跟多行释义（释义也可能与词性同行）。
    没有词性前缀的独立释义行也保留（POS 为空字符串）。"""
    blocks: list[tuple[str, str]] = []
    for line in lines:
        pos = leading_pos(line)
        if pos:
            rest = line[len(pos):].strip() if line.upper().startswith(pos) else ''
            blocks.append((pos, rest))
        elif not has_chinese(line):
            if blocks:
                pos_name, meaning = blocks[-1]
                blocks[-1] = (pos_name, f'{meaning} {line}'.strip())
            else:
                blocks.append(('', line))
    return blocks


def looks_like_pinyin(line: str) -> bool:
    """拼音行：小写拉丁（可含声调符号），不是词性行，长度有限"""
    if leading_pos(line) or has_chinese(line) or len(line) > 24:
        return False
    return bool(re.match(r'^[a-züāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ\s]+$', line))


def split_sections(lines: list[str]) -> tuple[list[str], list[str], list[str]]:
    """按 Collocation:/Sentence: 分成 head / collocation / sentence 三段"""
    head: list[str] = []
    colloc: list[str] = []
    sent: list[str] = []
    bucket = head
    for line in lines:
        lower = line.lower()
        if lower.startswith('collocation'):
            bucket = colloc
            continue
        if lower.startswith('sentence'):
            bucket = sent
            continue
        bucket.append(line)
    return head, colloc, sent


def parse_characters(head: list[str], hanzi: str) -> tuple[list[dict], list[tuple[str, str]]]:
    """从含字分解的 head 段提取单字信息；返回 (字列表, 词级词性释义块)。

    head 形如: [更, gèng, ADVERB, more;..., 好, hǎo, ADJECTIVE, good;..., NOUN, better]
    最后一个字只取它的第一个词性块，其后的词性块视为整词的释义。
    """
    chars: list[dict] = []
    word_blocks: list[tuple[str, str]] = []
    idx = 0
    expected = list(hanzi)
    pos_in_word = 0

    def is_char_line(line: str, char: str) -> bool:
        """单字行：等于该字，或以该字开头后接词性/释义（如 '况 NOUN condition'）"""
        return line == char or (line.startswith(char) and len(line) > 1 and not has_chinese(line[1:]))

    while idx < len(head):
        line = head[idx]
        if pos_in_word < len(expected) and is_char_line(line, expected[pos_in_word]):
            char = expected[pos_in_word]
            # 字行内联的词性释义（'况 NOUN condition; situation'）
            inline_rest = line[1:].strip()
            idx += 1
            char_pinyin = ''
            block_lines: list[str] = [inline_rest] if inline_rest else []
            if not inline_rest and idx < len(head) and looks_like_pinyin(head[idx]):
                char_pinyin = head[idx]
                idx += 1
            elif not inline_rest and idx < len(head) and split_pinyin_prefix(head[idx]):
                # 拼音和词性释义挤在一行：'hòu NOUN climate'。此前整行被当成释义，
                # 拼音留空，释义里漏出 'hòu NOUN'
                char_pinyin, rest = split_pinyin_prefix(head[idx])  # type: ignore[misc]
                block_lines.append(rest)
                idx += 1
            # 收集该字的释义行，直到下一个字或段落结束
            while idx < len(head):
                nxt = head[idx]
                if pos_in_word + 1 < len(expected) and is_char_line(nxt, expected[pos_in_word + 1]):
                    break
                if has_chinese(nxt):
                    break
                block_lines.append(nxt)
                idx += 1
            blocks = parse_pos_blocks(block_lines)
            is_last_char = pos_in_word == len(expected) - 1
            if is_last_char and len(blocks) > 1:
                # 末字只保留第一个词性块，其余归整词
                chars.append({
                    'character': char,
                    'pinyin': char_pinyin,
                    'definition': format_definition(blocks[:1]),
                })
                word_blocks = blocks[1:]
            else:
                chars.append({
                    'character': char,
                    'pinyin': char_pinyin,
                    'definition': format_definition(blocks),
                })
            pos_in_word += 1
        else:
            idx += 1

    return chars, word_blocks


def parse_collocations(colloc: list[str]) -> list[dict]:
    """中文搭配行后跟英文翻译行。

    带空位的搭配在 PPT 里被拆成三行：'简直' / 'X' / '相信（三级）'（意为「简直 X 相信」）。
    此前只取到其中一行，整条搭配就丢了目标词。
    """
    result: list[dict] = []
    idx = 0
    while idx < len(colloc):
        line = colloc[idx]
        if (has_chinese(line) and idx + 2 < len(colloc)
                and colloc[idx + 1].strip().upper() == 'X' and has_chinese(colloc[idx + 2])):
            line = f'{line} X {colloc[idx + 2]}'
            idx += 2
        if has_chinese(line):
            translation = ''
            if (idx + 1 < len(colloc) and not has_chinese(colloc[idx + 1])
                    and not leading_pos(colloc[idx + 1])
                    and re.search(r'[a-zA-Z]{2,}', colloc[idx + 1])):
                translation = colloc[idx + 1]
                idx += 1
            result.append({'collocation': line, 'translation': translation})
        idx += 1
    return result


def is_sentence_line(line: str) -> bool:
    """完整中文句：含中文且以句读结尾"""
    return has_chinese(line) and line[-1] in '。？！?!'


def is_translation_line(line: str) -> bool:
    """英文翻译行：无中文、含空格分隔的多个拉丁词、非拼音注音行"""
    if has_chinese(line) or line.startswith('/'):
        return False
    words = line.split()
    return len(words) >= 2 and any(w.isascii() and w.isalpha() for w in words)


def parse_sentences(sent: list[str]) -> list[dict]:
    """Sentence 段 -> [{sentence, pinyin, translation}]

    句子行之后是交替的 词 / 拼音 token（'/' 可能独占一行或与拼音同行），
    最后一条英文行是整句翻译。
    """
    sentences: list[dict] = []
    current: dict | None = None
    pairs: list[str] = []
    pending_word: str | None = None
    expecting_pinyin = False

    def flush():
        nonlocal current, pairs, pending_word, expecting_pinyin
        if current:
            current['pinyin'] = ' '.join(pairs)
            sentences.append(current)
        current = None
        pairs = []
        pending_word = None
        expecting_pinyin = False

    for line in sent:
        if is_sentence_line(line) and len(line) >= 4:
            flush()
            current = {'sentence': line, 'pinyin': '', 'translation': ''}
        elif current is not None:
            if is_translation_line(line):
                current['translation'] = line
                flush()
            elif line == '/':
                expecting_pinyin = True
            elif line.startswith('/') and len(line) > 1:
                if pending_word:
                    pairs.append(f'{pending_word}/{line[1:].strip()}')
                    pending_word = None
                expecting_pinyin = False
            elif has_chinese(line):
                # 可能带前置标点，如 '，  多'
                word = re.sub(r'^[，。：；？！、\s]+', '', line)
                if word:
                    pending_word = word.split()[0] if ' ' in word else word
            elif expecting_pinyin and pending_word:
                pairs.append(f'{pending_word}/{line.strip()}')
                pending_word = None
                expecting_pinyin = False
    flush()
    return sentences


def parse_word(hanzi: str, pinyin: str, slides: list[dict]) -> dict:
    """综合一个词的所有 slide，取各自最擅长的信息"""
    characters: list[dict] = []
    word_blocks: list[tuple[str, str]] = []
    collocations: list[dict] = []
    examples: list[dict] = []
    simple_def_blocks: list[tuple[str, str]] = []

    best_pinyin = pinyin

    for cand in slides:
        lines = clean_lines(cand['slide_text'])
        # 去掉开头的词行
        if lines and lines[0] == hanzi:
            lines = lines[1:]
        # 拼音可能被 PPT 拆成多行（如 难过 -> nán / guò），拼回完整拼音
        pinyin_parts: list[str] = []
        while lines and looks_like_pinyin(lines[0]):
            # 首行直接收；后续行需带声调符号，避免把英文释义误当拼音
            if pinyin_parts and not re.search(r'[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜü]', lines[0]):
                break
            pinyin_parts.append(lines.pop(0))
            if len(pinyin_parts) >= len(hanzi):
                break
        if pinyin_parts:
            joined = pinyin_parts[0] if len(pinyin_parts) == 1 else ''.join(pinyin_parts)
            if len(joined) > len(best_pinyin):
                best_pinyin = joined
        head, colloc, sent = split_sections(lines)

        # 字分解 slide：head 中出现独立的单字行（仅多字词）
        if len(hanzi) > 1 and any(ln == hanzi[0] for ln in head):
            chars, wblocks = parse_characters(head, hanzi)
            if len(chars) == len(hanzi) and not characters:
                characters = chars
                word_blocks = word_blocks or wblocks
        else:
            blocks = parse_pos_blocks(head)
            if blocks and not simple_def_blocks:
                simple_def_blocks = blocks

        if colloc and not collocations:
            collocations = parse_collocations(colloc)

        for s in parse_sentences(sent):
            if s['sentence'] not in {e['sentence'] for e in examples}:
                examples.append(s)

    definition = format_definition(simple_def_blocks or word_blocks) or 'No definition provided'

    if len(hanzi) == 1 and not characters:
        characters = [{'character': hanzi, 'pinyin': best_pinyin, 'definition': definition}]

    # 课件里有的单字只给了释义没给拼音（如 方面 的「方」「面」），从整词拼音切出
    if characters and any(not c['pinyin'] for c in characters):
        syllables = split_word_pinyin(best_pinyin, len(characters))
        if syllables:
            for char, syllable in zip(characters, syllables):
                char['pinyin'] = char['pinyin'] or syllable

    return {
        'hanzi': hanzi,
        'pinyin': best_pinyin,
        'definition': definition,
        'characters': characters,
        'collocations': collocations,
        'examples': examples,
    }


def load_all_words() -> list[dict]:
    """读取全部课件 JSON，按汉字合并所有 slide 后解析"""
    merged: dict[str, dict] = {}
    for path in sorted(DATA_DIR.glob('*.json')):
        if path.name.startswith('_') or 'answer' in path.name.lower():
            continue
        data = json.loads(path.read_text())
        for cand in data.get('word_candidates', []):
            hanzi = cand['hanzi'].strip()
            entry = merged.setdefault(hanzi, {'pinyin': cand['pinyin'].strip(), 'slides': []})
            entry['slides'].append(cand)
    return [parse_word(h, e['pinyin'], e['slides']) for h, e in merged.items()]


def existing_hanzi_map(cursor: sqlite3.Cursor) -> dict[str, int]:
    """通过 character 表反查已有词的汉字 -> word_id"""
    cursor.execute(
        "SELECT word_id, GROUP_CONCAT(character, '') FROM character GROUP BY word_id"
    )
    return {hanzi: word_id for word_id, hanzi in cursor.fetchall() if hanzi}


def import_words(words: list[dict]) -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    known = existing_hanzi_map(cursor)
    added = skipped = 0

    for w in words:
        if w['hanzi'] in known:
            skipped += 1
            continue
        cursor.execute(
            'INSERT INTO word (pinyin, definition) VALUES (?, ?)',
            (w['pinyin'], w['definition']),
        )
        word_id = cursor.lastrowid
        for ch in w['characters']:
            cursor.execute(
                'INSERT INTO character (character, pinyin, definition, audio, word_id) VALUES (?, ?, ?, ?, ?)',
                (ch['character'], ch['pinyin'], ch['definition'], '', word_id),
            )
        for col in w['collocations']:
            cursor.execute(
                'INSERT INTO collocation (collocation, translation, audio, word_id) VALUES (?, ?, ?, ?)',
                (col['collocation'], col['translation'], '', word_id),
            )
        for ex in w['examples']:
            cursor.execute(
                'INSERT INTO example (sentence, pinyin, translation, audio, word_id) VALUES (?, ?, ?, ?, ?)',
                (ex['sentence'], ex['pinyin'], ex['translation'], '', word_id),
            )
        added += 1

    conn.commit()
    conn.close()
    print(f'✅ 导入完成：新增 {added} 个词，跳过已存在 {skipped} 个')


# 课件词表中的易混淆词对（论文设计：近义词分散在不同课次学习，此处建立辨析关联）
CONFUSABLE_PAIRS = [
    {
        'words': ('改变', '变化'),
        'reason': '都表示"事物变得不同"，一个常作动词、一个常作名词，学习者容易混用。',
        'difference': '「改变」强调主动去改动，多作及物动词（改变+宾语）；\n「变化」强调事物自身发生的变动，多作名词或不及物动词，不能直接带宾语。',
        'examples': '✓ 他决定改变自己的生活习惯。\n✗ 他决定变化自己的生活习惯。（错误）\n✓ 这几年城市的变化很大。\n✓ 天气变化很快。',
        'tips': '后面带宾语用「改变」；说"有/发生了什么变化"用「变化」。',
        'difficulty_level': 2,
    },
    {
        'words': ('通过', '经过'),
        'reason': '都有"从中间过去"和"经由"的意思，很多语境看似都能用。',
        'difference': '「通过」侧重凭借某种方式/手段达到目的，也表示议案等被批准；\n「经过」侧重经历的过程或路过某地，也可作名词（事情的经过）。',
        'examples': '✓ 通过学习，他的汉语提高了很多。\n✓ 我每天上班都经过那家书店。\n✓ 计划通过了。\n✗ 计划经过了。（错误）\n✓ 请告诉我事情的经过。\n✗ 请告诉我事情的通过。（错误）',
        'tips': '强调"靠什么办法"用「通过」；强调"过程/路过"用「经过」。',
        'difficulty_level': 3,
    },
    {
        'words': ('看法', '想法'),
        'reason': '都表示头脑里的观点，常被当作完全同义。',
        'difference': '「看法」是对人或事物的评价、意见（对……的看法）；\n「想法」是心里的打算、主意，不一定针对某个对象。',
        'examples': '✓ 你对这件事有什么看法？\n✓ 我有一个好想法：周末去爬山吧。\n✗ 我有一个好看法：周末去爬山吧。（错误）',
        'tips': '评价别人/事情用「看法」；自己的主意打算用「想法」。',
        'difficulty_level': 2,
    },
    {
        'words': ('降低', '下降'),
        'reason': '都表示"变低"，方向相同，学习者常互换。',
        'difference': '「降低」是及物动词，可以带宾语（降低价格/标准）；\n「下降」是不及物动词，主语自己变低，不能带宾语。',
        'examples': '✓ 商店降低了价格。\n✗ 商店下降了价格。（错误）\n✓ 气温下降了五度。\n✓ 成绩下降了。',
        'tips': '"把什么降下来"用「降低」；"自己往下走"用「下降」。',
        'difficulty_level': 2,
    },
    {
        'words': ('发生', '出现'),
        'reason': '都表示"原来没有的事物有了"，在很多句子里好像都通。',
        'difference': '「发生」用于事件、情况（事故/问题/变化发生）；\n「出现」用于具体或抽象事物的显现（人/彩虹/新情况出现），侧重"从无到有地显露"。',
        'examples': '✓ 昨天发生了一起交通事故。\n✓ 天空出现了一道彩虹。\n✗ 天空发生了一道彩虹。（错误）\n✓ 会谈中出现了新问题。／会谈中发生了新问题。（都可，侧重不同）',
        'tips': '事件类主语（事故、事情）配「发生」；能"看见/显露出来"的配「出现」。',
        'difficulty_level': 3,
    },
    {
        'words': ('方法', '办法'),
        'reason': '都表示"做事的方式"，日常口语中界限模糊。',
        'difference': '「方法」偏书面、系统，指做事的门路和程序（学习方法、教学方法）；\n「办法」偏口语，指解决具体问题的主意（想办法、没办法）。',
        'examples': '✓ 这种学习方法很有效。\n✓ 别着急，我们一起想办法。\n✗ 别着急，我们一起想方法。（不自然）\n✓ 我实在没办法了。',
        'tips': '固定搭配记牢：想办法、没办法；学习/研究/使用+方法。',
        'difficulty_level': 2,
    },
    {
        'words': ('天气', '气候'),
        'reason': '都描述大气状况，中文里一短期一长期，学习者常搞反。',
        'difference': '「天气」指短时间（今天/这几天）的阴晴冷暖；\n「气候」指一个地区多年的平均大气规律，也比喻大环境。',
        'examples': '✓ 今天天气真好。\n✗ 今天气候真好。（错误）\n✓ 昆明气候温和，四季如春。\n✓ 我还不习惯北方的气候。',
        'tips': '说"今天/明天"必用「天气」；说一个地方长年的特点用「气候」。',
        'difficulty_level': 1,
    },
    {
        'words': ('最好', '更好'),
        'reason': '一个最高级一个比较级，但「最好」还有"建议"的用法，容易用错。',
        'difference': '「更好」是比较级：比原来/别的好；\n「最好」是最高级，也常用来提建议（你最好早点睡）。',
        'examples': '✓ 这家餐厅的菜比那家更好。\n✓ 这是我吃过的最好的菜。\n✓ 你最好先给他打个电话。\n✗ 你更好先给他打个电话。（错误）',
        'tips': '两个比用「更好」；多个里挑第一或给人提建议用「最好」。',
        'difficulty_level': 2,
    },
]


def seed_vocab_confusable_pairs() -> None:
    """为课件词表中的近义词建立 confusable_pairs 关联（按汉字反查 word_id）"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    known = existing_hanzi_map(cursor)
    added = skipped = missing = 0

    for pair in CONFUSABLE_PAIRS:
        h1, h2 = pair['words']
        id1, id2 = known.get(h1), known.get(h2)
        if not id1 or not id2:
            print(f'⚠️  {h1}/{h2}: 词表缺失，跳过')
            missing += 1
            continue
        cursor.execute(
            'SELECT 1 FROM confusable_pairs WHERE (word1_id = ? AND word2_id = ?) OR (word1_id = ? AND word2_id = ?)',
            (id1, id2, id2, id1),
        )
        if cursor.fetchone():
            skipped += 1
            continue
        cursor.execute(
            '''INSERT INTO confusable_pairs
               (word1_id, word2_id, reason, difference, examples, tips, difficulty_level)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (id1, id2, pair['reason'], pair['difference'], pair['examples'],
             pair['tips'], pair['difficulty_level']),
        )
        added += 1

    conn.commit()
    conn.close()
    print(f'✅ 易混淆词对：新增 {added}，已存在 {skipped}，词缺失 {missing}')


def quality_report(words: list[dict]) -> None:
    print(f'共解析 {len(words)} 个词\n')
    issues = 0
    for w in words:
        problems = []
        if w['definition'] == 'No definition provided':
            problems.append('缺词义')
        if len(w['characters']) != len(w['hanzi']):
            problems.append(f"字分解 {len(w['characters'])}/{len(w['hanzi'])}")
        elif any(not c['definition'] for c in w['characters']) and len(w['hanzi']) > 1:
            problems.append('有单字缺释义')
        if not w['examples']:
            problems.append('缺例句')
        elif any(not e['translation'] for e in w['examples']):
            problems.append('有例句缺翻译')
        elif any(not e['pinyin'] for e in w['examples']):
            problems.append('有例句缺拼音')
        flag = ' ⚠️ ' + ', '.join(problems) if problems else ''
        if problems:
            issues += 1
        print(f"{w['hanzi']}({w['pinyin']}): 词义[{w['definition'][:40]}] "
              f"字{len(w['characters'])} 搭配{len(w['collocations'])} 例句{len(w['examples'])}{flag}")
    print(f'\n{issues} 个词有解析问题')


if __name__ == '__main__':
    parsed = load_all_words()
    if '--report' in sys.argv:
        quality_report(parsed)
    else:
        import_words(parsed)
        seed_vocab_confusable_pairs()
