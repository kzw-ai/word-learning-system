#!/usr/bin/env python3
"""把已有的 user_progress.mastery_level 重算成「最近 10 道题的正确率」。

2026-11-11 起掌握度不再取全部累计正确率，改看最近几题（app_phase.recent_accuracy）。
新的作答会按新规则更新，这个脚本只是把改版前已有的行一次性对齐，免得今日复习的排序和百分比
要等学习者再答一次才变。只改 mastery_level 一列；下次复习日期已经排好，不重排。

这个词没有作答记录的行（只学过没练过）不动。

用法：
    python3 scripts/recompute_mastery.py            # 只列出会改什么
    python3 scripts/recompute_mastery.py --apply    # 写入
    （--db <路径> 指定数据库）

在生产库上运行前先备份数据库（sqlite3 ... ".backup ..."）。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / 'words_extended.db'

# 和 app_phase.MASTERY_RECENT_ANSWERS 一致
RECENT_ANSWERS = 10

RECENT_SQL = """
    SELECT er.is_correct
    FROM exercise_record er
    JOIN learning_session ls ON ls.session_id = er.session_id
    WHERE ls.user_id = ? AND ls.word_id = ?
      AND er.id = (SELECT MIN(e2.id) FROM exercise_record e2
                   WHERE e2.session_id = er.session_id AND e2.question_id = er.question_id)
    ORDER BY er.id DESC
    LIMIT ?
"""


def main(argv):
    apply = '--apply' in argv
    db_path = Path(argv[argv.index('--db') + 1]) if '--db' in argv else DB_PATH
    conn = sqlite3.connect(db_path)
    changes = []
    for row_id, user_id, word_id, old in conn.execute(
            'SELECT id, user_id, word_id, mastery_level FROM user_progress ORDER BY id').fetchall():
        answers = conn.execute(RECENT_SQL, (user_id, word_id, RECENT_ANSWERS)).fetchall()
        if not answers:
            continue
        new = sum(1 for (ok,) in answers if ok) / len(answers)
        if old is None or abs(old - new) > 1e-9:
            changes.append((row_id, user_id, word_id, old, new, len(answers)))

    for row_id, user_id, word_id, old, new, n in changes:
        old_text = '空' if old is None else f'{old:.0%}'
        print(f'user_progress #{row_id}  {user_id}  词 {word_id}：{old_text} → {new:.0%}（最近 {n} 题）')
    print(f'共 {len(changes)} 行要改')

    if apply and changes:
        with conn:
            conn.executemany('UPDATE user_progress SET mastery_level = ? WHERE id = ?',
                             [(new, row_id) for row_id, _, _, _, new, _ in changes])
        print('已写入')
    elif changes:
        print('加 --apply 才写入')
    conn.close()


if __name__ == '__main__':
    main(sys.argv[1:])
