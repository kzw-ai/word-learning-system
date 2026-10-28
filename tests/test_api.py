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
    del os.environ['WORDS_DB_PATH']


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
    def test_pairs_list(self, client):
        data = client.get('/api/confusable/pairs?limit=20').get_json()
        assert data['success'] is True
        assert data['total'] == 5
        pair = data['pairs'][0]
        for key in ('id', 'word1', 'word2', 'reason', 'difference', 'difficulty_level'):
            assert key in pair
        assert 'pinyin' in pair['word1'] and 'definition' in pair['word1']

    def test_pairs_difficulty_filter(self, client):
        data = client.get('/api/confusable/pairs?difficulty=1').get_json()
        assert data['success'] is True
        assert all(p['difficulty_level'] == 1 for p in data['pairs'])

    def test_single_pair(self, client):
        data = client.get('/api/confusable/pair/1').get_json()
        assert data['success'] is True
        assert data['pair']['id'] == 1

    def test_single_pair_not_found(self, client):
        resp = client.get('/api/confusable/pair/9999')
        assert resp.status_code == 404

    def test_record_requires_auth(self, anon_client):
        resp = anon_client.post('/api/confusable/exercise/record', json={
            'pair_id': 1, 'is_correct': True, 'response_time': 3.0,
        })
        assert resp.status_code == 401

    def test_record_with_session_token(self, client, auth_session):
        user_id, token = auth_session
        resp = client.post(
            '/api/confusable/exercise/record',
            json={'pair_id': 1, 'is_correct': True, 'response_time': 3.0},
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
    """一次复习 = 一节练习。日程按整节作答排，复习次数按会话数算。每个测试用自己的学习者"""

    @pytest.fixture(autouse=True)
    def _engine(self):
        import app_phase as mod
        if mod.spaced_repetition is None:
            pytest.skip('自适应引擎未加载')

    def _session(self, client, learner, session_id):
        resp = client.post('/api/learning/session/start', json={
            'sessionId': session_id, 'wordId': 1,
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
            row = mod.UserProgress.query.filter_by(user_id=learner, word_id=1).one()
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
