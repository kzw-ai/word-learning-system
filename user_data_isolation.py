#!/usr/bin/env python3
"""
用户数据隔离与权限控制模块
"""

import os
import re
import sqlite3
from functools import wraps
from flask import request, jsonify

def get_auth_manager():
    """动态获取认证管理器"""
    try:
        from auth import AuthManager
        return AuthManager()
    except ImportError:
        return None


# 访客身份：前端首次访问时生成的随机 ID，随 cookie（或 X-Guest-Id 头）发送。
# 随机串本身就是凭证——足够长、猜不到，所以无法冒充别的访客。
GUEST_ID_PATTERN = re.compile(r'^guest_[A-Za-z0-9]{16,64}$')


def user_id_param_allowed():
    """是否允许把请求里的 user_id（URL / query / body）当作身份。

    只用于开发和测试（UserSwitcher 切换测试用户、pytest）。生产环境里打开它
    就等于任何人在请求里填别人的 user_id 即可读写对方数据，所以默认关闭，
    须显式设置环境变量 ALLOW_USER_ID_PARAM=1。
    """
    return os.environ.get('ALLOW_USER_ID_PARAM') == '1'


def get_guest_id():
    """请求携带的、格式合法的访客 ID；没有则为 None"""
    guest_id = request.headers.get('X-Guest-Id') or request.cookies.get('guest_id')
    if guest_id and GUEST_ID_PATTERN.match(guest_id):
        return guest_id
    return None


def get_current_user_from_request():
    """
    从请求中确定当前用户。按优先级：
    1. Session Token —— 已登录用户
    2. 请求里的 user_id —— 仅当 ALLOW_USER_ID_PARAM=1（开发/测试）
    3. 访客 ID —— 未登录访客

    Returns:
        tuple: (user_id, is_authenticated)。登录用户与访客的身份都由请求凭证
        证明，is_authenticated 为 True；只有开发模式下取自参数的身份为 False。
    """
    auth_manager = get_auth_manager()

    if auth_manager:
        session_token = request.headers.get('X-Session-Token') or request.cookies.get('session_token')
        if session_token:
            try:
                validation = auth_manager.validate_session(session_token)
            except sqlite3.Error:
                # 认证表缺失等数据库问题：按未登录处理，而不是让整个请求 500
                validation = {'valid': False}
            if validation['valid']:
                return validation['user_id'], True

    if user_id_param_allowed():
        # view_args 在无路由匹配时为 None
        view_args = request.view_args or {}
        if 'user_id' in view_args:
            return view_args['user_id'], False
        user_id = request.args.get('user_id')
        if user_id:
            return user_id, False
        body = request.get_json(silent=True)
        if isinstance(body, dict) and (body.get('user_id') or body.get('userId')):
            return body.get('user_id') or body.get('userId'), False

    guest_id = get_guest_id()
    if guest_id:
        return guest_id, True

    return None, False


def require_authentication(allow_url_param=True):
    """
    装饰器：要求用户认证
    
    Args:
        allow_url_param: 是否允许URL参数认证（向后兼容）
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id, is_authenticated = get_current_user_from_request()
            
            if not user_id:
                return jsonify({
                    'success': False,
                    'error': 'Sign-in or guest identity required',
                    'code': 'AUTHENTICATION_REQUIRED'
                }), 401
            
            # 如果不允许URL参数，必须通过Session认证
            if not allow_url_param and not is_authenticated:
                return jsonify({
                    'success': False,
                    'error': 'Sign-in required',
                    'code': 'SESSION_REQUIRED'
                }), 401
            
            # 将user_id和认证状态注入到kwargs
            kwargs['current_user_id'] = user_id
            kwargs['is_authenticated'] = is_authenticated
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def check_data_ownership(target_user_id=None):
    """
    装饰器：检查数据所有权
    用户只能访问自己的数据
    
    Args:
        target_user_id: 如果提供，检查该用户ID；否则从URL参数获取
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            current_user_id, is_authenticated = get_current_user_from_request()
            
            if not current_user_id:
                return jsonify({
                    'success': False,
                    'error': 'Sign-in or guest identity required',
                    'code': 'AUTHENTICATION_REQUIRED'
                }), 401
            
            # 确定要检查的目标用户ID
            check_user_id = target_user_id
            view_args = request.view_args or {}
            if not check_user_id and 'user_id' in kwargs:
                check_user_id = kwargs['user_id']
            elif not check_user_id and 'user_id' in view_args:
                check_user_id = view_args['user_id']
            
            # 如果没有指定目标用户，使用当前用户
            if not check_user_id:
                kwargs['user_id'] = current_user_id
            elif check_user_id != current_user_id:
                # 数据所有权检查失败
                return jsonify({
                    'success': False,
                    'error': 'You can only access your own data',
                    'code': 'PERMISSION_DENIED'
                }), 403
            
            kwargs['current_user_id'] = current_user_id
            kwargs['is_authenticated'] = is_authenticated
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


class UserDataIsolation:
    """
    用户数据隔离工具类
    提供常用的数据查询过滤方法
    """
    
    @staticmethod
    def filter_user_sessions(sessions, user_id):
        """过滤用户会话数据"""
        return [s for s in sessions if s.user_id == user_id]
    
    @staticmethod
    def filter_user_progress(progress_list, user_id):
        """过滤用户进度数据"""
        return [p for p in progress_list if p.user_id == user_id]
    
    @staticmethod
    def validate_user_access(target_user_id, current_user_id):
        """验证用户访问权限"""
        return target_user_id == current_user_id
    
    @staticmethod
    def get_user_context(user_id):
        """获取用户上下文信息"""
        auth_manager = get_auth_manager()
        if auth_manager:
            return auth_manager.get_user_info(user_id)
        return {'user_id': user_id}


# 快捷函数
def require_auth():
    """快捷装饰器：要求认证（允许URL参数）"""
    return require_authentication(allow_url_param=True)


def require_session_auth():
    """快捷装饰器：要求Session认证（不允许URL参数）"""
    return require_authentication(allow_url_param=False)


def check_ownership():
    """快捷装饰器：检查数据所有权"""
    return check_data_ownership()

