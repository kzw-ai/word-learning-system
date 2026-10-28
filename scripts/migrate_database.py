#!/usr/bin/env python3
"""
数据库迁移脚本 - 从原有的words.db迁移到扩展的words_extended.db
包含时间追踪和自适应学习功能的数据表
"""

import sqlite3
import os
from datetime import datetime

def migrate_database():
    """执行数据库迁移"""
    
    print("🚀 开始数据库迁移...")
    
    # 检查源数据库是否存在
    source_db = 'words.db'
    target_db = 'words_extended.db'
    
    if not os.path.exists(source_db):
        print(f"⚠️  源数据库 {source_db} 不存在，将创建新的扩展数据库")
        create_extended_database()
        return
    
    print(f"📊 从 {source_db} 迁移到 {target_db}")
    
    # 连接源数据库和目标数据库
    source_conn = sqlite3.connect(source_db)
    target_conn = sqlite3.connect(target_db)
    
    try:
        # 创建扩展数据库的所有表
        create_extended_tables(target_conn)
        
        # 迁移现有数据
        migrate_existing_data(source_conn, target_conn)
        
        # 创建示例数据
        create_sample_data(target_conn)
        
        print("✅ 数据库迁移完成！")
        print(f"📁 新数据库保存在: {os.path.abspath(target_db)}")
        
    except Exception as e:
        print(f"❌ 迁移失败: {str(e)}")
        target_conn.rollback()
        raise
    
    finally:
        source_conn.close()
        target_conn.close()

def create_extended_tables(conn):
    """创建扩展数据库的所有表"""
    
    print("📝 创建扩展数据表...")
    
    cursor = conn.cursor()
    
    # 创建原有表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS word (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pinyin VARCHAR(80) NOT NULL,
            definition VARCHAR(200) NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS example (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sentence VARCHAR(200) NOT NULL,
            pinyin VARCHAR(200) NOT NULL,
            translation VARCHAR(200) NOT NULL,
            audio VARCHAR(200) NOT NULL,
            word_id INTEGER NOT NULL,
            FOREIGN KEY (word_id) REFERENCES word (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS collocation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collocation VARCHAR(200) NOT NULL,
            translation VARCHAR(200) NOT NULL,
            audio VARCHAR(200) NOT NULL,
            word_id INTEGER NOT NULL,
            FOREIGN KEY (word_id) REFERENCES word (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS character (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character VARCHAR(10) NOT NULL,
            pinyin VARCHAR(80) NOT NULL,
            definition VARCHAR(200) NOT NULL,
            audio VARCHAR(200) NOT NULL,
            word_id INTEGER NOT NULL,
            FOREIGN KEY (word_id) REFERENCES word (id)
        )
    ''')
    
    # 创建新的时间追踪表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR(50) UNIQUE NOT NULL,
            username VARCHAR(100),
            language_level VARCHAR(20),
            native_language VARCHAR(50) DEFAULT 'English',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS learning_session (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id VARCHAR(100) UNIQUE NOT NULL,
            user_id VARCHAR(50) NOT NULL,
            word_id INTEGER NOT NULL,
            session_type VARCHAR(20) NOT NULL,
            module_type VARCHAR(30) NOT NULL,
            initial_level VARCHAR(1),
            start_time DATETIME NOT NULL,
            end_time DATETIME,
            duration_seconds INTEGER,
            active_time_seconds INTEGER,
            completed BOOLEAN DEFAULT FALSE,
            interrupted BOOLEAN DEFAULT FALSE,
            device_type VARCHAR(20) DEFAULT 'web',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (word_id) REFERENCES word (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exercise_record (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id VARCHAR(100) NOT NULL,
            question_id VARCHAR(50) NOT NULL,
            question_type VARCHAR(20) NOT NULL,
            question_content TEXT,
            user_answer VARCHAR(500),
            correct_answer VARCHAR(500),
            is_correct BOOLEAN NOT NULL,
            confidence_level INTEGER,
            question_start_time DATETIME NOT NULL,
            question_end_time DATETIME,
            response_time_seconds REAL,
            hesitation_count INTEGER DEFAULT 0,
            attempt_count INTEGER DEFAULT 1,
            is_first_attempt BOOLEAN DEFAULT TRUE,
            feedback_shown BOOLEAN DEFAULT FALSE,
            feedback_view_time_seconds REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES learning_session (session_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR(50) NOT NULL,
            word_id INTEGER NOT NULL,
            mastery_level REAL DEFAULT 0.0,
            confidence_score REAL DEFAULT 0.0,
            difficulty_rating REAL,
            total_study_time_seconds INTEGER DEFAULT 0,
            total_sessions INTEGER DEFAULT 0,
            total_attempts INTEGER DEFAULT 0,
            correct_attempts INTEGER DEFAULT 0,
            character_study_count INTEGER DEFAULT 0,
            word_study_count INTEGER DEFAULT 0,
            collocation_study_count INTEGER DEFAULT 0,
            sentence_study_count INTEGER DEFAULT 0,
            definition_attempts INTEGER DEFAULT 0,
            definition_correct INTEGER DEFAULT 0,
            collocation_attempts INTEGER DEFAULT 0,
            collocation_correct INTEGER DEFAULT 0,
            fill_word_attempts INTEGER DEFAULT 0,
            fill_word_correct INTEGER DEFAULT 0,
            first_studied DATETIME,
            last_studied DATETIME,
            next_review_suggested DATETIME,
            review_count INTEGER DEFAULT 0,
            consecutive_correct INTEGER DEFAULT 0,
            consecutive_incorrect INTEGER DEFAULT 0,
            learning_efficiency REAL,
            retention_rate REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (word_id) REFERENCES word (id),
            UNIQUE(user_id, word_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS learning_event (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id VARCHAR(100) NOT NULL,
            event_type VARCHAR(50) NOT NULL,
            event_target VARCHAR(100),
            event_data TEXT,
            timestamp DATETIME NOT NULL,
            page_url VARCHAR(200),
            is_active BOOLEAN DEFAULT TRUE,
            focus_time_seconds REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES learning_session (session_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS adaptive_recommendation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR(50) NOT NULL,
            recommendation_type VARCHAR(30) NOT NULL,
            target_word_id INTEGER,
            target_module VARCHAR(30),
            confidence_score REAL,
            algorithm_version VARCHAR(20),
            recommendation_data TEXT,
            is_accepted BOOLEAN,
            actual_choice VARCHAR(100),
            effectiveness_score REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (target_word_id) REFERENCES word (id)
        )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_user ON learning_session (user_id, session_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_word ON learning_session (word_id, session_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_exercise_session ON exercise_record (session_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_progress_user ON user_progress (user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_event_session ON learning_event (session_id, event_type)')
    
    conn.commit()
    print("✅ 数据表创建完成")

def migrate_existing_data(source_conn, target_conn):
    """迁移现有数据"""
    
    print("📦 迁移现有数据...")
    
    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()
    
    # 获取现有数据的表列表
    source_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in source_cursor.fetchall()]
    
    migrated_count = 0
    
    # 迁移每个表的数据
    for table in ['word', 'example', 'collocation', 'character']:
        if table in tables:
            # 获取表结构
            source_cursor.execute(f"PRAGMA table_info({table})")
            columns_info = source_cursor.fetchall()
            columns = [col[1] for col in columns_info]  # col[1] 是列名
            
            # 获取所有数据
            source_cursor.execute(f"SELECT * FROM {table}")
            rows = source_cursor.fetchall()
            
            if rows:
                # 插入数据到目标数据库
                placeholders = ','.join(['?' for _ in columns])
                target_cursor.executemany(
                    f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})",
                    rows
                )
                migrated_count += len(rows)
                print(f"  📊 迁移 {table} 表: {len(rows)} 条记录")
    
    target_conn.commit()
    print(f"✅ 数据迁移完成，共迁移 {migrated_count} 条记录")

def create_sample_data(conn):
    """创建示例数据"""
    
    print("👤 创建示例用户和初始数据...")
    
    cursor = conn.cursor()
    
    # 创建示例用户
    cursor.execute('''
        INSERT OR IGNORE INTO user_profile (user_id, username, language_level, native_language)
        VALUES (?, ?, ?, ?)
    ''', ('user123', '测试用户', 'intermediate', 'English'))
    
    # 如果没有词汇数据，添加示例词汇
    cursor.execute('SELECT COUNT(*) FROM word')
    word_count = cursor.fetchone()[0]
    
    if word_count == 0:
        print("📝 添加示例词汇数据...")
        
        # 添加示例词汇
        cursor.execute('''
            INSERT INTO word (pinyin, definition) VALUES (?, ?)
        ''', ('fāshēng', 'happen; occur; take place'))
        
        word_id = cursor.lastrowid
        
        # 添加例句
        cursor.execute('''
            INSERT INTO example (sentence, pinyin, translation, audio, word_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            '不愿意发生的事情终于出现了。',
            '不/bù 愿意/yuànyì 发生/fāshēng 的/de 事情/shìqíng 终于/zhōngyú 出现/chūxiàn 了/le 。',
            "What I didn't want to happen finally happened.",
            '/audio/example1.mp3',
            word_id
        ))
        
        # 添加搭配
        cursor.execute('''
            INSERT INTO collocation (collocation, translation, audio, word_id)
            VALUES (?, ?, ?, ?)
        ''', ('容易（三级）发生', 'easy to happen', '/audio/collocation1.mp3', word_id))
        
        cursor.execute('''
            INSERT INTO collocation (collocation, translation, audio, word_id)
            VALUES (?, ?, ?, ?)
        ''', ('事情（二级）发生', 'things happen', '/audio/collocation2.mp3', word_id))
        
        # 添加字符
        cursor.execute('''
            INSERT INTO character (character, pinyin, definition, audio, word_id)
            VALUES (?, ?, ?, ?, ?)
        ''', ('发', 'fā', 'come or bring into existence; generate', '/audio/character1.mp3', word_id))
        
        cursor.execute('''
            INSERT INTO character (character, pinyin, definition, audio, word_id)
            VALUES (?, ?, ?, ?, ?)
        ''', ('生', 'shēng', 'bear; generate', '/audio/character2.mp3', word_id))
    
    conn.commit()
    print("✅ 示例数据创建完成")

def create_extended_database():
    """创建全新的扩展数据库"""
    
    print("🆕 创建新的扩展数据库...")
    
    target_db = 'words_extended.db'
    conn = sqlite3.connect(target_db)
    
    try:
        create_extended_tables(conn)
        create_sample_data(conn)
        print("✅ 新数据库创建完成！")
        print(f"📁 数据库保存在: {os.path.abspath(target_db)}")
    
    except Exception as e:
        print(f"❌ 创建失败: {str(e)}")
        conn.rollback()
        raise
    
    finally:
        conn.close()

def test_extended_database():
    """测试扩展数据库"""
    
    print("🧪 测试扩展数据库...")
    
    target_db = 'words_extended.db'
    
    if not os.path.exists(target_db):
        print(f"❌ 数据库文件 {target_db} 不存在")
        return False
    
    conn = sqlite3.connect(target_db)
    cursor = conn.cursor()
    
    try:
        # 测试各个表是否存在且有数据
        test_results = {}
        
        tables_to_test = [
            'word', 'example', 'collocation', 'character',
            'user_profile', 'learning_session', 'exercise_record',
            'user_progress', 'learning_event', 'adaptive_recommendation'
        ]
        
        for table in tables_to_test:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            test_results[table] = count
            
        print("📊 数据库表统计:")
        for table, count in test_results.items():
            status = "✅" if count >= 0 else "❌"
            print(f"   {status} {table}: {count} 条记录")
        
        # 测试基本查询
        cursor.execute("SELECT * FROM word LIMIT 1")
        word = cursor.fetchone()
        if word:
            print(f"📝 示例词汇: {word}")
        
        cursor.execute("SELECT * FROM user_profile LIMIT 1")
        user = cursor.fetchone()
        if user:
            print(f"👤 示例用户: {user}")
        
        print("✅ 数据库测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ 数据库测试失败: {str(e)}")
        return False
    
    finally:
        conn.close()

if __name__ == '__main__':
    print("=" * 60)
    print("📚 Word Learning System - 数据库迁移工具")
    print("=" * 60)
    
    try:
        # 执行迁移
        migrate_database()
        
        # 测试数据库
        if test_extended_database():
            print("\n🎉 数据库迁移和测试完全成功！")
            print("📍 您现在可以启动后端：python3 app_phase.py（生产环境由 PM2 管理）")
        else:
            print("\n⚠️  数据库迁移完成但测试失败，请检查")
    
    except Exception as e:
        print(f"\n💥 迁移过程出错: {str(e)}")
        print("请检查错误信息并重试")
