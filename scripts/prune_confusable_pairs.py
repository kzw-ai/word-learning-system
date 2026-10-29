#!/usr/bin/env python3
"""删除不是由学习资料流水线写入的易混淆词对。

作者 2026-10-29 定：辨析词对只收语料库确认的——四级目标词偏误 ≥ 10 次、写成这个词的占 20% 以上，
且这个词是一至三级词。以前手写的词对（论文课件的近义词、开发时补的）用语料库核对后只有「发生 / 发现」
符合，它也要按流水线重新生成讲解和辨析题；所以凡是不归属任何 HSK4 批次（hsk4_batch_owner）的词对都删掉。

删除前把词对和它们的辨析作答记录存成 JSON（数据库同目录的 backups/ 下）。词本身不动。

用法：
    python3 scripts/prune_confusable_pairs.py            # 只列出会删什么
    python3 scripts/prune_confusable_pairs.py --apply    # 留档后删除
    （--db <路径> 指定数据库）
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / 'words_extended.db'


def word_label(conn, word_id):
    """汉字（按 character.id 拼）；没有字的词（早期种子）用拼音"""
    chars = ''.join(ch for (ch,) in conn.execute('SELECT character FROM character WHERE word_id = ? ORDER BY id', (word_id,)))
    if chars:
        return chars
    row = conn.execute('SELECT pinyin FROM word WHERE id = ?', (word_id,)).fetchone()
    return row[0] if row else f'#{word_id}'


def legacy_pairs(conn):
    """不归属任何批次的词对：[dict]，含作答记录"""
    has_owner = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'hsk4_batch_owner'").fetchone()
    owned = {r for (r,) in conn.execute("SELECT ref_id FROM hsk4_batch_owner WHERE kind = 'pair'")} if has_owner else set()
    conn.row_factory = sqlite3.Row
    try:
        pairs = [dict(r) for r in conn.execute('SELECT * FROM confusable_pairs ORDER BY id') if r['id'] not in owned]
        for p in pairs:
            p['records'] = [dict(r) for r in conn.execute(
                'SELECT * FROM confusable_exercise_records WHERE pair_id = ? ORDER BY id', (p['id'],))]
    finally:
        conn.row_factory = None
    for p in pairs:
        p['words'] = f"{word_label(conn, p['word1_id'])} / {word_label(conn, p['word2_id'])}"
    return pairs


def prune(db_path=DB_PATH, apply=False):
    """返回 (要删的词对, 留档文件或 None)。一个事务完成，失败整体回滚。"""
    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    try:
        conn.execute('BEGIN IMMEDIATE')
        try:
            pairs = legacy_pairs(conn)
            if not apply or not pairs:
                conn.execute('ROLLBACK')
                return pairs, None
            backup_dir = Path(db_path).resolve().parent / 'backups'
            backup_dir.mkdir(exist_ok=True)
            archive = backup_dir / f"confusable_pairs_removed.{datetime.now():%Y%m%d-%H%M%S}.json"
            archive.write_text(json.dumps(pairs, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
            ids = [(p['id'],) for p in pairs]
            conn.executemany('DELETE FROM confusable_exercise_records WHERE pair_id = ?', ids)
            if conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'hsk4_batch_owner'").fetchone():
                conn.executemany("DELETE FROM hsk4_batch_owner WHERE kind = 'pair_questions' AND ref_id = ?", ids)
            conn.executemany('DELETE FROM confusable_pairs WHERE id = ?', ids)
            conn.execute('COMMIT')
            return pairs, archive
        except Exception:
            conn.execute('ROLLBACK')
            raise
    finally:
        conn.close()


if __name__ == '__main__':
    args = sys.argv[1:]
    db = Path(args[args.index('--db') + 1]) if '--db' in args else DB_PATH
    apply = '--apply' in args
    pairs, archive = prune(db, apply)
    for p in pairs:
        print(f"  #{p['id']} {p['words']}：辨析作答 {len(p['records'])} 条")
    if not pairs:
        print('没有要删的词对')
    elif archive:
        print(f'✅ 已删除 {len(pairs)} 对，留档 {archive}')
    else:
        print(f'共 {len(pairs)} 对会被删除（加 --apply 才删）')
