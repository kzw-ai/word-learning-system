#!/usr/bin/env python3
"""导入按论文 5.3 节流程批量制作的新 HSK 四级词学习资料（学习资料制作/ 第 7 步的产出）。

素材文件放在 data/learning_materials/hsk4/<批>.json，格式见 学习资料制作/制作流程.md 第 7 步。
只导入 status 为「作者已审核」的批次；应用启动时自动同步（同 parse_answer_decks），重复运行是幂等的：
- 词、字、搭配、例句：词库里还没有的词才插入；已有的词整个跳过，不往旧词里混入新内容。
- 练习题：写入 exercise_item，来源记为「HSK4 <批>」，按 (来源, 序号, 题型, 题干) 去重。只给本次新插入、
  或以前由这个批次插入的词出题。
- 易混淆词对：两个词都在词库里、且这对还没有时插入；辨析题存在 confusable_pairs.questions（JSON）。

用法:
    python3 scripts/import_hsk4_batches.py                     # 导入到 words_extended.db
    python3 scripts/import_hsk4_batches.py --db 路径 --include-unreviewed   # 测试：连待审核的也导入
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
    """confusable_pairs 加 questions 列（辨析题，论文 3.2.4）。exercise_item 表由 parse_answer_decks 建。"""
    columns = {row[1] for row in conn.execute('PRAGMA table_info(confusable_pairs)')}
    if columns and 'questions' not in columns:
        conn.execute('ALTER TABLE confusable_pairs ADD COLUMN questions TEXT')


def hanzi_map(conn):
    """通过 character 表反查已有词的汉字 -> word_id（同 import_learning_materials）"""
    rows = conn.execute("SELECT word_id, GROUP_CONCAT(character, '') FROM character GROUP BY word_id")
    return {hanzi: word_id for word_id, hanzi in rows if hanzi}


def insert_word(conn, w):
    word_id = conn.execute('INSERT INTO word (pinyin, definition) VALUES (?, ?)',
                           (w['pinyin'], w['definition'])).lastrowid
    conn.executemany('INSERT INTO character (character, pinyin, definition, audio, word_id) VALUES (?, ?, ?, ?, ?)',
                     [(c['character'], c['pinyin'], c['definition'], '', word_id) for c in w['characters']])
    conn.executemany('INSERT INTO collocation (collocation, translation, audio, word_id) VALUES (?, ?, ?, ?)',
                     [(c['collocation'], c['translation'], '', word_id) for c in w['collocations']])
    conn.executemany('INSERT INTO example (sentence, pinyin, translation, audio, word_id) VALUES (?, ?, ?, ?, ?)',
                     [(e['sentence'], e['pinyin'], e['translation'], '', word_id) for e in w['examples']])
    return word_id


def import_batch(conn, batch, now):
    deck = f"HSK4 {batch['batch']}"
    known = hanzi_map(conn)
    # 以前由这个批次导入的词（它们的题来源是 deck），重跑时继续同步它们的题
    owned = {row[0] for row in conn.execute('SELECT DISTINCT word_id FROM exercise_item WHERE source_deck = ?', (deck,))}
    added = skipped = items = 0
    for w in batch['words']:
        if w['hanzi'] in known:
            word_id = known[w['hanzi']]
            if word_id not in owned:
                skipped += 1
                continue
        else:
            word_id = known[w['hanzi']] = insert_word(conn, w)
            added += 1
        for index, q in enumerate(w['exercises'], 1):
            options = json.dumps(q['options'], ensure_ascii=False) if q['options'] else None
            cur = conn.execute('''INSERT OR IGNORE INTO exercise_item
                (word_id, question_type, stem, options_json, correct_answer, source_deck, source_slide, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (word_id, q['question_type'], q['stem'], options, q['correct_answer'], deck, index, now))
            items += cur.rowcount
    pairs = 0
    for p in batch.get('confusable_pairs', []):
        id1, id2 = known.get(p['word1']), known.get(p['word2'])
        if not id1 or not id2:
            continue
        questions = json.dumps(p.get('questions', []), ensure_ascii=False)
        row = conn.execute('''SELECT id FROM confusable_pairs
            WHERE (word1_id = ? AND word2_id = ?) OR (word1_id = ? AND word2_id = ?)''', (id1, id2, id2, id1)).fetchone()
        if row:
            continue
        conn.execute('''INSERT INTO confusable_pairs
            (word1_id, word2_id, reason, difference, examples, tips, difficulty_level, questions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (id1, id2, p['reason'], p['difference'], p['examples'], p['tips'], p['difficulty_level'], questions))
        pairs += 1
    return added, skipped, items, pairs


def import_into(db_path=DB_PATH, include_unreviewed=False):
    """返回 (新增词, 跳过的已有词, 新增练习题, 新增易混淆词对)。在一个事务里完成，失败整体回滚。"""
    batches = load_batches(include_unreviewed)
    totals = [0, 0, 0, 0]
    if not batches:
        return tuple(totals)
    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    try:
        conn.execute('BEGIN IMMEDIATE')
        try:
            ensure_schema(conn)
            now = datetime.now()
            for batch in batches:
                for i, n in enumerate(import_batch(conn, batch, now)):
                    totals[i] += n
            conn.execute('COMMIT')
        except Exception:
            conn.execute('ROLLBACK')
            raise
    finally:
        conn.close()
    return tuple(totals)


if __name__ == '__main__':
    args = sys.argv[1:]
    db = Path(args[args.index('--db') + 1]) if '--db' in args else DB_PATH
    added, skipped, items, pairs = import_into(db, '--include-unreviewed' in args)
    print(f'✅ HSK4 批次导入：新增词 {added}，跳过已有词 {skipped}，新增练习题 {items}，新增易混淆词对 {pairs}')
