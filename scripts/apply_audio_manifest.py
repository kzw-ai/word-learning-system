#!/usr/bin/env python3
"""把论文词库（words_extended.db 里已有材料的词）的发音音频地址补进库里。

清单由学习资料制作第 8 步生成（step8_audio.py --thesis）：data/learning_materials/audio/论文词库.json，
和音频文件一样不提交，部署时复制到服务器。按汉字找词，字按顺序、搭配和例句按原文对上再写。
只填空着的地址，或是早期示例留下的占位（/audio/ 开头，文件并不存在）；别的地址不动。
批次导入的词由 import_hsk4_batches.py 写发音，不在这份清单里。应用启动时自动执行，重复执行是幂等的。
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

import import_hsk4_batches

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# AUDIO_MANIFEST 可覆盖（测试指向不存在的文件）
MANIFEST = Path(os.environ.get('AUDIO_MANIFEST') or PROJECT_ROOT / 'data' / 'learning_materials' / 'audio' / '论文词库.json')
DB_PATH = PROJECT_ROOT / 'words_extended.db'


def replaceable(value):
    return not value or value.startswith('/audio/')


def fill(conn, table, row_id, current, audio):
    if replaceable(current) and audio and current != audio:
        conn.execute(f'UPDATE {table} SET audio = ? WHERE id = ?', (audio, row_id))
        return 1
    return 0


def apply(db_path=DB_PATH, manifest=None):
    """返回补入的地址数。一个事务完成，失败整体回滚。"""
    manifest = Path(manifest or MANIFEST)
    if not manifest.exists():
        return 0
    words = json.loads(manifest.read_text(encoding='utf-8'))['words']
    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    try:
        conn.execute('BEGIN IMMEDIATE')
        try:
            import_hsk4_batches.ensure_schema(conn)
            known = import_hsk4_batches.hanzi_map(conn)
            n = 0
            for w in words:
                word_id = known.get(w['hanzi'])
                if word_id is None:
                    continue
                n += fill(conn, 'word', word_id, conn.execute('SELECT audio FROM word WHERE id = ?', (word_id,)).fetchone()[0],
                          w['audio'])
                rows = conn.execute('SELECT id, character, audio FROM character WHERE word_id = ? ORDER BY id', (word_id,)).fetchall()
                for (row_id, ch, current), c in zip(rows, w['characters']):
                    if ch == c['character']:
                        n += fill(conn, 'character', row_id, current, c['audio'])
                for table, key, items in (('collocation', 'collocation', w['collocations']),
                                          ('example', 'sentence', w['examples'])):
                    by_text = {item[key]: item['audio'] for item in items}
                    for row_id, text, current in conn.execute(
                            f'SELECT id, {key}, audio FROM {table} WHERE word_id = ? ORDER BY id', (word_id,)).fetchall():
                        if text in by_text:
                            n += fill(conn, table, row_id, current, by_text[text])
            conn.execute('COMMIT')
        except Exception:
            conn.execute('ROLLBACK')
            raise
    finally:
        conn.close()
    return n


if __name__ == '__main__':
    args = sys.argv[1:]
    db = Path(args[args.index('--db') + 1]) if '--db' in args else DB_PATH
    print(f'✅ 论文词库发音音频：补入 {apply(db)} 处')
