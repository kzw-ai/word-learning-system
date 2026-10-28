#!/usr/bin/env python3
"""修复已入库学习素材里的已知缺陷。幂等：重复执行不再改动任何行。

import_learning_materials.py 只插入不更新，修好它的解析器并不能改正已经入库的
数据，所以由这个脚本按同样的规则修一遍。后端每次启动时也会调用 clean_database。

修复的六类问题：
1. 种子脚本 setup_confusable_data.py 早期写入的词拼音没有声调（yinwei、suoyi……），
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
                    fixes.append((f'词 {wid}（{hanzi}）补例句 {ex["sentence"]!r}',
                                  'INSERT INTO example (sentence, pinyin, translation, audio, word_id) VALUES (?, ?, ?, ?, ?)',
                                  (ex['sentence'], ex['pinyin'], ex['translation'], '', wid)))

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
