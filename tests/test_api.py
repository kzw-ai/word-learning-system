#!/usr/bin/env python3
"""
Phase 2 API 集成测试（Flask test client，无需启动服务器）

覆盖：核心数据端点、易混淆词、会话追踪、自适应推荐、
认证流程和用户数据隔离。

运行: python3 -m pytest tests/test_api.py -v
"""

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope='session')
def app(tmp_path_factory):
    """
    把数据库指向临时文件后再导入 app_phase。

    WORDS_DB_PATH 必须在导入前设置——SQLAlchemy 在模块导入时
    就绑定了数据库 URI，事后改配置不会生效。
    """
    db_file = str(tmp_path_factory.mktemp('api-db') / 'words_extended.db')
    os.environ['WORDS_DB_PATH'] = db_file
    # 启动时会导入 data/learning_materials 下作者审核过的批次和音频清单：测试库不要它们
    os.environ['HSK4_BATCH_DIR'] = str(tmp_path_factory.mktemp('hsk4-batches'))
    os.environ['AUDIO_MANIFEST'] = str(tmp_path_factory.mktemp('audio') / '论文词库.json')

    # 导入即触发 initialize_database()：建表 + 种子词汇/易混淆词 + 测试数据
    import app_phase as mod

    assert db_file in mod.app.config['SQLALCHEMY_DATABASE_URI'], \
        'app_phase 在设置 WORDS_DB_PATH 之前已被导入，测试会污染真实数据库'
    mod.app.config['TESTING'] = True

    # 认证表（user_session 等）由迁移脚本创建，不在 SQLAlchemy 模型里
    sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))
    from migrate_auth import migrate_auth_system  # pyrefly: ignore  # 运行时动态路径
    assert migrate_auth_system(db_file)

    yield mod.app
    for key in ('WORDS_DB_PATH', 'HSK4_BATCH_DIR', 'AUDIO_MANIFEST'):
        del os.environ[key]


@pytest.fixture(scope='session')
def client(app):
    return app.test_client()


@pytest.fixture
def anon_client(app):
    """全新 client——不带任何登录 cookie，用于匿名场景断言"""
    return app.test_client()


@pytest.fixture(scope='session')
def auth_session(client):
    """注册并登录一个用户，返回 (user_id, session_token)"""
    register = client.post('/api/auth/register', json={
        'username': 'pytest_user',
        'password': 'secret123',
    }).get_json()
    assert register['success'], register
    user_id = register['data']['user_id']

    login = client.post('/api/auth/login', json={
        'username': 'pytest_user',
        'password': 'secret123',
    }).get_json()
    assert login['success'], login
    return user_id, login['data']['session_token']


# ================================================
# 核心数据端点
# ================================================

class TestCoreEndpoints:
    def test_home(self, client):
        resp = client.get('/')
        assert resp.status_code == 200

    def test_stats(self, client):
        data = client.get('/api/stats').get_json()
        assert data['success'] is True
        assert data['data']['totalWords'] >= 1

    def test_words_list(self, client):
        resp = client.get('/words')
        assert resp.status_code == 200

    def test_word_detail(self, client):
        resp = client.get('/word/1')
        assert resp.status_code == 200

    def test_word_not_found(self, client):
        resp = client.get('/word/99999')
        assert resp.status_code == 404

    def test_users_list(self, client, monkeypatch):
        # 用户列表只给开发期的 UserSwitcher 用
        monkeypatch.setenv('ALLOW_USER_ID_PARAM', '1')
        data = client.get('/api/users').get_json()
        assert data['success'] is True
        assert isinstance(data['data'], list)

    def test_users_list_hidden_in_production(self, client):
        assert client.get('/api/users').status_code == 404


# ================================================
# 易混淆词 API
# ================================================

class TestConfusableApi:
    @pytest.fixture
    def pair(self, app):
        """一对测试词对，测完删掉（库里不再写入手写的种子词对）"""
        import app_phase as mod
        with app.app_context():
            w1 = mod.Word(pinyin='tūrán', definition='adj./adv. sudden; suddenly')
            w2 = mod.Word(pinyin='hūrán', definition='adv. suddenly')
            mod.db.session.add_all([w1, w2])
            mod.db.session.flush()
            row = mod.ConfusablePair(word1_id=w1.id, word2_id=w2.id, reason='r', difference='d', examples='e',
                                     tips='t', difficulty_level=1)
            mod.db.session.add(row)
            mod.db.session.commit()
            ids = (row.id, w1.id, w2.id)
        yield ids[0]
        with app.app_context():
            mod.ConfusableExerciseRecord.query.filter_by(pair_id=ids[0]).delete()
            mod.db.session.delete(mod.db.session.get(mod.ConfusablePair, ids[0]))
            for word_id in ids[1:]:
                mod.db.session.delete(mod.db.session.get(mod.Word, word_id))
            mod.db.session.commit()

    def test_no_handwritten_seed_pairs(self, client):
        """辨析词对只来自学习资料流水线：新库里没有词对"""
        assert client.get('/api/confusable/pairs?limit=50').get_json()['total'] == 0

    def test_pairs_list(self, client, pair):
        data = client.get('/api/confusable/pairs?limit=20').get_json()
        assert data['success'] is True
        assert data['total'] == 1
        listed = data['pairs'][0]
        assert listed['id'] == pair
        for key in ('id', 'word1', 'word2', 'reason', 'difference', 'difficulty_level'):
            assert key in listed
        assert 'pinyin' in listed['word1'] and 'definition' in listed['word1']

    def test_pairs_difficulty_filter(self, client, pair):
        data = client.get('/api/confusable/pairs?difficulty=1').get_json()
        assert data['success'] is True
        assert data['pairs'] and all(p['difficulty_level'] == 1 for p in data['pairs'])
        assert client.get('/api/confusable/pairs?difficulty=2').get_json()['pairs'] == []

    def test_single_pair(self, client, pair):
        data = client.get(f'/api/confusable/pair/{pair}').get_json()
        assert data['success'] is True
        assert data['pair']['id'] == pair

    def test_single_pair_not_found(self, client):
        resp = client.get('/api/confusable/pair/9999')
        assert resp.status_code == 404

    def test_record_requires_auth(self, anon_client, pair):
        resp = anon_client.post('/api/confusable/exercise/record', json={
            'pair_id': pair, 'is_correct': True, 'response_time': 3.0,
        })
        assert resp.status_code == 401

    def test_record_with_session_token(self, client, auth_session, pair):
        user_id, token = auth_session
        resp = client.post(
            '/api/confusable/exercise/record',
            json={'pair_id': pair, 'is_correct': True, 'response_time': 3.0},
            headers={'X-Session-Token': token},
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_statistics_blocks_other_users(self, client, auth_session):
        _, token = auth_session
        resp = client.get(
            '/api/confusable/user/someone_else/statistics',
            headers={'X-Session-Token': token},
        )
        assert resp.status_code == 403


# ================================================
# 学习会话追踪
# ================================================

class TestSessionTracking:
    def test_start_requires_auth(self, anon_client):
        resp = anon_client.post('/api/learning/session/start', json={
            'sessionId': 's-anonymous', 'wordId': 1,
            'sessionType': 'learning', 'moduleType': 'word',
            'startTime': '2026-01-01T10:00:00',
        })
        assert resp.status_code == 401

    def test_start_and_end_with_token(self, client, auth_session):
        user_id, token = auth_session
        headers = {'X-Session-Token': token}
        start = client.post('/api/learning/session/start', json={
            'sessionId': 's-pytest-1', 'wordId': 1,
            'sessionType': 'learning', 'moduleType': 'word',
            'startTime': '2026-01-01T10:00:00',
        }, headers=headers)
        assert start.get_json()['success'] is True, start.get_json()

        end = client.post('/api/learning/session/end', json={
            'sessionId': 's-pytest-1',
            'endTime': '2026-01-01T10:05:00',
            'durationSeconds': 300,
            'activeTimeSeconds': 250,
            'completed': True,
            'eventCount': 3,
        }, headers=headers)
        assert end.get_json()['success'] is True, end.get_json()

    def test_cannot_start_session_for_other_user(self, client, auth_session):
        _, token = auth_session
        resp = client.post('/api/learning/session/start', json={
            'sessionId': 's-pytest-2', 'userId': 'someone_else', 'wordId': 1,
            'sessionType': 'learning', 'moduleType': 'word',
            'startTime': '2026-01-01T10:00:00',
        }, headers={'X-Session-Token': token})
        assert resp.status_code == 403


# ================================================
# 自适应推荐与复习
# ================================================

class TestAdaptiveEndpoints:
    def test_recommendation(self, client, auth_session):
        user_id, token = auth_session
        data = client.get(
            f'/api/adaptive/recommendation/{user_id}',
            headers={'X-Session-Token': token},
        ).get_json()
        assert data['success'] is True
        assert 'type' in data['data']

    def test_recommendation_blocks_other_users(self, client, auth_session):
        _, token = auth_session
        resp = client.get(
            '/api/adaptive/recommendation/someone_else',
            headers={'X-Session-Token': token},
        )
        assert resp.status_code == 403

    def test_due_reviews(self, client, auth_session):
        user_id, token = auth_session
        data = client.get(
            f'/api/review/user/{user_id}/due',
            headers={'X-Session-Token': token},
        ).get_json()
        assert data['success'] is True
        assert isinstance(data['data'], list)

    def test_dashboard(self, client, auth_session):
        user_id, token = auth_session
        data = client.get(
            f'/api/analytics/user/{user_id}/dashboard',
            headers={'X-Session-Token': token},
        ).get_json()
        assert data['success'] is True


# ================================================
# 认证流程
# ================================================

class TestAuthFlow:
    def test_register_rejects_short_password(self, client):
        resp = client.post('/api/auth/register', json={
            'username': 'short_pw_user', 'password': '123',
        })
        assert resp.status_code == 400

    def test_register_rejects_missing_fields(self, client):
        resp = client.post('/api/auth/register', json={'username': 'no_pw'})
        assert resp.status_code == 400

    def test_login_wrong_password(self, client, auth_session):
        resp = client.post('/api/auth/login', json={
            'username': 'pytest_user', 'password': 'wrong-password',
        })
        assert resp.status_code == 401

    def test_validate_without_token(self, anon_client):
        data = anon_client.get('/api/auth/validate').get_json()
        assert data['success'] is True
        assert data['valid'] is False

    def test_validate_with_token(self, client, auth_session):
        user_id, token = auth_session
        data = client.get(
            '/api/auth/validate', headers={'X-Session-Token': token},
        ).get_json()
        assert data['valid'] is True
        assert data['user_id'] == user_id

    def test_validate_with_bogus_token(self, client):
        data = client.get(
            '/api/auth/validate', headers={'X-Session-Token': 'not-a-real-token'},
        ).get_json()
        assert data['valid'] is False


# ================================================
# 访客身份与防冒充
# ================================================

GUEST = 'guest_' + 'a1b2c3d4e5f6g7h8i9j0'
OTHER_GUEST = 'guest_' + 'z9y8x7w6v5u4t3s2r1q0'


def guest_headers(guest_id=GUEST):
    return {'X-Guest-Id': guest_id}


class TestGuestIdentity:
    def test_user_id_in_url_is_not_an_identity(self, anon_client, auth_session):
        # 生产模式下，URL 里填别人的 user_id 不能读到对方的数据
        user_id, _ = auth_session
        resp = anon_client.get(f'/api/review/user/{user_id}/due')
        assert resp.status_code == 401

    def test_guest_can_read_own_data(self, anon_client):
        resp = anon_client.get(f'/api/review/user/{GUEST}/due', headers=guest_headers())
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_guest_cannot_read_other_guest(self, anon_client):
        resp = anon_client.get(f'/api/review/user/{OTHER_GUEST}/due', headers=guest_headers())
        assert resp.status_code == 403

    def test_malformed_guest_id_rejected(self, anon_client):
        resp = anon_client.get('/api/review/user/guest_short/due',
                               headers=guest_headers('guest_short'))
        assert resp.status_code == 401

    def test_guest_cookie_works(self, app):
        c = app.test_client()
        c.set_cookie('guest_id', GUEST)
        resp = c.get(f'/api/review/user/{GUEST}/due')
        assert resp.status_code == 200

    def test_guest_learning_session_recorded(self, anon_client):
        resp = anon_client.post('/api/learning/session/start', json={
            'sessionId': 's-guest-1', 'userId': GUEST, 'wordId': 1,
            'sessionType': 'learning', 'moduleType': 'word',
            'startTime': '2026-01-01T10:00:00',
        }, headers=guest_headers())
        assert resp.get_json()['success'] is True, resp.get_json()

    def test_learning_state_is_owner_only(self, anon_client):
        put = anon_client.put(f'/api/users/{GUEST}/learning-state',
                              json={'wordId': 1, 'word': '发生'}, headers=guest_headers())
        assert put.get_json()['success'] is True
        assert anon_client.get(f'/api/users/{GUEST}/learning-state',
                               headers=guest_headers()).status_code == 200
        # 此前这两个接口没有任何认证
        assert anon_client.get(f'/api/users/{GUEST}/learning-state').status_code == 401
        assert anon_client.put(f'/api/users/{OTHER_GUEST}/learning-state', json={'wordId': 2},
                               headers=guest_headers()).status_code == 403

    def test_register_merges_guest_data(self, app):
        import sqlite3
        guest = 'guest_' + 'm3rg3m3rg3m3rg3m3rg3'
        c = app.test_client()
        c.post('/api/learning/session/start', json={
            'sessionId': 's-guest-merge', 'userId': guest, 'wordId': 1,
            'sessionType': 'learning', 'moduleType': 'word',
            'startTime': '2026-01-01T10:00:00',
        }, headers=guest_headers(guest))
        c.put(f'/api/users/{guest}/learning-state', json={'wordId': 1, 'word': '发生'},
              headers=guest_headers(guest))

        reg = c.post('/api/auth/register', json={'username': 'merged_user', 'password': 'secret123'},
                     headers=guest_headers(guest)).get_json()
        assert reg['success'], reg
        assert reg['data']['merged_guest_rows'] >= 1

        db = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db)
        try:
            owner = conn.execute("SELECT user_id FROM learning_session WHERE session_id='s-guest-merge'").fetchone()[0]
            assert owner == reg['data']['user_id']
            word = conn.execute("SELECT current_word FROM user_profile WHERE user_id=?",
                                (reg['data']['user_id'],)).fetchone()[0]
            assert word == '发生'
            assert conn.execute("SELECT COUNT(*) FROM user_profile WHERE user_id=?", (guest,)).fetchone()[0] == 0
        finally:
            conn.close()


class TestSessionBoundWrites:
    """事件与作答必须写进「自己的、真实存在的」会话"""

    def test_events_require_identity(self, anon_client):
        resp = anon_client.post('/api/learning/events/batch', json={
            'sessionId': 's-guest-1', 'events': [{'type': 'click'}]})
        assert resp.status_code == 401

    def test_events_into_unknown_session_rejected(self, anon_client):
        resp = anon_client.post('/api/learning/events/batch', json={
            'sessionId': 's-does-not-exist', 'events': [{'type': 'click'}]}, headers=guest_headers())
        assert resp.status_code == 404

    def test_events_into_other_users_session_rejected(self, anon_client):
        # s-guest-1 由 GUEST 创建（见 TestGuestIdentity），换一个访客写入
        anon_client.post('/api/learning/session/start', json={
            'sessionId': 's-guest-owned', 'userId': GUEST, 'wordId': 1,
            'sessionType': 'learning', 'moduleType': 'word',
            'startTime': '2026-01-01T10:00:00',
        }, headers=guest_headers())
        resp = anon_client.post('/api/learning/events/batch', json={
            'sessionId': 's-guest-owned', 'events': [{'type': 'click'}]},
            headers=guest_headers(OTHER_GUEST))
        assert resp.status_code == 403
        ok = anon_client.post('/api/learning/events/batch', json={
            'sessionId': 's-guest-owned', 'events': [{'type': 'click'}]}, headers=guest_headers())
        assert ok.get_json()['success'] is True

    def test_exercise_into_unknown_session_rejected(self, anon_client):
        resp = anon_client.post('/api/learning/exercise/record', json={
            'sessionId': 's-does-not-exist', 'questionId': 'q1', 'questionType': 'definition',
            'userAnswer': 'a', 'correctAnswer': 'a', 'isCorrect': True,
            'startTime': '2026-01-01T10:00:00', 'endTime': '2026-01-01T10:00:05',
        }, headers=guest_headers())
        assert resp.status_code == 404


# ================================================
# 间隔重复调度：按整节练习的表现
# ================================================

def _learner(name):
    return 'guest_' + (name + '0' * 20)[:20]


def _stored(progress):
    """库里存的值（去掉随当前时间变化的 days）"""
    return {k: v for k, v in progress.items() if k != 'days'}


class TestSessionReviewScheduling:
    """一次复习 = 一节练习。日程按整节作答排，复习次数按会话数算。每个测试用自己的学习者。

    用只有释义题的词：第一节释义全对就不用复习（论文表 4.2），词直接达标、进入 SM-2 巩固期，
    这里测的正是巩固期按整节表现排日程。学习期的规则见 TestThesisReviewPlan
    """

    WORD = 7  # 测试库里的「刚才」：只有释义题

    @pytest.fixture(autouse=True)
    def _engine(self):
        import app_phase as mod
        if mod.spaced_repetition is None:
            pytest.skip('自适应引擎未加载')

    def _session(self, client, learner, session_id):
        resp = client.post('/api/learning/session/start', json={
            'sessionId': session_id, 'wordId': self.WORD,
            'sessionType': 'learning', 'moduleType': 'exercise',
            'startTime': '2026-01-01T10:00:00',
        }, headers=guest_headers(learner))
        assert resp.get_json()['success'] is True, resp.get_json()

    def _answer(self, client, learner, session_id, question_id, correct):
        resp = client.post('/api/learning/exercise/record', json={
            'sessionId': session_id, 'questionId': question_id, 'questionType': 'definition',
            'userAnswer': 'x', 'correctAnswer': 'x' if correct else 'y', 'isCorrect': correct,
            'startTime': '2026-01-01T10:00:00', 'endTime': '2026-01-01T10:00:05',
            'responseTimeSeconds': 5, 'hesitationCount': 0, 'confidenceLevel': 3,
        }, headers=guest_headers(learner))
        assert resp.get_json()['success'] is True, resp.get_json()

    def _progress(self, app, learner):
        import app_phase as mod
        from datetime import datetime
        with app.app_context():
            row = mod.UserProgress.query.filter_by(user_id=learner, word_id=self.WORD).one()
            days = (row.next_review_suggested - datetime.now()).total_seconds() / 86400
            return {'count': row.review_count, 'days': days, 'attempts': row.total_attempts,
                    'correct': row.correct_attempts, 'mastery': row.mastery_level,
                    'next': row.next_review_suggested}

    def _records(self, app, session_id):
        import app_phase as mod
        with app.app_context():
            return mod.ExerciseRecord.query.filter_by(session_id=session_id).count()

    def test_schedule_follows_whole_session(self, app, anon_client):
        learner = _learner('sm2whole')
        # 第一节全对：第 1 次复习
        self._session(anon_client, learner, 's-whole-1')
        for q in ('q1', 'q2', 'q3'):
            self._answer(anon_client, learner, 's-whole-1', q, True)
        assert self._progress(app, learner)['count'] == 1

        # 第二节第一题对、后两题错：应按「错」排到一天后，而不是按第一题的「对」拉长间隔
        self._session(anon_client, learner, 's-whole-2')
        self._answer(anon_client, learner, 's-whole-2', 'q1', True)
        assert self._progress(app, learner)['days'] > 2, '只答了第一题（对）时按第 2 次复习排，间隔应拉长'
        self._answer(anon_client, learner, 's-whole-2', 'q2', False)
        self._answer(anon_client, learner, 's-whole-2', 'q3', False)
        progress = self._progress(app, learner)
        assert progress['count'] == 2, '同一节里每题都重算，复习次数只算一次'
        assert progress['days'] <= 1.01

    def test_replay_changes_neither_progress_nor_schedule(self, app, anon_client):
        learner = _learner('sm2replay')
        self._session(anon_client, learner, 's-replay-1')
        for q in ('q1', 'q2', 'q3'):
            self._answer(anon_client, learner, 's-replay-1', q, True)
        # 4 对 1 错 = 80%，算通过
        self._session(anon_client, learner, 's-replay-2')
        for q, ok in (('q1', True), ('q2', True), ('q3', True), ('q4', True), ('q5', False)):
            self._answer(anon_client, learner, 's-replay-2', q, ok)
        before = self._progress(app, learner)
        assert before['days'] > 2

        self._answer(anon_client, learner, 's-replay-2', 'q5', False)
        assert _stored(self._progress(app, learner)) == _stored(before), '重放的作答不能改累计正确率与日程'
        assert self._records(app, 's-replay-2') == 6, '原始作答照常保留'

    def test_late_answer_to_older_session_does_not_rewind(self, app, anon_client):
        learner = _learner('sm2older')
        self._session(anon_client, learner, 's-older-1')
        self._answer(anon_client, learner, 's-older-1', 'q1', True)
        self._session(anon_client, learner, 's-older-2')
        self._answer(anon_client, learner, 's-older-2', 'q1', True)
        before = self._progress(app, learner)
        assert before['count'] == 2

        self._answer(anon_client, learner, 's-older-1', 'q2', False)
        after = self._progress(app, learner)
        assert after['count'] == 2
        assert after['next'] == before['next']

    def test_concurrent_answers_end_in_the_full_session_schedule(self, app):
        from concurrent.futures import ThreadPoolExecutor
        learner = _learner('sm2concurrent')
        # 先完成一节：第二节若按单题的「对」排会是多日间隔，按整节的「错」才是一天
        self._session(app.test_client(), learner, 's-conc-1')
        self._answer(app.test_client(), learner, 's-conc-1', 'q1', True)
        self._session(app.test_client(), learner, 's-conc-2')
        answers = [('q1', True), ('q2', False), ('q3', True), ('q4', False), ('q5', True), ('q6', True)]
        with ThreadPoolExecutor(max_workers=len(answers)) as pool:
            list(pool.map(lambda a: self._answer(app.test_client(), learner, 's-conc-2', *a), answers))
        progress = self._progress(app, learner)
        assert progress['attempts'] == 1 + len(answers), '并发累加不能丢计数'
        assert progress['count'] == 2
        assert progress['days'] <= 1.01, '最后写入的日程必须基于整节 4/6 的作答'

    def test_answer_is_kept_when_scheduling_fails(self, app, anon_client, monkeypatch):
        import app_phase as mod
        learner = _learner('sm2failure')
        self._session(anon_client, learner, 's-fail-1')
        self._answer(anon_client, learner, 's-fail-1', 'q1', True)
        before = self._progress(app, learner)

        def broken(*_args, **_kwargs):
            raise RuntimeError('boom')
        monkeypatch.setattr(mod, 'schedule_review_from_session', broken)
        self._answer(anon_client, learner, 's-fail-1', 'q2', True)
        assert self._records(app, 's-fail-1') == 2, '调度出错时作答仍要保存'
        assert _stored(self._progress(app, learner)) == _stored(before), '这次的进度累加随调度失败一起撤回'

    def test_second_writer_waits_for_the_first(self, app, monkeypatch):
        """先到的请求在持锁期间停顿，后到的请求必须等它提交后再读写，不能读到旧进度"""
        import threading
        import time
        import app_phase as mod
        learner = _learner('sm2lockwait')
        # 先完成一节：既建好进度行（之后的累加只改内存里的对象，不会在停顿前自己写库
        # 拿到锁），也让第二节按单题的「对」排和按整节的「错」排间隔明显不同
        self._session(app.test_client(), learner, 's-lock-0')
        self._answer(app.test_client(), learner, 's-lock-0', 'q0', True)
        self._session(app.test_client(), learner, 's-lock-1')

        original = mod.schedule_review_from_session
        first_inside = threading.Event()

        def slow_first(session, progress):
            if not first_inside.is_set():
                first_inside.set()
                # 持着写锁停顿，模拟慢请求。主线程若被耽搁超过这个窗口，两个请求就成了
                # 先后执行，测试照样通过，只是没测到竞争
                time.sleep(0.5)
            return original(session, progress)
        monkeypatch.setattr(mod, 'schedule_review_from_session', slow_first)

        first = threading.Thread(target=self._answer, args=(app.test_client(), learner, 's-lock-1', 'q1', True))
        first.start()
        assert first_inside.wait(5)
        self._answer(app.test_client(), learner, 's-lock-1', 'q2', False)
        first.join()

        progress = self._progress(app, learner)
        assert progress['attempts'] == 3, '后到的请求读到了先到者提交前的进度，计数丢了'
        assert progress['count'] == 2
        assert progress['days'] <= 1.01, '最终日程必须基于整节两道题（1/2 未过）'


# ================================================
# 会话 VKS 初始档位补写（换设备时服务器档位晚到）
# ================================================

class TestSessionInitialLevel:
    LEARNER = _learner('vkslatelevel')

    def _start(self, client, session_id, level=None):
        body = {'sessionId': session_id, 'wordId': 1, 'sessionType': 'learning',
                'moduleType': 'word', 'startTime': '2026-01-01T10:00:00'}
        if level:
            body['initialLevel'] = level
        resp = client.post('/api/learning/session/start', json=body, headers=guest_headers(self.LEARNER))
        assert resp.get_json()['success'] is True, resp.get_json()

    def _set(self, client, session_id, level, learner=None):
        return client.post('/api/learning/session/initial-level',
                           json={'sessionId': session_id, 'initialLevel': level},
                           headers=guest_headers(learner or self.LEARNER))

    def _level(self, app, session_id):
        import app_phase as mod
        with app.app_context():
            return mod.LearningSession.query.filter_by(session_id=session_id).one().initial_level

    def test_fills_missing_level_once(self, app, anon_client):
        self._start(anon_client, 's-vks-late')
        resp = self._set(anon_client, 's-vks-late', 'C')
        assert resp.get_json() == {'success': True, 'updated': True}
        assert self._level(app, 's-vks-late') == 'C'

        # 已有档位不覆盖：初始档位是开始学这个词时的自评
        resp = self._set(anon_client, 's-vks-late', 'A')
        assert resp.get_json() == {'success': True, 'updated': False}
        assert self._level(app, 's-vks-late') == 'C'

    def test_does_not_overwrite_level_given_at_start(self, app, anon_client):
        self._start(anon_client, 's-vks-early', level='B')
        assert self._set(anon_client, 's-vks-early', 'D').get_json()['updated'] is False
        assert self._level(app, 's-vks-early') == 'B'

    def test_rejects_invalid_level_unknown_and_foreign_sessions(self, app, anon_client):
        self._start(anon_client, 's-vks-guard')
        assert self._set(anon_client, 's-vks-guard', 'F').status_code == 400
        assert self._set(anon_client, 's-vks-guard', None).status_code == 400
        assert self._set(anon_client, 's-vks-missing', 'C').status_code == 404
        assert self._set(anon_client, 's-vks-guard', 'C', learner=OTHER_GUEST).status_code == 403
        assert anon_client.post('/api/learning/session/initial-level',
                                json={'sessionId': 's-vks-guard', 'initialLevel': 'C'}).status_code == 401
        assert self._level(app, 's-vks-guard') is None


# ================================================
# 推荐反馈：是否采纳 + 推荐效果
# ================================================

class TestRecommendationFeedback:
    def _recommend(self, client, learner):
        resp = client.get(f'/api/adaptive/recommendation/{learner}', headers=guest_headers(learner))
        data = resp.get_json()['data']
        assert data.get('recommendationId'), data
        return data['recommendationId'], data['word_id']

    def _feedback(self, client, learner, rec_id, accepted, choice='word:1'):
        return client.post('/api/adaptive/feedback', json={
            'recommendationId': rec_id, 'accepted': accepted, 'actualChoice': choice,
        }, headers=guest_headers(learner))

    def _rec(self, app, rec_id):
        import app_phase as mod
        with app.app_context():
            rec = mod.db.session.get(mod.AdaptiveRecommendation, rec_id)
            return rec.is_accepted, rec.actual_choice, rec.effectiveness_score

    def _exercise_session(self, client, learner, session_id, word_id, answers, rec_id=None):
        body = {'sessionId': session_id, 'wordId': word_id, 'sessionType': 'exercise',
                'moduleType': 'exercise', 'startTime': '2026-01-01T10:00:00'}
        if rec_id is not None:
            body['recommendationId'] = rec_id
        client.post('/api/learning/session/start', json=body, headers=guest_headers(learner))
        for i, ok in enumerate(answers):
            client.post('/api/learning/exercise/record', json={
                'sessionId': session_id, 'questionId': f'q{i}', 'questionType': 'definition',
                'userAnswer': 'x', 'correctAnswer': 'x', 'isCorrect': ok,
                'startTime': '2026-01-01T10:00:00', 'endTime': '2026-01-01T10:00:05',
            }, headers=guest_headers(learner))

    def _bound(self, app, session_id):
        import app_phase as mod
        with app.app_context():
            return mod.LearningSession.query.filter_by(session_id=session_id).one().recommendation_id

    def test_first_answer_wins_and_is_private(self, app, anon_client):
        learner = _learner('recfeedback')
        rec_id, _ = self._recommend(anon_client, learner)
        assert self._feedback(anon_client, learner, rec_id, True, 'word:5').get_json() == {'success': True, 'updated': True}
        assert self._feedback(anon_client, learner, rec_id, False, 'today-review').get_json()['updated'] is False
        assert self._rec(app, rec_id)[:2] == (True, 'word:5')

        assert self._feedback(anon_client, OTHER_GUEST, rec_id, False).status_code == 404
        assert self._feedback(anon_client, learner, 999999, True).status_code == 404
        assert self._feedback(anon_client, learner, rec_id, 'yes').status_code == 400
        assert self._feedback(anon_client, learner, str(rec_id), True).status_code == 400
        assert self._feedback(anon_client, learner, True, True).status_code == 400, 'bool 不能当 id'
        assert anon_client.post('/api/adaptive/feedback', json={
            'recommendationId': rec_id, 'accepted': True}).status_code == 401

    def test_effectiveness_is_first_bound_session(self, app, anon_client):
        learner = _learner('receffect')
        rec_id, word_id = self._recommend(anon_client, learner)
        # 反馈请求丢了：照推荐建会话本身就记为采纳
        self._exercise_session(anon_client, learner, 's-receffect-1', word_id, [True, True, False, True], rec_id)
        assert self._bound(app, 's-receffect-1') == rec_id
        assert self._rec(app, rec_id) == (True, f'exercise:{word_id}', 0.75)
        # 之后绑定同一推荐的练习、没绑定的练习都不改它
        self._exercise_session(anon_client, learner, 's-receffect-2', word_id, [False, False], rec_id)
        self._exercise_session(anon_client, learner, 's-receffect-3', word_id, [False])
        assert self._rec(app, rec_id)[2] == 0.75

    def test_session_binds_only_own_recommendation_for_that_word(self, app, anon_client):
        learner = _learner('recbinding')
        rec_id, word_id = self._recommend(anon_client, learner)
        other_word = word_id + 1 if word_id != 1 else 2
        self._exercise_session(anon_client, learner, 's-recbind-word', other_word, [True], rec_id)
        self._exercise_session(anon_client, OTHER_GUEST, 's-recbind-user', word_id, [True], rec_id)
        self._exercise_session(anon_client, learner, 's-recbind-bool', word_id, [True], True)
        assert self._bound(app, 's-recbind-word') is None
        assert self._bound(app, 's-recbind-user') is None
        assert self._bound(app, 's-recbind-bool') is None
        assert self._rec(app, rec_id) == (None, None, None)

    def test_rejected_recommendation_stays_rejected(self, app, anon_client):
        learner = _learner('recrejected')
        rec_id, word_id = self._recommend(anon_client, learner)
        self._feedback(anon_client, learner, rec_id, False, 'today-review')
        # 即使之后的会话带着这条推荐，「没采纳」的结论也不改
        self._exercise_session(anon_client, learner, 's-recrejected-1', word_id, [True], rec_id)
        assert self._rec(app, rec_id) == (False, 'today-review', None)

    def test_learning_state_carries_recommendation_across_devices(self, app, anon_client):
        learner = _learner('recsync')
        rec_id, word_id = self._recommend(anon_client, learner)
        state = {'wordId': word_id, 'word': 'x', 'module': 'word', 'vksLevel': 'B', 'recommendationId': rec_id}
        assert anon_client.put(f'/api/users/{learner}/learning-state', json=state,
                               headers=guest_headers(learner)).get_json()['success']
        data = anon_client.get(f'/api/users/{learner}/learning-state', headers=guest_headers(learner)).get_json()['data']
        assert data['recommendationId'] == rec_id

        anon_client.put(f'/api/users/{learner}/learning-state', json={**state, 'recommendationId': 'oops'},
                        headers=guest_headers(learner))
        data = anon_client.get(f'/api/users/{learner}/learning-state', headers=guest_headers(learner)).get_json()['data']
        assert data['recommendationId'] is None

        # 旧页面不带这个字段：当作没有，不沿用之前存的推荐
        anon_client.put(f'/api/users/{learner}/learning-state', json=state, headers=guest_headers(learner))
        legacy = {k: v for k, v in state.items() if k != 'recommendationId'}
        anon_client.put(f'/api/users/{learner}/learning-state', json=legacy, headers=guest_headers(learner))
        data = anon_client.get(f'/api/users/{learner}/learning-state', headers=guest_headers(learner)).get_json()['data']
        assert data['recommendationId'] is None

    def test_registration_keeps_guest_recommendation(self, app):
        client = app.test_client()
        learner = _learner('recmerge')
        rec_id, word_id = self._recommend(client, learner)
        client.put(f'/api/users/{learner}/learning-state', json={
            'wordId': word_id, 'module': 'word', 'recommendationId': rec_id}, headers=guest_headers(learner))
        reg = client.post('/api/auth/register', json={'username': 'rec_merge_user', 'password': 'secret123'},
                          headers=guest_headers(learner)).get_json()
        assert reg['success'], reg
        account = reg['data']['user_id']
        login = client.post('/api/auth/login', json={'username': 'rec_merge_user', 'password': 'secret123'}).get_json()
        token = login['data']['session_token']
        data = client.get(f'/api/users/{account}/learning-state', headers={'X-Session-Token': token}).get_json()['data']
        assert data['recommendationId'] == rec_id
        # 推荐本身也归到了账号名下（访客身份已找不到它），换设备续学时建的会话仍能绑定它
        # 新 client：登录后的 client 带着账号 cookie，身份会认成账号
        assert self._feedback(app.test_client(), learner, rec_id, True).status_code == 404


# ================================================
# 论文表 4.2：复习内容与次数
# ================================================

class TestThesisReviewPlan:
    """次数在第一节练习定下；之后每节练习算一次复习，只出还需复习的题型"""

    @pytest.fixture(autouse=True)
    def _engine(self):
        import app_phase as mod
        if mod.spaced_repetition is None:
            pytest.skip('自适应引擎未加载')

    def _questions(self, client, learner):
        data = client.get('/api/learning/word/1/exercises?limit=10', headers=guest_headers(learner)).get_json()['data']
        return data['questions'], data.get('reviewTypes')

    def _session(self, client, learner, session_id, level=None, wrong_types=(), answer_types=None):
        body = {'sessionId': session_id, 'wordId': 1, 'sessionType': 'exercise',
                'moduleType': 'exercise', 'startTime': '2026-01-01T10:00:00'}
        if level:
            body['initialLevel'] = level
        client.post('/api/learning/session/start', json=body, headers=guest_headers(learner))
        questions, _ = self._questions(client, learner)
        wrong_once = set()
        for q in questions:
            if answer_types is not None and q['type'] not in answer_types:
                continue
            # 每个答错的题型只错第一道（两道搭配题错一道就算搭配题错）
            ok = not (q['type'] in wrong_types and q['type'] not in wrong_once)
            if not ok:
                wrong_once.add(q['type'])
            client.post('/api/learning/exercise/record', json={
                'sessionId': session_id, 'questionId': q['id'], 'questionType': q['type'],
                'userAnswer': 'x', 'correctAnswer': 'x', 'isCorrect': ok,
                'startTime': '2026-01-01T10:00:00', 'endTime': '2026-01-01T10:00:05',
            }, headers=guest_headers(learner))
        return questions

    def _plan(self, app, learner):
        import app_phase as mod
        from datetime import datetime
        with app.app_context():
            state = mod.review_state(learner, 1)
            progress = mod.UserProgress.query.filter_by(user_id=learner, word_id=1).one()
            days = (progress.next_review_suggested - datetime.utcnow()).total_seconds() / 86400
            return state['targets'], state['remaining'], state['reviews_done'], days

    def test_targets_follow_table_4_2(self, app, anon_client):
        # C 档：释义对 → 不复习；搭配错一道 → 6 次；填词对 → C 档 4 次
        learner = _learner('plantargets')
        self._session(anon_client, learner, 's-plan-c1', level='C', wrong_types={'collocation'})
        targets, remaining, done, days = self._plan(app, learner)
        assert targets == {'definition': 0, 'collocation': 6, 'fill_word': 4}
        assert remaining == targets and done == 0
        assert 0.9 < days < 1.1, '第一节之后隔 1 天复习'

    def test_wrong_definition_reviews_six_times_regardless_of_level(self, app, anon_client):
        learner = _learner('plandefwrong')
        self._session(anon_client, learner, 's-plan-e1', level='E', wrong_types={'definition'})
        targets, _, _, _ = self._plan(app, learner)
        assert targets == {'definition': 6, 'collocation': 2, 'fill_word': 2}

    def test_no_vks_level_uses_the_strictest_base(self, app, anon_client):
        learner = _learner('plannolevel')
        self._session(anon_client, learner, 's-plan-n1')
        targets, _, _, _ = self._plan(app, learner)
        assert targets == {'definition': 0, 'collocation': 5, 'fill_word': 5}

    def test_reviews_count_down_and_only_remaining_types_are_asked(self, app, anon_client):
        learner = _learner('plancountdown')
        self._session(anon_client, learner, 's-plan-d1', level='D', wrong_types={'fill_word'})
        targets, _, _, _ = self._plan(app, learner)
        assert targets == {'definition': 0, 'collocation': 3, 'fill_word': 6}

        intervals = []
        for n in range(1, 7):
            questions, review_types = self._questions(anon_client, learner)
            # 学习期只出还需复习的题型：释义题答对了，不再出
            assert {q['type'] for q in questions} == set(review_types)
            assert 'definition' not in review_types
            self._session(anon_client, learner, f's-plan-d{n + 1}')
            _, remaining, done, days = self._plan(app, learner)
            intervals.append(round(days))
            assert done == n
        assert remaining == {'definition': 0, 'collocation': 0, 'fill_word': 0}
        # 学习期间隔 2、2、3、3、3（第一节之后的 1 天见上一个测试）；6 次复习完转入 SM-2 巩固
        assert intervals[:5] == [2, 2, 3, 3, 3]
        assert intervals[5] >= 7, '达标后的首个巩固间隔约一周起'
        _, review_types = self._questions(anon_client, learner)
        assert review_types is None, '达标后恢复出全部题型'

    def test_review_starts_with_material_for_last_wrong_type(self, app, anon_client):
        import app_phase as mod
        learner = _learner('planmaterial')
        self._session(anon_client, learner, 's-plan-m1', level='B', wrong_types={'collocation'})
        with app.app_context():
            assert mod.review_entry_module(learner, 1) == 'collocation'
            mod.UserProgress.query.filter_by(user_id=learner, word_id=1).update(
                {'next_review_suggested': mod.datetime.utcnow() - mod.timedelta(hours=1)})
            mod.db.session.commit()
        due = anon_client.get(f'/api/review/user/{learner}/due', headers=guest_headers(learner)).get_json()['data']
        item = next(r for r in due if r['word_id'] == 1)
        assert item['recommended_module'] == 'collocation'
        assert item['reviews_remaining'] == 6
        assert item['review_types'] == ['collocation', 'fill_word']

        # 下一节全对：复习直接从练习开始
        self._session(anon_client, learner, 's-plan-m2')
        with app.app_context():
            assert mod.review_entry_module(learner, 1) == 'exercise'

    def test_unfinished_first_session_does_not_drop_question_types(self, app, anon_client):
        """第一节只答了释义题就离开：没答到的搭配、填词题不能当成「不复习」"""
        import app_phase as mod
        learner = _learner('planunfinished')
        self._session(anon_client, learner, 's-plan-u1', level='B', answer_types={'definition'})
        with app.app_context():
            state = mod.review_state(learner, 1)
        assert state['targets'] == {'definition': 0}
        assert state['pending'] == ['collocation', 'fill_word']
        assert not state['completed'], '还有题型没做过第一次练习，不能算达标'
        _, review_types = self._questions(anon_client, learner)
        assert set(review_types) == {'collocation', 'fill_word'}

        # 下一节答到搭配、填词：它们这时才定次数（B 档全对各 5 次）
        self._session(anon_client, learner, 's-plan-u2')
        with app.app_context():
            state = mod.review_state(learner, 1)
        assert state['targets'] == {'definition': 0, 'collocation': 5, 'fill_word': 5}
        assert state['remaining'] == {'definition': 0, 'collocation': 5, 'fill_word': 5}

    def test_late_vks_level_updates_targets(self, app, anon_client):
        """第一节练习时还没有档位，之后补写成 E：次数按 E 档重新推出"""
        import app_phase as mod
        learner = _learner('planlatevks')
        self._session(anon_client, learner, 's-plan-l1')
        assert self._plan(app, learner)[0]['collocation'] == 5
        anon_client.post('/api/learning/session/initial-level', json={'sessionId': 's-plan-l1', 'initialLevel': 'E'},
                         headers=guest_headers(learner))
        assert self._plan(app, learner)[0] == {'definition': 0, 'collocation': 2, 'fill_word': 2}

    def test_due_word_answered_perfectly_is_still_recommended(self, app, anon_client):
        """第一次全对（掌握度 1.0）的词按表 4.2 仍要复习，到期后推荐里要有它，入口与进度按计划"""
        import app_phase as mod
        learner = _learner('planperfect')
        self._session(anon_client, learner, 's-plan-p1', level='E')
        with app.app_context():
            mod.UserProgress.query.filter_by(user_id=learner, word_id=1).update(
                {'next_review_suggested': mod.datetime.utcnow() - mod.timedelta(hours=1)})
            mod.db.session.commit()
        rec = anon_client.get(f'/api/adaptive/recommendation/{learner}', headers=guest_headers(learner)).get_json()['data']
        assert rec['type'] in ('urgent_review', 'scheduled_review') and rec['word_id'] == 1, rec
        assert rec['recommended_module'] == 'exercise'
        assert rec['reviews_remaining'] == 2 and rec['review_types'] == ['collocation', 'fill_word']

    def test_collocation_counts_only_when_both_are_answered(self, app, anon_client):
        """两道搭配题算一个整体：只答一道（对）不算练过；只答一道但错了，已经是错"""
        import app_phase as mod
        learner = _learner('plancollocpair')
        questions, _ = self._questions(anon_client, learner)
        first_colloc = next(q for q in questions if q['type'] == 'collocation')
        anon_client.post('/api/learning/session/start', json={
            'sessionId': 's-plan-pair1', 'wordId': 1, 'sessionType': 'exercise', 'moduleType': 'exercise',
            'initialLevel': 'E', 'startTime': '2026-01-01T10:00:00'}, headers=guest_headers(learner))
        anon_client.post('/api/learning/exercise/record', json={
            'sessionId': 's-plan-pair1', 'questionId': first_colloc['id'], 'questionType': 'collocation',
            'userAnswer': 'x', 'correctAnswer': 'x', 'isCorrect': True,
            'startTime': '2026-01-01T10:00:00', 'endTime': '2026-01-01T10:00:05'}, headers=guest_headers(learner))
        with app.app_context():
            state = mod.review_state(learner, 1)
            summary = mod.review_summary(state)
        assert 'collocation' not in state['targets'] and 'collocation' in state['pending']
        assert summary['reviews_remaining'] >= 1, '次数未定的题型不能显示成已掌握'

        # 复习时只答一道搭配题，也不算复习了一次搭配
        learner2 = _learner('plancollocreview')
        self._session(anon_client, learner2, 's-plan-pair2', level='E')
        self._session(anon_client, learner2, 's-plan-pair3', answer_types={'fill_word'})
        questions, _ = self._questions(anon_client, learner2)
        colloc = next(q for q in questions if q['type'] == 'collocation')
        anon_client.post('/api/learning/session/start', json={
            'sessionId': 's-plan-pair4', 'wordId': 1, 'sessionType': 'exercise', 'moduleType': 'exercise',
            'startTime': '2026-01-01T10:00:00'}, headers=guest_headers(learner2))
        anon_client.post('/api/learning/exercise/record', json={
            'sessionId': 's-plan-pair4', 'questionId': colloc['id'], 'questionType': 'collocation',
            'userAnswer': 'x', 'correctAnswer': 'x', 'isCorrect': True,
            'startTime': '2026-01-01T10:00:00', 'endTime': '2026-01-01T10:00:05'}, headers=guest_headers(learner2))
        with app.app_context():
            state = mod.review_state(learner2, 1)
        assert state['remaining'] == {'definition': 0, 'collocation': 2, 'fill_word': 1}

    def test_generated_word_still_gets_fill_in_when_collocations_fill_the_limit(self, app, anon_client):
        """没有人工命题、搭配很多的词：普通练习的 5 道题里轮不到填词，复习时要能出"""
        import app_phase as mod
        learner = _learner('plangenerated')
        with app.app_context():
            word = mod.Word(pinyin='cèshì', definition='test')
            mod.db.session.add(word)
            mod.db.session.flush()
            for char, pinyin in (('测', 'cè'), ('试', 'shì')):
                mod.db.session.add(mod.Character(character=char, pinyin=pinyin, definition='', audio='', word_id=word.id))
            for i in range(4):
                mod.db.session.add(mod.Collocation(collocation=f'测试搭配{i}', translation='t', audio='', word_id=word.id))
            mod.db.session.add(mod.Example(sentence='他们在测试新系统。', pinyin='', translation='t', audio='', word_id=word.id))
            mod.db.session.commit()
            word_id = word.id
            assert mod.question_requirements(word_id) == {'definition': 1, 'collocation': 2, 'fill_word': 1}
        data = anon_client.get(f'/api/learning/word/{word_id}/exercises', headers=guest_headers(learner)).get_json()['data']
        assert 'fill_word' not in {q['type'] for q in data['questions']}, '普通练习仍按原来的顺序截断'

        anon_client.post('/api/learning/session/start', json={
            'sessionId': 's-plan-gen1', 'wordId': word_id, 'sessionType': 'exercise', 'moduleType': 'exercise',
            'initialLevel': 'D', 'startTime': '2026-01-01T10:00:00'}, headers=guest_headers(learner))
        for q in data['questions']:
            anon_client.post('/api/learning/exercise/record', json={
                'sessionId': 's-plan-gen1', 'questionId': q['id'], 'questionType': q['type'],
                'userAnswer': 'x', 'correctAnswer': 'x', 'isCorrect': True,
                'startTime': '2026-01-01T10:00:00', 'endTime': '2026-01-01T10:00:05'}, headers=guest_headers(learner))
        review = anon_client.get(f'/api/learning/word/{word_id}/exercises', headers=guest_headers(learner)).get_json()['data']
        assert 'fill_word' in {q['type'] for q in review['questions']}
        assert set(review['reviewTypes']) == {'collocation', 'fill_word'}

    def test_null_mastery_due_row_does_not_break_recommendation(self, app, anon_client):
        import app_phase as mod
        learner = _learner('plannullmastery')
        with app.app_context():
            mod.db.session.add(mod.UserProgress(user_id=learner, word_id=7, mastery_level=None,
                                                next_review_suggested=mod.datetime.utcnow() - mod.timedelta(hours=1)))
            mod.db.session.commit()
        rec = anon_client.get(f'/api/adaptive/recommendation/{learner}', headers=guest_headers(learner)).get_json()['data']
        assert rec['type'] != 'system_default', rec


# ================================================
# 易混淆词辨析：解锁时机与辨析题（论文 2.2.4、3.2.4）
# ================================================

class TestConfusableContrast:
    """两个词分别掌握到一定程度后才带出辨析（目标词学习期复习完，易混淆词学过并复习过一次）；辨析题全对后不再带出"""

    QUESTIONS = [
        {'question_type': 'confusable', 'stem': '我 ( ) 我这次做到了。', 'options': ['考虑', '想'], 'correct_answer': '想'},
        {'question_type': 'confusable', 'stem': '这房子可以 ( ) 。', 'options': ['想', '考虑'], 'correct_answer': '考虑'},
    ]

    @pytest.fixture(autouse=True)
    def _engine(self):
        import app_phase as mod
        if mod.spaced_repetition is None:
            pytest.skip('自适应引擎未加载')

    @pytest.fixture
    def pair(self, app):
        """在词 1 和一个新词之间建一对带辨析题的易混淆词，测完删掉"""
        import json
        import app_phase as mod
        with app.app_context():
            other = mod.Word(pinyin='xiǎng', definition='v. to think')
            mod.db.session.add(other)
            mod.db.session.flush()
            row = mod.ConfusablePair(word1_id=1, word2_id=other.id, reason='r', difference='d', examples='e', tips='t',
                                     difficulty_level=2, questions=json.dumps(self.QUESTIONS, ensure_ascii=False))
            mod.db.session.add(row)
            mod.db.session.commit()
            ids = (row.id, other.id)
        yield ids
        with app.app_context():
            mod.ConfusableExerciseRecord.query.filter_by(pair_id=ids[0]).delete()
            mod.db.session.delete(mod.db.session.get(mod.ConfusablePair, ids[0]))
            mod.db.session.delete(mod.db.session.get(mod.Word, ids[1]))
            mod.db.session.commit()

    def _practise(self, client, learner, word_id, session_id, correct=True):
        """一节练习：词 1 按出题接口全部作答（VKS 选 E，答对时表 4.2 复习 2 次达标）；没有素材的词答一道就算练过"""
        client.post('/api/learning/session/start', json={
            'sessionId': session_id, 'wordId': word_id, 'sessionType': 'exercise', 'moduleType': 'exercise',
            'initialLevel': 'E', 'startTime': '2026-01-01T10:00:00'}, headers=guest_headers(learner))
        if word_id == 1:
            data = client.get('/api/learning/word/1/exercises?limit=10', headers=guest_headers(learner)).get_json()['data']
            questions = [(q['id'], q['type']) for q in data['questions']]
        else:
            questions = [(f'definition-{word_id}', 'definition')]
        for question_id, question_type in questions:
            client.post('/api/learning/exercise/record', json={
                'sessionId': session_id, 'questionId': question_id, 'questionType': question_type,
                'userAnswer': 'x', 'correctAnswer': 'x', 'isCorrect': correct,
                'startTime': '2026-01-01T10:00:00', 'endTime': '2026-01-01T10:00:05',
            }, headers=guest_headers(learner))

    def _unlock(self, client, learner, prefix, *others):
        """目标词（词 1）学习期复习完：学 1 次 + 复习 2 次；其他词学过并复习过一次"""
        for n, word in enumerate((1, 1, 1) + tuple(w for w in others for _ in range(2))):
            self._practise(client, learner, word, f'{prefix}{n}')

    def _offered(self, client, learner):
        return client.get('/api/confusable/for-word/1', headers=guest_headers(learner)).get_json()['pair_id']

    def _answer(self, client, learner, pair_id, index, correct, questions=None, attempt_id=None, answer=None):
        import uuid
        from confusable_api import question_version
        q = (questions or self.QUESTIONS)[index]
        if answer is None:
            answer = q['correct_answer'] if correct else next(o for o in q['options'] if o != q['correct_answer'])
        return client.post('/api/confusable/exercise/record', headers=guest_headers(learner), json={
            'pair_id': pair_id, 'question_index': index, 'question_version': question_version(q), 'user_answer': answer,
            'response_time': 2.0, 'attempt_id': attempt_id or uuid.uuid4().hex})

    def test_offered_only_after_both_words_were_reviewed(self, anon_client, pair):
        pair_id, other = pair
        learner = _learner('contrastunlock')
        assert self._offered(anon_client, learner) is None, '还没学过，不带出'
        self._practise(anon_client, learner, 1, 's-contrast-1')
        self._practise(anon_client, learner, other, 's-contrast-o1')
        assert self._offered(anon_client, learner) is None, '刚学完第一次（论文：先分开学）'
        self._practise(anon_client, learner, 1, 's-contrast-2')
        self._practise(anon_client, learner, other, 's-contrast-o2')
        assert self._offered(anon_client, learner) is None, '目标词只复习了 1 次，学习期（E 档 2 次）还没复习完'
        self._practise(anon_client, learner, 1, 's-contrast-3')
        assert self._offered(anon_client, learner) == pair_id, '目标词复习完、易混淆词复习过一次'
        assert anon_client.get('/api/confusable/for-word/1').get_json()['pair_id'] is None, '认不出身份时不带出'

    def test_confusable_word_needs_one_review(self, app, anon_client, pair):
        import app_phase as mod
        pair_id, other = pair
        with app.app_context():
            # 有了字才出得了释义题；第一次答错要复习 6 次，学过一次时还没复习完
            char = mod.Character(character='想', pinyin='xiǎng', definition='to think', audio='', word_id=other)
            mod.db.session.add(char)
            mod.db.session.commit()
            char_id = char.id
        try:
            learner = _learner('contrastconfusable')
            for n in range(3):
                self._practise(anon_client, learner, 1, f's-contrast-t{n}')
            self._practise(anon_client, learner, other, 's-contrast-t3', correct=False)
            assert self._offered(anon_client, learner) is None, '目标词复习完了，易混淆词只学过一次'
            self._practise(anon_client, learner, other, 's-contrast-t4')
            assert self._offered(anon_client, learner) == pair_id
        finally:
            with app.app_context():
                mod.db.session.delete(mod.db.session.get(mod.Character, char_id))
                mod.db.session.commit()

    def test_confusable_word_done_on_first_practice_still_needs_a_review(self, anon_client, pair):
        # 没有素材的词第一次练习就达标（没有要复习的题型），但还没复习过
        pair_id, other = pair
        learner = _learner('contrastnoreview')
        for n in range(3):
            self._practise(anon_client, learner, 1, f's-contrast-n{n}')
        self._practise(anon_client, learner, other, 's-contrast-n3')
        assert self._offered(anon_client, learner) is None, '易混淆词达标了，但一次都没复习'
        self._practise(anon_client, learner, other, 's-contrast-n4')
        assert self._offered(anon_client, learner) == pair_id, '达标以后又练过一次，算复习过'

    def test_hsk4_confusable_must_finish_its_learning_phase(self, app, anon_client, pair):
        import app_phase as mod
        pair_id, other = pair
        with app.app_context():
            mod.db.session.get(mod.ConfusablePair, pair_id).word2_level = 4
            # 有了字才出得了释义题；第一次答错要复习 6 次
            char = mod.Character(character='想', pinyin='xiǎng', definition='to think', audio='', word_id=other)
            mod.db.session.add(char)
            mod.db.session.commit()
            char_id = char.id
        try:
            learner = _learner('contrasthsk4')
            for n in range(3):
                self._practise(anon_client, learner, 1, f's-contrast-h{n}')
            self._practise(anon_client, learner, other, 's-contrast-h3', correct=False)
            for n in range(4, 9):
                self._practise(anon_client, learner, other, f's-contrast-h{n}')
            assert self._offered(anon_client, learner) is None, '四级的易混淆词复习了 5 次，还差 1 次'
            self._practise(anon_client, learner, other, 's-contrast-h9')
            assert self._offered(anon_client, learner) == pair_id, '两个四级词都学习期复习完'
        finally:
            with app.app_context():
                mod.db.session.delete(mod.db.session.get(mod.Character, char_id))
                mod.db.session.get(mod.ConfusablePair, pair_id).word2_level = None
                mod.db.session.commit()

    def test_passing_the_quiz_stops_offering_until_a_wrong_answer(self, anon_client, pair):
        pair_id, other = pair
        learner = _learner('contrastpass')
        self._unlock(anon_client, learner, 's-contrast-p', other)
        assert self._offered(anon_client, learner) == pair_id
        self._answer(anon_client, learner, pair_id, 0, True)
        self._answer(anon_client, learner, pair_id, 0, True)
        assert self._offered(anon_client, learner) == pair_id, '同一题答对两次不算过关，第 2 题还没答'
        self._answer(anon_client, learner, pair_id, 1, True)
        assert self._offered(anon_client, learner) is None, '每道题最近一次都对，不再带出'
        self._answer(anon_client, learner, pair_id, 1, False)
        assert self._offered(anon_client, learner) == pair_id, '有题最近一次答错，下次再带出'

    def test_reports_whether_the_pair_was_attempted(self, anon_client, pair):
        pair_id, other = pair
        learner = _learner('contrastattempted')
        self._unlock(anon_client, learner, 's-contrast-a', other)
        get = lambda: anon_client.get('/api/confusable/for-word/1', headers=guest_headers(learner)).get_json()
        assert get() == {'success': True, 'pair_id': pair_id, 'attempted': False}
        self._answer(anon_client, learner, pair_id, 0, False)
        assert get() == {'success': True, 'pair_id': pair_id, 'attempted': True}, '做过没全对：再带出时直接展开讲解'

    def test_server_judges_answers_and_validates_input(self, app, anon_client, pair):
        import app_phase as mod
        pair_id, _ = pair
        learner = _learner('contrastjudge')
        from confusable_api import question_version
        v = question_version(self.QUESTIONS[0])
        post = lambda body: anon_client.post('/api/confusable/exercise/record', json=body, headers=guest_headers(learner))
        wrong = post({'pair_id': pair_id, 'question_index': 0, 'question_version': v, 'user_answer': '考虑', 'is_correct': True})
        assert wrong.status_code == 200 and wrong.get_json()['is_correct'] is False, '客户端报的对错不用'
        assert wrong.get_json()['correct_answer'] == '想'
        assert post({'pair_id': 99999, 'question_index': 0, 'question_version': v, 'user_answer': '想'}).status_code == 404
        assert post({'pair_id': pair_id, 'question_index': 5, 'question_version': v, 'user_answer': '想'}).status_code == 409, '题目撤下了'
        assert post({'pair_id': pair_id, 'question_index': 0, 'question_version': v, 'user_answer': '别的'}).status_code == 400
        assert post({'pair_id': pair_id, 'question_index': 0, 'question_version': 'old', 'user_answer': '想'}).status_code == 409
        assert post({'pair_id': str(pair_id), 'is_correct': True}).status_code == 400
        assert post({'pair_id': pair_id, 'is_correct': True, 'response_time': True}).status_code == 400
        assert post({'pair_id': pair_id, 'is_correct': True, 'response_time': -1}).status_code == 400
        assert anon_client.post('/api/confusable/exercise/record', json=[1], headers=guest_headers(learner)).status_code == 400
        # 重试沿用同一个作答编号：只记一条，返回当时的结果
        for _ in range(2):
            resp = self._answer(anon_client, learner, pair_id, 1, False, attempt_id='retry-1')
            assert resp.status_code == 200 and resp.get_json()['is_correct'] is False
        with app.app_context():
            assert mod.ConfusableExerciseRecord.query.filter_by(user_id=learner, attempt_id='retry-1').count() == 1
        # 同一个编号换了答案：冲突，不能报告保存成功
        conflict = self._answer(anon_client, learner, pair_id, 1, True, attempt_id='retry-1')
        assert conflict.status_code == 409 and conflict.get_json()['code'] == 'ATTEMPT_CONFLICT'

    def test_paused_when_schema_is_not_ready(self, anon_client, pair, monkeypatch):
        import app_phase as mod
        pair_id, other = pair
        learner = _learner('contrastpaused')
        self._unlock(anon_client, learner, 's-contrast-z', other)
        monkeypatch.setattr(mod, 'CONTRAST_SCHEMA_READY', False)
        assert self._offered(anon_client, learner) is None
        assert self._answer(anon_client, learner, pair_id, 0, True).status_code == 503

    def test_changed_question_must_be_answered_again(self, app, anon_client, pair):
        import json
        import app_phase as mod
        pair_id, other = pair
        learner = _learner('contrastchanged')
        self._unlock(anon_client, learner, 's-contrast-c', other)
        self._answer(anon_client, learner, pair_id, 0, True)
        self._answer(anon_client, learner, pair_id, 1, True)
        assert self._offered(anon_client, learner) is None
        changed = [dict(self.QUESTIONS[0]), dict(self.QUESTIONS[1], stem='这件事我得 ( ) 一下。')]
        with app.app_context():
            mod.db.session.get(mod.ConfusablePair, pair_id).questions = json.dumps(changed, ensure_ascii=False)
            mod.db.session.commit()
        assert self._offered(anon_client, learner) == pair_id, '第 2 题改过了，以前的作答不算'
        self._answer(anon_client, learner, pair_id, 1, True, questions=changed)
        assert self._offered(anon_client, learner) is None
        # 只改答案（题干不变）也算改过：第 1 题以前答的「想」不再算对
        changed[0] = dict(changed[0], correct_answer='考虑')
        with app.app_context():
            mod.db.session.get(mod.ConfusablePair, pair_id).questions = json.dumps(changed, ensure_ascii=False)
            mod.db.session.commit()
        assert self._offered(anon_client, learner) == pair_id

    def test_pairs_with_questions_come_before_old_pairs_without(self, app, anon_client, pair):
        import app_phase as mod
        pair_id, other = pair
        with app.app_context():
            # 词 1 另有一对编号更小、没有辨析题的旧词对
            third = mod.Word(pinyin='kàn', definition='v. to look')
            mod.db.session.add(third)
            mod.db.session.flush()
            # 编号 0：比带题的词对小，只按编号排就会先带出它
            old = mod.ConfusablePair(id=0, word1_id=third.id, word2_id=1,
                                     reason='r', difference='d', examples='e', tips='t', difficulty_level=1)
            mod.db.session.add(old)
            mod.db.session.commit()
            old_id, third_id = old.id, third.id
        assert old_id < pair_id
        try:
            learner = _learner('contrastorder')
            self._unlock(anon_client, learner, 's-contrast-r', other, third_id)
            assert self._offered(anon_client, learner) == pair_id, '有题、没过关的优先'
            self._answer(anon_client, learner, pair_id, 0, True)
            self._answer(anon_client, learner, pair_id, 1, True)
            assert self._offered(anon_client, learner) == old_id, '过关后才轮到没有题的旧词对'
        finally:
            with app.app_context():
                mod.db.session.delete(mod.db.session.get(mod.ConfusablePair, old_id))
                mod.db.session.delete(mod.db.session.get(mod.Word, third_id))
                mod.db.session.commit()

    def test_pair_payload_includes_questions(self, client, pair):
        pair_id, _ = pair
        data = client.get(f'/api/confusable/pair/{pair_id}').get_json()
        from confusable_api import question_version
        assert data['pair']['questions'] == [dict(q, version=question_version(q)) for q in self.QUESTIONS]
        listed = client.get('/api/confusable/pairs?limit=50').get_json()['pairs']
        assert all(isinstance(p['questions'], list) for p in listed)


class TestHsk4BatchImport:
    """学习资料制作第 7 步的素材：只导入作者已审核的批次；重复导入不重复插入；重新审核后的修改能同步"""

    def _word(self, hanzi, chars, definition='v. to think'):
        return {
            'hanzi': hanzi, 'pinyin': 'p', 'definition': definition,
            'characters': [{'character': c, 'pinyin': 'p', 'definition': 'd'} for c in chars],
            'collocations': [{'collocation': f'认真（三级） {hanzi}', 'translation': 'carefully'}],
            'examples': [{'sentence': f'我{hanzi}。', 'pinyin': 'p', 'translation': 'v1'}],
            'exercises': [
                # 两个词的释义题题干相同：不能被当成同一道题
                {'question_type': 'definition', 'stem': definition, 'options': [hanzi, '老师', '明天', '书'], 'correct_answer': hanzi},
                {'question_type': 'fill_word', 'stem': f'我{chars[0]} ( ) 。', 'options': [], 'correct_answer': chars[1]},
            ],
        }

    def _write(self, path, status, words, pairs=()):
        import json
        path.write_text(json.dumps({'batch': '测试批', 'status': status, 'words': words,
                                    'confusable_pairs': list(pairs)}, ensure_ascii=False), encoding='utf-8')

    def _items(self, conn, hanzi):
        return conn.execute("SELECT question_type, correct_answer FROM exercise_item WHERE source_deck = ? ORDER BY source_slide",
                            (f'HSK4 测试批 {hanzi}',)).fetchall()

    def test_only_reviewed_batches_idempotent_and_synced(self, app, tmp_path, monkeypatch):
        import sqlite3
        sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))
        import import_hsk4_batches as imp  # pyrefly: ignore  # 运行时动态路径
        db = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        monkeypatch.setattr(imp, 'BATCH_DIR', tmp_path)
        path = tmp_path / '测试批.json'
        words = [self._word('测验', '测验'), self._word('思索', '思索')]
        self._write(path, '待审核', words)
        assert imp.import_into(db) == (0, 0, 0, 0), '待审核的批次不导入'
        self._write(path, imp.APPROVED, words)
        assert imp.import_into(db) == (2, 0, 4, 0), '两个词的题干相同也各自导入'
        assert imp.import_into(db) == (0, 0, 0, 0), '重复导入不重复插入'

        # 重新审核：改了答案、撤下填字题、改了例句翻译
        words[0]['exercises'][0]['options'] = ['测验', '老师', '明天', '笔']
        words[0]['exercises'].pop()
        words[0]['examples'][0]['translation'] = 'v2'
        self._write(path, imp.APPROVED, words)
        d = imp.import_details(db)
        assert (d['items_updated'], d['items_removed'], d['items_added']) == (1, 1, 0)
        conn = sqlite3.connect(db)
        try:
            assert self._items(conn, '测验') == [('definition', '测验')]
            assert len(self._items(conn, '思索')) == 2
            word_id = imp.hanzi_map(conn)['测验']
            assert conn.execute('SELECT translation FROM example WHERE word_id = ?', (word_id,)).fetchall() == [('v2',)]
        finally:
            conn.close()
        data = app.test_client().get(f'/api/learning/word/{word_id}/exercises?limit=10').get_json()['data']
        assert data['source'] == 'authored' and [q['type'] for q in data['questions']] == ['definition']

    def test_old_pair_keeps_its_text_and_batch_pair_is_synced(self, app, tmp_path, monkeypatch):
        import json
        import sqlite3
        sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))
        import import_hsk4_batches as imp  # pyrefly: ignore  # 运行时动态路径
        db = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        monkeypatch.setattr(imp, 'BATCH_DIR', tmp_path)
        path = tmp_path / '辨析批.json'
        q = [{'question_type': 'confusable', 'stem': '我 ( ) 。', 'options': ['甲乙', '丙丁'], 'correct_answer': '甲乙'}]
        old_pair = {'word1': '甲乙', 'word2': '丙丁', 'reason': 'new', 'difference': 'd', 'examples': 'e', 'tips': 't',
                    'difficulty_level': 2, 'questions': q}
        new_pair = dict(old_pair, word1='揣摩', word2='推敲', reason='batch', word2_level=4)
        words = [self._word('揣摩', '揣摩'), self._word('推敲', '推敲')]
        write = lambda: path.write_text(json.dumps({'batch': '辨析批', 'status': imp.APPROVED, 'words': words,
                                                    'confusable_pairs': [old_pair, new_pair]}, ensure_ascii=False),
                                        encoding='utf-8')
        conn = sqlite3.connect(db)
        try:
            # 词库里已有、不归属任何批次的旧词对（没有辨析题）
            ids = []
            for chars in ('甲乙', '丙丁'):
                wid = conn.execute("INSERT INTO word (pinyin, definition) VALUES ('p', 'd')").lastrowid
                conn.executemany('INSERT INTO character (character, pinyin, definition, audio, word_id) VALUES (?, ?, ?, ?, ?)',
                                 [(c, 'p', 'd', '', wid) for c in chars])
                ids.append(wid)
            conn.execute("INSERT INTO confusable_pairs (word1_id, word2_id, reason, difference, examples, tips, difficulty_level) "
                         "VALUES (?, ?, 'old', 'd', 'e', 't', 1)", ids)
            conn.commit()
        finally:
            conn.close()
        write()
        first = imp.import_details(db)
        assert (first['pairs_added'], first['pairs_updated']) == (1, 1), '新词对插入，旧词对补题'
        old_pair['reason'], new_pair['reason'] = 'newer', 'batch v2'
        write()
        assert imp.import_details(db)['pairs_updated'] == 1, '只有归属批次的词对被同步'
        conn = sqlite3.connect(db)
        try:
            reason, questions = conn.execute('SELECT reason, questions FROM confusable_pairs WHERE word1_id = ?', (ids[0],)).fetchone()
            assert reason == 'old', '旧词对的讲解保持原样，补题以后也不被覆盖'
            assert json.loads(questions) == q
        finally:
            conn.close()
        # 补上的题由这个批次继续同步：撤下题目也能生效
        old_pair['questions'] = []
        write()
        assert imp.import_details(db)['pairs_updated'] == 1
        conn = sqlite3.connect(db)
        try:
            reason, questions = conn.execute('SELECT reason, questions FROM confusable_pairs WHERE word1_id = ?', (ids[0],)).fetchone()
            assert (reason, json.loads(questions)) == ('old', [])
            known = imp.hanzi_map(conn)
            assert conn.execute('SELECT reason, word2_level FROM confusable_pairs WHERE word1_id = ?',
                                (known['揣摩'],)).fetchone() == ('batch v2', 4), '易混淆词等级一起写入'
        finally:
            conn.close()

    def test_old_pair_gets_word2_level_in_its_stored_direction(self, app, tmp_path, monkeypatch):
        import json
        import sqlite3
        sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))
        import import_hsk4_batches as imp  # pyrefly: ignore  # 运行时动态路径
        db = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        monkeypatch.setattr(imp, 'BATCH_DIR', tmp_path)
        conn = sqlite3.connect(db)
        try:
            ids = {}
            for chars in ('琢玉', '雕石', '刻木', '磨刀'):
                ids[chars] = conn.execute("INSERT INTO word (pinyin, definition) VALUES ('p', 'd')").lastrowid
                conn.executemany('INSERT INTO character (character, pinyin, definition, audio, word_id) VALUES (?, ?, ?, ?, ?)',
                                 [(c, 'p', 'd', '', ids[chars]) for c in chars])
            # 两对没有题的旧词对：一对和素材同向，一对反向（素材里是 刻木 → 磨刀）
            for w1, w2 in (('琢玉', '雕石'), ('磨刀', '刻木')):
                conn.execute("INSERT INTO confusable_pairs (word1_id, word2_id, reason, difference, examples, tips, "
                             "difficulty_level) VALUES (?, ?, 'old', 'd', 'e', 't', 1)", (ids[w1], ids[w2]))
            conn.commit()
        finally:
            conn.close()
        q = [{'question_type': 'confusable', 'stem': '( ) 。', 'options': ['琢玉', '雕石'], 'correct_answer': '琢玉'}]
        same = {'word1': '琢玉', 'word2': '雕石', 'reason': 'new', 'difference': 'd', 'examples': 'e', 'tips': 't',
                'difficulty_level': 2, 'questions': q, 'word2_level': 4}
        reverse = dict(same, word1='刻木', word2='磨刀', word2_level=2)
        path = tmp_path / '等级批.json'
        write = lambda: path.write_text(json.dumps({'batch': '等级批', 'status': imp.APPROVED, 'words': [],
                                                    'confusable_pairs': [same, reverse]}, ensure_ascii=False),
                                        encoding='utf-8')
        level = lambda w1: sqlite3.connect(db).execute(
            'SELECT word2_level FROM confusable_pairs WHERE word1_id = ?', (ids[w1],)).fetchone()[0]
        write()
        assert imp.import_details(db)['pairs_updated'] == 2, '两对旧词对都补题'
        assert level('琢玉') == 4, '补题时写入易混淆词等级'
        assert level('磨刀') == 4, '反向存的旧词对：库里的 word2 是素材的目标词（四级）'
        assert imp.import_details(db)['pairs_updated'] == 0, '再导入不变'
        same['word2_level'] = 3
        write()
        assert imp.import_details(db)['pairs_updated'] == 1 and level('琢玉') == 3, '等级改了也同步'

    def test_word_without_exercises_stays_owned(self, app, tmp_path, monkeypatch):
        import sqlite3
        sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))
        import import_hsk4_batches as imp  # pyrefly: ignore  # 运行时动态路径
        db = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        monkeypatch.setattr(imp, 'BATCH_DIR', tmp_path)
        path = tmp_path / '空题批.json'
        word = self._word('琢磨', '琢磨')
        exercises, word['exercises'] = word['exercises'], []
        path.write_text(__import__('json').dumps({'batch': '空题批', 'status': imp.APPROVED, 'words': [word]},
                                                 ensure_ascii=False), encoding='utf-8')
        assert imp.import_details(db)['words_added'] == 1
        word['exercises'] = exercises
        path.write_text(__import__('json').dumps({'batch': '空题批', 'status': imp.APPROVED, 'words': [word]},
                                                 ensure_ascii=False), encoding='utf-8')
        d = imp.import_details(db)
        assert (d['words_synced'], d['items_added']) == (1, 2), '没有题时导入的词仍归属这个批次，补回的题能同步进去'


# ================================================
# 发音音频：库里存地址（/api/audio/<指纹>.mp3），文件在 AUDIO_DIR
# ================================================

class TestAudio:
    @staticmethod
    def _url(n):
        return f'/api/audio/{n:016x}.mp3'

    def test_serves_fingerprinted_files_only(self, client, tmp_path, monkeypatch):
        import app_phase as mod
        monkeypatch.setattr(mod, 'AUDIO_DIR', str(tmp_path))
        (tmp_path / '0123456789abcdef.mp3').write_bytes(b'ID3fake')
        (tmp_path / 'secret.txt').write_text('x')
        resp = client.get('/api/audio/0123456789abcdef.mp3')
        assert resp.status_code == 200 and resp.data == b'ID3fake' and resp.mimetype == 'audio/mpeg'
        assert 'max-age=31536000' in resp.headers.get('Cache-Control', ''), '文件名是内容指纹，可以长期缓存'
        for bad in ('secret.txt', '0123456789abcdef.wav', 'ABCDEF0123456789.mp3', 'fedcba9876543210.mp3'):
            assert client.get(f'/api/audio/{bad}').status_code == 404, bad

    def test_word_detail_includes_audio(self, app, client):
        import app_phase as mod
        with app.app_context():
            word = mod.Word(pinyin='p', definition='d', audio=self._url(1))
            mod.db.session.add(word)
            mod.db.session.commit()
            word_id = word.id
        try:
            assert client.get(f'/word/{word_id}').get_json()['audio'] == self._url(1)
        finally:
            with app.app_context():
                mod.db.session.delete(mod.db.session.get(mod.Word, word_id))
                mod.db.session.commit()

    def test_batch_import_writes_audio(self, app, tmp_path, monkeypatch):
        import json
        import sqlite3
        sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))
        import import_hsk4_batches as imp  # pyrefly: ignore  # 运行时动态路径
        db = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        monkeypatch.setattr(imp, 'BATCH_DIR', tmp_path)
        a = self._url
        word = {'hanzi': '斟酌', 'pinyin': 'zhēnzhuó', 'definition': 'v. to consider', 'audio': a(1),
                'characters': [{'character': '斟', 'pinyin': 'zhēn', 'definition': 'd', 'audio': a(2)},
                               {'character': '酌', 'pinyin': 'zhuó', 'definition': 'd', 'audio': a(3)}],
                'collocations': [{'collocation': '认真（三级） 斟酌', 'translation': 't', 'audio': a(4)}],
                'examples': [{'sentence': '我再斟酌一下。', 'pinyin': 'p', 'translation': 't', 'audio': a(5)}],
                'exercises': []}
        path = tmp_path / '音频批.json'
        write = lambda: path.write_text(json.dumps({'batch': '音频批', 'status': imp.APPROVED, 'words': [word]},
                                                   ensure_ascii=False), encoding='utf-8')

        def stored():
            conn = sqlite3.connect(db)
            try:
                word_id = imp.hanzi_map(conn)['斟酌']
                q = lambda table: [r[0] for r in conn.execute(f'SELECT audio FROM {table} WHERE word_id = ? ORDER BY id', (word_id,))]
                return (conn.execute('SELECT audio FROM word WHERE id = ?', (word_id,)).fetchone()[0],
                        q('character'), q('collocation'), q('example'))
            finally:
                conn.close()
        write()
        imp.import_details(db)
        assert stored() == (a(1), [a(2), a(3)], [a(4)], [a(5)])
        word['examples'][0]['audio'] = a(6)  # 改了拼音、重新生成：地址变了
        write()
        imp.import_details(db)
        assert stored()[3] == [a(6)], '重新导入时发音地址同步'

    def test_thesis_manifest_fills_only_empty_or_placeholder(self, app, tmp_path):
        import json
        import sqlite3
        sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))
        import apply_audio_manifest as am  # pyrefly: ignore  # 运行时动态路径
        db = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        a = self._url
        conn = sqlite3.connect(db)
        try:
            word_id = conn.execute("INSERT INTO word (pinyin, definition, audio) VALUES ('chóuchú', 'd', '')").lastrowid
            conn.executemany('INSERT INTO character (character, pinyin, definition, audio, word_id) VALUES (?, ?, ?, ?, ?)',
                             [('踌', 'chóu', 'd', '/audio/character_1.mp3', word_id), ('躇', 'chú', 'd', a(99), word_id)])
            conn.execute("INSERT INTO collocation (collocation, translation, audio, word_id) VALUES ('犹豫 踌躇', 't', '', ?)", (word_id,))
            conn.execute("INSERT INTO example (sentence, pinyin, translation, audio, word_id) VALUES ('他踌躇了很久。', 'p', 't', '', ?)",
                         (word_id,))
            conn.commit()
        finally:
            conn.close()
        manifest = tmp_path / '论文词库.json'
        manifest.write_text(json.dumps({'words': [
            {'hanzi': '踌躇', 'audio': a(7),
             'characters': [{'character': '踌', 'audio': a(8)}, {'character': '躇', 'audio': a(9)}],
             'collocations': [{'collocation': '犹豫 踌躇', 'audio': a(10)}],
             'examples': [{'sentence': '他踌躇了很久。', 'audio': a(11)}]},
            {'hanzi': '库里没有的词', 'audio': a(12), 'characters': [], 'collocations': [], 'examples': []},
        ]}, ensure_ascii=False), encoding='utf-8')
        assert am.apply(db, manifest) == 4, '空的和占位的补上，已有的（躇）不动'
        conn = sqlite3.connect(db)
        try:
            assert [r[0] for r in conn.execute('SELECT audio FROM character WHERE word_id = ? ORDER BY id', (word_id,))] == [a(8), a(99)]
            assert conn.execute('SELECT audio FROM word WHERE id = ?', (word_id,)).fetchone()[0] == a(7)
        finally:
            conn.close()
        assert am.apply(db, manifest) == 0, '再执行不变'
