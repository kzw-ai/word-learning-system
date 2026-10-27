#!/usr/bin/env python3
"""
数据库迁移脚本 - 添加认证相关字段和表
"""

import sqlite3
from datetime import datetime

def migrate_auth_system(db_path='words_extended.db', seed_test_passwords=True):
    """添加认证系统所需的数据库结构（幂等，可重复执行）

    seed_test_passwords: 给所有没有密码的用户设成 password123，只用于测试库。
    后端启动时以 False 调用——否则每个新建的访客档案都会被设上这个公开密码。
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("🔄 开始数据库迁移...")
    
    try:
        # 1. 检查user_profile表是否需要添加字段
        cursor.execute("PRAGMA table_info(user_profile)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # 添加password_hash字段
        if 'password_hash' not in columns:
            print("   ➕ 添加 password_hash 字段...")
            cursor.execute("""
                ALTER TABLE user_profile
                ADD COLUMN password_hash TEXT
            """)
        
        # 添加email字段
        if 'email' not in columns:
            print("   ➕ 添加 email 字段...")
            cursor.execute("""
                ALTER TABLE user_profile
                ADD COLUMN email TEXT
            """)
            # 创建唯一索引代替UNIQUE约束
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_user_email 
                ON user_profile(email) 
                WHERE email IS NOT NULL
            """)
        
        # 添加last_login字段
        if 'last_login' not in columns:
            print("   ➕ 添加 last_login 字段...")
            cursor.execute("""
                ALTER TABLE user_profile
                ADD COLUMN last_login DATETIME
            """)
        
        # 2. 创建user_session表
        print("   📋 创建 user_session 表...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_session (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                created_at DATETIME NOT NULL,
                expires_at DATETIME NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                updated_at DATETIME,
                device_info TEXT,
                ip_address TEXT,
                FOREIGN KEY (user_id) REFERENCES user_profile(user_id)
            )
        """)
        
        # 创建索引以提高查询性能
        print("   📑 创建索引...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_token 
            ON user_session(session_token)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_session 
            ON user_session(user_id, is_active)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_expires 
            ON user_session(expires_at)
        """)
        
        # 3. 为现有用户设置默认密码（用于测试）
        if not seed_test_passwords:
            conn.commit()
            print("✅ 认证表结构已就绪")
            return True
        print("   🔑 为现有测试用户设置默认密码...")
        from werkzeug.security import generate_password_hash
        default_password_hash = generate_password_hash('password123', method='pbkdf2:sha256')
        
        cursor.execute("""
            UPDATE user_profile
            SET password_hash = ?
            WHERE password_hash IS NULL
        """, (default_password_hash,))
        
        updated_count = cursor.rowcount
        if updated_count > 0:
            print(f"   ✅ 为 {updated_count} 个用户设置了默认密码（password123）")
        
        conn.commit()
        
        print("\n✅ 数据库迁移完成！")
        print("\n📊 迁移摘要:")
        print("   - ✅ user_profile表已更新（添加认证字段）")
        print("   - ✅ user_session表已创建")
        print("   - ✅ 相关索引已创建")
        print(f"   - ✅ {updated_count} 个测试用户可使用密码：password123")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ 迁移失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        conn.close()


def verify_migration(db_path='words_extended.db'):
    """验证迁移是否成功"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("\n🔍 验证迁移结果...")
    
    try:
        # 检查user_profile表结构
        cursor.execute("PRAGMA table_info(user_profile)")
        profile_columns = [row[1] for row in cursor.fetchall()]
        print(f"   user_profile 字段: {', '.join(profile_columns)}")
        
        # 检查user_session表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='user_session'
        """)
        if cursor.fetchone():
            print("   ✅ user_session 表存在")
            
            cursor.execute("PRAGMA table_info(user_session)")
            session_columns = [row[1] for row in cursor.fetchall()]
            print(f"   user_session 字段: {', '.join(session_columns)}")
        else:
            print("   ❌ user_session 表不存在")
        
        # 检查用户数量
        cursor.execute("SELECT COUNT(*) FROM user_profile")
        user_count = cursor.fetchone()[0]
        print(f"   📊 用户总数: {user_count}")
        
        # 检查有密码的用户数量
        cursor.execute("SELECT COUNT(*) FROM user_profile WHERE password_hash IS NOT NULL")
        user_with_password = cursor.fetchone()[0]
        print(f"   🔑 已设置密码的用户: {user_with_password}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 验证失败: {str(e)}")
        return False
        
    finally:
        conn.close()


def rollback_migration(db_path='words_extended.db'):
    """回滚迁移（仅用于开发测试）"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("⚠️  警告：即将回滚数据库迁移...")
    response = input("确定要继续吗？(yes/no): ")
    
    if response.lower() != 'yes':
        print("❌ 取消回滚")
        return
    
    try:
        # 删除user_session表
        cursor.execute("DROP TABLE IF EXISTS user_session")
        print("   ✅ 已删除 user_session 表")
        
        # 注意：SQLite不支持删除列，所以我们不能删除已添加的字段
        # 如果需要完全回滚，需要重建整个表
        print("   ⚠️  注意：已添加到user_profile的字段无法删除（SQLite限制）")
        
        conn.commit()
        print("✅ 回滚完成")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ 回滚失败: {str(e)}")
        
    finally:
        conn.close()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'rollback':
        rollback_migration()
    elif len(sys.argv) > 1 and sys.argv[1] == 'verify':
        verify_migration()
    else:
        # 执行迁移
        success = migrate_auth_system()
        if success:
            verify_migration()

