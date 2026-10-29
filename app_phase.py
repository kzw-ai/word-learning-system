#!/usr/bin/env python3
"""
第二阶段扩展API服务
集成自适应推荐引擎、学习分析和复习调度功能
"""

from flask import Flask, g, jsonify, request, make_response, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, timezone
import os
import re
import json
import random
import sqlite3
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError

# 导入自适应引擎
try:
    from adaptive_engine import AdaptiveRecommendationEngine, SpacedRepetitionAlgorithm
except ImportError:
    print("⚠️  自适应引擎模块未找到，将使用简化版本")
    AdaptiveRecommendationEngine = None
    SpacedRepetitionAlgorithm = None

# 导入认证模块
try:
    from auth import AuthManager, require_auth
except ImportError:
    print("⚠️  认证模块未找到，将禁用认证功能")
    AuthManager = None
    require_auth = lambda f: f  # 空装饰器

# 导入数据隔离模块
try:
    from user_data_isolation import (
        require_authentication, 
        check_data_ownership,
        get_current_user_from_request,
        get_guest_id,
        user_id_param_allowed
    )
except ImportError:
    print("⚠️  数据隔离模块未找到，将使用基础功能")
    require_authentication = lambda allow_url_param=True: lambda f: f
    check_data_ownership = lambda: lambda f: f
    get_current_user_from_request = lambda: (None, False)
    get_guest_id = lambda: None
    user_id_param_allowed = lambda: True

# 导入易混淆词API模块
try:
    from confusable_api import question_version, register_confusable_apis
except ImportError:
    print("⚠️  易混淆词API模块未找到")
    register_confusable_apis = None

app = Flask(__name__)
CORS(app, supports_credentials=True)  # pyrefly: ignore  # 支持credentials以便使用cookies

# 配置Session
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# 配置数据库（WORDS_DB_PATH 环境变量可覆盖，供测试/部署使用）
basedir = os.path.abspath(os.path.dirname(__file__))
_db_path = os.environ.get('WORDS_DB_PATH', os.path.join(basedir, 'words_extended.db'))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + _db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 数据库模型定义
class Word(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pinyin = db.Column(db.String(80), nullable=False)
    definition = db.Column(db.String(200), nullable=False)
    # 整词发音的地址（/api/audio/<指纹>.mp3）；字、搭配、例句的 audio 列同此。音频文件见 AUDIO_DIR
    audio = db.Column(db.String(200))
    # 新 HSK 四级词的加权词频排名（1–600）和档位（高频/中频/低频，论文 5.3.1），见 data/hsk4_frequency_tiers.csv；
    # 不在四级词表里的词（一至三级易混淆词、论文词库里的低等级词）为空
    freq_rank = db.Column(db.Integer)
    freq_tier = db.Column(db.String(10))

class ExerciseItem(db.Model):
    """论文 6 套答案课件里的人工命题。

    由 scripts/parse_answer_decks.py 从 data/learning_materials/the answer*.json
    解析入库。这些题的干扰项是作者按教学设计挑的（形近、义近、同音），
    远优于从词库随机抽词拼凑出来的选项。
    """
    __tablename__ = 'exercise_item'
    __table_args__ = (
        db.UniqueConstraint('source_deck', 'source_slide', 'question_type', 'stem',
                            name='uq_exercise_item_source'),
    )
    id = db.Column(db.Integer, primary_key=True)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False, index=True)
    question_type = db.Column(db.String(20), nullable=False)
    stem = db.Column(db.Text, nullable=False)
    options_json = db.Column(db.Text)          # JSON 数组；填词题为空
    correct_answer = db.Column(db.String(100), nullable=False)
    source_deck = db.Column(db.String(100), nullable=False)
    source_slide = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Example(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sentence = db.Column(db.String(200), nullable=False)
    pinyin = db.Column(db.String(200), nullable=False)
    translation = db.Column(db.String(200), nullable=False)
    audio = db.Column(db.String(200), nullable=False)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)

class Collocation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    collocation = db.Column(db.String(200), nullable=False)
    translation = db.Column(db.String(200), nullable=False)
    audio = db.Column(db.String(200), nullable=False)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)

class Character(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    character = db.Column(db.String(10), nullable=False)
    pinyin = db.Column(db.String(80), nullable=False)
    definition = db.Column(db.String(200), nullable=False)
    audio = db.Column(db.String(200), nullable=False)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)

class UserProfile(db.Model):
    __tablename__ = 'user_profile'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), unique=True, nullable=False)
    username = db.Column(db.String(100))
    language_level = db.Column(db.String(20))
    native_language = db.Column(db.String(50), default='English')
    # 持久化学习状态（跨设备恢复）
    current_word_id = db.Column(db.Integer)
    current_word = db.Column(db.String(50))
    current_module = db.Column(db.String(30))
    current_vks_level = db.Column(db.String(5))
    # 当前这一轮是照哪条推荐在学：随学习位置一起跨设备同步，换设备续学时
    # 学习会话仍能绑定到这条推荐（推荐效果按绑定算）
    current_recommendation_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class LearningSession(db.Model):
    __tablename__ = 'learning_session'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), unique=True, nullable=False)
    user_id = db.Column(db.String(50), nullable=False)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)
    session_type = db.Column(db.String(20), nullable=False)
    module_type = db.Column(db.String(30), nullable=False)
    initial_level = db.Column(db.String(1))
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    duration_seconds = db.Column(db.Integer)
    active_time_seconds = db.Column(db.Integer)
    completed = db.Column(db.Boolean, default=False)
    interrupted = db.Column(db.Boolean, default=False)
    device_type = db.Column(db.String(20), default='web')
    # 照哪条推荐开始学的（adaptive_recommendation.id）；推荐效果按它算，见
    # score_recommendation_from_session
    recommendation_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ExerciseRecord(db.Model):
    __tablename__ = 'exercise_record'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False)
    question_id = db.Column(db.String(50), nullable=False)
    question_type = db.Column(db.String(20), nullable=False)
    question_content = db.Column(db.Text)
    user_answer = db.Column(db.String(500))
    correct_answer = db.Column(db.String(500))
    is_correct = db.Column(db.Boolean, nullable=False)
    confidence_level = db.Column(db.Integer)
    question_start_time = db.Column(db.DateTime, nullable=False)
    question_end_time = db.Column(db.DateTime)
    response_time_seconds = db.Column(db.Float)
    hesitation_count = db.Column(db.Integer, default=0)
    attempt_count = db.Column(db.Integer, default=1)
    is_first_attempt = db.Column(db.Boolean, default=True)
    feedback_shown = db.Column(db.Boolean, default=False)
    feedback_view_time_seconds = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserProgress(db.Model):
    __tablename__ = 'user_progress'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'word_id', name='uq_user_progress_user_word'),
    )
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)
    mastery_level = db.Column(db.Float, default=0.0)
    confidence_score = db.Column(db.Float, default=0.0)
    difficulty_rating = db.Column(db.Float)
    total_study_time_seconds = db.Column(db.Integer, default=0)
    total_sessions = db.Column(db.Integer, default=0)
    total_attempts = db.Column(db.Integer, default=0)
    correct_attempts = db.Column(db.Integer, default=0)
    character_study_count = db.Column(db.Integer, default=0)
    word_study_count = db.Column(db.Integer, default=0)
    collocation_study_count = db.Column(db.Integer, default=0)
    sentence_study_count = db.Column(db.Integer, default=0)
    definition_attempts = db.Column(db.Integer, default=0)
    definition_correct = db.Column(db.Integer, default=0)
    collocation_attempts = db.Column(db.Integer, default=0)
    collocation_correct = db.Column(db.Integer, default=0)
    fill_word_attempts = db.Column(db.Integer, default=0)
    fill_word_correct = db.Column(db.Integer, default=0)
    first_studied = db.Column(db.DateTime)
    last_studied = db.Column(db.DateTime)
    next_review_suggested = db.Column(db.DateTime)
    review_count = db.Column(db.Integer, default=0)
    consecutive_correct = db.Column(db.Integer, default=0)
    consecutive_incorrect = db.Column(db.Integer, default=0)
    learning_efficiency = db.Column(db.Float)
    retention_rate = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AdaptiveRecommendation(db.Model):
    __tablename__ = 'adaptive_recommendation'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    recommendation_type = db.Column(db.String(30), nullable=False)
    target_word_id = db.Column(db.Integer, db.ForeignKey('word.id'))
    target_module = db.Column(db.String(30))
    confidence_score = db.Column(db.Float)
    algorithm_version = db.Column(db.String(20))
    recommendation_data = db.Column(db.Text)
    is_accepted = db.Column(db.Boolean)
    actual_choice = db.Column(db.String(100))
    effectiveness_score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ConfusablePair(db.Model):
    __tablename__ = 'confusable_pairs'
    id = db.Column(db.Integer, primary_key=True)
    word1_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)
    word2_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)
    reason = db.Column(db.Text)
    difference = db.Column(db.Text)
    examples = db.Column(db.Text)
    tips = db.Column(db.Text)
    difficulty_level = db.Column(db.Integer, default=1)
    # 辨析题（论文 3.2.4）：JSON 数组 [{stem, options, correct_answer}]，由 scripts/import_hsk4_batches.py 导入
    questions = db.Column(db.Text)
    # 易混淆词（word2）的 HSK 等级：4 是另一个四级词，两个词都要学习期复习完才辨析；空值按一至三级
    word2_level = db.Column(db.Integer)

class ConfusableExerciseRecord(db.Model):
    __tablename__ = 'confusable_exercise_records'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    pair_id = db.Column(db.Integer, db.ForeignKey('confusable_pairs.id'), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    response_time = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # 辨析题的题号（confusable_pairs.questions 里的下标）、作答时那道题的版本号与所选答案，由后端判分。
    # 旧记录为空。版本号由题干、选项、答案算出（confusable_api.question_version）：改过的题以前的作答不再算数
    question_index = db.Column(db.Integer)
    question_version = db.Column(db.String(16))
    user_answer = db.Column(db.String(50))
    # 客户端为每次作答生成的编号；重试沿用同一个，(user_id, attempt_id) 唯一，不会重复记录
    attempt_id = db.Column(db.String(64))

class LearningEvent(db.Model):
    __tablename__ = 'learning_event'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False)
    # 真实列名是 event_target；属性名保留 target，与 models_extended.py 的表结构对齐
    target = db.Column('event_target', db.String(100))
    event_data = db.Column(db.Text)  # JSON string
    page_url = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# 论文表 4.3 的按题型特征列：题型 -> (作答次数列, 答对次数列)
QUESTION_TYPE_PROGRESS_COLUMNS = {
    'definition': ('definition_attempts', 'definition_correct'),
    'collocation': ('collocation_attempts', 'collocation_correct'),
    'fill_word': ('fill_word_attempts', 'fill_word_correct'),
}


def get_or_create_user_progress(user_id, word_id):
    """按 (user_id, word_id) 取进度行，不存在则创建。

    此前生产代码从无一处 INSERT，adaptive_engine 的纯 UPDATE 永远影响 0 行，
    导致论文表 4.3 的「学习次数 / 学习总时长 / 各题型正误」特征全部为空，
    复习调度也因查不到行而恒退化成 new_learning。
    """
    progress = UserProgress.query.filter_by(user_id=user_id, word_id=word_id).first()
    if progress is not None:
        return progress

    progress = UserProgress(
        user_id=user_id,
        word_id=word_id,
        first_studied=datetime.utcnow(),
    )
    db.session.add(progress)
    try:
        db.session.flush()  # 让同一事务内后续的 UPDATE 能看到这一行
    except IntegrityError:
        # 并发请求下另一个事务已插入同一 (user_id, word_id)，回滚后取它的行。
        # 作答接口先 INSERT 作答再来这里，已持写锁，走不到这个分支；若走到，
        # 回滚会连同未提交的作答一起撤掉，由调用方重新写入
        db.session.rollback()
        progress = UserProgress.query.filter_by(user_id=user_id, word_id=word_id).first()
    return progress


def accumulate_exercise_into_progress(user_id, word_id, question_type, is_correct):
    """把一次练习作答累加进 user_progress 的论文特征列。

    连对/连错/掌握度也在这里维护：adaptive_engine 那条 UPDATE 是从
    exercise_result 里取这两个值的，而调用方从来没传过，导致它们被恒写成 0，
    SM-2 的连对加成与连错惩罚两条通路完全失效。
    """
    progress = get_or_create_user_progress(user_id, word_id)
    if progress is None:
        return None

    progress.total_attempts = (progress.total_attempts or 0) + 1
    if is_correct:
        progress.correct_attempts = (progress.correct_attempts or 0) + 1

    columns = QUESTION_TYPE_PROGRESS_COLUMNS.get(question_type)
    if columns:
        attempts_column, correct_column = columns
        setattr(progress, attempts_column, (getattr(progress, attempts_column) or 0) + 1)
        if is_correct:
            setattr(progress, correct_column, (getattr(progress, correct_column) or 0) + 1)

    if is_correct:
        progress.consecutive_correct = (progress.consecutive_correct or 0) + 1
        progress.consecutive_incorrect = 0
    else:
        progress.consecutive_incorrect = (progress.consecutive_incorrect or 0) + 1
        progress.consecutive_correct = 0

    # 掌握度取累计正确率，供 adaptive_engine 的 ease factor 与间隔调节使用
    if progress.total_attempts:
        progress.mastery_level = (progress.correct_attempts or 0) / progress.total_attempts

    progress.last_studied = datetime.utcnow()
    return progress


# ---- 论文表 4.2：复习内容与次数（第四章 4.1 节「自适应规则」）----
# 搭配题、填词题、释义题分别计次；易混淆词辨析题不计。
#   搭配题、填词题：第一次练习答对，按 VKS 档位复习 A/B 5 次、C 4 次、D 3 次、E 2 次；
#                   答错，不论档位复习 6 次（学 1 次 + 复习 6 次 = 论文的「重复 7 次」）。
#   释义题：第一次练习答错复习 6 次，答对不复习（表 4.3 备注）。
#   两道搭配题算一个整体，都对才算对。复习时再答错，次数不变，但复习前先看对应的学习材料。
REVIEW_QUESTION_TYPES = ('definition', 'collocation', 'fill_word')
THESIS_BASE_REVIEWS = {'A': 5, 'B': 5, 'C': 4, 'D': 3, 'E': 2}
# 没有 VKS 自评（如从看板推荐直接开始）时按最保守的档位
DEFAULT_BASE_REVIEWS = 5
REVIEWS_AFTER_WRONG_FIRST_PRACTICE = 6
# 学习期的复习间隔（天）：论文用 2 周完成 2–6 次复习，未规定间隔；6 次复习正好 14 天
LEARNING_PHASE_INTERVALS = (1, 2, 2, 3, 3, 3)
# 复习前要看的学习材料：答错的题型对应的学习页
REVIEW_MATERIAL_MODULE = {'definition': 'word', 'collocation': 'collocation', 'fill_word': 'sentence'}
MODULE_ORDER = ('character', 'word', 'collocation', 'sentence', 'exercise')


def review_target(question_type, all_correct, vks_level):
    """某种题型第一次练习之后要复习几次（表 4.2）"""
    if not all_correct:
        return REVIEWS_AFTER_WRONG_FIRST_PRACTICE
    if question_type == 'definition':
        return 0
    return THESIS_BASE_REVIEWS.get(vks_level, DEFAULT_BASE_REVIEWS)


def question_requirements(word_id):
    """这个词出得了哪些计次的题型，以及一节里每种要答满几道才算练过一次。

    与出题接口的条件一致：有人工命题按命题；否则释义题总有，搭配题要有搭配素材，
    填词题要有包含这个词的例句（第一条）。搭配题按论文两道算一个整体，
    这个词不足两道时以实有的为准；其余题型一道。
    """
    # 没有单字记录的词出题接口直接不出题（见 get_word_exercises），一种题型也出不了
    if Character.query.filter_by(word_id=word_id).first() is None:
        return {}
    authored = dict(db.session.query(ExerciseItem.question_type, func.count(ExerciseItem.id))
                    .filter_by(word_id=word_id).group_by(ExerciseItem.question_type).all())
    if authored:
        counts = {t: n for t, n in authored.items() if t in REVIEW_QUESTION_TYPES}
    else:
        counts = {'definition': 1}
        collocations = Collocation.query.filter_by(word_id=word_id).count()
        if collocations:
            counts['collocation'] = collocations
        example = Example.query.filter_by(word_id=word_id).order_by(Example.id.asc()).first()
        hanzi = get_word_hanzi(word_id)
        if example and hanzi and hanzi in example.sentence:
            counts['fill_word'] = 1
    return {t: (min(2, n) if t == 'collocation' else 1) for t, n in counts.items()}


def review_state(user_id, word_id):
    """从学习会话与作答推出论文表 4.2 的复习进度；这个词还没有作答时返回 None。

    不单独存目标次数，每次都由数据推出：
    - 每种题型的「第一次练习」是第一节含这种题型作答的练习，按它的对错与 VKS 档位定次数。
      第一节没答完、某种题型没答到时，它等到之后第一节答到它的练习再定，不会被当成不复习。
    - VKS 档位取这个词最早带档位的学习会话（任何模块），晚到补写的档位也会被用上。
    - 之后每节练习里，每种还有剩余次数的题型各减 1，不论对错；同一题提交多次只算第一次。
      一节里没有任何还需复习的题型时不算一次复习。
    - 学习期的复习要等到期：上一次进度有变化（定了次数或减了次数）的那节练习，最后一次作答之后
      过了 LEARNING_PHASE_INTERVALS 的间隔，这节练习才算一次复习（与 schedule_review_from_session 排的日程一致）。
      没到期就另开一节练习（同一天连做几节）不减次数，免得一天把两周的复习做完。
    - 每种出得了的题型都定过次数、且都复习完，才算达标。
    已知限制：复习日程（next_review_suggested）只在提交作答时重排。往更早的会话补交作答、
    之后才补写 VKS 档位时，这里推出的次数会变，已排的日程要等下一节练习才跟上；
    前端不会往旧会话补交，补写档位只会把次数调低（没有档位时按最严格的 5 次）。
    """
    rows = (
        db.session.query(LearningSession.id, ExerciseRecord.question_id,
                         ExerciseRecord.question_type, ExerciseRecord.is_correct, ExerciseRecord.created_at)
        .join(ExerciseRecord, ExerciseRecord.session_id == LearningSession.session_id)
        .filter(LearningSession.user_id == user_id, LearningSession.word_id == word_id)
        .order_by(LearningSession.id, ExerciseRecord.id)
        .all()
    )
    if not rows:
        return None
    sessions = {}  # 会话 id → {题目 id: (题型, 对错)}，dict 保持插入顺序即会话先后
    answered_at = {}  # 会话 id → (第一次作答时间, 最后一次作答时间)，按服务器写入时间
    for session_pk, question_id, question_type, is_correct, created_at in rows:
        sessions.setdefault(session_pk, {}).setdefault(question_id, (question_type, bool(is_correct)))
        first, _ = answered_at.get(session_pk, (created_at, None))
        answered_at[session_pk] = (first, created_at)

    level_row = (LearningSession.query
                 .filter(LearningSession.user_id == user_id, LearningSession.word_id == word_id,
                         LearningSession.initial_level.isnot(None))
                 .order_by(LearningSession.id).first())
    vks_level = level_row.initial_level if level_row else None
    required = question_requirements(word_id)
    available = set(required)

    targets, remaining = {}, {}
    reviews_done, after_completion, completed = 0, 0, False
    last_change_session, last_change_at = None, None
    for index, (session_pk, answers) in enumerate(sessions.items()):
        if completed:
            after_completion += 1
            continue
        first_answer, last_answer = answered_at[session_pk]
        due_at = None
        if last_change_at is not None:
            due_at = last_change_at + timedelta(
                days=LEARNING_PHASE_INTERVALS[min(reviews_done, len(LEARNING_PHASE_INTERVALS) - 1)])
        on_schedule = due_at is None or first_answer is None or first_answer >= due_at
        by_type = {}
        for question_type, is_correct in answers.values():
            by_type.setdefault(question_type, []).append(is_correct)
        reviewed = changed = False
        for question_type in REVIEW_QUESTION_TYPES:
            if question_type not in by_type:
                continue
            answers = by_type[question_type]
            # 两道搭配题算一个整体：都答了才算练过；但只要错了一道就已经是「错」
            finished = len(answers) >= required.get(question_type, 1)
            if question_type not in targets:
                if finished or not all(answers):
                    # 这种题型的第一次练习
                    targets[question_type] = review_target(question_type, finished and all(answers), vks_level)
                    remaining[question_type] = targets[question_type]
                    changed = True
            elif remaining[question_type] > 0 and finished and on_schedule:
                remaining[question_type] -= 1
                reviewed = changed = True
        if index > 0 and reviewed:
            reviews_done += 1
        if changed:
            last_change_session, last_change_at = session_pk, last_answer
        # 只看现在还出得了的题型：素材删掉的题型复习不了，剩下的次数不能挡住达标
        completed = available <= set(targets) and not any(remaining.get(t, 0) for t in available)

    last_answers = list(sessions.values())[-1].values()
    return {
        'vks_level': vks_level,
        'targets': targets,
        # 只留现在还出得了的题型
        'remaining': {t: n for t, n in remaining.items() if t in available},
        # 出得了、但还没做过第一次练习的题型
        'pending': sorted(available - set(targets)),
        'reviews_done': reviews_done,
        'after_completion': after_completion,
        'completed': completed,
        'last_wrong_types': sorted({t for t, ok in last_answers if not ok}),
        # 最后一节让进度有变化的练习（LearningSession.id）和它最后一次作答的时间，复习日程从这里排
        'last_change_session': last_change_session,
        'last_change_at': last_change_at,
    }


def remaining_review_types(user_id, word_id):
    """还在学习期的词，返回还要练的题型（还有复习次数的，加上还没做过第一次练习的）；
    没有作答或已达标返回 None"""
    state = review_state(user_id, word_id)
    if state is None or state['completed']:
        return None
    types = {t for t, n in state['remaining'].items() if n > 0} | set(state['pending'])
    return types or None


def word_ready_for_contrast(user_id, word_id, is_target):
    """论文 2.2.4：目标词与易混淆词先分开学，「分别掌握到一定程度后」再对比学习。「一定程度」（作者确定）：
    - 四级词（目标词，以及四级的易混淆词）：学习期复习完（表 4.2 的次数达标，即交给 SM-2 巩固的时候），
      按档位是学后 3–14 天；
    - 一至三级易混淆词：学习者以前学过，学过并复习过一次即可。只有释义题、第一次就答对的词第一次练习就达标，
      所以看实际复习过的节数（学习期的复习加上达标以后的练习），不看是否达标。
    一次请求里同一个词的复习进度只算一次（一个词可能属于好几对）。"""
    cache = g.setdefault('contrast_state', {})
    key = (str(user_id), word_id)
    if key not in cache:
        cache[key] = review_state(user_id, word_id)
    state = cache[key]
    if not state:
        return False
    if is_target:
        return state['completed']
    return state['reviews_done'] + state['after_completion'] >= 1


def contrast_passed(user_id, pair_id, questions):
    """辨析题过关：当前每道题最近一次作答都答对。只认作答时版本号与现在相同的记录（题干、选项、答案都没改过），
    所以题目改过以后要重新作答；重复提交同一题、只做部分题都不算过关。
    已知局限：以记录先后（id）代表作答先后，一轮作答的请求若迟到到下一轮之后才落库，会被当成最近一次。"""
    latest = {}
    rows = (db.session.query(ConfusableExerciseRecord.question_index, ConfusableExerciseRecord.question_version,
                             ConfusableExerciseRecord.is_correct)
            .filter(ConfusableExerciseRecord.user_id == str(user_id), ConfusableExerciseRecord.pair_id == pair_id,
                    ConfusableExerciseRecord.question_index.isnot(None))
            .order_by(ConfusableExerciseRecord.id.desc()).all())
    for index, version, ok in rows:
        if 0 <= index < len(questions) and version == question_version(questions[index]):
            latest.setdefault(index, bool(ok))
    return all(latest.get(i) for i in range(len(questions)))


def confusable_pair_due(user_id, pair_id, word1_id, word2_id, questions, word2_level=None):
    """练习结束时要不要带出这一对的辨析：两个词都 word_ready_for_contrast（word1 是四级目标词、word2 是易混淆词，
    批次导入的词对都是这个顺序；word2_level 为 4 时 word2 也按四级词要求），且这一对还没练过关（contrast_passed）；
    答错的下次练这两个词时再带出。
    没有辨析题的旧词对没有作答可看，解锁后都算到期，但 for-word 接口会优先带出有题、还没过关的词对。
    辨析题不计入论文表 4.2 的复习次数。"""
    if not (word_ready_for_contrast(user_id, word1_id, is_target=True)
            and word_ready_for_contrast(user_id, word2_id, is_target=word2_level == 4)):
        return False
    return not questions or not contrast_passed(user_id, pair_id, questions)


def review_summary(state):
    """给到期列表、推荐用的复习进度：还要复习几节、哪些题型"""
    if state['completed']:
        return {'reviews_remaining': 0, 'review_types': []}
    # 还没做过第一次练习的题型次数未定，至少还要一节；不能显示成已掌握
    return {
        'reviews_remaining': max(list(state['remaining'].values()) + ([1] if state['pending'] else []), default=0),
        'review_types': sorted({t for t, n in state['remaining'].items() if n > 0} | set(state['pending'])),
    }


def review_entry_module(user_id, word_id, state=None):
    """复习从哪个模块开始：上一节练习答错的题型先看对应的学习材料，都对就直接练习。

    这个词还没有作答时返回 None，由调用方沿用原来的规则。
    """
    state = state if state is not None else review_state(user_id, word_id)
    if state is None:
        return None
    modules = [REVIEW_MATERIAL_MODULE[t] for t in state['last_wrong_types'] if t in REVIEW_MATERIAL_MODULE]
    return min(modules, key=MODULE_ORDER.index) if modules else 'exercise'


# 一节练习按多少正确率算「答对」进入下一个复习间隔。三四道题的一节里错一道就不算
# （2/3 < 0.8），明天再复习；题多时允许偶尔失手。
SESSION_PASS_ACCURACY = 0.8


def session_first_answers(session):
    """这节练习的作答，同一道题提交多次（双击、重放）只取第一次"""
    rows = (ExerciseRecord.query.filter_by(session_id=session.session_id)
            .order_by(ExerciseRecord.id).all())
    first_by_question = {}
    for r in rows:
        first_by_question.setdefault(r.question_id, r)
    return list(first_by_question.values())


def score_recommendation_from_session(session):
    """把这节练习的正确率记为它所绑定推荐的效果。

    推荐效果 = 照这条推荐开始学之后，第一节有作答的练习的正确率（同一题只算第一次）。
    用会话上绑定的 recommendation_id 认定「照这条推荐学的」，不靠时间先后推断：
    多台设备、反馈晚到都不影响归属。每题提交后重算，最终是整节的成绩；之后绑定
    同一推荐的练习不再改它。在调用方的事务里运行，由调用方提交。
    """
    if not session.recommendation_id:
        return
    first_answered = (
        db.session.query(func.min(LearningSession.id))
        .join(ExerciseRecord, ExerciseRecord.session_id == LearningSession.session_id)
        .filter(LearningSession.recommendation_id == session.recommendation_id)
        .scalar()
    )
    if first_answered != session.id:
        return
    recommendation = db.session.get(AdaptiveRecommendation, session.recommendation_id)
    records = session_first_answers(session)
    # 已记为没采纳的推荐不计效果（结论以第一次为准，不被之后的会话推翻）
    if recommendation is None or recommendation.is_accepted is False or not records:
        return
    recommendation.effectiveness_score = sum(1 for r in records if r.is_correct) / len(records)


def schedule_review_from_session(session, progress):
    """按这节练习到目前为止的全部作答，重排这个词的下次复习。

    一次「复习」= 一节练习，不是一道题。在调用方的事务里运行、只改 progress 对象，
    由调用方提交：读到的作答与进度和写回的日程是同一时刻的。
    同一道题提交多次（双击、重放）只算第一次。会话先后按自增 id 排：start_time
    来自客户端，可能带时区偏移或相同。这个词已有更新的会话作答时不动：
    往旧会话补交的作答不能覆盖新会话排的日程。
    """
    newer_answered = (
        db.session.query(LearningSession.id)
        .join(ExerciseRecord, ExerciseRecord.session_id == LearningSession.session_id)
        .filter(
            LearningSession.user_id == session.user_id,
            LearningSession.word_id == session.word_id,
            LearningSession.id > session.id,
        )
        .first()
    )
    if newer_answered:
        return False

    records = session_first_answers(session)
    if not records:
        return False

    def mean(values, default):
        values = [v for v in values if v is not None]
        return sum(values) / len(values) if values else default

    accuracy = sum(1 for r in records if r.is_correct) / len(records)
    exercise_result = {
        'is_correct': accuracy >= SESSION_PASS_ACCURACY,
        'response_time': mean([r.response_time_seconds for r in records], 5.0),
        'confidence': mean([r.confidence_level for r in records], 3),
        'hesitation_count': mean([r.hesitation_count for r in records], 0),
    }
    prior_reviews = (
        db.session.query(func.count(func.distinct(LearningSession.session_id)))
        .join(ExerciseRecord, ExerciseRecord.session_id == LearningSession.session_id)
        .filter(
            LearningSession.user_id == session.user_id,
            LearningSession.word_id == session.word_id,
            LearningSession.id < session.id,
        )
        .scalar()
    ) or 0

    # 学习期按论文表 4.2 的次数、以 LEARNING_PHASE_INTERVALS 的间隔复习；
    # 各题型次数都复习完，转入 SM-2 的长间隔巩固
    state = review_state(session.user_id, session.word_id)
    if not state['completed']:
        if state['last_change_session'] != session.id:
            # 这节练习没让进度有变化（一种题型都没答满就退出，或复习还没到期）：日程不动，
            # 免得没做完的词被推后 1–3 天。还没有日程（第一节就没答满）时现在就能接着练
            if progress.next_review_suggested is None:
                progress.next_review_suggested = datetime.utcnow()
                progress.updated_at = datetime.utcnow()
            return False
        if state['pending']:
            # 还有题型没做过第一次练习（这节没做完）：现在就能接着练
            progress.next_review_suggested = state['last_change_at'] or datetime.utcnow()
        else:
            days = LEARNING_PHASE_INTERVALS[min(state['reviews_done'], len(LEARNING_PHASE_INTERVALS) - 1)]
            progress.next_review_suggested = (state['last_change_at'] or datetime.utcnow()) + timedelta(days=days)
    else:
        # 巩固期从 SM-2 的第 3 次复习起算（首个间隔约一周），之后每节逐次拉长
        progress.next_review_suggested = spaced_repetition.engine.next_review_from(
            progress.mastery_level or 0.0,
            2 + state['after_completion'],
            progress.consecutive_correct or 0,
            progress.consecutive_incorrect or 0,
            exercise_result,
        )
    progress.review_count = prior_reviews + 1
    progress.updated_at = datetime.utcnow()
    return True


# 全局推荐引擎实例
recommendation_engine = None
spaced_repetition = None

def get_db_connection():
    """获取数据库连接"""
    return sqlite3.connect(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))

def get_word_hanzi(word_id):
    """由 character 表按顺序拼出词的汉字（word 表没有 hanzi 列）"""
    chars = Character.query.filter_by(word_id=word_id).order_by(Character.id).all()
    return ''.join(c.character for c in chars) if chars else None

def init_recommendation_engine():
    """初始化推荐引擎"""
    global recommendation_engine, spaced_repetition
    
    if AdaptiveRecommendationEngine and SpacedRepetitionAlgorithm:
        try:
            db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
            recommendation_engine = AdaptiveRecommendationEngine(db_path)
            spaced_repetition = SpacedRepetitionAlgorithm(db_path)
            print("✅ 自适应推荐引擎初始化成功")
        except Exception as e:
            print(f"⚠️  推荐引擎初始化失败: {str(e)}")
    else:
        print("⚠️  使用简化版推荐引擎")

# ================================================
# 原有API路由
# ================================================

@app.route('/')
def home():
    return jsonify({
        "message": "第二阶段：自适应学习API",
        "version": "2.0.0",
        "features": [
            "智能推荐引擎",
            "间隔重复算法", 
            "学习分析dashboard",
            "个性化学习路径"
        ],
        "endpoints": [
            "GET  /words - 词汇列表",
            "GET  /word/<id> - 词汇详情",
            "POST /api/learning/session/start - 开始学习会话",
            "POST /api/learning/session/end - 结束学习会话",
            "POST /api/learning/session/initial-level - 补写会话的 VKS 初始档位",
            "POST /api/learning/exercise/record - 记录练习结果",
            "POST /api/learning/events/batch - 批量记录学习事件",
            "GET  /api/adaptive/recommendation/<user_id> - 获取个性化推荐",
            "POST /api/adaptive/feedback - 记录推荐反馈",
            "GET  /api/review/user/<user_id>/due - 获取到期复习内容",
            "GET  /api/analytics/user/<user_id>/dashboard - 获取学习dashboard",
            "GET  /api/stats - 系统统计"
        ]
    })

@app.route('/word/<int:id>', methods=['GET'])
def get_word(id):
    word = Word.query.get_or_404(id)
    examples = Example.query.filter_by(word_id=id).all()
    collocations = Collocation.query.filter_by(word_id=id).all()
    characters = Character.query.filter_by(word_id=id).all()
    
    hanzi = ''.join([char.character for char in characters]) if characters else None

    word_data = {
        'id': word.id,
        'pinyin': word.pinyin,
        'definition': word.definition,
        'hanzi': hanzi,
        'audio': word.audio or '',
        'examples': [
            {
                'sentence': ex.sentence,
                'pinyin': ex.pinyin,
                'translation': ex.translation,
                'audio': ex.audio
            }
            for ex in examples
        ],
        'collocations': [
            {
                'collocation': col.collocation,
                'translation': col.translation,
                'audio': col.audio
            }
            for col in collocations
        ],
        'characters': [
            {
                'character': char.character,
                'pinyin': char.pinyin,
                'definition': char.definition,
                'audio': char.audio
            }
            for char in characters
        ]
    }
    return jsonify(word_data)

# 发音音频：学习资料制作第 8 步用 Azure 语音生成的 mp3，文件名是内容指纹。不提交（含教材例句的朗读），
# 部署时连同批次素材复制到服务器。库里只存地址，文件按地址从这里读
AUDIO_DIR = os.path.join(basedir, 'data', 'learning_materials', 'audio')
AUDIO_NAME = re.compile(r'^[0-9a-f]{16}\.mp3$')


@app.route('/api/audio/<name>', methods=['GET'])
def get_audio(name):
    """内容指纹作文件名，内容变了文件名就变：浏览器可以长期缓存。只认指纹格式的文件名，读不到目录外的文件"""
    if not AUDIO_NAME.match(name):
        return jsonify({'success': False, 'error': 'Not found'}), 404
    return send_from_directory(AUDIO_DIR, name, mimetype='audio/mpeg', max_age=365 * 24 * 3600)


@app.route('/words', methods=['GET'])
def list_words():
    words = Word.query.all()
    # 汉字由 character 表按插入顺序拼接（word 表历史上没有 hanzi 列）
    hanzi_map = {}
    for char in Character.query.order_by(Character.id).all():
        hanzi_map[char.word_id] = hanzi_map.get(char.word_id, '') + char.character
    words_data = [
        {'id': word.id, 'hanzi': hanzi_map.get(word.id), 'pinyin': word.pinyin, 'definition': word.definition}
        for word in words
    ]
    return jsonify(words_data)

@app.route('/exercise/submit', methods=['POST'])
def submit_exercise():
    data = request.get_json()
    answer = data.get('answer')
    correct_answer = 'D'
    return jsonify({'correct': answer == correct_answer})

# ================================================
# 第一阶段时间追踪API
# ================================================

@app.route('/api/learning/session/start', methods=['POST'])
@require_authentication(allow_url_param=True)
def start_learning_session(current_user_id=None, **kwargs):
    try:
        data = request.get_json()
        
        # 验证权限：确保用户只能为自己创建会话
        request_user_id = data.get('userId')
        if request_user_id and request_user_id != current_user_id:
            return jsonify({
                'success': False,
                'error': 'You can only create your own sessions',
                'code': 'PERMISSION_DENIED'
            }), 403
        
        # 照推荐开始学的会话绑定那条推荐。只认自己的、针对这个词的推荐；
        # 对不上就当没有，不拒绝建会话
        recommendation = None
        rec_id = data.get('recommendationId')
        if type(rec_id) is int:
            recommendation = db.session.get(AdaptiveRecommendation, rec_id)
            if (recommendation is None or recommendation.user_id != current_user_id
                    or recommendation.target_word_id != data['wordId']):
                recommendation = None

        # 使用认证的用户ID
        session = LearningSession(
            session_id=data['sessionId'],
            user_id=current_user_id,  # 使用认证的用户ID
            word_id=data['wordId'],
            session_type=data['sessionType'],
            module_type=data['moduleType'],
            initial_level=data.get('initialLevel'),
            start_time=datetime.fromisoformat(data['startTime'].replace('Z', '+00:00')),
            device_type=data.get('deviceType', 'web'),
            recommendation_id=recommendation.id if recommendation else None,
        )
        
        db.session.add(session)
        # 照推荐建了会话就是采纳了：前端的反馈请求不等待，可能晚到或丢失，这里补上。
        # 条件更新，已有结论（含同时到达的「没采纳」）不改，与反馈接口「第一次为准」一致
        if recommendation is not None:
            AdaptiveRecommendation.query.filter(
                AdaptiveRecommendation.id == recommendation.id,
                AdaptiveRecommendation.is_accepted.is_(None),
            ).update({'is_accepted': True, 'actual_choice': f"{data['moduleType']}:{data['wordId']}"},
                     synchronize_session=False)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'sessionId': data['sessionId'],
            'message': 'Session started successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/learning/session/end', methods=['POST'])
@require_authentication(allow_url_param=True)
def end_learning_session(current_user_id=None, **kwargs):
    try:
        data = request.get_json()
        
        session = LearningSession.query.filter_by(session_id=data['sessionId']).first()
        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        # 验证权限：只能结束自己的会话
        if session.user_id != current_user_id:
            return jsonify({
                'success': False,
                'error': 'You can only end your own sessions',
                'code': 'PERMISSION_DENIED'
            }), 403
        
        session.end_time = datetime.fromisoformat(data['endTime'].replace('Z', '+00:00'))
        session.duration_seconds = data['durationSeconds']
        session.active_time_seconds = data.get('activeTimeSeconds')
        session.completed = data.get('completed', True)
        session.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Session ended successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/learning/session/initial-level', methods=['POST'])
@require_authentication(allow_url_param=True)
def set_session_initial_level(current_user_id=None, **kwargs):
    """给已建好的会话补上 VKS 初始档位。

    追踪器在会话状态从 localStorage 读出时就建会话；本地没有这个词的档位、
    服务器上有（换了设备）时，档位要等服务器状态返回才知道，会话已带着空档位建好。
    只在 initial_level 仍为空时写：它是「开始学这个词时」的自评，不随之后的改动覆盖。
    """
    data = request.get_json(silent=True) or {}
    level = data.get('initialLevel')
    if level not in ('A', 'B', 'C', 'D', 'E'):
        return jsonify({'success': False, 'error': 'initialLevel must be A–E'}), 400

    session = LearningSession.query.filter_by(session_id=data.get('sessionId')).first()
    if session is None:
        return jsonify({'success': False, 'error': 'Session not found', 'code': 'SESSION_NOT_FOUND'}), 404
    if session.user_id != current_user_id:
        return jsonify({
            'success': False,
            'error': 'You can only change your own sessions',
            'code': 'PERMISSION_DENIED'
        }), 403

    try:
        updated = LearningSession.query.filter(
            LearningSession.session_id == session.session_id,
            LearningSession.initial_level.is_(None),
        ).update({'initial_level': level, 'updated_at': datetime.utcnow()}, synchronize_session=False)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    return jsonify({'success': True, 'updated': bool(updated)})


@app.route('/api/learning/exercise/record', methods=['POST'])
@require_authentication(allow_url_param=True)
def record_exercise_result(current_user_id=None, **kwargs):
    try:
        data = request.get_json()
        
        # 验证权限：检查session是否属于当前用户
        session = LearningSession.query.filter_by(session_id=data['sessionId']).first()
        # 会话不存在不能当作「通过」：否则任何身份都能往编造的会话里写作答，
        # 也会掩盖会话没建成、作答却「保存成功」的情况
        if session is None:
            return jsonify({
                'success': False,
                'error': 'Session not found',
                'code': 'SESSION_NOT_FOUND'
            }), 404
        if session.user_id != current_user_id:
            return jsonify({
                'success': False,
                'error': 'You can only record answers in your own sessions',
                'code': 'PERMISSION_DENIED'
            }), 403
        
        record_fields = dict(
            session_id=data['sessionId'],
            question_id=data['questionId'],
            question_type=data['questionType'],
            question_content=data.get('questionContent'),
            user_answer=data['userAnswer'],
            correct_answer=data['correctAnswer'],
            is_correct=data['isCorrect'],
            confidence_level=data.get('confidenceLevel'),
            question_start_time=datetime.fromisoformat(data['startTime'].replace('Z', '+00:00')),
            question_end_time=datetime.fromisoformat(data['endTime'].replace('Z', '+00:00')),
            response_time_seconds=data.get('responseTimeSeconds'),
            hesitation_count=data.get('hesitationCount', 0),
            attempt_count=data.get('attemptCount', 1),
            is_first_attempt=data.get('isFirstAttempt', True)
        )
        exercise = ExerciseRecord(**record_fields)
        
        # 作答、进度累加、复习调度在同一个事务里，且第一条语句就是这条 INSERT：
        # SQLite 从这里起持有写锁直到提交，同一用户的并发提交只能排队，后到的请求
        # 读到的是先到者提交后的作答与进度，不会拿旧值覆盖新日程。
        db.session.add(exercise)
        db.session.flush()

        # 同一会话里这道题已经交过（双击、重放）：只留原始记录，不再累加进度、不重排日程
        is_replay = ExerciseRecord.query.filter(
            ExerciseRecord.session_id == data['sessionId'],
            ExerciseRecord.question_id == data['questionId'],
            ExerciseRecord.id < exercise.id,
        ).first() is not None

        if not is_replay:
            try:
                # 累加论文表 4.3 的特征列
                progress = accumulate_exercise_into_progress(
                    session.user_id,
                    session.word_id,
                    data['questionType'],
                    bool(data['isCorrect']),
                )
                if progress is not None and spaced_repetition:
                    schedule_review_from_session(session, progress)
                score_recommendation_from_session(session)
            except Exception as e:
                db.session.rollback()
                print(f"⚠️  用户进度或间隔重复更新失败: {str(e)}")

        # 进度或调度出错（含 get_or_create_user_progress 的回滚）不能连累作答本身：
        # 回滚撤掉了这次的进度改动，作答本身重新写入
        if exercise not in db.session:
            db.session.add(ExerciseRecord(**record_fields))
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Exercise recorded successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/learning/events/batch', methods=['POST'])
@require_authentication(allow_url_param=True)
def record_batch_events(current_user_id=None, **kwargs):
    """批量记录学习事件（页面停留、点击、音频播放等）"""
    try:
        data = request.get_json()
        session_id = data.get('sessionId')
        events = data.get('events', [])
        
        if not session_id:
            return jsonify({'success': False, 'error': 'sessionId is required'}), 400

        # 此前不认证也不查归属：知道 sessionId 就能往别人的会话里写伪造事件，
        # 编一个不存在的 sessionId 也能写进孤立事件
        session = LearningSession.query.filter_by(session_id=session_id).first()
        if session is None:
            return jsonify({'success': False, 'error': 'Session not found', 'code': 'SESSION_NOT_FOUND'}), 404
        if session.user_id != current_user_id:
            return jsonify({'success': False, 'error': 'You can only record events in your own sessions', 'code': 'PERMISSION_DENIED'}), 403
        
        if not events:
            return jsonify({'success': True, 'message': 'No events to record', 'count': 0})
        
        recorded_count = 0
        for event in events:
            try:
                timestamp_str = event.get('timestamp', '')
                if isinstance(timestamp_str, str) and timestamp_str:
                    try:
                        event_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        event_time = datetime.utcnow()
                else:
                    event_time = datetime.utcnow()
                
                learning_event = LearningEvent(
                    session_id=session_id,
                    event_type=event.get('type', 'unknown'),
                    target=event.get('target'),
                    event_data=json.dumps(event.get('data')) if event.get('data') else None,
                    page_url=event.get('pageUrl'),
                    timestamp=event_time
                )
                db.session.add(learning_event)
                recorded_count += 1
            except Exception as e:
                print(f"⚠️  跳过无效事件: {str(e)}")
                continue
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Recorded {recorded_count} events',
            'count': recorded_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/learning/word/<int:word_id>/exercises', methods=['GET'])
def get_word_exercises(word_id):
    """为指定词汇生成练习题集"""
    word = db.session.get(Word, word_id)
    if not word:
        return jsonify({'success': False, 'error': 'Word not found'}), 404

    try:
        question_limit = max(1, min(int(request.args.get('limit', 5)), 10))
    except (TypeError, ValueError):
        question_limit = 5

    try:
        desired_option_count = max(2, min(int(request.args.get('options', 4)), 6))
    except (TypeError, ValueError):
        desired_option_count = 4

    def get_word_hanzi(w):
        chars = Character.query.filter_by(word_id=w.id).order_by(Character.id.asc()).all()
        return ''.join([c.character for c in chars]) if chars else w.pinyin

    base_hanzi = get_word_hanzi(word)

    # 没有 character 行的词，get_word_hanzi 会回退到 pinyin 列，正确答案就成了
    # 'fāshēng'、'突然 tūrán' 这类畸形串。干扰项已被过滤成纯汉字，正确答案反而
    # 变成唯一的「拼音格式」异类——学习者不用认词、只看格式就能选中。
    # 这类词（id 2..15）本来也进不了推荐链路，直接不出题。
    if Character.query.filter_by(word_id=word.id).count() == 0:
        return jsonify({
            'success': False,
            'error': 'No exercises available for this word'
        }), 404

    # 学习期的复习只出还需复习的题型（论文表 4.2）。出题接口不要求登录，认得出身份
    # （登录或访客 cookie）且这个词有未完成的复习计划时才筛选
    review_types = None
    try:
        viewer_id, _ = get_current_user_from_request()
        if viewer_id:
            review_types = remaining_review_types(viewer_id, word.id)
    except Exception as e:
        print(f"⚠️  读取复习计划失败: {e}")

    # 优先使用论文课件里的人工命题：干扰项经过教学设计，
    # 填词题挖的也是词中一个字。查不到才回落到下面的程序生成逻辑。
    authored = (
        ExerciseItem.query.filter_by(word_id=word.id)
        .order_by(ExerciseItem.question_type.desc(), ExerciseItem.id.asc())
        .all()
    )
    if review_types:
        authored = [it for it in authored if it.question_type in review_types] or authored
    if authored:
        type_order = {'definition': 0, 'collocation': 1, 'fill_word': 2}
        sort_key = lambda it: (type_order.get(it.question_type, 9), it.id)
        authored.sort(key=sort_key)
        # 先保证每种题型至少一道，再按原顺序补满。直接截断会让题多的词
        # （如「感觉」8 道、「当」7 道）永远排不到排在最后的填词题。
        selected, seen_types = [], set()
        for item in authored:
            if item.question_type not in seen_types:
                seen_types.add(item.question_type)
                selected.append(item)
        for item in authored:
            if item not in selected:
                selected.append(item)
        selected = sorted(selected[:question_limit], key=sort_key)
        questions = []
        for index, item in enumerate(selected, start=1):
            options = json.loads(item.options_json) if item.options_json else []
            questions.append({
                'id': f'authored-{item.id}',
                'type': item.question_type,
                'question': item.stem,
                'options': options,
                'correctAnswer': item.correct_answer,
                'feedback': f"正确答案：{item.correct_answer}（选自{item.source_deck}）"
            })
        return jsonify({
            'success': True,
            'data': {
                'wordId': word.id,
                'word': base_hanzi,
                'definition': word.definition,
                'questions': questions,
                'source': 'authored',
                'reviewTypes': sorted(review_types) if review_types else None
            }
        })

    def build_options():
        candidates = {base_hanzi}
        # 只从「有 character 行」的词里抽干扰项。无素材的词 get_word_hanzi 会回退到
        # pinyin 列，渲染出 'fāshēng'、'突然 tūrán' 这类畸形选项，格式上一眼就不是
        # 答案，会把四选一退化成二三选一，损害测量效度。
        words_with_chars = db.session.query(Character.word_id).distinct()
        random_candidates = (
            Word.query.filter(Word.id != word.id, Word.id.in_(words_with_chars))
            .order_by(db.func.random())
            .limit(desired_option_count * 2)
            .all()
        )
        for candidate in random_candidates:
            cand_hanzi = get_word_hanzi(candidate)
            if cand_hanzi:
                candidates.add(cand_hanzi)
            if len(candidates) >= desired_option_count:
                break

        option_list = list(candidates)
        random.shuffle(option_list)
        return option_list[:desired_option_count]

    options = build_options()
    questions = []

    # 释义题的干扰项优先放易混淆词对里的「搭档」（以为↔认为、因为↔所以）：论文原题的
    # 干扰项特意选形近、义近的词，随机抽来的词一眼就能排除。英文释义能区分两者，
    # 所以只用在释义题；搭配题不放——「还 ( )」填以为、认为都通，会出成歧义题。
    definition_options = list(options)
    partner = db.session.execute(text("""
        SELECT CASE WHEN word1_id = :wid THEN word2_id ELSE word1_id END
        FROM confusable_pairs WHERE word1_id = :wid OR word2_id = :wid
        ORDER BY id LIMIT 1
    """), {'wid': word.id}).scalar()
    partner_word = Word.query.get(partner) if partner else None
    partner_hanzi = get_word_hanzi(partner_word) if partner_word else None
    if (partner_hanzi and partner_hanzi != base_hanzi and partner_hanzi not in definition_options
            and Character.query.filter_by(word_id=partner).count() > 0):
        distractors = [o for o in definition_options if o != base_hanzi]
        if distractors:
            definition_options[definition_options.index(distractors[0])] = partner_hanzi
            random.shuffle(definition_options)

    questions.append({
        'id': f'definition-{word.id}',
        'type': 'definition',
        'question': word.definition,
        'options': definition_options,
        'correctAnswer': base_hanzi,
        'feedback': f"正确答案：{base_hanzi}。释义：{word.definition}"
    })

    # 先生成全部候选，按复习题型筛选后再截到题数上限：边生成边截断时搭配多的词
    # 永远轮不到填词题，复习要练填词也出不来。普通练习截出来的仍是原来的顺序与题目
    collocations = (
        Collocation.query.filter_by(word_id=word.id)
        .order_by(Collocation.id.asc())
        .all()
    )
    for index, collocation in enumerate(collocations, start=1):
        placeholder = collocation.collocation.replace(base_hanzi, ' ( ) ')
        if placeholder == collocation.collocation:
            placeholder = collocation.collocation
        questions.append({
            'id': f'collocation-{word.id}-{index}',
            'type': 'collocation',
            'question': placeholder,
            'options': options,
            'correctAnswer': base_hanzi,
            'feedback': f"原搭配：{collocation.collocation}；翻译：{collocation.translation}"
        })

    example = (
        Example.query.filter_by(word_id=word.id)
        .order_by(Example.id.asc())
        .first()
    )
    if example:
        # 论文题型规格：填词题挖掉词中的「一个字」而非整词（对照 word 1 的原型题
        # '不愿意发 ( ) 的事情终于出现了。' -> 答案 '生'）。挖整词会把「单字填空」
        # 退化成「整词书写」，与 §6.3 的填词题习得分析不符。
        word_chars = (
            Character.query.filter_by(word_id=word.id)
            .order_by(Character.id.asc())
            .all()
        )
        if word_chars:
            blanked_char = word_chars[-1].character
            kept_prefix = ''.join(c.character for c in word_chars[:-1])
        else:
            blanked_char = base_hanzi
            kept_prefix = ''

        sentence_placeholder = example.sentence.replace(
            base_hanzi, f'{kept_prefix} ( ) ', 1
        )
        # 例句里找不到该词形时无法挖空，宁可不出这道题，也不要出一道
        # 无处填写、学习者必然答错的题去污染正确率数据。
        if sentence_placeholder != example.sentence:
            questions.append({
                'id': f'sentence-{word.id}-1',
                'type': 'fill_word',
                'question': sentence_placeholder,
                'options': [],
                'correctAnswer': blanked_char,
                'feedback': f"例句：{example.sentence}；翻译：{example.translation}"
            })
        else:
            print(f"⚠️  词 {word.id}（{base_hanzi}）的例句不含该词形，跳过填词题")

    if review_types:
        questions = [q for q in questions if q['type'] in review_types] or questions
    questions = questions[:question_limit]

    if not questions:
        return jsonify({'success': False, 'error': 'No exercises available for this word'}), 404

    return jsonify({
        'success': True,
        'data': {
            'wordId': word.id,
            'word': base_hanzi,
            'definition': word.definition,
            'options': options,
            'questionCount': len(questions),
            'questions': questions,
            'reviewTypes': sorted(review_types) if review_types else None
        }
    })


@app.route('/api/users', methods=['GET'])
def get_users():
    """获取用户列表，可选搜索与限制数量（仅开发期的 UserSwitcher 使用）"""
    # 生产环境不公开全部用户
    if not user_id_param_allowed():
        return jsonify({'success': False, 'error': 'Not found'}), 404
    try:
        try:
            limit = int(request.args.get('limit', 50))
        except (TypeError, ValueError):
            limit = 50
        limit = max(1, min(limit, 200))

        search = (request.args.get('search') or '').strip()

        query = UserProfile.query
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                (UserProfile.user_id.ilike(pattern)) |
                (UserProfile.username.ilike(pattern))
            )

        users = query.order_by(UserProfile.created_at.desc()).limit(limit).all()
        user_ids = [user.user_id for user in users]

        progress_map: dict[str, dict[str, object]] = {}
        if user_ids:
            progress_rows = (
                db.session.query(
                    UserProgress.user_id,
                    func.count(UserProgress.word_id).label('words_studied'),
                    func.max(UserProgress.last_studied).label('last_studied')
                )
                .filter(UserProgress.user_id.in_(user_ids))
                .group_by(UserProgress.user_id)
                .all()
            )
            for row in progress_rows:
                progress_map[row.user_id] = {
                    'wordsStudied': int(row.words_studied or 0),
                    'lastStudied': row.last_studied.isoformat() if row.last_studied else None
                }

        last_session_map: dict[str, dict[str, object]] = {}
        if user_ids:
            last_session_subquery = (
                db.session.query(
                    LearningSession.user_id.label('user_id'),
                    func.max(LearningSession.start_time).label('last_start')
                )
                .filter(LearningSession.user_id.in_(user_ids))
                .group_by(LearningSession.user_id)
                .subquery()
            )

            last_sessions = (
                db.session.query(
                    LearningSession.user_id,
                    LearningSession.word_id,
                    LearningSession.module_type,
                    LearningSession.session_type,
                    LearningSession.start_time,
                    Word.pinyin.label('word')
                )
                .join(last_session_subquery, (
                    (LearningSession.user_id == last_session_subquery.c.user_id) &
                    (LearningSession.start_time == last_session_subquery.c.last_start)
                ))
                .outerjoin(Word, Word.id == LearningSession.word_id)
                .all()
            )

            for row in last_sessions:
                last_session_map[row.user_id] = {
                    'wordId': row.word_id,
                    'word': row.word,
                    'moduleType': row.module_type,
                    'sessionType': row.session_type,
                    'startedAt': row.start_time.isoformat() if row.start_time else None
                }

        data = []
        for user in users:
            metrics = progress_map.get(user.user_id, {})
            data.append({
                'userId': user.user_id,
                'username': user.username,
                'languageLevel': user.language_level,
                'nativeLanguage': user.native_language,
                'createdAt': user.created_at.isoformat() if user.created_at else None,
                'updatedAt': user.updated_at.isoformat() if user.updated_at else None,
                'wordsStudied': metrics.get('wordsStudied', 0),
                'lastStudied': metrics.get('lastStudied'),
                'lastSession': last_session_map.get(user.user_id)
            })

        return jsonify({'success': True, 'data': data})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/users/<user_id>/sessions/recent', methods=['GET'])
@require_authentication(allow_url_param=True)
def get_recent_sessions(user_id, current_user_id=None, **kwargs):
    """获取指定用户最近的学习会话列表"""
    try:
        # 验证权限：用户只能查看自己的会话
        if user_id != current_user_id:
            return jsonify({
                'success': False,
                'error': 'You can only access your own data',
                'code': 'PERMISSION_DENIED'
            }), 403
        
        try:
            limit = int(request.args.get('limit', 10))
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, 50))

        sessions = (
            db.session.query(
                LearningSession.session_id,
                LearningSession.word_id,
                LearningSession.module_type,
                LearningSession.session_type,
                LearningSession.start_time,
                LearningSession.end_time,
                LearningSession.duration_seconds,
                Word.pinyin.label('word')
            )
            .outerjoin(Word, Word.id == LearningSession.word_id)
            .filter(LearningSession.user_id == user_id)
            .order_by(LearningSession.start_time.desc())
            .limit(limit)
            .all()
        )

        data = []
        for item in sessions:
            data.append({
                'sessionId': item.session_id,
                'wordId': item.word_id,
                'word': item.word,
                'moduleType': item.module_type,
                'sessionType': item.session_type,
                'startTime': item.start_time.isoformat() if item.start_time else None,
                'endTime': item.end_time.isoformat() if item.end_time else None,
                'durationSeconds': item.duration_seconds
            })

        return jsonify({'success': True, 'data': data})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


# ================================================
# 学习状态持久化API（跨设备恢复）
# ================================================

@app.route('/api/users/<user_id>/learning-state', methods=['GET'])
@require_authentication(allow_url_param=True)
def get_learning_state(user_id, current_user_id=None, **kwargs):
    """获取用户当前学习状态（用于跨设备恢复）"""
    if user_id != current_user_id:
        return jsonify({'success': False, 'error': 'You can only access your own data', 'code': 'PERMISSION_DENIED'}), 403
    try:
        profile = UserProfile.query.filter_by(user_id=user_id).first()
        if not profile:
            return jsonify({
                'success': True,
                'data': {'wordId': None, 'word': None, 'module': None, 'vksLevel': None,
                         'recommendationId': None, 'lastUpdated': None}
            })
        
        return jsonify({
            'success': True,
            'data': {
                'wordId': profile.current_word_id,
                'word': profile.current_word,
                'module': profile.current_module,
                'vksLevel': profile.current_vks_level,
                'recommendationId': profile.current_recommendation_id,
                # updated_at 存的是不带时区的 UTC；不标时区的话浏览器按本地时间解析，
                # 东八区会把服务器状态看早 8 小时，另一台设备 8 小时内的进度恢复不过来
                'lastUpdated': profile.updated_at.replace(tzinfo=timezone.utc).isoformat() if profile.updated_at else None
            }
        })
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/users/<user_id>/learning-state', methods=['PUT'])
@require_authentication(allow_url_param=True)
def save_learning_state(user_id, current_user_id=None, **kwargs):
    """保存用户当前学习状态（跨设备持久化）"""
    if user_id != current_user_id:
        return jsonify({'success': False, 'error': 'You can only change your own data', 'code': 'PERMISSION_DENIED'}), 403
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        profile = UserProfile.query.filter_by(user_id=user_id).first()
        if not profile:
            # 自动创建用户 profile
            profile = UserProfile(user_id=user_id)
            db.session.add(profile)
        
        if 'wordId' in data:
            profile.current_word_id = data['wordId']
        if 'word' in data:
            profile.current_word = data['word']
        if 'module' in data:
            profile.current_module = data['module']
        if 'vksLevel' in data:
            profile.current_vks_level = data['vksLevel']
        # 缺这个字段也当作「没有」：现在的前端每次都带，不带的是部署前还开着的旧页面，
        # 它从今日复习等入口重新开始时不会清掉，沿用会把无关的学习记到旧推荐上。
        # 只存整数；是否属于本人、是否针对这个词，在建学习会话绑定时再校验
        rec_id = data.get('recommendationId')
        profile.current_recommendation_id = rec_id if type(rec_id) is int else None
        
        profile.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Learning state saved successfully'
        })
    except Exception as exc:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(exc)}), 500


# ================================================
# 第二阶段自适应推荐API
# ================================================

@app.route('/api/adaptive/recommendation/<user_id>', methods=['GET'])
@require_authentication(allow_url_param=True)
def get_adaptive_recommendation(user_id, current_user_id=None, **kwargs):
    """获取个性化推荐"""
    try:
        # 验证权限：用户只能获取自己的推荐
        if user_id != current_user_id:
            return jsonify({
                'success': False,
                'error': 'You can only access your own data',
                'code': 'PERMISSION_DENIED'
            }), 403
        
        # 获取上下文参数
        context = {}
        if request.args.get('context'):
            try:
                context = json.loads(request.args.get('context'))
            except:
                pass
        
        # 使用推荐引擎获取推荐
        if recommendation_engine:
            recommendation = recommendation_engine.get_next_recommendation(user_id, context)
            
            # 引擎返回的 word 字段是 pinyin 列，展示时换成汉字
            if recommendation.get('word_id'):
                hanzi = get_word_hanzi(recommendation['word_id'])
                if hanzi:
                    recommendation['word'] = hanzi

            # 推荐的是复习：按论文规则决定入口（上一节答错的题型先看学习材料），并带上复习进度。
            # 复习入口优先于下面按 VKS 档位分配的入口：VKS 决定的是新学一个词从哪里开始
            review_entry = None
            if recommendation.get('type') in ('urgent_review', 'scheduled_review') and recommendation.get('word_id'):
                state = review_state(user_id, recommendation['word_id'])
                if state is not None:
                    review_entry = review_entry_module(user_id, recommendation['word_id'], state)
                    recommendation['recommended_module'] = review_entry
                    recommendation.update(review_summary(state))

            # 根据 VKS 测试选项动态分配入口
            vks_level = context.get('vks_level') if context else None
            if vks_level and not review_entry:
                vks_modules = {
                    'A': 'character',
                    'B': 'word',
                    'C': 'collocation',
                    'D': 'sentence',
                    'E': 'exercise'
                }
                recommendation['recommended_module'] = vks_modules.get(vks_level, 'word')
            elif recommendation.get('recommended_module') is None and recommendation.get('word_id'):
                recommendation['recommended_module'] = 'word'

            # 保存推荐记录。暂无任务（all_caught_up，没有词）不算一次推荐，不记
            recommendation['recommendationId'] = (recommendation_engine.save_recommendation(user_id, recommendation)
                                                  if recommendation.get('word_id') else None)
        else:
            # 简化版推荐
            recommendation = get_simple_recommendation(user_id, context)
        
        return jsonify({
            'success': True,
            'data': recommendation
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/adaptive/feedback', methods=['POST'])
@require_authentication(allow_url_param=True)
def record_recommendation_feedback(current_user_id=None, **kwargs):
    """记录用户有没有照推荐去学。

    accepted：照推荐开始学了（true），或推荐显示着却选了别的（false）。
    actualChoice：实际去学的，如 'word:17'、'today-review'。
    以第一次上报为准：同一条推荐重复上报（重放、先后两个入口）不改已有结论。
    推荐效果 effectiveness_score 不由前端给，见 score_recommendation_from_session。
    """
    data = request.get_json(silent=True) or {}

    feedback_user_id = data.get('userId')
    if feedback_user_id and feedback_user_id != current_user_id:
        return jsonify({
            'success': False,
            'error': 'You can only give feedback on your own recommendations',
            'code': 'PERMISSION_DENIED'
        }), 403

    accepted = data.get('accepted')
    actual_choice = data.get('actualChoice')
    # type(...) is int：bool 是 int 的子类，isinstance 会放过 recommendationId: true
    if not isinstance(accepted, bool) or type(data.get('recommendationId')) is not int:
        return jsonify({'success': False, 'error': 'recommendationId (integer) and accepted (boolean) are required'}), 400
    if actual_choice is not None and (not isinstance(actual_choice, str) or len(actual_choice) > 100):
        return jsonify({'success': False, 'error': 'actualChoice must be a string of at most 100 characters'}), 400

    rec = db.session.get(AdaptiveRecommendation, data['recommendationId'])
    if rec is None or rec.user_id != current_user_id:
        # 别人的推荐也按「不存在」答，不暴露 id 是否有效
        return jsonify({'success': False, 'error': 'Recommendation not found'}), 404

    try:
        updated = AdaptiveRecommendation.query.filter(
            AdaptiveRecommendation.id == rec.id,
            AdaptiveRecommendation.is_accepted.is_(None),
        ).update({'is_accepted': accepted, 'actual_choice': actual_choice}, synchronize_session=False)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    return jsonify({'success': True, 'updated': bool(updated)})

@app.route('/api/review/user/<user_id>/due', methods=['GET'])
@require_authentication(allow_url_param=True)
def get_due_reviews(user_id, current_user_id=None, **kwargs):
    """获取到期复习内容"""
    try:
        # 验证权限：用户只能查看自己的复习
        if user_id != current_user_id:
            return jsonify({
                'success': False,
                'error': 'You can only access your own data',
                'code': 'PERMISSION_DENIED'
            }), 403
        
        limit = int(request.args.get('limit', 10))
        
        if spaced_repetition:
            reviews = spaced_repetition.get_due_reviews(user_id, limit)
        else:
            reviews = get_simple_due_reviews(user_id, limit)

        # 有复习计划的词按论文规则：上一节答错的题型先看对应学习材料，并带上还剩几次
        for review in reviews:
            state = review_state(user_id, review['word_id'])
            if state is None:
                continue
            review['recommended_module'] = review_entry_module(user_id, review['word_id'], state)
            review.update(review_summary(state))
        
        return jsonify({
            'success': True,
            'data': reviews
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/user/<user_id>/dashboard', methods=['GET'])
@require_authentication(allow_url_param=True)
def get_user_dashboard(user_id, current_user_id=None, **kwargs):
    """获取用户学习dashboard数据"""
    try:
        # 验证权限：用户只能查看自己的Dashboard
        if user_id != current_user_id:
            return jsonify({
                'success': False,
                'error': 'You can only access your own data',
                'code': 'PERMISSION_DENIED'
            }), 403
        
        time_range = request.args.get('range', 'month')  # week, month, all
        
        dashboard_data = generate_dashboard_data(user_id, time_range)
        
        return jsonify({
            'success': True,
            'data': dashboard_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/user/<user_id>/progress', methods=['GET'])
@require_authentication(allow_url_param=True)
def get_user_detailed_progress(user_id, current_user_id=None, **kwargs):
    """获取用户详细学习进度"""
    try:
        # 验证权限：用户只能查看自己的进度
        if user_id != current_user_id:
            return jsonify({
                'success': False,
                'error': 'You can only access your own data',
                'code': 'PERMISSION_DENIED'
            }), 403
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 获取用户进度列表
        cursor.execute("""
            SELECT up.word_id, w.pinyin, up.mastery_level, up.confidence_score,
                   up.total_study_time_seconds, up.total_sessions, up.total_attempts, up.correct_attempts,
                   up.last_studied, up.next_review_suggested, up.learning_efficiency
            FROM user_progress up
            JOIN word w ON up.word_id = w.id
            WHERE up.user_id = ?
            ORDER BY up.mastery_level DESC, up.last_studied DESC
        """, (user_id,))
        
        results = cursor.fetchall()
        progress_list = []
        
        for result in results:
            word_id, pinyin, mastery_level, confidence_score, total_time, sessions, attempts, correct, last_studied, next_review, efficiency = result
            
            progress_list.append({
                'wordId': word_id,
                'word': pinyin,
                'masteryLevel': mastery_level,
                'confidenceScore': confidence_score,
                'totalStudyTime': total_time,
                'totalSessions': sessions,
                'accuracyRate': correct / max(attempts, 1),
                'lastStudied': last_studied,
                'nextReview': next_review,
                'learningEfficiency': efficiency
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': progress_list
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_system_stats():
    """获取系统统计信息"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 基础统计
        cursor.execute("SELECT COUNT(*) FROM user_profile")
        user_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM word")
        word_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM learning_session")
        session_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM exercise_record")
        exercise_count = cursor.fetchone()[0]
        
        # 进度统计
        cursor.execute("""
            SELECT 
                AVG(mastery_level) as avg_mastery,
                AVG(learning_efficiency) as avg_efficiency,
                COUNT(*) as progress_records
            FROM user_progress
        """)
        progress_stats = cursor.fetchone()
        
        # 最近活动
        cursor.execute("""
            SELECT COUNT(*) FROM learning_session 
            WHERE created_at >= datetime('now', '-7 days')
        """)
        recent_sessions = cursor.fetchone()[0]
        
        conn.close()
        
        stats = {
            'totalUsers': user_count,
            'totalWords': word_count,
            'totalSessions': session_count,
            'totalExercises': exercise_count,
            'recentSessions': recent_sessions,
            'averageMastery': progress_stats[0] if progress_stats[0] else 0,
            'averageEfficiency': progress_stats[1] if progress_stats[1] else 0,
            'progressRecords': progress_stats[2] if progress_stats[2] else 0,
            'adaptiveEngine': recommendation_engine is not None,
            'spacedRepetition': spaced_repetition is not None
        }
        
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ================================================
# 简化版推荐函数（fallback）
# ================================================

def get_simple_recommendation(user_id, context):
    """简化版推荐（当推荐引擎不可用时）：选一个用户还没学过的词"""
    studied = db.session.query(UserProgress.word_id).filter_by(user_id=user_id)
    has_materials = db.session.query(Example.word_id)
    word = (
        Word.query.filter(Word.id.in_(has_materials), ~Word.id.in_(studied)).order_by(Word.id).first()
        or Word.query.filter(Word.id.in_(has_materials)).order_by(Word.id).first()
        or Word.query.order_by(Word.id).first()
    )
    vks_modules = {'A': 'character', 'B': 'word', 'C': 'collocation', 'D': 'sentence', 'E': 'exercise'}
    vks_level = context.get('vks_level') if context else None
    hanzi = get_word_hanzi(word.id) if word else None
    return {
        'type': 'simple_recommendation',
        'priority': 'medium',
        'word_id': word.id if word else 1,
        'word': hanzi or (word.pinyin if word else '发生'),
        'reason': 'Keep going with a new word',
        'recommended_module': vks_modules.get(vks_level, 'word'),
        'confidence': 0.5,
        'estimated_time': 300,
        'algorithm_version': 'simple_1.0'
    }

def get_simple_due_reviews(user_id, limit):
    """简化版到期复习（当SRS不可用时）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT up.word_id, w.pinyin, up.mastery_level, up.last_studied, up.review_count
            FROM user_progress up
            JOIN word w ON up.word_id = w.id
            WHERE up.user_id = ?
            AND up.last_studied < datetime('now', '-3 days')
            ORDER BY up.last_studied ASC
            LIMIT ?
        """, (user_id, limit))
        
        results = cursor.fetchall()
        reviews = []
        
        for result in results:
            word_id, pinyin, mastery_level, last_studied, review_count = result
            mastery_level = mastery_level or 0
            reviews.append({
                'word_id': word_id,
                'word': get_word_hanzi(word_id) or pinyin,
                'pinyin': pinyin,
                'mastery_level': mastery_level,
                'days_overdue': 3,
                'review_count': review_count or 0,
                'priority_score': 1 - mastery_level,
                # 前端没有 'review' 这个模块；与 adaptive_engine 的默认复习模块一致
                'recommended_module': 'word'
            })
        
        return reviews
        
    finally:
        conn.close()

def generate_dashboard_data(user_id, time_range):
    """生成dashboard数据"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 时间范围过滤
        if time_range == 'week':
            date_filter = "datetime('now', '-7 days')"
        elif time_range == 'month':
            date_filter = "datetime('now', '-30 days')"
        else:
            date_filter = "datetime('1970-01-01')"  # 所有时间
        
        # 学习概览
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total_sessions,
                SUM(duration_seconds) as total_time,
                AVG(duration_seconds) as avg_session_time,
                COUNT(CASE WHEN completed = 1 THEN 1 END) as completed_sessions
            FROM learning_session
            WHERE user_id = ? AND start_time >= {date_filter}
        """, (user_id,))
        
        overview = cursor.fetchone()
        
        # 掌握程度分布
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN mastery_level >= 0.8 THEN 1 END) as mastered,
                COUNT(CASE WHEN mastery_level >= 0.6 AND mastery_level < 0.8 THEN 1 END) as learning,
                COUNT(CASE WHEN mastery_level < 0.6 THEN 1 END) as struggling,
                COUNT(*) as total
            FROM user_progress
            WHERE user_id = ?
        """, (user_id,))
        
        mastery_dist = cursor.fetchone()
        
        # 准确率趋势（按题型）
        cursor.execute(f"""
            SELECT 
                er.question_type,
                COUNT(*) as total,
                SUM(CASE WHEN er.is_correct = 1 THEN 1 ELSE 0 END) as correct
            FROM exercise_record er
            JOIN learning_session ls ON er.session_id = ls.session_id
            WHERE ls.user_id = ? AND er.created_at >= {date_filter}
            GROUP BY er.question_type
        """, (user_id,))
        
        accuracy_by_type = cursor.fetchall()
        
        # 学习时间趋势（最近7天）
        cursor.execute("""
            SELECT 
                DATE(start_time) as date,
                SUM(duration_seconds) as daily_time,
                COUNT(*) as daily_sessions
            FROM learning_session
            WHERE user_id = ? AND start_time >= datetime('now', '-7 days')
            GROUP BY DATE(start_time)
            ORDER BY date
        """, (user_id,))
        
        daily_stats = cursor.fetchall()
        
        # 今日统计。学过的词不算 VKS 自评页的会话：自评页曾经一律记在默认的 1 号词上，
        # 学一个新词会多算一个「发生」
        cursor.execute("""
            SELECT 
                COUNT(*) as sessions,
                SUM(duration_seconds) as study_time,
                COUNT(DISTINCT CASE WHEN module_type != 'entrance' THEN word_id END) as words_studied
            FROM learning_session
            WHERE user_id = ? AND DATE(start_time) = DATE('now')
        """, (user_id,))
        
        today = cursor.fetchone()
        
        # 今日练习统计
        cursor.execute("""
            SELECT 
                COUNT(*) as exercises,
                AVG(CASE WHEN is_correct = 1 THEN 1.0 ELSE 0.0 END) as accuracy
            FROM exercise_record er
            JOIN learning_session ls ON er.session_id = ls.session_id
            WHERE ls.user_id = ? AND DATE(er.created_at) = DATE('now')
        """, (user_id,))
        
        today_exercises = cursor.fetchone()
        
        # 到期复习数量
        cursor.execute("""
            SELECT COUNT(*) FROM user_progress
            WHERE user_id = ? AND next_review_suggested <= datetime('now')
        """, (user_id,))
        
        due_reviews = cursor.fetchone()[0]
        
        # 整体进度
        cursor.execute("""
            SELECT COUNT(*) FROM word
        """)
        total_words = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT 
                AVG(mastery_level) as avg_mastery
            FROM user_progress
            WHERE user_id = ?
        """, (user_id,))
        
        avg_mastery = cursor.fetchone()[0] or 0
        
        dashboard = {
            'overview': {
                'totalSessions': overview[0] or 0,
                'totalStudyTime': overview[1] or 0,
                'averageSessionTime': overview[2] or 0,
                'completionRate': (overview[3] / max(overview[0], 1)) if overview[0] else 0
            },
            'masteryDistribution': {
                'mastered': mastery_dist[0] or 0,
                'learning': mastery_dist[1] or 0,
                'struggling': mastery_dist[2] or 0,
                'total': mastery_dist[3] or 0
            },
            'accuracyByType': [
                {
                    'questionType': row[0],
                    'accuracy': row[2] / max(row[1], 1),
                    'totalAttempts': row[1]
                }
                for row in accuracy_by_type
            ],
            'dailyProgress': [
                {
                    'date': row[0],
                    'studyTime': row[1] or 0,
                    'sessions': row[2] or 0
                }
                for row in daily_stats
            ],
            'todayStats': {
                'studyTimeMinutes': int((today[1] or 0) / 60),
                'wordsReviewed': today[2] or 0,
                'exercisesCompleted': today_exercises[0] or 0,
                'averageAccuracy': today_exercises[1] or 0
            },
            'overallProgress': {
                'totalWords': total_words,
                'studiedWords': mastery_dist[3] or 0,
                'masteredWords': mastery_dist[0] or 0,
                'averageMastery': avg_mastery
            },
            'dueReviews': due_reviews,
            'recommendations': [],
            'strengths': [],
            'weaknesses': []
        }
        
        return dashboard
        
    finally:
        conn.close()

# ================================================
# 用户认证API
# ================================================

def merge_guest_into_user(guest_id, user_id):
    """把访客名下的学习数据转到刚注册的账号，返回迁移的行数；失败返回 None。

    learning_event / exercise_record 挂在 session_id 上，随 learning_session 一起转移。
    访客的档案（当前学习位置等）复制到新账号后删除。
    """
    conn = sqlite3.connect(_db_path, timeout=30)
    try:
        moved = 0
        for table in ('learning_session', 'user_progress', 'adaptive_recommendation',
                      'confusable_exercise_records'):
            moved += conn.execute(
                f"UPDATE {table} SET user_id = ? WHERE user_id = ?", (user_id, guest_id)
            ).rowcount
        conn.execute("""
            UPDATE user_profile SET
                current_word_id = (SELECT current_word_id FROM user_profile WHERE user_id = :g),
                current_word = (SELECT current_word FROM user_profile WHERE user_id = :g),
                current_module = (SELECT current_module FROM user_profile WHERE user_id = :g),
                current_vks_level = (SELECT current_vks_level FROM user_profile WHERE user_id = :g),
                current_recommendation_id = (SELECT current_recommendation_id FROM user_profile WHERE user_id = :g)
            WHERE user_id = :u AND EXISTS (SELECT 1 FROM user_profile WHERE user_id = :g)
        """, {'g': guest_id, 'u': user_id})
        conn.execute("DELETE FROM user_profile WHERE user_id = ?", (guest_id,))
        conn.commit()
        return moved
    except sqlite3.Error as e:
        conn.rollback()
        print(f"⚠️  访客数据合并失败: {e}")
        return None
    finally:
        conn.close()


@app.route('/api/auth/register', methods=['POST'])
def register():
    """用户注册"""
    try:
        if not AuthManager:
            return jsonify({'success': False, 'error': 'Accounts are not available'}), 503
        
        auth_manager = AuthManager()
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        email = data.get('email')
        native_language = data.get('native_language', 'English')
        
        # 验证必填字段
        if not username or not password:
            return jsonify({'success': False, 'error': 'Please enter a username and password'}), 400
        
        # 验证密码强度
        if len(password) < 6:
            return jsonify({'success': False, 'error': 'Use at least 6 characters for the password'}), 400
        
        # 注册用户
        result = auth_manager.register_user(
            username=username,
            password=password,
            email=email,
            native_language=native_language
        )
        
        if result['success']:
            # 先以访客身份学习、后注册的学习者，进度并入新账号
            guest_id = get_guest_id()
            merged = merge_guest_into_user(guest_id, result['user_id']) if guest_id else 0
            return jsonify({
                'success': True,
                'data': {
                    'user_id': result['user_id'],
                    'username': username,
                    'merged_guest_rows': merged or 0,
                    # 账号已建好，但访客数据没并过来（如数据库锁超时）：明确告知，
                    # 不与「本来就没有访客数据」混为一谈
                    'guest_merge': 'failed' if merged is None else ('done' if merged else 'none')
                },
                'message': result['message']
            })
        else:
            return jsonify({'success': False, 'error': result['message']}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/login', methods=['POST'])
def login():
    """用户登录"""
    try:
        if not AuthManager:
            return jsonify({'success': False, 'error': 'Accounts are not available'}), 503
        
        auth_manager = AuthManager()
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        remember_me = data.get('remember_me', False)
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Please enter a username and password'}), 400
        
        # 执行登录
        result = auth_manager.login(username, password)
        
        if result['success']:
            # 创建响应
            response = make_response(jsonify({
                'success': True,
                'data': {
                    'user_id': result['user_id'],
                    'username': result['username'],
                    'email': result.get('email'),
                    'session_token': result['session_token']
                },
                'message': result['message']
            }))
            
            # 设置cookie（可选，也可以让前端使用localStorage）
            max_age = 7 * 24 * 60 * 60 if remember_me else None  # 7天或session
            response.set_cookie(
                'session_token',
                result['session_token'],  # pyrefly: ignore  # 运行时必为 str
                max_age=max_age,
                httponly=True,
                samesite='Lax'
            )
            
            return response
        else:
            return jsonify({'success': False, 'error': result['message']}), 401
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """用户登出"""
    try:
        if not AuthManager:
            return jsonify({'success': False, 'error': 'Accounts are not available'}), 503
        
        auth_manager = AuthManager()
        # 从header或cookie获取session token
        session_token = request.headers.get('X-Session-Token') or request.cookies.get('session_token')
        
        if not session_token:
            return jsonify({'success': False, 'error': 'Not signed in'}), 401
        
        # 执行登出
        result = auth_manager.logout(session_token)
        
        if result['success']:
            # 清除cookie
            response = make_response(jsonify({
                'success': True,
                'message': result['message']
            }))
            response.set_cookie('session_token', '', max_age=0)
            return response
        else:
            return jsonify({'success': False, 'error': result['message']}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/me', methods=['GET'])
def get_current_user():
    """获取当前登录用户信息"""
    try:
        if not AuthManager:
            return jsonify({'success': False, 'error': 'Accounts are not available'}), 503
        
        auth_manager = AuthManager()
        # 从header或cookie获取session token
        session_token = request.headers.get('X-Session-Token') or request.cookies.get('session_token')
        
        if not session_token:
            return jsonify({'success': False, 'error': 'Not signed in', 'code': 'NOT_AUTHENTICATED'}), 401
        
        # 验证session
        validation = auth_manager.validate_session(session_token)
        
        if not validation['valid']:
            return jsonify({'success': False, 'error': validation['message'], 'code': 'INVALID_SESSION'}), 401
        
        # 获取用户信息
        user_info = auth_manager.get_user_info(validation['user_id'])
        
        if user_info:
            return jsonify({
                'success': True,
                'data': user_info
            })
        else:
            return jsonify({'success': False, 'error': 'User not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/validate', methods=['GET'])
def validate_session():
    """验证session是否有效（用于前端检查登录状态）"""
    try:
        if not AuthManager:
            return jsonify({'success': False, 'valid': False}), 503
        
        auth_manager = AuthManager()
        session_token = request.headers.get('X-Session-Token') or request.cookies.get('session_token')
        
        if not session_token:
            return jsonify({'success': True, 'valid': False, 'reason': 'no_token'})
        
        validation = auth_manager.validate_session(session_token)
        
        return jsonify({
            'success': True,
            'valid': validation['valid'],
            'user_id': validation.get('user_id'),
            'reason': validation.get('message')
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ================================================
# 应用初始化
# ================================================

def ensure_user_profile_columns():
    """为旧数据库补齐 user_profile 新增列（create_all 不会修改已存在的表）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(user_profile)")
    existing = {row[1] for row in cursor.fetchall()}
    new_columns = {
        'current_word_id': 'INTEGER',
        'current_word': 'VARCHAR(50)',
        'current_module': 'VARCHAR(30)',
        'current_vks_level': 'VARCHAR(5)',
        'current_recommendation_id': 'INTEGER',
    }
    for column, ddl in new_columns.items():
        if existing and column not in existing:
            cursor.execute(f"ALTER TABLE user_profile ADD COLUMN {column} {ddl}")
            print(f"   ➕ 已为 user_profile 补齐 {column} 列")
    conn.commit()
    conn.close()


def ensure_learning_session_columns():
    """为旧数据库补齐 learning_session 新增列（create_all 不会修改已存在的表）"""
    conn = sqlite3.connect(_db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(learning_session)")
        existing = {row[1] for row in cursor.fetchall()}
        if existing and 'recommendation_id' not in existing:
            cursor.execute("ALTER TABLE learning_session ADD COLUMN recommendation_id INTEGER")
            conn.commit()
            print("   ➕ 已为 learning_session 补齐 recommendation_id 列")
    except sqlite3.Error as e:
        print(f"⚠️  learning_session 列迁移失败: {e}")
    finally:
        conn.close()


def ensure_review_indexes():
    """复习进度每次都由会话与作答推出（见 review_state），给这两个查询补索引"""
    conn = sqlite3.connect(_db_path)
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS ix_exercise_record_session ON exercise_record (session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_learning_session_user_word ON learning_session (user_id, word_id)")
        conn.commit()
    except sqlite3.Error as e:
        print(f"⚠️  创建复习查询索引失败: {e}")
    finally:
        conn.close()


def ensure_learning_event_columns():
    """把老库里 learning_event 的 target 列重命名为 event_target。

    历史上 scripts/simple_test_data.py 会用 target 建表，而 models_extended.py 与
    真实生产库用的是 event_target。两种列名的库并存时，另一方的写入必然 500。
    """
    conn = sqlite3.connect(_db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(learning_event)")
        columns = {row[1] for row in cursor.fetchall()}
        if columns and 'target' in columns and 'event_target' not in columns:
            cursor.execute("ALTER TABLE learning_event RENAME COLUMN target TO event_target")
            conn.commit()
            print("   ➕ 已将 learning_event.target 重命名为 event_target")
    except sqlite3.Error as e:
        print(f"⚠️  learning_event 列名迁移失败: {e}")
    finally:
        conn.close()


def ensure_user_progress_unique_index():
    """给已存在的 user_progress 表补 (user_id, word_id) 唯一索引。

    db.create_all() 不会修改已存在的表，所以模型上的 UniqueConstraint 对老库无效；
    没有这个索引，并发写入会产生重复进度行，特征累加就会被拆散到多行上。
    """
    conn = sqlite3.connect(_db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_user_progress_user_word
            ON user_progress (user_id, word_id)
        """)
        conn.commit()
    except sqlite3.IntegrityError:
        # 老库里已有重复的 (user_id, word_id)，需要人工合并后再建索引
        print("⚠️  user_progress 存在重复的 (user_id, word_id)，唯一索引未创建")
    except sqlite3.Error as e:
        print(f"⚠️  创建 user_progress 唯一索引失败: {e}")
    finally:
        conn.close()

CONTRAST_SCHEMA_READY = False


WORD_COLUMNS = (('audio', 'VARCHAR(200)'), ('freq_rank', 'INTEGER'), ('freq_tier', 'VARCHAR(10)'))


def ensure_word_columns():
    """为旧数据库补齐 word.audio（整词发音地址）、freq_rank、freq_tier（词频排名和档位）。必须在第一次用 ORM 查 Word 之前执行：
    模型里有这些列，库里没有时所有词的查询都会报错。加列失败（别的进程正持有写锁）时再看一次是否已由别的进程加上。"""
    conn = sqlite3.connect(_db_path, timeout=30)
    try:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(word)")}
        for column, ddl in WORD_COLUMNS:
            if not existing or column in existing:
                continue
            try:
                conn.execute(f"ALTER TABLE word ADD COLUMN {column} {ddl}")
                conn.commit()
                print(f"   ➕ 已为 word 补齐 {column} 列")
            except sqlite3.Error:
                if column not in {row[1] for row in conn.execute("PRAGMA table_info(word)")}:
                    raise
    finally:
        conn.close()


def ensure_confusable_pair_columns():
    """为旧数据库补齐辨析题相关的列和索引：confusable_pairs.questions、word2_level，
    confusable_exercise_records 的题号、版本号、所选答案、作答编号，以及作答编号的唯一索引。
    必须在第一次查询这两个模型之前执行。加列失败（如别的进程正持有写锁）时再看一次列是否已由别的进程加上。
    做不完时不中断启动（后面还有认证迁移、推荐引擎等初始化），只把 CONTRAST_SCHEMA_READY 置为假：
    辨析不再带出，作答接口返回 503。"""
    global CONTRAST_SCHEMA_READY
    wanted = {
        'confusable_pairs': [('questions', 'TEXT'), ('word2_level', 'INTEGER')],
        'confusable_exercise_records': [('question_index', 'INTEGER'), ('question_version', 'VARCHAR(16)'),
                                        ('user_answer', 'VARCHAR(50)'), ('attempt_id', 'VARCHAR(64)')],
    }
    conn = sqlite3.connect(_db_path, timeout=30)
    CONTRAST_SCHEMA_READY = False
    try:
        for table, columns in wanted.items():
            existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            for column, ddl in columns:
                if not existing or column in existing:
                    continue
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
                    conn.commit()
                    print(f"   ➕ 已为 {table} 补齐 {column} 列")
                except sqlite3.Error:
                    if column not in {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}:
                        raise
        conn.execute("CREATE INDEX IF NOT EXISTS ix_confusable_records_user_pair "
                     "ON confusable_exercise_records (user_id, pair_id, id)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_confusable_records_attempt "
                     "ON confusable_exercise_records (user_id, attempt_id) WHERE attempt_id IS NOT NULL")
        conn.commit()
        indexes = {row[1] for row in conn.execute("PRAGMA index_list(confusable_exercise_records)")}
        CONTRAST_SCHEMA_READY = 'uq_confusable_records_attempt' in indexes
    except sqlite3.Error as e:
        print(f"⚠️  辨析题的列或索引没能补齐，辨析暂停使用: {e}")
    finally:
        conn.close()


def initialize_database():
    """初始化数据库和测试数据"""
    try:
        with app.app_context():
            db.create_all()
            ensure_word_columns()
            ensure_user_profile_columns()
            ensure_learning_session_columns()
            ensure_confusable_pair_columns()
            ensure_learning_event_columns()
            ensure_user_progress_unique_index()
            ensure_review_indexes()
            # 注册/登录依赖的列和 user_session 表此前只在测试里建过，部署后
            # 注册登录必然 500。幂等执行；不设测试密码（见 migrate_auth_system）
            try:
                import sys
                sys.path.insert(0, os.path.join(basedir, 'scripts'))
                import migrate_auth  # pyrefly: ignore  # 运行时动态路径
                migrate_auth.migrate_auth_system(_db_path, seed_test_passwords=False)
            except Exception as e:
                print(f"⚠️  认证表结构迁移失败: {str(e)}")
            print("✅ 数据库表创建成功")
            
            # 检查是否需要添加初始数据
            if Word.query.count() == 0:
                print("📝 添加初始词汇数据...")
                word = Word(pinyin='fāshēng', definition='happen; occur; take place')
                db.session.add(word)
                db.session.commit()
                
                # 添加词汇组件
                example = Example(
                    sentence='不愿意发生的事情终于出现了。',
                    pinyin='不/bù 愿意/yuànyì 发生/fāshēng 的/de 事情/shìqíng 终于/zhōngyú 出现/chūxiàn 了/le 。',
                    translation="What I didn't want to happen finally happened.",
                    audio='/audio/example1.mp3',
                    word_id=word.id
                )
                db.session.add(example)
                
                collocation1 = Collocation(
                    collocation='容易（三级）发生',
                    translation='easy to happen',
                    audio='/audio/collocation1.mp3',
                    word_id=word.id
                )
                collocation2 = Collocation(
                    collocation='事情（二级）发生',
                    translation='things happen',
                    audio='/audio/collocation2.mp3',
                    word_id=word.id
                )
                db.session.add(collocation1)
                db.session.add(collocation2)
                
                character1 = Character(
                    character='发',
                    pinyin='fā',
                    definition='come or bring into existence; generate',
                    audio='/audio/character1.mp3',
                    word_id=word.id
                )
                character2 = Character(
                    character='生',
                    pinyin='shēng',
                    definition='bear; generate',
                    audio='/audio/character2.mp3',
                    word_id=word.id
                )
                db.session.add(character1)
                db.session.add(character2)
                
                db.session.commit()
                print("✅ 初始数据添加完成")
            
            # 易混淆词对只来自学习资料流水线（语料库确认、易混淆词限一至三级，作者 2026-10-29 定），
            # 由下面的 HSK4 批次导入写入；不再写入手写的种子词对

            # 修复已入库素材的已知缺陷（拼音混在释义里、缺拼音、搭配丢了目标词等）。
            # 导入脚本只插入不更新，修好它不会改正旧数据；这里幂等，改过一次后不再动
            try:
                import sys
                sys.path.insert(0, os.path.join(basedir, 'scripts'))
                import clean_materials  # pyrefly: ignore  # 运行时动态路径
                fixed = clean_materials.clean_database(_db_path)
                if fixed:
                    print(f"🧹 学习素材修复 {fixed} 行")
            except Exception as e:
                print(f"⚠️  学习素材修复失败: {str(e)}")

            # 论文课件里的人工命题。每次启动都与课件同步，而不是「表空才导」：
            # 先只有示范词、后导入教材的库，以及解析器修正过的题，都要靠这一步
            # 补齐或更正，否则练习会静默回落到随机干扰项。同步是幂等的。
            try:
                import sys
                sys.path.insert(0, os.path.join(basedir, 'scripts'))
                import parse_answer_decks  # pyrefly: ignore  # 运行时动态路径
                inserted, updated, pruned, unmatched = parse_answer_decks.import_into(_db_path)
                if inserted or updated or pruned:
                    print(f"📝 论文练习题同步：新增 {inserted} 条，更新 {updated} 条，删除过期 {pruned} 条")
                if unmatched:
                    print(f"⚠️  论文练习题有 {unmatched} 组在词库中找不到对应词")
            except Exception as e:
                print(f"⚠️  论文练习题同步失败: {str(e)}")

            # 按论文 5.3 节流程批量制作的四级词学习资料（只导入作者已审核的批次），幂等
            try:
                import sys
                sys.path.insert(0, os.path.join(basedir, 'scripts'))
                import import_hsk4_batches  # pyrefly: ignore  # 运行时动态路径
                added, _, items, pairs = import_hsk4_batches.import_into(_db_path)
                if added or items or pairs:
                    print(f"📝 四级词批次导入：新增词 {added}，练习题 {items}，易混淆词对 {pairs}")
            except Exception as e:
                print(f"⚠️  四级词批次导入失败: {str(e)}")

            # 四级词的词频排名和档位（推荐新词按高、中、低频轮流），批次导入之后补，幂等
            try:
                changed = import_hsk4_batches.apply_frequency_tiers(_db_path)
                if changed:
                    print(f"📝 四级词词频档位补入 {changed} 个词")
            except Exception as e:
                print(f"⚠️  四级词词频档位补入失败: {str(e)}")

            # 论文词库里的词的发音音频（学习资料制作第 8 步 --thesis 生成的清单），幂等
            try:
                import sys
                sys.path.insert(0, os.path.join(basedir, 'scripts'))
                import apply_audio_manifest  # pyrefly: ignore  # 运行时动态路径
                filled = apply_audio_manifest.apply(_db_path)
                if filled:
                    print(f"🔊 论文词库发音音频补入 {filled} 处")
            except Exception as e:
                print(f"⚠️  论文词库发音音频补入失败: {str(e)}")

            # 检查是否有测试数据
            if UserProfile.query.count() == 0:
                print("📊 生成测试数据...")
                try:
                    import sys
                    sys.path.insert(0, os.path.join(basedir, 'scripts'))
                    import simple_test_data  # pyrefly: ignore  # 运行时动态路径
                    simple_test_data.generate_simple_test_data()
                except Exception as e:
                    print(f"⚠️  测试数据生成失败: {str(e)}")
            
        # 初始化推荐引擎
        init_recommendation_engine()
        
    except Exception as e:
        print(f"❌ 数据库初始化失败: {str(e)}")

# 在module级别注册易混淆词API（gunicorn不走__main__）
if register_confusable_apis:
    try:
        register_confusable_apis(app, db, require_authentication, check_data_ownership,
                                  pair_due=confusable_pair_due, schema_ready=lambda: CONTRAST_SCHEMA_READY)
    except Exception as e:
        print(f"⚠️  易混淆词API模块级注册失败: {str(e)}")

# gunicorn启动时自动初始化
initialize_database()

if __name__ == '__main__':
    print("🚀 启动第二阶段自适应学习API服务...")
    
    # 初始化数据库
    initialize_database()
    
    print("\n📍 第二阶段API服务信息:")
    print("   🎯 智能推荐引擎: ", "✅ 已启用" if recommendation_engine else "⚠️  简化模式")
    print("   🔄 间隔重复算法: ", "✅ 已启用" if spaced_repetition else "⚠️  简化模式")
    print("   📊 学习分析功能: ✅ 已启用")
    print("   🌐 服务地址: http://localhost:5004")
    print("\n📋 主要新功能:")
    print("   - GET  /api/adaptive/recommendation/<user_id> - 个性化推荐")
    print("   - GET  /api/review/user/<user_id>/due - 到期复习")
    print("   - GET  /api/analytics/user/<user_id>/dashboard - 学习dashboard")
    print("   - POST /api/adaptive/feedback - 推荐反馈")
    
    app.run(debug=True, port=5004, use_reloader=False)
