#!/usr/bin/env python3
"""修复已入库学习素材里的已知缺陷。幂等：重复执行不再改动任何行。

import_learning_materials.py 只插入不更新，修好它的解析器并不能改正已经入库的
数据，所以由这个脚本按同样的规则修一遍。后端每次启动时也会调用 clean_database。

修复的六类问题：
1. 种子脚本 setup_confusable_data.py（已删除）早期写入的词拼音没有声调（yinwei、suoyi……），
   辨析页直接显示成这样。这些是项目自己的种子数据，没有课件可推，按对照表改正。
2. 课件里单字的拼音和词性释义挤在一行（'hòu NOUN climate'），整行被当成了释义：
   拼音为空，释义里漏出 'hòu NOUN'。拆开，词性改成 n. / v. 缩写。
3. 仍缺拼音、或拼音不带声调的单字，从整词拼音按音节切出（切法唯一时才填）。
4. 带空位的搭配（'简直' / 'X' / '相信（三级）'）只存了其中一行，丢了目标词。
   用修好的解析器从课件原文找出完整的那条替换（唯一匹配时才改）。
5. 课件里有素材、库里却是空壳的词：导入脚本遇到已存在的词整个跳过，而辨析种子脚本
   先插了只有两个字的「发现」，课件里「发现」的搭配和例句就从没进库。补入，不改已有行。
6. 孤立的测试词（苹果、学校、老师、重复的发生……）：没有字、例句、搭配，也没有被
   辨析词对、练习题、学习进度、学习会话引用。删除，连同指向它的推荐日志（旧引擎曾把
   这些无素材的词推荐给测试用户；现在只推荐有例句的词）。其余任何一处有引用就保留。
7. 论文课件素材的拼音错误（2026-10-29 生成发音音频时查出，作者确认改正）：
   「通过」的「通」标成 tòng、「当时」标成 dàngshí、例句里的「当 dàng」「王 wàng」「脏 zàng」；
   还有 10 条例句的拼音行缺了句尾（课件里那几个字的拼音没解析出来）。只在仍是错的值时改，
   而且只改论文词库的词：归属四级批次（hsk4_batch_owner）的词由流水线校对，不动
   （「当时 dàngshí」也是合法读音，义为「当即」，不能见到就改）。

用法：
    python3 scripts/clean_materials.py --report     # 只看会改什么，不写库
    python3 scripts/clean_materials.py --apply      # 写库
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from import_learning_materials import (  # noqa: E402
    TONE_MARKS,
    format_definition,
    load_all_words,
    parse_pos_blocks,
    split_pinyin_prefix,
    split_word_pinyin,
    strip_tones,
)

# 7. 论文课件素材的拼音勘误：(词, 错误拼音) → 正确拼音；(词, 字, 错误拼音) → 正确拼音
WORD_PINYIN_FIXES = {('当时', 'dàngshí'): 'dāngshí'}
CHAR_PINYIN_FIXES = {('当时', '当', 'dàng'): 'dāng', ('通过', '通', 'tòng'): 'tōng'}
# 例句里个别词的读音：例句 → [(错误的「词/拼音」, 正确的)]
EXAMPLE_TOKEN_FIXES = {
    '当他提出送她回家时，她竟然没有拒绝。': [('当/dàng', '当/dāng')],
    '当时我还不懂是什么意思。': [('当时/dàngshí', '当时/dāngshí')],
    '经理：小王，卫生间怎么那么脏啊？': [('王/wàng', '王/wáng'), ('脏/zàng', '脏/zāng')],
    '小王：表演得真棒。李老师：是我孙子。': [('王/wàng', '王/wáng')],
}
# 拼音行缺了句尾的例句：拼音行里的字还和例句对不上时，整行换成补全的
EXAMPLE_PINYIN_LINES = {
    '小林：我还不习惯北方的气候，估计是天气太干。':
        '小林/xiǎolín ： 我/wǒ 还/hái 不/bù 习惯/xíguàn 北方/běifāng 的/de 气候/qìhòu ， 估计/gūjì 是/shì 天气/tiānqì 太/tài 干/gān 。',
    '有些经过科学研究，证明是错误的。':
        '有些/yǒuxiē 经过/jīngguò 科学/kēxué 研究/yánjiū ， 证明/zhèngmíng 是/shì 错误/cuòwù 的/de 。',
    '就这样过了三年，他终于去实现自己的想法了。':
        '就/jiù 这样/zhèyàng 过/guò 了/le 三/sān 年/nián ， 他/tā 终于/zhōngyú 去/qù 实现/shíxiàn 自己/zìjǐ 的/de 想法/xiǎngfa 了/le 。',
    '如果你想正确使用筷子，那就好好练习吧。':
        '如果/rúguǒ 你/nǐ 想/xiǎng 正确/zhèngquè 使用/shǐyòng 筷子/kuàizi ， 那/nà 就/jiù 好好/hǎohāo 练习/liànxí 吧/ba 。',
    '说完，他就出去了，我感觉到他在擦眼泪。':
        '说完/shuōwán ， 他/tā 就/jiù 出去/chūqù 了/le ， 我/wǒ 感觉到/gǎnjuédào 他/tā 在/zài 擦/cā 眼泪/yǎnlèi 。',
    '我的电话响了，看号码似乎是公司的。':
        '我/wǒ 的/de 电话/diànhuà 响/xiǎng 了/le ， 看/kàn 号码/hàomǎ 似乎/sìhū 是/shì 公司/gōngsī 的/de 。',
    '生意就这样成了。': '生意/shēngyì 就/jiù 这样/zhèyàng 成/chéng 了/le 。',
    '小雨：在我看来，赚钱多少不是最重要的，兴趣才是关键。':
        '小雨/xiǎoyǔ ： 在/zài 我/wǒ 看来/kànlái ， 赚钱/zhuànqián 多少/duōshao 不是/bùshì 最/zuì 重要/zhòngyào 的/de ， '
        '兴趣/xìngqù 才/cái 是/shì 关键/guānjiàn 。',
    '诸位，万页书可以使你成为一个学者了。':
        '诸位/zhūwèi ， 万/wàn 页/yè 书/shū 可以/kěyǐ 使/shǐ 你/nǐ 成为/chéngwéi 一个/yīgè 学者/xuézhě 了/le 。',
    '不愿意发生的事情终于出现了。':
        '不/bù 愿意/yuànyì 发生/fāshēng 的/de 事情/shìqing 终于/zhōngyú 出现/chūxiàn 了/le 。',
}
_HANZI = re.compile('[\u4e00-\u9fff]')


def _pinyin_line_hanzi(line: str | None) -> str:
    """拼音行「我/wǒ 想/xiǎng 。」里的汉字：「我想」"""
    return ''.join(_HANZI.findall(''.join(t.partition('/')[0] for t in (line or '').split())))


def fixed_example_pinyin(sentence: str, pinyin: str | None) -> str:
    """第 7 类勘误后的例句拼音行；没有要改的就原样返回"""
    line = pinyin or ''
    full = EXAMPLE_PINYIN_LINES.get(sentence)
    if full and _pinyin_line_hanzi(line) != ''.join(_HANZI.findall(sentence)):
        line = full
    for bad, good in EXAMPLE_TOKEN_FIXES.get(sentence, []):
        line = re.sub(f'(?<!\\S){re.escape(bad)}(?!\\S)', good, line)
    return line


# setup_confusable_data.py 早期写入的无声调词拼音
SEED_WORD_PINYIN = {
    'fasheng': 'fāshēng',
    'faxian': 'fāxiàn',
    'yiwei': 'yǐwéi',
    'renwei': 'rènwéi',
    'yinwei': 'yīnwèi',
    'suoyi': 'suǒyǐ',
}

_TONED = re.compile(f'[{TONE_MARKS}]')


def _has_tone(text: str | None) -> bool:
    return bool(text and _TONED.search(text))


def plan_fixes(conn: sqlite3.Connection) -> list[tuple[str, str, tuple]]:
    """算出要执行的修改：[(说明, SQL, 参数)]。只读，不写库。"""
    fixes: list[tuple[str, str, tuple]] = []

    # 1. 种子词的无声调拼音
    word_pinyin = {}
    for wid, pinyin in conn.execute('SELECT id, pinyin FROM word'):
        fixed = SEED_WORD_PINYIN.get(pinyin)
        if fixed:
            fixes.append((f'词 {wid} 拼音 {pinyin} -> {fixed}',
                          'UPDATE word SET pinyin = ? WHERE id = ?', (fixed, wid)))
        word_pinyin[wid] = fixed or pinyin

    # 2. 拼音挤在释义里
    chars = conn.execute(
        'SELECT id, word_id, character, pinyin, definition FROM character ORDER BY word_id, id'
    ).fetchall()
    char_pinyin = {}
    for cid, _wid, char, pinyin, definition in chars:
        split = split_pinyin_prefix(definition or '')
        if split and (not pinyin or strip_tones(pinyin) == strip_tones(split[0])):
            new_pinyin, rest = split
            new_def = format_definition(parse_pos_blocks([rest])) or rest
            fixes.append((f'字 {cid}「{char}」{definition!r} -> {new_pinyin} / {new_def!r}',
                          'UPDATE character SET pinyin = ?, definition = ? WHERE id = ?',
                          (new_pinyin, new_def, cid)))
            pinyin = new_pinyin
        char_pinyin[cid] = pinyin

    # 3. 缺拼音或无声调的单字：按整词拼音切
    by_word: dict[int, list[tuple[int, str]]] = {}
    for cid, wid, char, _p, _d in chars:
        by_word.setdefault(wid, []).append((cid, char))
    for wid, members in by_word.items():
        current = [char_pinyin[cid] for cid, _ in members]
        if all(_has_tone(p) for p in current) or not _has_tone(word_pinyin.get(wid)):
            continue
        syllables = split_word_pinyin(word_pinyin[wid], len(members))
        if not syllables:
            continue
        for (cid, char), old, syllable in zip(members, current, syllables):
            # 已有带声调的拼音不动；无声调的只在与切出的音节相同（只差声调）时替换，
            # 保留轻声等本来就不标调的读法
            if old and (_has_tone(old) or strip_tones(old) != strip_tones(syllable) or not _has_tone(syllable)):
                continue
            fixes.append((f'字 {cid}「{char}」拼音 {old!r} -> {syllable}',
                          'UPDATE character SET pinyin = ? WHERE id = ?', (syllable, cid)))

    # 4. 缺目标词的搭配：从课件原文找回完整的那条
    hanzi_by_word = {wid: ''.join(c for _, c in members) for wid, members in by_word.items()}
    source_words = load_all_words()
    parsed = {w['hanzi']: [c['collocation'] for c in w['collocations']] for w in source_words}
    for cid, wid, text in conn.execute('SELECT id, word_id, collocation FROM collocation'):
        head = hanzi_by_word.get(wid)
        if not head or head in text:
            continue
        candidates = [c for c in parsed.get(head, []) if text in c and head in c]
        if len(candidates) == 1:
            fixes.append((f'搭配 {cid}（{head}）{text!r} -> {candidates[0]!r}',
                          'UPDATE collocation SET collocation = ? WHERE id = ?', (candidates[0], cid)))

    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}

    # 5. 空壳词补入课件素材
    if 'example' in tables:
        for source in source_words:
            if not (source['collocations'] or source['examples']):
                continue
            for wid, hanzi in hanzi_by_word.items():
                if hanzi != source['hanzi']:
                    continue
                has_material = conn.execute(
                    'SELECT (SELECT COUNT(*) FROM example WHERE word_id = ?) + '
                    '(SELECT COUNT(*) FROM collocation WHERE word_id = ?)', (wid, wid)
                ).fetchone()[0]
                if has_material:
                    continue
                for col in source['collocations']:
                    fixes.append((f'词 {wid}（{hanzi}）补搭配 {col["collocation"]!r}',
                                  'INSERT INTO collocation (collocation, translation, audio, word_id) VALUES (?, ?, ?, ?)',
                                  (col['collocation'], col['translation'], '', wid)))
                for ex in source['examples']:
                    # 补入时就套用第 7 类勘误：同一轮里第 7 类看不到这些新行，否则要到下次启动才改
                    fixes.append((f'词 {wid}（{hanzi}）补例句 {ex["sentence"]!r}',
                                  'INSERT INTO example (sentence, pinyin, translation, audio, word_id) VALUES (?, ?, ?, ?, ?)',
                                  (ex['sentence'], fixed_example_pinyin(ex['sentence'], ex['pinyin']), ex['translation'], '', wid)))

    # 6. 孤立测试词。引用检查只针对库里存在的表；任何一处有引用都不删
    references = [
        ('character', 'word_id'), ('example', 'word_id'), ('collocation', 'word_id'),
        ('confusable_pairs', 'word1_id'), ('confusable_pairs', 'word2_id'),
        ('exercise_item', 'word_id'), ('user_progress', 'word_id'),
        ('learning_session', 'word_id'),
    ]
    conditions = ' AND '.join(
        f'NOT EXISTS (SELECT 1 FROM {table} WHERE {column} = w.id)'
        for table, column in references if table in tables
    )
    for wid, pinyin in conn.execute(f'SELECT w.id, w.pinyin FROM word w WHERE {conditions}').fetchall():
        if 'adaptive_recommendation' in tables:
            stale = conn.execute('SELECT COUNT(*) FROM adaptive_recommendation WHERE target_word_id = ?',
                                 (wid,)).fetchone()[0]
            if stale:
                fixes.append((f'删除指向孤立词 {wid} 的 {stale} 条推荐日志',
                              'DELETE FROM adaptive_recommendation WHERE target_word_id = ?', (wid,)))
        fixes.append((f'删除孤立词 {wid}（{pinyin}）', 'DELETE FROM word WHERE id = ?', (wid,)))

    # 7. 论文课件素材的拼音勘误，只改论文词库的词。字按 id 顺序拼成词（与页面显示一致）
    batch_words = {r for (r,) in conn.execute("SELECT ref_id FROM hsk4_batch_owner WHERE kind = 'word'")} \
        if 'hsk4_batch_owner' in tables else set()
    word_chars: dict[int, list[tuple[int, str, str]]] = {}
    for cid, wid, char, pinyin in conn.execute('SELECT id, word_id, character, pinyin FROM character ORDER BY word_id, id'):
        if wid not in batch_words:
            word_chars.setdefault(wid, []).append((cid, char, pinyin))
    hanzi_of = {wid: ''.join(c for _, c, _ in cs) for wid, cs in word_chars.items()}
    for wid, pinyin in conn.execute('SELECT id, pinyin FROM word').fetchall():
        if wid in batch_words:
            continue
        fixed = WORD_PINYIN_FIXES.get((hanzi_of.get(wid), pinyin))
        if fixed:
            fixes.append((f'词 {wid}（{hanzi_of[wid]}）拼音 {pinyin} -> {fixed}',
                          'UPDATE word SET pinyin = ? WHERE id = ?', (fixed, wid)))
    for wid, cs in word_chars.items():
        for cid, char, pinyin in cs:
            fixed = CHAR_PINYIN_FIXES.get((hanzi_of[wid], char, pinyin))
            if fixed:
                fixes.append((f'字 {cid}（{hanzi_of[wid]}的{char}）拼音 {pinyin} -> {fixed}',
                              'UPDATE character SET pinyin = ? WHERE id = ?', (fixed, cid)))
    for eid, wid, sentence, pinyin in conn.execute('SELECT id, word_id, sentence, pinyin FROM example').fetchall():
        if wid in batch_words:
            continue
        line = fixed_example_pinyin(sentence, pinyin)
        if line != (pinyin or ''):
            fixes.append((f'例句 {eid}「{sentence[:12]}…」拼音勘误',
                          'UPDATE example SET pinyin = ? WHERE id = ?', (line, eid)))

    return fixes


def clean_database(db_path: str) -> int:
    """执行全部修复，返回改动的行数。整体在一个事务里，失败回滚。"""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        fixes = plan_fixes(conn)
        for _, sql, params in fixes:
            conn.execute(sql, params)
        conn.commit()
        return len(fixes)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> int:
    db = os.environ.get('WORDS_DB_PATH', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'words_extended.db'))
    if '--apply' in sys.argv:
        print(f'💾 {db}: 修复 {clean_database(db)} 行')
        return 0
    conn = sqlite3.connect(db)
    try:
        fixes = plan_fixes(conn)
    finally:
        conn.close()
    print(f'📋 {db}: 待修复 {len(fixes)} 行（--apply 执行）')
    for desc, _, _ in fixes:
        print('   -', desc)
    return 0


if __name__ == '__main__':
    sys.exit(main())
