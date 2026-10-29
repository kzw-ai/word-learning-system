#!/usr/bin/env python3
"""
自适应学习推荐引擎
基于论文《自适应对外汉语中级词汇学习系统研究与设计》
实现智能推荐算法、间隔重复算法和学习路径优化
"""

import sqlite3
import json
import traceback
import math
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np

class AdaptiveRecommendationEngine:
    """自适应推荐引擎主类"""
    
    def __init__(self, db_path='words_extended.db'):
        self.db_path = db_path
        self.algorithm_version = "2.0.0"
        
        # 算法参数
        self.vks_weights = {
            'A': {'character': 1.0, 'word': 0.8, 'collocation': 0.6, 'sentence': 0.4},
            'B': {'character': 0.2, 'word': 1.0, 'collocation': 0.8, 'sentence': 0.6},
            'C': {'character': 0.1, 'word': 0.3, 'collocation': 1.0, 'sentence': 0.8},
            'D': {'character': 0.0, 'word': 0.2, 'collocation': 0.4, 'sentence': 1.0},
            'E': {'character': 0.0, 'word': 0.0, 'collocation': 0.0, 'sentence': 0.2}
        }
        
        # 间隔重复参数（改进的SM-2算法）
        self.base_intervals = [1, 3, 7, 14, 30, 90, 180, 365]  # 天数
        self.ease_factor_default = 2.5
        self.min_ease_factor = 1.3
        self.max_ease_factor = 5.0
        self.mastery_threshold = 0.8
        
        # 学习模式阈值
        self.efficiency_thresholds = {
            'high': 1.2,
            'medium': 0.8,
            'low': 0.5
        }
        
        self.accuracy_thresholds = {
            'high': 0.85,
            'medium': 0.7,
            'low': 0.5
        }
        
    def get_connection(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)
    
    def get_next_recommendation(self, user_id: str, context: Optional[Dict] = None) -> Dict:
        """
        获取下一步学习推荐
        
        Args:
            user_id: 用户ID
            context: 上下文信息（当前词汇、模块等）
            
        Returns:
            推荐结果字典
        """
        try:
            # 1. 检查是否有紧急复习需求
            review_rec = self.check_urgent_review(user_id)
            if review_rec:
                return review_rec
            
            # 2. 检查常规复习需求
            review_rec = self.check_regular_review(user_id)
            if review_rec:
                return review_rec
            
            # 3. 基于用户状态推荐新内容
            learning_rec = self.recommend_learning_content(user_id, context)
            if learning_rec:
                return learning_rec
            
            # 4. 默认推荐
            return self.get_default_recommendation(user_id)
            
        except Exception:
            print(f"推荐引擎错误: {traceback.format_exc()}")
            return self.get_fallback_recommendation(user_id)
    
    def check_urgent_review(self, user_id: str) -> Optional[Dict]:
        """检查紧急复习需求"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 查找掌握程度下降的词汇
            cursor.execute("""
                SELECT up.word_id, up.mastery_level, up.last_studied, w.pinyin
                FROM user_progress up
                JOIN word w ON up.word_id = w.id
                WHERE up.user_id = ?
                AND up.mastery_level BETWEEN 0.3 AND 0.7
                AND up.last_studied < datetime('now', '-7 days')
                AND up.consecutive_incorrect >= 2
                ORDER BY up.mastery_level ASC, up.last_studied ASC
                LIMIT 1
            """, (user_id,))
            
            result = cursor.fetchone()
            if result:
                word_id, mastery_level, last_studied, pinyin = result
                
                return {
                    'type': 'urgent_review',
                    'priority': 'high',
                    'word_id': word_id,
                    'word': pinyin,
                    'reason': f'Your mastery dropped to {mastery_level:.0%} — review it now',
                    'recommended_module': self.determine_review_module(user_id, word_id),
                    'confidence': 0.9,
                    'estimated_time': 300,  # 5分钟
                    'algorithm_version': self.algorithm_version
                }
        
        finally:
            conn.close()
        
        return None
    
    def check_regular_review(self, user_id: str) -> Optional[Dict]:
        """检查常规复习需求"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 查找到期复习的词汇
            cursor.execute("""
                SELECT up.word_id, up.mastery_level, up.next_review_suggested, 
                       w.pinyin, up.review_count
                FROM user_progress up
                JOIN word w ON up.word_id = w.id
                WHERE up.user_id = ?
                AND datetime(up.next_review_suggested) <= datetime('now')
                ORDER BY up.next_review_suggested ASC, up.mastery_level ASC
                LIMIT 1
            """, (user_id,))
            # 不再按掌握度过滤：到期与否由复习日程决定。论文表 4.2 要求第一次就全对的词
            # 也按档位复习 2–5 次，此前掌握度 1.0 的词到期了也不会被推荐
            
            result = cursor.fetchone()
            if result:
                word_id, mastery_level, next_review, pinyin, review_count = result
                # 旧行的掌握度可能是 NULL，按 0 处理（不再按掌握度过滤后，这类行也会被选中）
                mastery_level = mastery_level or 0
                
                # 计算复习优先级
                days_overdue = (datetime.utcnow() - datetime.fromisoformat(next_review)).days
                priority_score = (1 - mastery_level) * (1 + days_overdue * 0.1)
                
                return {
                    'type': 'scheduled_review',
                    'priority': 'medium' if priority_score > 0.5 else 'low',
                    'word_id': word_id,
                    'word': pinyin,
                    'reason': f'Time for a scheduled review (mastery {mastery_level:.0%})',
                    'recommended_module': self.determine_review_module(user_id, word_id),
                    'confidence': 0.8,
                    'estimated_time': 240,  # 4分钟
                    'days_overdue': days_overdue,
                    'review_count': review_count,
                    'algorithm_version': self.algorithm_version
                }
        
        finally:
            conn.close()
        
        return None
    
    def recommend_learning_content(self, user_id: str, context: Optional[Dict] = None) -> Optional[Dict]:
        """推荐新的学习内容"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 获取用户学习模式
            user_pattern = self.analyze_user_learning_pattern(user_id)
            
            candidate = self.next_new_word(cursor, user_id)
            if not candidate:
                return None
            word_id, pinyin = candidate
            mastery_level = 0
            
            # 基于用户模式和当前上下文确定学习模块
            if context and 'vks_level' in context:
                recommended_module = self.recommend_module_by_vks(context['vks_level'])
            else:
                recommended_module = self.recommend_module_by_pattern(user_pattern, mastery_level)
            
            return {
                'type': 'new_learning',
                'priority': 'medium',
                'word_id': word_id,
                'word': pinyin,
                'reason': 'A new word to learn',
                'recommended_module': recommended_module,
                'confidence': 0.7,
                'estimated_time': self.estimate_learning_time(user_pattern, recommended_module),
                'user_pattern': user_pattern,
                'algorithm_version': self.algorithm_version
            }
            
        finally:
            conn.close()

    # 推荐新词时三档轮流的先后：学过的词数相同时先高频
    FREQ_TIERS = ('高频', '中频', '低频')

    def next_new_word(self, cursor, user_id: str) -> Optional[Tuple[int, str]]:
        """下一个要学的新词 (word_id, pinyin)，没有时返回 None。只选这个用户还没学过（没有进度）、
        出得了题（有单字和例句）的词；学过的词由复习日程安排，不再当新词推荐。顺序固定，刷新不会换词：
        1. 一至三级易混淆词：它的四级目标词已经学过、且不是今天才学的（论文 2.2.4：先分开学，排在目标词之后）；
        2. 四级词按高、中、低频轮流（论文 5.3.1：每次学习安排相当比例的三档词）：从学过的词最少的一档里
           取词频排名最靠前的；
        3. 不在四级词表里的其他词（论文词库里的低等级词），按 id；等目标词的易混淆词排在最后。"""
        unstudied = """NOT EXISTS (SELECT 1 FROM user_progress up WHERE up.word_id = w.id AND up.user_id = ?)
            AND EXISTS (SELECT 1 FROM example e WHERE e.word_id = w.id)
            AND EXISTS (SELECT 1 FROM character c WHERE c.word_id = w.id)"""
        cursor.execute(f"""
            SELECT w.id, w.pinyin FROM confusable_pairs p
            JOIN word w ON w.id = p.word2_id
            JOIN user_progress t ON t.word_id = p.word1_id AND t.user_id = ?
            WHERE p.word2_level < 4 AND date(t.first_studied) < date('now') AND {unstudied}
            ORDER BY t.first_studied, p.id
            LIMIT 1
        """, (user_id, user_id))
        row = cursor.fetchone()
        if row:
            return row

        cursor.execute("""
            SELECT w.freq_tier, COUNT(up.word_id) FROM word w
            LEFT JOIN user_progress up ON up.word_id = w.id AND up.user_id = ?
            WHERE w.freq_tier IS NOT NULL
            GROUP BY w.freq_tier
        """, (user_id,))
        studied = dict(cursor.fetchall())
        order = sorted(studied, key=lambda t: (studied[t], self.FREQ_TIERS.index(t) if t in self.FREQ_TIERS else 9))
        for tier in order:
            cursor.execute(f"""
                SELECT w.id, w.pinyin FROM word w
                WHERE w.freq_tier = ? AND {unstudied}
                ORDER BY w.freq_rank, w.id
                LIMIT 1
            """, (tier, user_id))
            row = cursor.fetchone()
            if row:
                return row

        cursor.execute(f"""
            SELECT w.id, w.pinyin FROM word w
            WHERE w.freq_tier IS NULL AND {unstudied}
            ORDER BY EXISTS (SELECT 1 FROM confusable_pairs p WHERE p.word2_id = w.id AND p.word2_level < 4), w.id
            LIMIT 1
        """, (user_id,))
        return cursor.fetchone()

    @staticmethod
    def level_of(value: Optional[float], thresholds: Dict) -> str:
        """按阈值分 high / medium / low；没有数据（None）时为 unknown"""
        if value is None:
            return 'unknown'
        if value >= thresholds['high']:
            return 'high'
        if value >= thresholds['medium']:
            return 'medium'
        return 'low'

    def analyze_user_learning_pattern(self, user_id: str) -> Dict:
        """分析用户学习模式"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 获取用户整体学习统计
            cursor.execute("""
                SELECT 
                    AVG(mastery_level) as avg_mastery,
                    AVG(learning_efficiency) as avg_efficiency,
                    AVG(CAST(correct_attempts AS FLOAT) / total_attempts) as avg_accuracy,
                    COUNT(*) as total_words,
                    AVG(total_study_time_seconds) as avg_study_time
                FROM user_progress
                WHERE user_id = ?
            """, (user_id,))
            
            stats = cursor.fetchone()
            if not stats[3]:  # 新用户：一条进度都没有（不能看平均掌握度，学过但掌握度为 0 的不是新用户）
                return {
                    'type': 'new_user',
                    'efficiency': 'unknown',
                    'accuracy': 'unknown',
                    'preference': 'systematic'
                }
            
            avg_mastery, avg_efficiency, avg_accuracy, total_words, avg_study_time = stats
            
            # 学习效率 learning_efficiency 没有任何代码写入，全是 NULL，AVG 也是 NULL；学过词但没作答过时
            # 准确率的分母是 0，同样是 NULL。拿 None 比大小会抛异常，引擎就退回固定的 1 号词，
            # 学过一个词以后看板永远推荐「发生」。没有数据时按 unknown，同新用户
            efficiency_level = self.level_of(avg_efficiency, self.efficiency_thresholds)
            accuracy_level = self.level_of(avg_accuracy, self.accuracy_thresholds)
            
            # 分析学习偏好（基于各模块的学习时间分布）
            cursor.execute("""
                SELECT 
                    AVG(character_study_count) as char_avg,
                    AVG(word_study_count) as word_avg,
                    AVG(collocation_study_count) as coll_avg,
                    AVG(sentence_study_count) as sent_avg
                FROM user_progress
                WHERE user_id = ?
            """, (user_id,))
            
            module_stats = cursor.fetchone()
            char_avg, word_avg, coll_avg, sent_avg = module_stats
            
            # 确定学习偏好
            module_scores = {
                'character': char_avg or 0,
                'word': word_avg or 0,
                'collocation': coll_avg or 0,
                'sentence': sent_avg or 0
            }
            preferred_module = max(module_scores, key=lambda k: module_scores[k])
            
            return {
                'type': 'experienced_user',
                'efficiency': efficiency_level,
                'accuracy': accuracy_level,
                'preference': preferred_module,
                'avg_mastery': avg_mastery,
                'avg_efficiency': avg_efficiency,
                'avg_accuracy': avg_accuracy,
                'total_words': total_words,
                'avg_study_time': avg_study_time
            }
            
        finally:
            conn.close()
    
    def recommend_module_by_vks(self, vks_level: str) -> str:
        """基于VKS测试结果推荐模块"""
        vks_modules = {
            'A': 'character',
            'B': 'word', 
            'C': 'collocation',
            'D': 'sentence',
            'E': 'exercise'
        }
        return vks_modules.get(vks_level, 'word')
    
    def recommend_module_by_pattern(self, user_pattern: Dict, mastery_level: float) -> str:
        """基于用户模式推荐模块"""
        if user_pattern['type'] == 'new_user':
            return 'character'  # 新用户从字符开始
        
        # 基于掌握程度和用户偏好
        if mastery_level < 0.3:
            if user_pattern['accuracy'] == 'low':
                return 'character'  # 基础薄弱，从字符开始
            else:
                return 'word'
        elif mastery_level < 0.6:
            return 'collocation'  # 中等水平，学习搭配
        else:
            return 'sentence'  # 较高水平，学习句子应用
    
    def determine_review_module(self, user_id: str, word_id: int) -> str:
        """确定复习模块"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 获取用户在各题型上的表现
            cursor.execute("""
                SELECT 
                    definition_attempts, definition_correct,
                    collocation_attempts, collocation_correct,
                    fill_word_attempts, fill_word_correct
                FROM user_progress
                WHERE user_id = ? AND word_id = ?
            """, (user_id, word_id))
            
            result = cursor.fetchone()
            if not result:
                return 'word'  # 默认复习模块
            
            # 题型统计字段允许为 NULL（从未做过该题型），按 0 处理
            (def_attempts, def_correct, coll_attempts, coll_correct,
             fill_attempts, fill_correct) = (value or 0 for value in result)

            # 计算各题型准确率
            def_rate = (def_correct / def_attempts) if def_attempts > 0 else 1.0
            coll_rate = (coll_correct / coll_attempts) if coll_attempts > 0 else 1.0
            fill_rate = (fill_correct / fill_attempts) if fill_attempts > 0 else 1.0
            
            # 找出最薄弱的环节
            rates = {
                'word': def_rate,
                'collocation': coll_rate,
                'sentence': fill_rate
            }
            
            weakest_module = min(rates, key=lambda k: rates[k])
            
            # 如果最薄弱的准确率太低，推荐对应的复习模块
            if rates[weakest_module] < 0.7:
                return weakest_module
            else:
                return 'exercise'  # 整体水平可以，直接练习
                
        finally:
            conn.close()
    
    def estimate_learning_time(self, user_pattern: Dict, module: str) -> int:
        """估算学习时间（秒）"""
        base_times = {
            'character': 300,  # 5分钟
            'word': 240,       # 4分钟
            'collocation': 360, # 6分钟
            'sentence': 420,   # 7分钟
            'exercise': 300    # 5分钟
        }
        
        base_time = base_times.get(module, 300)
        
        # 根据用户效率调整
        if user_pattern['efficiency'] == 'high':
            return int(base_time * 0.7)
        elif user_pattern['efficiency'] == 'low':
            return int(base_time * 1.5)
        else:
            return base_time
    
    def calculate_next_review_time(self, user_id: str, word_id: int, 
                                 exercise_result: Dict) -> datetime:
        """
        计算下次复习时间（基于改进的SM-2算法）
        
        Args:
            user_id: 用户ID
            word_id: 词汇ID
            exercise_result: 练习结果 {'is_correct': bool, 'response_time': float, 'confidence': int}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 获取当前进度信息
            cursor.execute("""
                SELECT mastery_level, review_count, consecutive_correct, consecutive_incorrect
                FROM user_progress
                WHERE user_id = ? AND word_id = ?
            """, (user_id, word_id))
            
            result = cursor.fetchone()
            if not result:
                # 新词汇，设置初始值
                mastery_level, review_count, consecutive_correct, consecutive_incorrect = 0.0, 0, 0, 0
            else:
                mastery_level, review_count, consecutive_correct, consecutive_incorrect = result
            
            return self.next_review_from(mastery_level, review_count, consecutive_correct,
                                         consecutive_incorrect, exercise_result)
            
        finally:
            conn.close()
    
    def next_review_from(self, mastery_level: float, review_count: int,
                         consecutive_correct: int, consecutive_incorrect: int,
                         exercise_result: Dict) -> datetime:
        """由给定的进度与本次结果算下次复习时间，不读写数据库。

        调用方已在自己的事务里持有进度行时用它，避免另开连接读到事务外的旧值。
        """
        # 计算质量因子（0-5）
        quality = self.calculate_quality_factor(exercise_result)
        
        # 获取或计算ease factor
        ease_factor = self.get_ease_factor(mastery_level, consecutive_correct)
        
        # 更新ease factor
        ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        ease_factor = max(self.min_ease_factor, min(self.max_ease_factor, ease_factor))
        
        # 计算间隔
        if quality < 3:  # 答错了
            interval_days = 1  # 重新开始
            consecutive_correct = 0
            consecutive_incorrect += 1
        else:  # 答对了
            consecutive_correct += 1
            consecutive_incorrect = 0
            
            if review_count == 0:
                interval_days = 1
            elif review_count == 1:
                interval_days = 6
            else:
                # 使用ease factor计算间隔
                previous_interval = self.get_previous_interval(review_count - 1)
                interval_days = int(previous_interval * ease_factor)
            
            # 基于掌握程度调整间隔
            mastery_adjustment = 0.5 + mastery_level
            interval_days = int(interval_days * mastery_adjustment)
            
            # 基于响应时间调整
            response_time = exercise_result.get('response_time', 5.0)
            if response_time < 3.0:  # 快速回答
                interval_days = int(interval_days * 1.2)
            elif response_time > 10.0:  # 慢速回答
                interval_days = int(interval_days * 0.8)
        
        # 限制最大最小间隔
        interval_days = max(1, min(365, interval_days))
        
        # 计算下次复习时间
        # UTC：到期判断用的是 SQLite 的 datetime('now')（UTC）。此前用服务器本地时间，
        # 服务器在 UTC-4，每个词都提前 4 小时到期
        next_review = datetime.utcnow() + timedelta(days=interval_days)
        return next_review

    def calculate_quality_factor(self, exercise_result: Dict) -> float:
        """计算答题质量因子（0-5）"""
        is_correct = exercise_result.get('is_correct', False)
        response_time = exercise_result.get('response_time', 10.0)
        confidence = exercise_result.get('confidence', 3)
        hesitation_count = exercise_result.get('hesitation_count', 0)
        
        if not is_correct:
            return max(0, 2 - hesitation_count * 0.5)  # 错误答案，质量0-2
        
        # 正确答案的质量计算
        base_quality = 3.0
        
        # 响应时间调整
        if response_time < 3.0:
            base_quality += 1.0  # 快速正确
        elif response_time < 5.0:
            base_quality += 0.5
        elif response_time > 15.0:
            base_quality -= 0.5  # 慢速正确
        
        # 信心度调整
        confidence_adjustment = (confidence - 3) * 0.2
        base_quality += confidence_adjustment
        
        # 犹豫次数调整
        base_quality -= hesitation_count * 0.3
        
        return max(0, min(5, base_quality))
    
    def get_ease_factor(self, mastery_level: float, consecutive_correct: int) -> float:
        """获取ease factor"""
        # 基于掌握程度的基础ease factor
        base_ease = self.ease_factor_default + (mastery_level - 0.5) * 0.5
        
        # 基于连续正确次数的调整
        consecutive_bonus = min(consecutive_correct * 0.1, 0.5)
        
        return max(self.min_ease_factor, min(self.max_ease_factor, base_ease + consecutive_bonus))
    
    def get_previous_interval(self, review_count: int) -> int:
        """获取之前的复习间隔"""
        if review_count < len(self.base_intervals):
            return self.base_intervals[review_count]
        else:
            # 超出预设间隔，使用指数增长
            return self.base_intervals[-1] * (2 ** (review_count - len(self.base_intervals) + 1))
    
    def get_default_recommendation(self, user_id: str) -> Dict:
        """没有到期复习、也没有新词可学时：明确告诉前端暂时没有任务（word_id 为空，不能开始学习），
        并带上最近一次复习的时间（UTC，没有排期时为空）"""
        conn = self.get_connection()
        try:
            next_review_at = conn.execute("""
                SELECT MIN(datetime(next_review_suggested)) FROM user_progress
                WHERE user_id = ? AND next_review_suggested IS NOT NULL
            """, (user_id,)).fetchone()[0]
        finally:
            conn.close()
        return {
            'type': 'all_caught_up',
            'priority': 'low',
            'word_id': None,
            'reason': 'Nothing to study right now',
            'recommended_module': None,
            'next_review_at': next_review_at,
            'confidence': 0.5,
            'estimated_time': 0,
            'algorithm_version': self.algorithm_version
        }
    
    def get_fallback_recommendation(self, user_id: Optional[str] = None) -> Dict:
        """推荐出错时的退路：这个用户还没学过、出得了题的词（按 id）；都学过了或查不出来时 word_id 为空（暂无任务）。
        以前固定返回 1 号词，出错就一直推荐同一个词，故障也被掩盖了"""
        word_id = None
        if user_id:
            try:
                conn = self.get_connection()
                try:
                    row = conn.execute("""
                        SELECT w.id FROM word w
                        WHERE EXISTS (SELECT 1 FROM example e WHERE e.word_id = w.id)
                        AND EXISTS (SELECT 1 FROM character c WHERE c.word_id = w.id)
                        AND NOT EXISTS (SELECT 1 FROM user_progress up WHERE up.word_id = w.id AND up.user_id = ?)
                        ORDER BY w.id LIMIT 1
                    """, (user_id,)).fetchone()
                finally:
                    conn.close()
                if row:
                    word_id = row[0]
            except Exception:
                print(f"推荐引擎退路也出错: {traceback.format_exc()}")
        return {
            'type': 'system_default',
            'priority': 'low',
            'word_id': word_id,
            'reason': 'Suggested for you',
            'recommended_module': 'word',
            'confidence': 0.3,
            'estimated_time': 300,
            'algorithm_version': self.algorithm_version
        }
    
    def record_recommendation_feedback(self, recommendation_id: str, user_id: str, 
                                     feedback: Dict) -> bool:
        """记录推荐反馈"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE adaptive_recommendation 
                SET is_accepted = ?, actual_choice = ?, effectiveness_score = ?
                WHERE id = ? AND user_id = ?
            """, (
                feedback.get('accepted', False),
                feedback.get('actual_choice'),
                feedback.get('effectiveness_score'),
                recommendation_id,
                user_id
            ))
            
            conn.commit()
            return cursor.rowcount > 0
            
        finally:
            conn.close()
    
    def save_recommendation(self, user_id: str, recommendation: Dict) -> int:
        """保存推荐记录"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO adaptive_recommendation
                (user_id, recommendation_type, target_word_id, target_module,
                 confidence_score, algorithm_version, recommendation_data, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                recommendation['type'],
                recommendation.get('word_id'),
                recommendation.get('recommended_module'),
                recommendation.get('confidence', 0.0),
                self.algorithm_version,
                json.dumps(recommendation),
                # UTC，与其他表的 created_at（模型默认 utcnow）一致
                datetime.utcnow()
            ))
            
            conn.commit()
            return cursor.lastrowid or 0
            
        finally:
            conn.close()

# 间隔重复算法专用类
class SpacedRepetitionAlgorithm:
    """间隔重复算法实现"""
    
    def __init__(self, db_path='words_extended.db'):
        self.db_path = db_path
        self.engine = AdaptiveRecommendationEngine(db_path)
    
    def update_user_progress_after_exercise(self, user_id: str, word_id: int, 
                                          exercise_result: Dict):
        """练习后更新用户进度和复习计划"""
        conn = self.engine.get_connection()
        cursor = conn.cursor()
        
        try:
            # 计算下次复习时间
            next_review = self.engine.calculate_next_review_time(user_id, word_id, exercise_result)
            
            # 更新用户进度
            cursor.execute("""
                UPDATE user_progress 
                SET 
                    last_studied = ?,
                    next_review_suggested = ?,
                    review_count = review_count + 1,
                    consecutive_correct = ?,
                    consecutive_incorrect = ?,
                    updated_at = ?
                WHERE user_id = ? AND word_id = ?
            """, (
                datetime.now(),
                next_review,
                exercise_result.get('consecutive_correct', 0),
                exercise_result.get('consecutive_incorrect', 0),
                datetime.now(),
                user_id,
                word_id
            ))
            
            conn.commit()
            
            return {
                'success': True,
                'next_review': next_review,
                'message': f'Next review: {next_review.strftime("%Y-%m-%d %H:%M")} UTC'
            }
            
        except Exception as e:
            conn.rollback()
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            conn.close()
    
    def get_due_reviews(self, user_id: str, limit: int = 10) -> List[Dict]:
        """获取到期复习列表"""
        conn = self.engine.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT up.word_id, w.pinyin, up.mastery_level, up.next_review_suggested,
                       up.review_count, up.consecutive_incorrect
                FROM user_progress up
                JOIN word w ON up.word_id = w.id
                WHERE up.user_id = ?
                AND datetime(up.next_review_suggested) <= datetime('now')
                ORDER BY up.next_review_suggested ASC, up.mastery_level ASC
                LIMIT ?
            """, (user_id, limit))
            
            results = cursor.fetchall()
            reviews = []
            
            for result in results:
                word_id, pinyin, mastery_level, next_review, review_count, consecutive_incorrect = result
                # 种子脚本写入的旧行可能是 NULL，按 0 处理，否则优先级计算直接抛异常
                mastery_level = mastery_level or 0
                consecutive_incorrect = consecutive_incorrect or 0
                
                # 计算优先级
                days_overdue = (datetime.utcnow() - datetime.fromisoformat(next_review)).days
                priority = (1 - mastery_level) * (1 + days_overdue * 0.1) * (1 + consecutive_incorrect * 0.2)
                
                # word 表没有汉字列，按 character 表顺序拼出；拼不出时退回拼音
                cursor.execute(
                    "SELECT character FROM character WHERE word_id = ? ORDER BY id",
                    (word_id,)
                )
                hanzi = ''.join(row[0] for row in cursor.fetchall())

                reviews.append({
                    'word_id': word_id,
                    'word': hanzi or pinyin,
                    'pinyin': pinyin,
                    'mastery_level': mastery_level,
                    'days_overdue': days_overdue,
                    'review_count': review_count,
                    'priority_score': priority,
                    'recommended_module': self.engine.determine_review_module(user_id, word_id)
                })
            
            # 按优先级排序
            reviews.sort(key=lambda x: x['priority_score'], reverse=True)
            
            return reviews
            
        finally:
            conn.close()

def test_adaptive_engine():
    """测试自适应引擎功能"""
    print("🧪 测试自适应推荐引擎...")
    
    engine = AdaptiveRecommendationEngine()
    
    # 测试用户
    test_user = 'test_user_001'
    
    try:
        # 1. 测试获取推荐
        recommendation = engine.get_next_recommendation(test_user)
        print("✅ 推荐获取测试通过:")
        print(f"   类型: {recommendation['type']}")
        print(f"   原因: {recommendation['reason']}")
        print(f"   推荐模块: {recommendation['recommended_module']}")
        
        # 2. 测试用户模式分析
        pattern = engine.analyze_user_learning_pattern(test_user)
        print("✅ 用户模式分析测试通过:")
        print(f"   类型: {pattern['type']}")
        print(f"   效率: {pattern.get('efficiency', 'unknown')}")
        print(f"   准确率: {pattern.get('accuracy', 'unknown')}")
        
        # 3. 测试间隔重复算法
        srs = SpacedRepetitionAlgorithm()
        exercise_result = {
            'is_correct': True,
            'response_time': 4.5,
            'confidence': 4,
            'hesitation_count': 0
        }
        
        result = srs.update_user_progress_after_exercise(test_user, 1, exercise_result)
        print("✅ 间隔重复算法测试通过:")
        print(f"   成功: {result['success']}")
        if result['success']:
            print(f"   下次复习: {result['next_review']}")
        
        # 4. 测试到期复习
        due_reviews = srs.get_due_reviews(test_user)
        print(f"✅ 到期复习测试通过: 找到 {len(due_reviews)} 个待复习词汇")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    test_adaptive_engine()
