#!/usr/bin/env python3
"""
易混淆词辨析 API扩展
添加到 app_phase.py 中
"""

import hashlib
import json
import re

from flask import jsonify, request
from sqlalchemy import text

from user_data_isolation import get_current_user_from_request

# 无 character 行的词，pinyin 列里混写了汉字，形如 '突然 tūrán'
HANZI_PREFIX = re.compile(r'^([\u4e00-\u9fff]+)\s+(.+)$')

def question_version(question):
    """一道辨析题的版本号：题干、选项、答案任何一项改了，版本号就变。作答记下它，改过的题以前的作答不再算数"""
    key = {k: question.get(k) for k in ('stem', 'options', 'correct_answer')}
    return hashlib.sha256(json.dumps(key, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def parse_questions(raw):
    """confusable_pairs.questions（JSON）→ 辨析题列表，每题附上 version；旧数据没有这一列的值时为空列表"""
    try:
        questions = json.loads(raw) if raw else []
    except ValueError:
        return []
    if not isinstance(questions, list):
        return []
    return [dict(q, version=question_version(q)) for q in questions if isinstance(q, dict)]


def register_confusable_apis(app, db, require_authentication, check_ownership, pair_due=None, schema_ready=None):
    """注册易混淆词相关的API端点。

    schema_ready() 为假时（启动时没能补齐辨析题需要的列和唯一索引），不带出辨析，作答接口返回 503。

    pair_due(user_id, pair_id, word1_id, word2_id, questions) 判断练习结束时要不要带出这一对的辨析
    （论文 2.2.4：两个词分别掌握到一定程度后再对比学习）；不传时只要有词对就带出。
    """

    def word_display(word_id, raw_pinyin):
        """返回 (汉字, 拼音)。word 表没有汉字列，按 character 表顺序拼出；
        拼不出时尝试从 pinyin 列拆出混写的汉字，都没有则汉字为 None。"""
        rows = db.session.execute(
            text("SELECT character FROM character WHERE word_id = :id ORDER BY id"),
            {'id': word_id}
        ).fetchall()
        if rows:
            return ''.join(r[0] for r in rows), raw_pinyin
        match = HANZI_PREFIX.match(raw_pinyin or '')
        if match:
            return match.group(1), match.group(2)
        return None, raw_pinyin

    def word_payload(word_id, raw_pinyin, definition):
        hanzi, pinyin = word_display(word_id, raw_pinyin)
        return {'id': word_id, 'hanzi': hanzi, 'pinyin': pinyin, 'definition': definition}

    @app.route('/api/confusable/pairs', methods=['GET'])
    def get_confusable_pairs():
        """获取易混淆词对列表"""
        try:
            limit = request.args.get('limit', 10, type=int)
            offset = request.args.get('offset', 0, type=int)
            difficulty = request.args.get('difficulty', type=int)
            
            sql = """
                SELECT 
                    cp.id,
                    cp.word1_id,
                    cp.word2_id,
                    w1.pinyin as word1_pinyin,
                    w2.pinyin as word2_pinyin,
                    w1.definition as word1_definition,
                    w2.definition as word2_definition,
                    cp.reason,
                    cp.difference,
                    cp.examples,
                    cp.tips,
                    cp.difficulty_level,
                    cp.questions
                FROM confusable_pairs cp
                JOIN word w1 ON cp.word1_id = w1.id
                JOIN word w2 ON cp.word2_id = w2.id
            """
            
            if difficulty:
                sql += " WHERE cp.difficulty_level = :difficulty"
            
            sql += " ORDER BY cp.difficulty_level, cp.id LIMIT :limit OFFSET :offset"
            
            params = {'limit': limit, 'offset': offset}
            if difficulty:
                params['difficulty'] = difficulty
            
            result = db.session.execute(text(sql), params)
            pairs = []
            
            for row in result:
                pairs.append({
                    'id': row[0],
                    'word1': word_payload(row[1], row[3], row[5]),
                    'word2': word_payload(row[2], row[4], row[6]),
                    'reason': row[7],
                    'difference': row[8],
                    'examples': row[9],
                    'tips': row[10],
                    'difficulty_level': row[11],
                    'questions': parse_questions(row[12])
                })
            
            return jsonify({
                'success': True,
                'pairs': pairs,
                'total': len(pairs)
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/confusable/for-word/<int:word_id>', methods=['GET'])
    def get_confusable_for_word(word_id):
        """查询练习结束时要不要带出这个词的辨析环节：有易混淆词对，且这位学习者两个词都已
        掌握到一定程度、这一对还没练过关（见 pair_due）。认不出身份时不带出。"""
        try:
            rows = db.session.execute(text("""
                SELECT id, word1_id, word2_id, questions FROM confusable_pairs
                WHERE word1_id = :word_id OR word2_id = :word_id
                ORDER BY id
            """), {'word_id': word_id}).fetchall()
            if pair_due is None:
                return jsonify({'success': True, 'pair_id': rows[0][0] if rows else None})
            viewer_id, _ = get_current_user_from_request()
            if not viewer_id or (schema_ready and not schema_ready()):
                return jsonify({'success': True, 'pair_id': None})
            # 有辨析题、还没过关的词对优先；没有题的旧词对解锁后一直到期，排在后面才不会挡住新词对
            rows = sorted(rows, key=lambda r: (not parse_questions(r[3]), r[0]))
            due = next((r[0] for r in rows if pair_due(viewer_id, r[0], r[1], r[2], parse_questions(r[3]))), None)
            return jsonify({'success': True, 'pair_id': due})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/confusable/pair/<int:pair_id>', methods=['GET'])
    def get_confusable_pair(pair_id):
        """获取单个易混淆词对的详细信息"""
        try:
            query = text("""
                SELECT 
                    cp.id,
                    cp.word1_id,
                    cp.word2_id,
                    w1.pinyin as word1_pinyin,
                    w2.pinyin as word2_pinyin,
                    w1.definition as word1_definition,
                    w2.definition as word2_definition,
                    cp.reason,
                    cp.difference,
                    cp.examples,
                    cp.tips,
                    cp.difficulty_level,
                    cp.questions
                FROM confusable_pairs cp
                JOIN word w1 ON cp.word1_id = w1.id
                JOIN word w2 ON cp.word2_id = w2.id
                WHERE cp.id = :pair_id
            """)
            
            result = db.session.execute(query, {'pair_id': pair_id}).fetchone()
            
            if not result:
                return jsonify({'success': False, 'error': '未找到该易混淆词对'}), 404
            
            pair = {
                'id': result[0],
                'word1': word_payload(result[1], result[3], result[5]),
                'word2': word_payload(result[2], result[4], result[6]),
                'reason': result[7],
                'difference': result[8],
                'examples': result[9],
                'tips': result[10],
                'difficulty_level': result[11],
                'questions': parse_questions(result[12])
            }
            
            return jsonify({
                'success': True,
                'pair': pair
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/confusable/exercise/record', methods=['POST'])
    @require_authentication()
    def record_confusable_exercise(current_user_id=None, **kwargs):
        """记录易混淆词辨析练习。

        辨析题传 question_index（questions 里的下标）、question_version（作答时那道题的 version）、user_answer，
        由这里对照题目判分，客户端给的 is_correct 不用；题目改过或撤下了（页面过期）时返回 409 QUESTION_CHANGED。
        attempt_id 是客户端为这次作答生成的编号，重试沿用同一个，同一用户的同一编号只记一次；
        同一编号却带着不同内容时返回 409 ATTEMPT_CONFLICT。
        过关看每道题最近一次作答（见 app_phase.contrast_passed）。不带题号的旧调用照旧记录客户端的 is_correct。
        """
        try:
            if schema_ready and not schema_ready():
                return jsonify({'success': False, 'error': 'Saving answers is temporarily unavailable'}), 503
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                return jsonify({'success': False, 'error': 'JSON object expected'}), 400
            is_int = lambda v: isinstance(v, int) and not isinstance(v, bool)
            pair_id = data.get('pair_id')
            response_time = data.get('response_time')
            attempt_id = data.get('attempt_id')
            if not is_int(pair_id):
                return jsonify({'success': False, 'error': 'pair_id must be an integer'}), 400
            if response_time is not None and not (isinstance(response_time, (int, float))
                                                  and not isinstance(response_time, bool) and response_time >= 0):
                return jsonify({'success': False, 'error': 'response_time must be a non-negative number'}), 400
            if attempt_id is not None and not (isinstance(attempt_id, str) and 0 < len(attempt_id) <= 64):
                return jsonify({'success': False, 'error': 'attempt_id must be a short string'}), 400
            row = db.session.execute(text("SELECT questions FROM confusable_pairs WHERE id = :id"),
                                     {'id': pair_id}).fetchone()
            if row is None:
                return jsonify({'success': False, 'error': 'Pair not found'}), 404

            question_index = data.get('question_index')
            user_answer = data.get('user_answer')
            version = correct_answer = None
            if question_index is not None:
                questions = parse_questions(row[0])
                if not is_int(question_index):
                    return jsonify({'success': False, 'error': 'Invalid question_index'}), 400
                question = questions[question_index] if 0 <= question_index < len(questions) else None
                if question is None or data.get('question_version') != question['version']:
                    return jsonify({'success': False, 'error': 'This question has changed. Please reload.',
                                    'code': 'QUESTION_CHANGED'}), 409
                if user_answer not in question.get('options', []):
                    return jsonify({'success': False, 'error': 'user_answer is not one of the options'}), 400
                version, correct_answer = question['version'], question.get('correct_answer')
                is_correct = user_answer == correct_answer
            else:
                is_correct = data.get('is_correct')
                if not isinstance(is_correct, bool):
                    return jsonify({'success': False, 'error': '缺少必要参数'}), 400
                user_answer = None

            query = text("""
                INSERT OR IGNORE INTO confusable_exercise_records
                (user_id, pair_id, is_correct, response_time, question_index, question_version, user_answer, attempt_id)
                VALUES (:user_id, :pair_id, :is_correct, :response_time, :question_index, :question_version,
                        :user_answer, :attempt_id)
            """)

            result = db.session.execute(query, {
                'user_id': current_user_id,
                'pair_id': pair_id,
                'is_correct': is_correct,
                'response_time': response_time,
                'question_index': question_index,
                'question_version': version,
                'user_answer': user_answer,
                'attempt_id': attempt_id,
            })
            if result.rowcount == 0 and attempt_id is not None:
                # 这个作答编号已经记过：内容一致就是重试，返回当时的结果；不一致是冲突，不能报告保存成功
                prior = db.session.execute(text("""
                    SELECT pair_id, question_index, question_version, user_answer, is_correct
                    FROM confusable_exercise_records WHERE user_id = :user_id AND attempt_id = :attempt_id
                """), {'user_id': current_user_id, 'attempt_id': attempt_id}).fetchone()
                db.session.rollback()
                if prior is None or tuple(prior[:4]) != (pair_id, question_index, version, user_answer):
                    return jsonify({'success': False, 'error': 'attempt_id was already used for a different answer',
                                    'code': 'ATTEMPT_CONFLICT'}), 409
                is_correct = bool(prior[4])
            else:
                db.session.commit()

            return jsonify({
                'success': True,
                'is_correct': is_correct,
                'correct_answer': correct_answer,
                'message': '练习记录已保存'
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/confusable/user/<user_id>/statistics', methods=['GET'])
    @require_authentication()
    @check_ownership()
    def get_confusable_statistics(user_id, current_user_id=None, **kwargs):
        """获取用户的易混淆词辨析统计"""
        try:
            query = text("""
                SELECT 
                    COUNT(*) as total_exercises,
                    SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct_count,
                    AVG(response_time) as avg_response_time
                FROM confusable_exercise_records
                WHERE user_id = :user_id
            """)
            
            result = db.session.execute(query, {'user_id': user_id}).fetchone()
            
            total = result[0] or 0
            correct = result[1] or 0
            accuracy = (correct / total * 100) if total > 0 else 0
            
            return jsonify({
                'success': True,
                'statistics': {
                    'total_exercises': total,
                    'correct_count': correct,
                    'accuracy': round(accuracy, 2),
                    'avg_response_time': round(result[2] or 0, 2)
                }
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    print("✅ 易混淆词辨析API已注册")

