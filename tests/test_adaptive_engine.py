#!/usr/bin/env python3
"""
自适应引擎算法层单元测试

覆盖改良 SM-2 间隔计算、质量因子、ease factor、
模块推荐规则和到期复习优先级排序。

运行: python3 -m pytest tests/test_adaptive_engine.py -v
"""

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adaptive_engine import AdaptiveRecommendationEngine, SpacedRepetitionAlgorithm


# ================================================
# 夹具
# ================================================

@pytest.fixture
def db_path(tmp_path):
    """建一个最小可用的临时数据库（word + character + example + confusable_pairs + user_progress）"""
    path = str(tmp_path / 'test.db')
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE word (
            id INTEGER NOT NULL PRIMARY KEY,
            pinyin VARCHAR(80) NOT NULL,
            definition VARCHAR(200) NOT NULL,
            freq_rank INTEGER,
            freq_tier VARCHAR(10)
        );
        CREATE TABLE user_progress (
            id INTEGER NOT NULL PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL,
            word_id INTEGER NOT NULL,
            mastery_level FLOAT,
            confidence_score FLOAT,
            difficulty_rating FLOAT,
            total_study_time_seconds INTEGER,
            total_sessions INTEGER,
            total_attempts INTEGER,
            correct_attempts INTEGER,
            character_study_count INTEGER,
            word_study_count INTEGER,
            collocation_study_count INTEGER,
            sentence_study_count INTEGER,
            definition_attempts INTEGER,
            definition_correct INTEGER,
            collocation_attempts INTEGER,
            collocation_correct INTEGER,
            fill_word_attempts INTEGER,
            fill_word_correct INTEGER,
            first_studied DATETIME,
            last_studied DATETIME,
            next_review_suggested DATETIME,
            review_count INTEGER,
            consecutive_correct INTEGER,
            consecutive_incorrect INTEGER,
            learning_efficiency FLOAT,
            retention_rate FLOAT,
            created_at DATETIME,
            updated_at DATETIME,
            FOREIGN KEY(word_id) REFERENCES word (id)
        );
        CREATE TABLE character (
            id INTEGER NOT NULL PRIMARY KEY,
            character VARCHAR(10) NOT NULL,
            word_id INTEGER NOT NULL,
            FOREIGN KEY(word_id) REFERENCES word (id)
        );
        CREATE TABLE example (id INTEGER PRIMARY KEY, word_id INTEGER, sentence TEXT);
        CREATE TABLE confusable_pairs (id INTEGER PRIMARY KEY, word1_id INTEGER, word2_id INTEGER, word2_level INTEGER);
    """)
    conn.execute("INSERT INTO word (id, pinyin, definition) VALUES (1, 'fāshēng', 'happen')")
    conn.execute("INSERT INTO word (id, pinyin, definition) VALUES (2, 'túrán', 'sudden')")
    # 词 2 故意不给 character 行，覆盖「拼不出汉字」的分支
    conn.executemany("INSERT INTO character (character, word_id) VALUES (?, ?)",
                     [('发', 1), ('生', 1)])
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def engine(db_path):
    return AdaptiveRecommendationEngine(db_path)


@pytest.fixture
def spaced(db_path):
    return SpacedRepetitionAlgorithm(db_path)


def add_words(db_path, words):
    """加几个出得了题的词（有单字、有例句）：[(word_id, 词频档位, 排名)]"""
    conn = sqlite3.connect(db_path)
    for word_id, tier, rank in words:
        conn.execute("INSERT INTO word (id, pinyin, definition, freq_tier, freq_rank) VALUES (?, ?, '', ?, ?)",
                     (word_id, f'w{word_id}', tier, rank))
        conn.execute("INSERT INTO character (character, word_id) VALUES ('字', ?)", (word_id,))
        conn.execute("INSERT INTO example (word_id, sentence) VALUES (?, '例句')", (word_id,))
    conn.commit()
    conn.close()


def insert_progress(db_path, user_id='u1', word_id=1, **overrides):
    """插入一条 user_progress，未指定字段用合理默认值"""
    row = {
        'user_id': user_id,
        'word_id': word_id,
        'mastery_level': 0.5,
        'total_study_time_seconds': 600,
        'total_sessions': 3,
        'total_attempts': 10,
        'correct_attempts': 7,
        'character_study_count': 1,
        'word_study_count': 2,
        'collocation_study_count': 1,
        'sentence_study_count': 1,
        'last_studied': datetime.now() - timedelta(days=1),
        'next_review_suggested': datetime.now() + timedelta(days=1),
        'review_count': 1,
        'consecutive_correct': 1,
        'consecutive_incorrect': 0,
        'learning_efficiency': 1.0,
        'created_at': datetime.now(),
        'updated_at': datetime.now(),
    }
    row.update(overrides)
    conn = sqlite3.connect(db_path)
    cols = ', '.join(row.keys())
    marks = ', '.join('?' * len(row))
    conn.execute(f"INSERT INTO user_progress ({cols}) VALUES ({marks})", list(row.values()))
    conn.commit()
    conn.close()


# ================================================
# 质量因子 calculate_quality_factor
# ================================================

class TestQualityFactor:
    def test_incorrect_answer_capped_at_two(self, engine):
        q = engine.calculate_quality_factor({'is_correct': False, 'response_time': 5.0})
        assert 0 <= q <= 2

    def test_incorrect_with_hesitation_lower(self, engine):
        base = engine.calculate_quality_factor({'is_correct': False, 'hesitation_count': 0})
        hesitant = engine.calculate_quality_factor({'is_correct': False, 'hesitation_count': 2})
        assert hesitant < base

    def test_incorrect_never_negative(self, engine):
        q = engine.calculate_quality_factor({'is_correct': False, 'hesitation_count': 10})
        assert q == 0

    def test_fast_confident_correct_is_high(self, engine):
        q = engine.calculate_quality_factor(
            {'is_correct': True, 'response_time': 2.0, 'confidence': 5, 'hesitation_count': 0})
        assert q >= 4

    def test_slow_correct_lower_than_fast_correct(self, engine):
        fast = engine.calculate_quality_factor({'is_correct': True, 'response_time': 2.0})
        slow = engine.calculate_quality_factor({'is_correct': True, 'response_time': 20.0})
        assert slow < fast

    def test_quality_bounded_zero_to_five(self, engine):
        cases = [
            {'is_correct': True, 'response_time': 1.0, 'confidence': 5},
            {'is_correct': True, 'response_time': 30.0, 'confidence': 1, 'hesitation_count': 8},
            {'is_correct': False, 'hesitation_count': 5},
        ]
        for case in cases:
            assert 0 <= engine.calculate_quality_factor(case) <= 5


# ================================================
# Ease factor
# ================================================

class TestEaseFactor:
    def test_default_at_medium_mastery(self, engine):
        assert engine.get_ease_factor(0.5, 0) == pytest.approx(2.5)

    def test_clamped_to_min(self, engine):
        assert engine.get_ease_factor(0.0, 0) >= engine.min_ease_factor

    def test_clamped_to_max(self, engine):
        assert engine.get_ease_factor(1.0, 100) <= engine.max_ease_factor

    def test_consecutive_bonus_caps(self, engine):
        five = engine.get_ease_factor(0.5, 5)
        many = engine.get_ease_factor(0.5, 50)
        assert five == pytest.approx(many)  # 连续正确加成封顶 0.5

    def test_higher_mastery_higher_ease(self, engine):
        assert engine.get_ease_factor(0.9, 0) > engine.get_ease_factor(0.2, 0)


# ================================================
# 复习间隔基线 get_previous_interval
# ================================================

class TestPreviousInterval:
    def test_within_base_intervals(self, engine):
        for i, expected in enumerate(engine.base_intervals):
            assert engine.get_previous_interval(i) == expected

    def test_beyond_base_grows_exponentially(self, engine):
        n = len(engine.base_intervals)
        assert engine.get_previous_interval(n) == engine.base_intervals[-1] * 2
        assert engine.get_previous_interval(n + 1) == engine.base_intervals[-1] * 4


# ================================================
# SM-2 下次复习时间 calculate_next_review_time
# ================================================

class TestNextReviewTime:
    def test_wrong_answer_resets_to_one_day(self, engine, db_path):
        insert_progress(db_path, mastery_level=0.9, review_count=5, consecutive_correct=4)
        next_review = engine.calculate_next_review_time(
            'u1', 1, {'is_correct': False, 'response_time': 5.0})
        delta = next_review - datetime.utcnow()  # 引擎按 UTC 给出下次复习时间
        assert timedelta(hours=23) < delta < timedelta(hours=25)

    def test_new_word_first_interval_short(self, engine, db_path):
        # 数据库无记录 → 新词，首次间隔应为最短档
        next_review = engine.calculate_next_review_time(
            'nobody', 1, {'is_correct': True, 'response_time': 5.0})
        delta = next_review - datetime.utcnow()  # 引擎按 UTC 给出下次复习时间
        assert delta < timedelta(days=2)

    def test_mastered_word_gets_longer_interval_than_weak(self, engine, db_path):
        insert_progress(db_path, user_id='strong', word_id=1,
                        mastery_level=0.9, review_count=4, consecutive_correct=4)
        insert_progress(db_path, user_id='weak', word_id=1,
                        mastery_level=0.2, review_count=4, consecutive_correct=0)
        result = {'is_correct': True, 'response_time': 5.0}
        strong_review = engine.calculate_next_review_time('strong', 1, result)
        weak_review = engine.calculate_next_review_time('weak', 1, result)
        assert strong_review > weak_review

    def test_interval_bounded_one_to_365_days(self, engine, db_path):
        insert_progress(db_path, user_id='max', word_id=1,
                        mastery_level=1.0, review_count=20, consecutive_correct=20)
        next_review = engine.calculate_next_review_time(
            'max', 1, {'is_correct': True, 'response_time': 1.0, 'confidence': 5})
        delta = next_review - datetime.utcnow()  # 引擎按 UTC 给出下次复习时间
        assert delta <= timedelta(days=366)

    def test_fast_response_extends_interval(self, engine, db_path):
        insert_progress(db_path, user_id='fast', word_id=1,
                        mastery_level=0.6, review_count=3, consecutive_correct=2)
        insert_progress(db_path, user_id='slow', word_id=1,
                        mastery_level=0.6, review_count=3, consecutive_correct=2)
        fast_review = engine.calculate_next_review_time(
            'fast', 1, {'is_correct': True, 'response_time': 2.0})
        slow_review = engine.calculate_next_review_time(
            'slow', 1, {'is_correct': True, 'response_time': 12.0})
        assert fast_review > slow_review


# ================================================
# 模块推荐规则
# ================================================

class TestModuleRecommendation:
    def test_vks_mapping(self, engine):
        assert engine.recommend_module_by_vks('A') == 'character'
        assert engine.recommend_module_by_vks('B') == 'word'
        assert engine.recommend_module_by_vks('C') == 'collocation'
        assert engine.recommend_module_by_vks('D') == 'sentence'
        assert engine.recommend_module_by_vks('E') == 'exercise'

    def test_vks_unknown_falls_back_to_word(self, engine):
        assert engine.recommend_module_by_vks('X') == 'word'
        assert engine.recommend_module_by_vks('') == 'word'

    def test_new_user_starts_with_character(self, engine):
        pattern = {'type': 'new_user', 'accuracy': 'unknown'}
        assert engine.recommend_module_by_pattern(pattern, 0.0) == 'character'

    def test_low_mastery_low_accuracy_gets_character(self, engine):
        pattern = {'type': 'experienced_user', 'accuracy': 'low'}
        assert engine.recommend_module_by_pattern(pattern, 0.2) == 'character'

    def test_mid_mastery_gets_collocation(self, engine):
        pattern = {'type': 'experienced_user', 'accuracy': 'high'}
        assert engine.recommend_module_by_pattern(pattern, 0.5) == 'collocation'

    def test_high_mastery_gets_sentence(self, engine):
        pattern = {'type': 'experienced_user', 'accuracy': 'high'}
        assert engine.recommend_module_by_pattern(pattern, 0.8) == 'sentence'


# ================================================
# 学习时间估算
# ================================================

class TestEstimateLearningTime:
    def test_high_efficiency_shortens(self, engine):
        base = engine.estimate_learning_time({'efficiency': 'medium'}, 'word')
        fast = engine.estimate_learning_time({'efficiency': 'high'}, 'word')
        assert fast < base

    def test_low_efficiency_extends(self, engine):
        base = engine.estimate_learning_time({'efficiency': 'medium'}, 'word')
        slow = engine.estimate_learning_time({'efficiency': 'low'}, 'word')
        assert slow > base

    def test_unknown_module_uses_default_base(self, engine):
        assert engine.estimate_learning_time({'efficiency': 'medium'}, 'nonexistent') == 300


# ================================================
# 用户模式分析
# ================================================

class TestUserPattern:
    def test_new_user_detected(self, engine):
        pattern = engine.analyze_user_learning_pattern('ghost_user')
        assert pattern['type'] == 'new_user'

    def test_experienced_user_levels(self, engine, db_path):
        insert_progress(db_path, user_id='pro', word_id=1,
                        learning_efficiency=1.5, total_attempts=20, correct_attempts=18)
        pattern = engine.analyze_user_learning_pattern('pro')
        assert pattern['type'] == 'experienced_user'
        assert pattern['efficiency'] == 'high'
        assert pattern['accuracy'] == 'high'


# ================================================
# 推荐主流程
# ================================================

class TestRecommendationFlow:
    REQUIRED_KEYS = {'type', 'priority', 'confidence'}

    def test_urgent_review_triggers(self, engine, db_path):
        insert_progress(
            db_path, user_id='u1', word_id=1,
            mastery_level=0.5,
            last_studied=datetime.now() - timedelta(days=8),
            consecutive_incorrect=2,
        )
        rec = engine.get_next_recommendation('u1')
        assert rec['type'] == 'urgent_review'
        assert rec['word_id'] == 1
        assert self.REQUIRED_KEYS <= set(rec)

    def test_new_user_gets_valid_recommendation(self, engine):
        rec = engine.get_next_recommendation('brand_new_user')
        assert self.REQUIRED_KEYS <= set(rec)
        assert 0 <= rec['confidence'] <= 1


# ================================================
# 间隔重复：到期复习
# ================================================

class TestDueReviews:
    def test_only_due_items_returned(self, spaced, db_path):
        insert_progress(db_path, user_id='u1', word_id=1,
                        next_review_suggested=datetime.now() - timedelta(days=2))
        insert_progress(db_path, user_id='u1', word_id=2,
                        next_review_suggested=datetime.now() + timedelta(days=5))
        reviews = spaced.get_due_reviews('u1')
        assert [r['word_id'] for r in reviews] == [1]

    def test_priority_favors_weak_and_overdue(self, spaced, db_path):
        insert_progress(db_path, user_id='u1', word_id=1,
                        mastery_level=0.9,
                        next_review_suggested=datetime.now() - timedelta(days=1))
        insert_progress(db_path, user_id='u1', word_id=2,
                        mastery_level=0.1, consecutive_incorrect=3,
                        next_review_suggested=datetime.now() - timedelta(days=10))
        reviews = spaced.get_due_reviews('u1')
        assert reviews[0]['word_id'] == 2  # 掌握差且逾期久的优先

    def test_limit_respected(self, spaced, db_path):
        for word_id in (1, 2):
            insert_progress(db_path, user_id='u1', word_id=word_id,
                            next_review_suggested=datetime.now() - timedelta(days=1))
        assert len(spaced.get_due_reviews('u1', limit=1)) == 1

    def test_word_is_hanzi_with_pinyin_fallback(self, spaced, db_path):
        for word_id in (1, 2):
            insert_progress(db_path, user_id='u1', word_id=word_id,
                            next_review_suggested=datetime.now() - timedelta(days=1))
        by_id = {r['word_id']: r for r in spaced.get_due_reviews('u1')}
        assert (by_id[1]['word'], by_id[1]['pinyin']) == ('发生', 'fāshēng')
        assert by_id[2]['word'] == 'túrán'  # 没有 character 行时退回拼音

    def test_update_after_exercise_persists(self, spaced, db_path):
        insert_progress(db_path, user_id='u1', word_id=1, review_count=1)
        result = spaced.update_user_progress_after_exercise(
            'u1', 1, {'is_correct': True, 'response_time': 4.0, 'consecutive_correct': 2})
        assert result['success'] is True

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT review_count, next_review_suggested FROM user_progress "
            "WHERE user_id='u1' AND word_id=1").fetchone()
        conn.close()
        assert row[0] == 2  # review_count 已自增
        assert datetime.fromisoformat(row[1]) > datetime.now()


# ================================================
# 学习模式缺数据：learning_efficiency 没有代码写入，全是 NULL
# ================================================

class TestPatternWithMissingData:
    def test_null_efficiency_still_recommends_a_new_word(self, engine, db_path):
        """学过一个词以后，AVG(learning_efficiency) 为 NULL，不能让引擎抛异常、退回固定的 1 号词"""
        add_words(db_path, [(3, None, None)])
        insert_progress(db_path, word_id=1, mastery_level=1.0, learning_efficiency=None,
                        total_attempts=0, correct_attempts=0,
                        next_review_suggested=datetime.now() + timedelta(days=1))
        rec = engine.get_next_recommendation('u1')
        assert rec['type'] == 'new_learning'
        assert rec['word_id'] == 3

    def test_level_of_unknown_without_data(self):
        thresholds = {'high': 0.8, 'medium': 0.5}
        assert AdaptiveRecommendationEngine.level_of(None, thresholds) == 'unknown'
        assert AdaptiveRecommendationEngine.level_of(0.9, thresholds) == 'high'
        assert AdaptiveRecommendationEngine.level_of(0.6, thresholds) == 'medium'
        assert AdaptiveRecommendationEngine.level_of(0.1, thresholds) == 'low'

    def test_fallback_picks_an_unstudied_word_not_word_one(self, engine, db_path):
        add_words(db_path, [(3, None, None)])
        conn = sqlite3.connect(db_path)
        conn.execute("INSERT INTO example (word_id, sentence) VALUES (1, '发生了什么？')")
        conn.commit()
        conn.close()
        insert_progress(db_path, word_id=1)
        assert engine.get_fallback_recommendation('u1')['word_id'] == 3
        # 词 2 没有单字，出不了题，不推荐；学完了就是暂无任务，不再退回 1 号词
        insert_progress(db_path, word_id=3)
        assert engine.get_fallback_recommendation('u1')['word_id'] is None

    def test_learner_with_zero_mastery_is_not_a_new_user(self, engine, db_path):
        insert_progress(db_path, word_id=1, mastery_level=0.0)
        assert engine.analyze_user_learning_pattern('u1')['type'] == 'experienced_user'


# ================================================
# 新词的顺序：论文 5.3.1 高、中、低频均衡；2.2.4 易混淆词排在目标词之后
# ================================================

class TestNewWordOrder:
    TIERED = [(10, '高频', 1), (11, '高频', 2), (12, '中频', 3), (13, '中频', 4), (14, '低频', 5), (15, '低频', 6)]

    def next_word(self, engine):
        rec = engine.get_next_recommendation('u1')
        assert rec['type'] == 'new_learning', rec
        return rec['word_id']

    def study(self, db_path, word_id, **overrides):
        insert_progress(db_path, word_id=word_id, next_review_suggested=datetime.utcnow() + timedelta(days=1),
                        **overrides)

    def test_tiers_take_turns_in_frequency_order(self, engine, db_path):
        add_words(db_path, self.TIERED)
        picked = []
        for _ in range(6):
            word_id = self.next_word(engine)
            picked.append(word_id)
            self.study(db_path, word_id)
        assert picked == [10, 12, 14, 11, 13, 15]

    def test_same_word_until_it_is_studied(self, engine, db_path):
        """顺序固定：刷新看板、进入口页不会换成另一个词"""
        add_words(db_path, self.TIERED)
        assert {self.next_word(engine) for _ in range(5)} == {10}

    def test_studied_word_is_never_a_new_word(self, engine, db_path):
        """掌握度低、三天没学的词由复习日程安排，不能被当成新词提前推出来"""
        add_words(db_path, [(10, '高频', 1), (12, '中频', 3)])
        self.study(db_path, 10, mastery_level=0.0, last_studied=datetime.now() - timedelta(days=5))
        assert self.next_word(engine) == 12

    def test_confusable_partner_comes_after_its_target(self, engine, db_path):
        add_words(db_path, self.TIERED + [(20, None, None)])
        conn = sqlite3.connect(db_path)
        conn.execute("INSERT INTO confusable_pairs (word1_id, word2_id, word2_level) VALUES (10, 20, 3)")
        conn.commit()
        conn.close()
        assert self.next_word(engine) == 10
        # 目标词今天才学：易混淆词不在同一天接着学（先分开学）
        self.study(db_path, 10, first_studied=datetime.utcnow())
        assert self.next_word(engine) == 12
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE user_progress SET first_studied = ? WHERE word_id = 10",
                     (datetime.utcnow() - timedelta(days=1),))
        conn.commit()
        conn.close()
        assert self.next_word(engine) == 20

    def test_untiered_words_come_after_the_hsk4_words(self, engine, db_path):
        add_words(db_path, [(3, None, None), (14, '低频', 5)])
        assert self.next_word(engine) == 14
        self.study(db_path, 14)
        assert self.next_word(engine) == 3

    def test_all_caught_up_has_no_word_and_says_when_next(self, engine, db_path):
        add_words(db_path, [(10, '高频', 1)])
        due = datetime.utcnow() + timedelta(days=2)
        insert_progress(db_path, word_id=10, next_review_suggested=due)
        insert_progress(db_path, word_id=1, next_review_suggested=due + timedelta(days=3))
        rec = engine.get_next_recommendation('u1')
        assert rec['type'] == 'all_caught_up'
        assert rec['word_id'] is None
        assert rec['next_review_at'] == due.strftime('%Y-%m-%d %H:%M:%S')
