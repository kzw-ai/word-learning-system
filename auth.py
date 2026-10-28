#!/usr/bin/env python3
"""
用户认证模块
实现注册、登录、Session管理等功能
"""

from werkzeug.security import generate_password_hash, check_password_hash
from flask import session
import os
import secrets
import sqlite3
from datetime import datetime, timedelta

class AuthManager:
    """用户认证管理器"""

    def __init__(self, db_path=None):
        # WORDS_DB_PATH 环境变量可覆盖数据库路径，与 app_phase 保持一致
        self.db_path = db_path or os.environ.get('WORDS_DB_PATH', 'words_extended.db')
        self.session_lifetime = timedelta(days=7)  # Session有效期7天
    
    def get_connection(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)
    
    def register_user(self, username, password, email=None, native_language='English'):
        """
        注册新用户
        
        Args:
            username: 用户名
            password: 密码（明文）
            email: 邮箱（可选）
            native_language: 母语
            
        Returns:
            dict: {'success': bool, 'user_id': str, 'message': str}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 检查用户名是否已存在
            cursor.execute("""
                SELECT id FROM user_profile WHERE username = ?
            """, (username,))
            
            if cursor.fetchone():
                return {
                    'success': False,
                    'message': 'That username is taken'
                }
            
            # 检查邮箱是否已存在
            if email:
                cursor.execute("""
                    SELECT id FROM user_profile WHERE email = ?
                """, (email,))
                
                if cursor.fetchone():
                    return {
                        'success': False,
                        'message': 'That email is already registered'
                    }
            
            # 生成user_id
            user_id = self.generate_user_id(username)
            
            # 加密密码
            password_hash = generate_password_hash(password, method='pbkdf2:sha256')
            
            # 创建用户
            cursor.execute("""
                INSERT INTO user_profile 
                (user_id, username, password_hash, email, native_language, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                username,
                password_hash,
                email,
                native_language,
                datetime.now(),
                datetime.now()
            ))
            
            conn.commit()
            
            return {
                'success': True,
                'user_id': user_id,
                'message': 'Signed up'
            }
            
        except Exception as e:
            conn.rollback()
            return {
                'success': False,
                'message': f'Sign-up failed: {str(e)}'
            }
        finally:
            conn.close()
    
    def login(self, username, password):
        """
        用户登录
        
        Args:
            username: 用户名或邮箱
            password: 密码
            
        Returns:
            dict: {'success': bool, 'user_id': str, 'session_token': str, 'message': str}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 查询用户（支持用户名或邮箱登录）
            cursor.execute("""
                SELECT id, user_id, username, password_hash, email
                FROM user_profile
                WHERE username = ? OR email = ?
            """, (username, username))
            
            user = cursor.fetchone()
            
            if not user:
                return {
                    'success': False,
                    'message': 'Wrong username or password'
                }
            
            user_pk_id, user_id, username, password_hash, email = user
            
            # 验证密码
            if not check_password_hash(password_hash, password):
                return {
                    'success': False,
                    'message': 'Wrong username or password'
                }
            
            # 生成session token
            session_token = self.generate_session_token()
            
            # 保存session
            cursor.execute("""
                INSERT INTO user_session 
                (user_id, session_token, created_at, expires_at, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, (
                user_id,
                session_token,
                datetime.now(),
                datetime.now() + self.session_lifetime,
                True
            ))
            
            # 更新最后登录时间
            cursor.execute("""
                UPDATE user_profile
                SET last_login = ?, updated_at = ?
                WHERE user_id = ?
            """, (datetime.now(), datetime.now(), user_id))
            
            conn.commit()
            
            return {
                'success': True,
                'user_id': user_id,
                'username': username,
                'email': email,
                'session_token': session_token,
                'message': 'Signed in'
            }
            
        except Exception as e:
            conn.rollback()
            return {
                'success': False,
                'message': f'Sign-in failed: {str(e)}'
            }
        finally:
            conn.close()
    
    def logout(self, session_token):
        """
        用户登出
        
        Args:
            session_token: Session令牌
            
        Returns:
            dict: {'success': bool, 'message': str}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE user_session
                SET is_active = 0, updated_at = ?
                WHERE session_token = ?
            """, (datetime.now(), session_token))
            
            conn.commit()
            
            return {
                'success': True,
                'message': 'Signed out'
            }
            
        except Exception as e:
            conn.rollback()
            return {
                'success': False,
                'message': f'Sign-out failed: {str(e)}'
            }
        finally:
            conn.close()
    
    def validate_session(self, session_token):
        """
        验证session是否有效
        
        Args:
            session_token: Session令牌
            
        Returns:
            dict: {'valid': bool, 'user_id': str, 'message': str}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT user_id, expires_at, is_active
                FROM user_session
                WHERE session_token = ?
            """, (session_token,))
            
            result = cursor.fetchone()
            
            if not result:
                return {
                    'valid': False,
                    'message': 'Session not found'
                }
            
            user_id, expires_at, is_active = result
            
            # 检查是否过期
            if datetime.fromisoformat(expires_at) < datetime.now():
                return {
                    'valid': False,
                    'message': 'Session expired'
                }
            
            # 检查是否激活
            if not is_active:
                return {
                    'valid': False,
                    'message': 'Session is no longer valid'
                }
            
            return {
                'valid': True,
                'user_id': user_id,
                'message': 'Session is valid'
            }
            
        finally:
            conn.close()
    
    def get_user_info(self, user_id):
        """
        获取用户信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            dict: 用户信息
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT user_id, username, email, native_language, language_level, created_at, last_login
                FROM user_profile
                WHERE user_id = ?
            """, (user_id,))
            
            result = cursor.fetchone()
            
            if not result:
                return None
            
            return {
                'user_id': result[0],
                'username': result[1],
                'email': result[2],
                'native_language': result[3],
                'language_level': result[4],
                'created_at': result[5],
                'last_login': result[6]
            }
            
        finally:
            conn.close()
    
    def change_password(self, user_id, old_password, new_password):
        """
        修改密码
        
        Args:
            user_id: 用户ID
            old_password: 旧密码
            new_password: 新密码
            
        Returns:
            dict: {'success': bool, 'message': str}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 获取当前密码hash
            cursor.execute("""
                SELECT password_hash FROM user_profile WHERE user_id = ?
            """, (user_id,))
            
            result = cursor.fetchone()
            
            if not result:
                return {
                    'success': False,
                    'message': 'User not found'
                }
            
            password_hash = result[0]
            
            # 验证旧密码
            if not check_password_hash(password_hash, old_password):
                return {
                    'success': False,
                    'message': 'The current password is wrong'
                }
            
            # 生成新密码hash
            new_password_hash = generate_password_hash(new_password, method='pbkdf2:sha256')
            
            # 更新密码
            cursor.execute("""
                UPDATE user_profile
                SET password_hash = ?, updated_at = ?
                WHERE user_id = ?
            """, (new_password_hash, datetime.now(), user_id))
            
            # 使所有旧session失效
            cursor.execute("""
                UPDATE user_session
                SET is_active = 0, updated_at = ?
                WHERE user_id = ?
            """, (datetime.now(), user_id))
            
            conn.commit()
            
            return {
                'success': True,
                'message': 'Password changed. Please sign in again.'
            }
            
        except Exception as e:
            conn.rollback()
            return {
                'success': False,
                'message': f'Password change failed: {str(e)}'
            }
        finally:
            conn.close()
    
    def generate_user_id(self, username):
        """生成唯一的user_id"""
        import hashlib
        timestamp = datetime.now().timestamp()
        raw = f"{username}_{timestamp}"
        return f"user_{hashlib.md5(raw.encode()).hexdigest()[:12]}"
    
    def generate_session_token(self):
        """生成安全的session token"""
        return secrets.token_urlsafe(32)
    
    def cleanup_expired_sessions(self):
        """清理过期的session"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                DELETE FROM user_session
                WHERE expires_at < ? OR (is_active = 0 AND updated_at < ?)
            """, (datetime.now(), datetime.now() - timedelta(days=30)))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            return {
                'success': True,
                'deleted_count': deleted_count
            }
            
        except Exception as e:
            conn.rollback()
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            conn.close()


# 认证装饰器
def require_auth(f):
    """API认证装饰器"""
    from functools import wraps
    from flask import request, jsonify
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 从header获取session token
        session_token = request.headers.get('X-Session-Token') or request.cookies.get('session_token')
        
        if not session_token:
            return jsonify({
                'success': False,
                'error': 'Not signed in',
                'code': 'UNAUTHORIZED'
            }), 401
        
        # 验证session
        auth_manager = AuthManager()
        validation = auth_manager.validate_session(session_token)
        
        if not validation['valid']:
            return jsonify({
                'success': False,
                'error': validation['message'],
                'code': 'INVALID_SESSION'
            }), 401
        
        # 将user_id添加到request context（Flask 动态属性）
        request.user_id = validation['user_id']  # pyrefly: ignore
        
        return f(*args, **kwargs)
    
    return decorated_function


def test_auth_system():
    """测试认证系统"""
    print("🧪 测试用户认证系统...")
    
    auth = AuthManager()
    
    # 测试1: 注册用户
    print("\n1️⃣ 测试用户注册...")
    result = auth.register_user(
        username='test_user',
        password='test123456',
        email='test@example.com'
    )
    print(f"   结果: {result}")
    
    if result['success']:
        user_id = result['user_id']
        
        # 测试2: 登录
        print("\n2️⃣ 测试用户登录...")
        login_result = auth.login('test_user', 'test123456')
        print(f"   结果: {login_result}")
        
        if login_result['success']:
            session_token = login_result['session_token']
            
            # 测试3: 验证session
            print("\n3️⃣ 测试Session验证...")
            validation = auth.validate_session(session_token)
            print(f"   结果: {validation}")
            
            # 测试4: 获取用户信息
            print("\n4️⃣ 测试获取用户信息...")
            user_info = auth.get_user_info(user_id)
            print(f"   结果: {user_info}")
            
            # 测试5: 登出
            print("\n5️⃣ 测试用户登出...")
            logout_result = auth.logout(session_token)
            print(f"   结果: {logout_result}")
            
            # 测试6: 验证登出后的session
            print("\n6️⃣ 测试登出后Session...")
            validation = auth.validate_session(session_token)
            print(f"   结果: {validation}")
    
    print("\n✅ 认证系统测试完成")


if __name__ == '__main__':
    test_auth_system()

