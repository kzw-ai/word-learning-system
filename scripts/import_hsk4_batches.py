#!/usr/bin/env python3
"""导入按论文 5.3 节流程批量制作的新 HSK 四级词学习资料（学习资料制作/ 第 7 步的产出）。

素材文件放在 data/learning_materials/hsk4/<批>.json，格式见 学习资料制作/制作流程.md 第 7 步。
这个目录不提交到仓库（素材里有教材例句，仓库是公开的），部署时单独复制到服务器的同一位置。

只导入 status 为「作者已审核」的批次；应用启动时自动同步（同 parse_answer_decks），重复运行是幂等的。
批次插入的词和易混淆词对记在 hsk4_batch_owner 表里（归属），之后按归属同步：
- 词库里还没有的词：插入词、字、搭配、例句和练习题（来源记为「HSK4 <批> <词>」），记下归属。
- 归属这个批次的词：与素材同步——拼音、释义更新；字、搭配、例句有变化时整组替换；
  练习题按 (来源, 序号, 题型, 题干) 更新、新增、删除已撤下的。重新审核后的修改因此能生效。
- 词库里已有、但不归属这个批次的词：整个跳过，不往旧词里混入新内容。
- 易混淆词对：还没有就插入并记下归属；归属这个批次的按素材同步全部内容；
  不归属任何批次的旧词对只在还没有辨析题时补上题，讲解保持原样。
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BATCH_DIR = PROJECT_ROOT / 'data' / 'learning_materials' / 'hsk4'
DB_PATH = PROJECT_ROOT / 'words_extended.db'
APPROVED = '作者已审核'


def load_batches(include_unreviewed=False):
    batches = []
    for path in sorted(BATCH_DIR.glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('status') == APPROVED or include_unreviewed:
            batches.append(data)
    return batches


def ensure_schema(conn):
    """归属表；confusable_pairs 加 questions 列（辨析题，论文 3.2.4）。应用启动时已补过列，这里给单独运行时兜底。"""
    conn.execute('''CREATE TABLE IF NOT EXISTS hsk4_batch_owner (
        kind TEXT NOT NULL, ref_id INTEGER NOT NULL, batch TEXT NOT NULL, PRIMARY KEY (kind, ref_id))''')
    columns = {row[1] for row in conn.execute('PRAGMA table_info(confusable_pairs)')}
    if columns and 'questions' not in columns:
        conn.execute('ALTER TABLE confusable_pairs ADD COLUMN questions TEXT')


def owners(conn, kind):
    return dict(conn.execute('SELECT ref_id, batch FROM hsk4_batch_owner WHERE kind = ?', (kind,)))


def claim(conn, kind, ref_id, batch):
    conn.execute('INSERT INTO hsk4_batch_owner (kind, ref_id, batch) VALUES (?, ?, ?)', (kind, ref_id, batch))


def hanzi_map(conn):
    """汉字 -> word_id。按 character.id 的顺序拼字（与页面显示一致）；GROUP_CONCAT 不保证顺序。"""
    chars = {}
    for word_id, ch in conn.execute('SELECT word_id, character FROM character ORDER BY word_id, id'):
        chars.setdefault(word_id, []).append(ch)
    return {''.join(cs): word_id for word_id, cs in chars.items()}


CONTENT = {
    'character': ('characters', ('character', 'pinyin', 'definition')),
    'collocation': ('collocations', ('collocation', 'translation')),
    'example': ('examples', ('sentence', 'pinyin', 'translation')),
}


def write_content(conn, word_id, w):
    """词的拼音、释义，以及字、搭配、例句写入。字、搭配、例句和素材一致时不动，
    有变化时整组替换（这几张表没有被别的表引用）。"""
    conn.execute('UPDATE word SET pinyin = ?, definition = ? WHERE id = ?', (w['pinyin'], w['definition'], word_id))
    same = all(
        conn.execute(f'SELECT {", ".join(cols)} FROM {table} WHERE word_id = ? ORDER BY id', (word_id,)).fetchall()
        == [tuple(item[c] for c in cols) for item in w[key]]
        for table, (key, cols) in CONTENT.items())
    if same:
        return
    for table in ('character', 'collocation', 'example'):
        conn.execute(f'DELETE FROM {table} WHERE word_id = ?', (word_id,))
    conn.executemany('INSERT INTO character (character, pinyin, definition, audio, word_id) VALUES (?, ?, ?, ?, ?)',
                     [(c['character'], c['pinyin'], c['definition'], '', word_id) for c in w['characters']])
    conn.executemany('INSERT INTO collocation (collocation, translation, audio, word_id) VALUES (?, ?, ?, ?)',
                     [(c['collocation'], c['translation'], '', word_id) for c in w['collocations']])
    conn.executemany('INSERT INTO example (sentence, pinyin, translation, audio, word_id) VALUES (?, ?, ?, ?, ?)',
                     [(e['sentence'], e['pinyin'], e['translation'], '', word_id) for e in w['examples']])


def sync_exercises(conn, word_id, deck, exercises, now):
    """这个词的练习题与素材对齐：同键更新答案和选项，新题插入，撤下的删除。返回 (新增, 更新, 删除)。"""
    current = {}
    for index, q in enumerate(exercises, 1):
        options = json.dumps(q['options'], ensure_ascii=False) if q['options'] else None
        current[(index, q['question_type'], q['stem'])] = (options, q['correct_answer'])
    existing = {(slide, qtype, stem): (item_id, options, answer) for item_id, slide, qtype, stem, options, answer in conn.execute(
        'SELECT id, source_slide, question_type, stem, options_json, correct_answer FROM exercise_item WHERE source_deck = ?',
        (deck,))}
    stale = [v[0] for k, v in existing.items() if k not in current]
    conn.executemany('DELETE FROM exercise_item WHERE id = ?', [(i,) for i in stale])
    inserted = updated = 0
    for (index, qtype, stem), (options, answer) in current.items():
        old = existing.get((index, qtype, stem))
        if old is None:
            conn.execute('''INSERT INTO exercise_item
                (word_id, question_type, stem, options_json, correct_answer, source_deck, source_slide, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (word_id, qtype, stem, options, answer, deck, index, now))
            inserted += 1
        elif old[1:] != (options, answer):
            conn.execute('UPDATE exercise_item SET word_id = ?, options_json = ?, correct_answer = ? WHERE id = ?',
                         (word_id, options, answer, old[0]))
            updated += 1
    return inserted, updated, len(stale)


def sync_pair(conn, p, id1, id2, batch, pair_owners):
    """返回 'inserted' / 'updated' / None"""
    questions = json.dumps(p.get('questions', []), ensure_ascii=False)
    fields = (p['reason'], p['difference'], p['examples'], p['tips'], p['difficulty_level'], questions)
    row = conn.execute('''SELECT id, reason, difference, examples, tips, difficulty_level, questions FROM confusable_pairs
        WHERE (word1_id = ? AND word2_id = ?) OR (word1_id = ? AND word2_id = ?)''', (id1, id2, id2, id1)).fetchone()
    if row is None:
        pair_id = conn.execute('''INSERT INTO confusable_pairs
            (word1_id, word2_id, reason, difference, examples, tips, difficulty_level, questions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (id1, id2, *fields)).lastrowid
        claim(conn, 'pair', pair_id, batch)
        pair_owners[pair_id] = batch
        return 'inserted'
    pair_id, old_questions = row[0], row[6]
    owner = pair_owners.get(pair_id)
    if owner == batch:
        if tuple(row[1:]) != fields:
            conn.execute('''UPDATE confusable_pairs SET reason = ?, difference = ?, examples = ?, tips = ?,
                difficulty_level = ?, questions = ? WHERE id = ?''', (*fields, pair_id))
            return 'updated'
        return None
    if owner is None and (not old_questions or old_questions == '[]') and p.get('questions'):
        # 不归属任何批次的旧词对：只补辨析题，讲解保持原样；补过以后不再改动
        conn.execute('UPDATE confusable_pairs SET questions = ? WHERE id = ?', (questions, pair_id))
        return 'updated'
    return None


def import_batch(conn, batch, now):
    """返回 [新增词, 跳过的已有词, 同步的已有词, 新增题, 更新题, 删除题, 新增词对, 更新词对]"""
    counts = [0] * 8
    name = batch['batch']
    known = hanzi_map(conn)
    word_owners = owners(conn, 'word')
    pair_owners = owners(conn, 'pair')
    for w in batch['words']:
        hanzi = w['hanzi']
        word_id = known.get(hanzi)
        if word_id is not None and word_owners.get(word_id) == name:
            write_content(conn, word_id, w)
            counts[2] += 1
        elif word_id is not None:
            counts[1] += 1
            continue
        else:
            word_id = conn.execute('INSERT INTO word (pinyin, definition) VALUES (?, ?)',
                                   (w['pinyin'], w['definition'])).lastrowid
            write_content(conn, word_id, w)
            claim(conn, 'word', word_id, name)
            word_owners[word_id] = name
            known[hanzi] = word_id
            counts[0] += 1
        for i, n in enumerate(sync_exercises(conn, word_id, f'HSK4 {name} {hanzi}', w['exercises'], now)):
            counts[3 + i] += n
    for p in batch.get('confusable_pairs', []):
        id1, id2 = known.get(p['word1']), known.get(p['word2'])
        if id1 and id2:
            result = sync_pair(conn, p, id1, id2, name, pair_owners)
            counts[6] += result == 'inserted'
            counts[7] += result == 'updated'
    return counts


def import_into(db_path=DB_PATH, include_unreviewed=False):
    """返回 (新增词, 跳过的已有词, 新增练习题, 新增或更新的易混淆词对)。一个事务完成，失败整体回滚。
    更细的计数（同步的词、更新/删除的题）见 import_details。"""
    d = import_details(db_path, include_unreviewed)
    return d['words_added'], d['words_skipped'], d['items_added'], d['pairs_added'] + d['pairs_updated']


def import_details(db_path=DB_PATH, include_unreviewed=False):
    names = ('words_added', 'words_skipped', 'words_synced', 'items_added', 'items_updated', 'items_removed',
             'pairs_added', 'pairs_updated')
    totals = dict.fromkeys(names, 0)
    batches = load_batches(include_unreviewed)
    if not batches:
        return totals
    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    try:
        conn.execute('BEGIN IMMEDIATE')
        try:
            ensure_schema(conn)
            now = datetime.now()
            for batch in batches:
                for name, n in zip(names, import_batch(conn, batch, now)):
                    totals[name] += n
            conn.execute('COMMIT')
        except Exception:
            conn.execute('ROLLBACK')
            raise
    finally:
        conn.close()
    return totals


if __name__ == '__main__':
    args = sys.argv[1:]
    db = Path(args[args.index('--db') + 1]) if '--db' in args else DB_PATH
    d = import_details(db, '--include-unreviewed' in args)
    print('✅ HSK4 批次导入：' + '，'.join(f'{k} {v}' for k, v in d.items()))
