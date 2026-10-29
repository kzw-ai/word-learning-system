#!/usr/bin/env python3
"""学习素材的拼音工具与入库数据修复（scripts/clean_materials.py）"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))

import clean_materials  # noqa: E402  # pyrefly: ignore
from import_learning_materials import split_pinyin_prefix, split_word_pinyin  # noqa: E402  # pyrefly: ignore


class TestPinyinTools:
    def test_split_word_pinyin(self):
        assert split_word_pinyin('fāngmiàn', 2) == ['fāng', 'miàn']
        assert split_word_pinyin('qíngkuàng', 2) == ['qíng', 'kuàng']
        assert split_word_pinyin("xī'ān", 2) == ['xī', 'ān']

    def test_split_word_pinyin_refuses_to_guess(self):
        # 没有隔音符号时 fangan 既可以是 fang'an（方案）也可以是 fan'gan（反感）
        assert split_word_pinyin('fangan', 2) is None
        assert split_word_pinyin('fāngmiàn', 6) is None
        assert split_word_pinyin('', 2) is None

    def test_split_pinyin_prefix(self):
        assert split_pinyin_prefix('hòu NOUN climate') == ('hòu', 'NOUN climate')
        assert split_pinyin_prefix('diǎn place; point') == ('diǎn', 'place; point')
        # 普通英文释义、词性缩写开头的释义都不能被当成拼音
        assert split_pinyin_prefix('n. side; party') is None
        assert split_pinyin_prefix('simply X believe') is None


def make_db(path):
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE word (id INTEGER PRIMARY KEY, pinyin TEXT, definition TEXT);
        CREATE TABLE character (id INTEGER PRIMARY KEY, character TEXT, pinyin TEXT,
                                definition TEXT, audio TEXT, word_id INTEGER);
        CREATE TABLE collocation (id INTEGER PRIMARY KEY, collocation TEXT, translation TEXT,
                                  audio TEXT, word_id INTEGER);
        CREATE TABLE example (id INTEGER PRIMARY KEY, sentence TEXT, pinyin TEXT, translation TEXT,
                              audio TEXT, word_id INTEGER);
        CREATE TABLE confusable_pairs (id INTEGER PRIMARY KEY, word1_id INTEGER, word2_id INTEGER);
        CREATE TABLE adaptive_recommendation (id INTEGER PRIMARY KEY, user_id TEXT, target_word_id INTEGER);
        INSERT INTO word VALUES (1, 'qìhòu', 'climate'), (2, 'fāngmiàn', 'aspect'), (3, 'yinwei', 'because'),
            -- 4：辨析种子插入的空壳「发现」，课件里有它的素材
            (4, 'faxian', 'discover'),
            -- 5：孤立测试词（只被旧推荐日志引用）；6：没有素材但在辨析词对里，必须保留
            (5, '苹果', 'apple'), (6, '突然 tūrán', 'sudden');
        INSERT INTO confusable_pairs VALUES (1, 6, 1);
        INSERT INTO adaptive_recommendation VALUES (1, 'test_user_001', 5);
        INSERT INTO character VALUES
            (1, '气', 'qì', 'n. weather', NULL, 1),
            (2, '候', '', 'hòu NOUN climate', NULL, 1),
            (3, '方', '', 'n. side; party', NULL, 2),
            (4, '面', '', 'n. side', NULL, 2),
            (5, '因', 'yin', 'cause', NULL, 3),
            (6, '为', 'wei', 'for', NULL, 3),
            (7, '发', 'fa', 'send out', NULL, 4),
            (8, '现', 'xian', 'appear', NULL, 4);
    """)
    conn.commit()
    conn.close()


class TestCleanMaterials:
    def test_fixes_known_defects(self, tmp_path):
        db = str(tmp_path / 'm.db')
        make_db(db)
        assert clean_materials.clean_database(db) > 0
        conn = sqlite3.connect(db)
        rows = dict(conn.execute('SELECT id, pinyin || " | " || definition FROM character'))
        assert rows[2] == 'hòu | n. climate'
        assert rows[3].startswith('fāng | ') and rows[4].startswith('miàn | ')
        assert rows[5].startswith('yīn') and rows[6].startswith('wèi')
        assert conn.execute('SELECT pinyin FROM word WHERE id = 3').fetchone()[0] == 'yīnwèi'
        conn.close()

    def test_fills_shell_word_from_source(self, tmp_path):
        db = str(tmp_path / 'm.db')
        make_db(db)
        clean_materials.clean_database(db)
        conn = sqlite3.connect(db)
        collocations = [r[0] for r in conn.execute('SELECT collocation FROM collocation WHERE word_id = 4')]
        assert any('发现' in c for c in collocations)
        assert conn.execute('SELECT COUNT(*) FROM example WHERE word_id = 4').fetchone()[0] > 0
        conn.close()

    def test_deletes_only_unreferenced_orphans(self, tmp_path):
        db = str(tmp_path / 'm.db')
        make_db(db)
        clean_materials.clean_database(db)
        conn = sqlite3.connect(db)
        ids = {r[0] for r in conn.execute('SELECT id FROM word')}
        assert 5 not in ids                       # 孤立测试词被删
        assert conn.execute('SELECT COUNT(*) FROM adaptive_recommendation').fetchone()[0] == 0
        assert 6 in ids                           # 辨析词对引用着，保留
        conn.close()

    def test_idempotent(self, tmp_path):
        db = str(tmp_path / 'm.db')
        make_db(db)
        clean_materials.clean_database(db)
        assert clean_materials.clean_database(db) == 0

    def test_thesis_pinyin_errata(self, tmp_path):
        """第 7 类：论文课件素材的拼音错误，只改仍是错的值"""
        db = str(tmp_path / 'm.db')
        make_db(db)
        conn = sqlite3.connect(db)
        conn.executescript("""
            INSERT INTO word VALUES (11, 'dàngshí', 'then'), (12, 'tōngguò', 'pass');
            INSERT INTO character VALUES (21, '当', 'dàng', 'when', '', 11), (22, '时', 'shí', 'time', '', 11),
                                         (23, '通', 'tòng', 'through', '', 12), (24, '过', 'guò', 'pass', '', 12);
            INSERT INTO example VALUES
                (31, '经理：小王，卫生间怎么那么脏啊？', '经理/jīnglǐ 小/xiǎo 王/wàng 卫生间/wèishēngjiān 怎么/zěnme 那么/nàme 脏/zàng 啊/a', 't', '', 11),
                (32, '生意就这样成了。', '生意/shēngyì 就/jiù 这样/zhèyàng 成/chéng', 't', '', 11),
                (33, '不愿意发生的事情终于出现了。', '不/bù 愿意/yuànyì 发生/fāshēng 的/de 事情/shìqíng 终于/zhōngyú 出现/chūxiàn 了/le 。', 't', '', 11);
        """)
        conn.commit()
        conn.close()
        clean_materials.clean_database(db)
        conn = sqlite3.connect(db)
        assert conn.execute('SELECT pinyin FROM word WHERE id = 11').fetchone()[0] == 'dāngshí'
        assert [r[0] for r in conn.execute('SELECT pinyin FROM character WHERE id IN (21, 23) ORDER BY id')] == ['dāng', 'tōng']
        line = dict(conn.execute('SELECT id, pinyin FROM example WHERE id >= 31'))
        assert '王/wáng' in line[31] and '脏/zāng' in line[31] and 'wàng' not in line[31]
        assert line[32].endswith('成/chéng 了/le 。'), '缺的句尾补上'
        assert line[33].endswith('出现/chūxiàn 了/le 。') and 'shìqíng' in line[33], '本来完整的一行不动'
        conn.close()
        assert clean_materials.clean_database(db) == 0

    def test_thesis_errata_leave_batch_words_alone(self, tmp_path):
        """「当时 dàngshí」（当即）也是合法读音：归属四级批次的词由流水线校对，勘误不动"""
        db = str(tmp_path / 'm.db')
        make_db(db)
        conn = sqlite3.connect(db)
        conn.executescript("""
            CREATE TABLE hsk4_batch_owner (kind TEXT, ref_id INTEGER, batch TEXT, PRIMARY KEY (kind, ref_id));
            INSERT INTO hsk4_batch_owner VALUES ('word', 11, '第09批');
            INSERT INTO word VALUES (11, 'dàngshí', 'immediately');
            INSERT INTO character VALUES (21, '当', 'dàng', 'right', '', 11), (22, '时', 'shí', 'time', '', 11);
        """)
        conn.commit()
        conn.close()
        clean_materials.clean_database(db)
        conn = sqlite3.connect(db)
        assert conn.execute('SELECT pinyin FROM word WHERE id = 11').fetchone()[0] == 'dàngshí'
        assert conn.execute('SELECT pinyin FROM character WHERE id = 21').fetchone()[0] == 'dàng'
        conn.close()


class TestSupplementMaterials:
    """data/learning_materials/supplement_confusable_words.json：课件里没有的词按论文规则补写"""

    def test_loaded_with_the_slides(self):
        from import_learning_materials import load_all_words  # pyrefly: ignore
        words = {w['hanzi']: w for w in load_all_words()}
        for hanzi in ('以为', '认为', '因为', '所以'):
            assert hanzi in words, hanzi
            word = words[hanzi]
            assert len(word['collocations']) == 2 and len(word['examples']) >= 1

    def test_well_formed(self):
        from import_learning_materials import load_all_words, split_word_pinyin  # pyrefly: ignore
        words = {w['hanzi']: w for w in load_all_words()}
        for hanzi in ('以为', '认为', '因为', '所以'):
            word = words[hanzi]
            # 每条搭配、每个例句都含目标词；例句的逐词切分拼回去等于原句
            assert all(hanzi in c['collocation'] for c in word['collocations'])
            for ex in word['examples']:
                assert hanzi in ex['sentence']
                tokens = [t.split('/')[0].lstrip('，。') for t in ex['pinyin'].split() if '/' in t]
                assert ''.join(tokens) == ex['sentence'].replace('，', '').replace('。', '')
            # 单字拼音与整词拼音的音节一致
            assert [c['pinyin'] for c in word['characters']] == split_word_pinyin(word['pinyin'], len(hanzi))


class TestPruneConfusablePairs:
    """辨析词对只来自学习资料流水线：不归属批次的旧词对留档后删除"""

    def _db(self, tmp_path, name='words_extended.db'):
        db = tmp_path / name
        conn = sqlite3.connect(db)
        conn.executescript('''
            CREATE TABLE word (id INTEGER PRIMARY KEY, pinyin TEXT, definition TEXT);
            CREATE TABLE character (id INTEGER PRIMARY KEY, character TEXT, word_id INTEGER);
            CREATE TABLE confusable_pairs (id INTEGER PRIMARY KEY, word1_id INTEGER, word2_id INTEGER, reason TEXT);
            CREATE TABLE confusable_exercise_records (id INTEGER PRIMARY KEY, user_id TEXT, pair_id INTEGER);
            CREATE TABLE hsk4_batch_owner (kind TEXT, ref_id INTEGER, batch TEXT, PRIMARY KEY (kind, ref_id));
            INSERT INTO word VALUES (1, 'fāshēng', ''), (2, 'fāxiàn', ''), (3, 'tūrán', '');
            INSERT INTO character VALUES (1, '发', 1), (2, '生', 1), (3, '发', 2), (4, '现', 2);
            INSERT INTO confusable_pairs VALUES (1, 1, 2, 'old'), (2, 3, 2, 'seed'), (3, 1, 2, 'batch');
            INSERT INTO confusable_exercise_records VALUES (1, 'u', 1), (2, 'u', 3);
            INSERT INTO hsk4_batch_owner VALUES ('pair', 3, '第02批'), ('pair_questions', 1, '第02批');
        ''')
        conn.commit()
        conn.close()
        return db

    def test_report_only_by_default(self, tmp_path):
        import prune_confusable_pairs  # pyrefly: ignore
        db = self._db(tmp_path)
        pairs, archive = prune_confusable_pairs.prune(db)
        assert [p['id'] for p in pairs] == [1, 2] and archive is None
        assert [p['words'] for p in pairs] == ['发生 / 发现', 'tūrán / 发现'], '没有字的词显示拼音'
        assert sqlite3.connect(db).execute('SELECT COUNT(*) FROM confusable_pairs').fetchone()[0] == 3

    def test_apply_archives_then_deletes(self, tmp_path):
        import json
        import prune_confusable_pairs  # pyrefly: ignore
        db = self._db(tmp_path)
        _, archive = prune_confusable_pairs.prune(db, apply=True)
        saved = json.loads(archive.read_text(encoding='utf-8'))
        assert [p['id'] for p in saved] == [1, 2] and saved[0]['records'] == [{'id': 1, 'user_id': 'u', 'pair_id': 1}]
        conn = sqlite3.connect(db)
        assert conn.execute('SELECT id FROM confusable_pairs').fetchall() == [(3,)], '归属批次的词对保留'
        assert conn.execute('SELECT pair_id FROM confusable_exercise_records').fetchall() == [(3,)]
        assert conn.execute('SELECT kind, ref_id FROM hsk4_batch_owner').fetchall() == [('pair', 3)]
        assert prune_confusable_pairs.prune(db, apply=True) == ([], None), '再运行没有要删的'

    def test_archives_of_two_databases_do_not_overwrite_each_other(self, tmp_path):
        import prune_confusable_pairs  # pyrefly: ignore
        archives = [prune_confusable_pairs.prune(self._db(tmp_path, name), apply=True)[1] for name in ('a.db', 'b.db')]
        assert archives[0] != archives[1] and all(a.exists() for a in archives), '同一秒、同一目录也各留一份'
