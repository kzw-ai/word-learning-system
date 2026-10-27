#!/usr/bin/env python3
"""把论文 6 套答案课件里的人工命题解析入库。

这些题是作者按教学设计手工出的——干扰项经过挑选（形近、义近、同音），
填词题挖的是词中一个字。系统此前完全没用它们，练习题改由程序随机抽词拼凑，
干扰项与被考词毫无关系，测量效度远低于原始命题。

数据源是 data/learning_materials/the answer*.json（课件已解析成 JSON，
不需要重新处理 pptx）。每张 practice 幻灯片是一个词的完整题组：
    1. Find responding word.     释义题：给英文释义，四选一
    2. Find right collocation.   搭配题：给带空的搭配，四选一（可能不止一道）
    3. Fill in right word.       填词题：句中挖掉词里的一个字

用法：
    python3 scripts/parse_answer_decks.py --report     # 只解析并报告，不写库
    python3 scripts/parse_answer_decks.py --import     # 解析并写入 exercise_item
"""
import argparse
import glob
import io
import json
import os
import re
import sqlite3
import sys
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'data', 'learning_materials')

# 题型分节标记。课件里这些词被 PPT 拆成了多行，故用 \s+ 容忍换行
RE_SECTION_DEFINITION = re.compile(r'Find\s+responding\s+word\.', re.I)
RE_SECTION_COLLOCATION = re.compile(r'(?:\d\.\s*)?Find\s+right\s+collocation\.', re.I)
# 有两张幻灯片写成 "Fill in right word, its Pinyin and its tone."
RE_SECTION_FILL = re.compile(r'(?:\d\.\s*)?Fill\s+in\s+right\s+word(?:,[^.]{0,60})?\s*\.', re.I)

# 选项标记：A. B. C. D.（PPT 里常被拆行，故容忍空白）
RE_OPT_MARKER = re.compile(r'([A-D])\s*\.\s*')

# 答案标记：多数是字母（ A ），但有一张幻灯片直接写答案汉字（当）
RE_ANSWER_LETTER = re.compile(r'[（(]\s*([A-D])\s*[)）]')
RE_ANSWER_HANZI = re.compile(r'[（(]\s*([一-鿿]{1,6})\s*[)）]')

# 填词题答案：句子里被括起来的汉字，如 降（低）成本
RE_FILL_ANSWER = re.compile(r'[（(]\s*([一-鿿]+)\s*[)）]')

# 句末标点之后断句，标点保留在前一句
RE_SENTENCE_END = re.compile(r'(?<=[。？！?!])')

BLANK = ' ( ) '


def normalize(text):
    """把 PPT 拆碎的换行合并成单空格，便于正则跨行匹配。"""
    return ' '.join((text or '').split())


def _last_option_body(gap):
    """从「最后一个选项 + 下一题题干」的混合文本里，切出属于选项的部分。

    课件里选项与下一题题干本来就分行（'D.\n发生\n事情（\nB\n）'），
    换行就是天然分隔符——早早把换行合并成空格会让 D 选项把下一题题干吞进去，
    连正确答案都会变脏（曾出现「答案=发生 事情」）。

    只取第一行。全语料 453 个边界明确的选项里只有 1 个跨行
    （「因为 …… 所以 ……」），而下一题题干带前导词的情况更常见
    （'D.\n然后\n跟\nX\n（B）' 里「跟 X」属于题干），故按单行切最稳。
    """
    lines = [ln for ln in gap.split('\n') if ln.strip()]
    if not lines:
        return '', 0
    first = lines[0]
    return first, gap.index(first) + len(first)


def parse_question_runs(chunk):
    """把一段文本切成若干 (题干, 选项dict)。

    版式是 [题干][A. B. C. D.] 反复出现。注意 chunk 必须保留换行。
    """
    markers = list(RE_OPT_MARKER.finditer(chunk))

    # 先把标记归拢成 A→B→C→D 的连续游程
    runs, current = [], []
    for mk in markers:
        letter = mk.group(1)
        if letter == 'A':
            if current:
                runs.append(current)
            current = [mk]
        elif current and ord(letter) == ord(current[-1].group(1)) + 1:
            current.append(mk)
        else:
            if current:
                runs.append(current)
            current = []
    if current:
        runs.append(current)

    results = []
    stem_start = 0
    for i, run in enumerate(runs):
        stem = chunk[stem_start:run[0].start()]
        options = {}
        for j, mk in enumerate(run):
            body_start = mk.end()
            if j + 1 < len(run):
                body_end = run[j + 1].start()
            elif i + 1 < len(runs):
                body_end = runs[i + 1][0].start()
            else:
                body_end = len(chunk)

            if j == len(run) - 1 and i + 1 < len(runs):
                gap = chunk[body_start:body_end]
                body, consumed = _last_option_body(gap)
                stem_start = body_start + consumed
            else:
                body = chunk[body_start:body_end]
                stem_start = body_end
            options[mk.group(1)] = normalize(body)
        results.append((normalize(stem), options))
    return results


def find_answer(chunk, options):
    """定位答案标记，返回 (答案文本, 匹配对象)；找不到返回 (None, None)。"""
    m = RE_ANSWER_LETTER.search(chunk)
    if m:
        return options.get(m.group(1)), m
    m = RE_ANSWER_HANZI.search(chunk)
    if m:
        # 直接写汉字的情况：核对它确实是选项之一，避免把题干括号误当答案
        text = m.group(1)
        if not options or text in options.values():
            return text, m
    return None, None


def parse_slide(text, deck, slide_index):
    """解析一张 practice 幻灯片，返回题目列表；解析不出的部分记入 problems。"""
    items, problems = [], []
    flat = text  # 保留换行：选项与下一题题干靠换行分隔

    def section(start_re, *later_res):
        """取 start_re 之后、下一个分节标记之前的那段文本。"""
        m = start_re.search(flat)
        if not m:
            return None
        start = m.end()
        end = len(flat)
        for r in later_res:
            m2 = r.search(flat, start)
            if m2:
                end = min(end, m2.start())
        return flat[start:end]

    # ---- 1. 释义题（一节一道）----
    part = section(RE_SECTION_DEFINITION, RE_SECTION_COLLOCATION, RE_SECTION_FILL)
    target_word = None
    if part:
        runs = parse_question_runs(part)
        if len(runs) != 1:
            problems.append('%s slide%s: 释义题解析出 %d 道，预期 1 道' % (deck, slide_index, len(runs)))
        for stem_raw, options in runs[:1]:
            answer, marker = find_answer(stem_raw, options)
            if not (marker and len(options) == 4 and answer):
                problems.append('%s slide%s: 释义题解析失败(选项%d个)' % (deck, slide_index, len(options)))
                continue
            # 题干 = 去掉答案标记后剩下的英文释义
            stem = normalize(stem_raw[:marker.start()] + ' ' + stem_raw[marker.end():])
            if not stem:
                problems.append('%s slide%s: 释义题题干为空' % (deck, slide_index))
                continue
            target_word = answer
            items.append({
                'question_type': 'definition',
                'stem': stem,
                'options': [options[k] for k in 'ABCD'],
                'correct_answer': answer,
            })

    # ---- 2. 搭配题（可能多道）----
    part = section(RE_SECTION_COLLOCATION, RE_SECTION_FILL)
    if part:
        for stem_raw, options in parse_question_runs(part):
            answer, marker = find_answer(stem_raw, options)
            if not (marker and len(options) == 4 and answer):
                if stem_raw.strip():
                    problems.append('%s slide%s: 搭配题解析失败(选项%d个)' % (deck, slide_index, len(options)))
                continue
            # 题干里的（X）就是要填的空
            stem = normalize(stem_raw[:marker.start()] + BLANK + stem_raw[marker.end():])
            items.append({
                'question_type': 'collocation',
                'stem': stem,
                'options': [options[k] for k in 'ABCD'],
                'correct_answer': answer,
            })

    # ---- 3. 填词题 ----
    part = section(RE_SECTION_FILL)
    if part:
        # 去掉偶尔混进来的拼音行（如 "shen1"）
        part = normalize(re.sub(r'\b[a-zA-Z]+\d?\b', ' ', part))
        if len(RE_FILL_ANSWER.findall(part)) > 1:
            # 一页里有多句各挖一个空（如「更（好）」出现两次）：按句拆成独立的题，
            # 否则只挖第一个空，其余括号会把答案直接露在题干里
            sentences = [x.strip() for x in RE_SENTENCE_END.split(part) if x.strip()]
        else:
            sentences = [part] if part else []
        found = False
        for sentence in sentences:
            answers = RE_FILL_ANSWER.findall(sentence)
            if not answers:
                continue
            found = True
            if len(answers) > 1:
                problems.append(f'{deck} slide{slide_index}: 填词题一句里有多个空，跳过')
                continue
            m = RE_FILL_ANSWER.search(sentence)
            answer = m.group(1)
            # 填回答案后句子里必须出现目标词，否则考的不是这个词
            # （课件里「变化」一页写成了「变（好）」）
            filled = sentence[:m.start()] + answer + sentence[m.end():]
            if target_word and target_word not in filled:
                problems.append(
                    f'{deck} slide{slide_index}: 填词题补全后是「{filled}」，'
                    f'不含目标词「{target_word}」，跳过'
                )
                continue
            items.append({
                'question_type': 'fill_word',
                'stem': normalize(sentence[:m.start()] + BLANK + sentence[m.end():]),
                'options': [],
                'correct_answer': answer,
            })
        if part and not found:
            problems.append(f'{deck} slide{slide_index}: 填词题找不到括号答案')

    return items, problems, target_word


def parse_all():
    all_slides, problems = [], []
    for path in sorted(glob.glob(os.path.join(DATA_DIR, 'the answer*.json'))):
        deck = os.path.basename(path).replace('.json', '')
        data = json.load(io.open(path, encoding='utf-8'))
        for slide in data.get('slides', []):
            text = slide.get('text', '')
            if 'practice' not in normalize(text).lower():
                continue
            idx = slide.get('index')
            items, probs, target = parse_slide(text, deck, idx)
            problems.extend(probs)
            if not target:
                problems.append(f'{deck} slide{idx}: 无法确定目标词，整组跳过')
                continue
            all_slides.append({'deck': deck, 'slide': idx, 'word': target, 'items': items})
    return all_slides, problems


def resolve_word_ids(conn, slides):
    """把目标词的汉字映射到 word.id（词形由 character 表拼接得出）。"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT word_id, GROUP_CONCAT(character, '')
        FROM (SELECT word_id, character FROM character ORDER BY word_id, id)
        GROUP BY word_id
    """)
    hanzi_to_id = {h: wid for wid, h in cursor.fetchall() if h}
    resolved, unmatched = [], []
    for s in slides:
        wid = hanzi_to_id.get(s['word'])
        if wid is None:
            unmatched.append(s['word'])
        else:
            s['word_id'] = wid
            resolved.append(s)
    return resolved, unmatched


def create_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exercise_item (
            id INTEGER PRIMARY KEY,
            word_id INTEGER NOT NULL,
            question_type VARCHAR(20) NOT NULL,
            stem TEXT NOT NULL,
            options_json TEXT,
            correct_answer VARCHAR(100) NOT NULL,
            source_deck VARCHAR(100) NOT NULL,
            source_slide INTEGER,
            created_at DATETIME,
            FOREIGN KEY (word_id) REFERENCES word (id)
        )
    """)
    # 同一课件同一张幻灯片的同一道题不重复导入
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_exercise_item_source
        ON exercise_item (source_deck, source_slide, question_type, stem)
    """)


def sync_items(conn, slides, resolved):
    """把 exercise_item 与解析结果对齐：新题插入、答案/选项/词变了的更新、
    课件里已不存在的删除。不提交，由调用方在同一事务里提交或回滚。

    返回 (新增, 更新, 删除)。
    """
    # 只清理本次成功解析出题的课件。课件文件缺失或整份解析失败时，
    # 它的题保持原样——缺输入不能被当成「这些题都该删」。
    parsed_decks = {s['deck'] for s in slides}
    current = {(s['deck'], s['slide'], it['question_type'], it['stem'])
               for s in slides for it in s['items']}
    stale = [row[0] for row in conn.execute(
        "SELECT id, source_deck, source_slide, question_type, stem FROM exercise_item"
    ) if row[1] in parsed_decks and tuple(row[1:]) not in current]
    conn.executemany("DELETE FROM exercise_item WHERE id = ?", [(i,) for i in stale])

    # 去重键不含答案和选项，按键 upsert：题干不变而答案被修正时也要更新
    inserted = updated = 0
    now = datetime.now()
    for s in resolved:
        for it in s['items']:
            options_json = json.dumps(it['options'], ensure_ascii=False) if it['options'] else None
            key = (s['deck'], s['slide'], it['question_type'], it['stem'])
            row = conn.execute("""
                SELECT id, word_id, options_json, correct_answer FROM exercise_item
                WHERE source_deck = ? AND source_slide = ? AND question_type = ? AND stem = ?
            """, key).fetchone()
            if row is None:
                conn.execute("""
                    INSERT INTO exercise_item
                    (word_id, question_type, stem, options_json, correct_answer,
                     source_deck, source_slide, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (s['word_id'], it['question_type'], it['stem'], options_json,
                      it['correct_answer'], s['deck'], s['slide'], now))
                inserted += 1
            elif row[1:] != (s['word_id'], options_json, it['correct_answer']):
                conn.execute("""
                    UPDATE exercise_item SET word_id = ?, options_json = ?, correct_answer = ?
                    WHERE id = ?
                """, (s['word_id'], options_json, it['correct_answer'], row[0]))
                updated += 1
    return inserted, updated, len(stale)


def sync_database(db_path, slides):
    """在一个 IMMEDIATE 事务里完成建表、匹配和同步，失败整体回滚。
    IMMEDIATE 让多个 worker 同时启动时排队执行，而不是交错删改。"""
    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    try:
        conn.execute('BEGIN IMMEDIATE')
        try:
            create_table(conn)
            resolved, unmatched = resolve_word_ids(conn, slides)
            counts = sync_items(conn, slides, resolved)
            conn.execute('COMMIT')
        except Exception:
            conn.execute('ROLLBACK')
            raise
    finally:
        conn.close()
    return counts, unmatched


def import_into(db_path):
    """供后端每次启动时调用，把 exercise_item 与课件同步；重复执行不改变任何行。
    返回 (新增, 更新, 删除, 未匹配词数)。"""
    slides, _ = parse_all()
    if not slides:
        raise RuntimeError(f'{DATA_DIR} 下没有解析出任何题，未改动数据库')
    (inserted, updated, pruned), unmatched = sync_database(db_path, slides)
    return inserted, updated, pruned, len(unmatched)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--import', dest='do_import', action='store_true', help='写入数据库')
    ap.add_argument('--report', action='store_true', help='只解析并报告')
    ap.add_argument('--db', default=os.environ.get('WORDS_DB_PATH', 'words_extended.db'))
    args = ap.parse_args()
    if not (args.do_import or args.report):
        ap.error('请指定 --report 或 --import')

    slides, problems = parse_all()
    total = sum(len(s['items']) for s in slides)
    by_type = {}
    for s in slides:
        for it in s['items']:
            by_type[it['question_type']] = by_type.get(it['question_type'], 0) + 1

    print('📖 解析结果')
    print('   practice 幻灯片: %d' % len(slides))
    print('   题目总数: %d  %s' % (total, by_type))

    conn = sqlite3.connect(args.db)
    resolved, unmatched = resolve_word_ids(conn, slides)
    print('   匹配到词库: %d 组' % len(resolved))
    if unmatched:
        print('   ⚠️ 词库里找不到的词(%d): %s' % (len(unmatched), '、'.join(unmatched)))
    if problems:
        print('   ⚠️ 解析问题 %d 条:' % len(problems))
        for p in problems[:20]:
            print('      -', p)
        if len(problems) > 20:
            print('      ... 另有 %d 条' % (len(problems) - 20))
    if not problems and not unmatched:
        print('   ✅ 无解析问题')

    if args.report:
        conn.close()
        return 0 if not problems else 1

    conn.close()
    if not slides:
        print('❌ 没有解析出任何题，未改动数据库')
        return 1
    (inserted, updated, pruned), _ = sync_database(args.db, slides)
    print('💾 写入 %s: 新增 %d 条，更新 %d 条，删除过期 %d 条'
          % (args.db, inserted, updated, pruned))
    return 0


if __name__ == '__main__':
    sys.exit(main())
