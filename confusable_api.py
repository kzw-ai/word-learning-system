#!/usr/bin/env python3
"""
易混淆词辨析 API扩展
添加到 app_phase.py 中
"""

import re

from flask import jsonify, request
from sqlalchemy import text

# 无 character 行的词，pinyin 列里混写了汉字，形如 '突然 tūrán'
HANZI_PREFIX = re.compile(r'^([\u4e00-\u9fff]+)\s+(.+)$')

def register_confusable_apis(app, db, require_authentication, check_ownership):
    """注册易混淆词相关的API端点"""

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
                    cp.difficulty_level
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
                    'difficulty_level': row[11]
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
        """查询某词是否有易混淆词对（用于学习流程中带出辨析环节）"""
        try:
            query = text("""
                SELECT id FROM confusable_pairs
                WHERE word1_id = :word_id OR word2_id = :word_id
                LIMIT 1
            """)
            row = db.session.execute(query, {'word_id': word_id}).fetchone()
            return jsonify({'success': True, 'pair_id': row[0] if row else None})
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
                    cp.difficulty_level
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
                'difficulty_level': result[11]
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
        """记录易混淆词辨析练习"""
        try:
            data = request.get_json()
            pair_id = data.get('pair_id')
            is_correct = data.get('is_correct')
            response_time = data.get('response_time')
            
            if not pair_id or is_correct is None:
                return jsonify({'success': False, 'error': '缺少必要参数'}), 400
            
            query = text("""
                INSERT INTO confusable_exercise_records 
                (user_id, pair_id, is_correct, response_time)
                VALUES (:user_id, :pair_id, :is_correct, :response_time)
            """)
            
            db.session.execute(query, {
                'user_id': current_user_id,
                'pair_id': pair_id,
                'is_correct': is_correct,
                'response_time': response_time
            })
            db.session.commit()
            
            return jsonify({
                'success': True,
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

