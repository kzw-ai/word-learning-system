#!/usr/bin/env python3
"""
Create confusable_pairs tables and seed initial data.
Run this script once to set up the confusable words feature.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'words_extended.db')

def setup_confusable_tables():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Create tables
    cur.execute("""
        CREATE TABLE IF NOT EXISTS confusable_pairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word1_id INTEGER NOT NULL,
            word2_id INTEGER NOT NULL,
            reason TEXT,
            difference TEXT,
            examples TEXT,
            tips TEXT,
            difficulty_level INTEGER DEFAULT 1,
            FOREIGN KEY (word1_id) REFERENCES word(id),
            FOREIGN KEY (word2_id) REFERENCES word(id)
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS confusable_exercise_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            pair_id INTEGER NOT NULL,
            is_correct BOOLEAN,
            response_time FLOAT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pair_id) REFERENCES confusable_pairs(id)
        )
    """)
    
    # Check if we need seed data
    cur.execute("SELECT COUNT(*) FROM confusable_pairs")
    if cur.fetchone()[0] > 0:
        print("confusable_pairs already has data, skipping seed.")
        conn.close()
        return
    
    # Ensure we have the needed words
    # Word 1: fasheng (should already exist)
    cur.execute("SELECT id FROM word WHERE pinyin='fasheng' OR pinyin='fāshēng'")
    row = cur.fetchone()
    if row:
        fasheng_id = row[0]
    else:
        cur.execute("INSERT INTO word (pinyin, definition) VALUES ('fāshēng', 'happen; occur; take place')")
        fasheng_id = cur.lastrowid
    
    # Word 2: faxian
    cur.execute("SELECT id FROM word WHERE pinyin='faxian' OR pinyin='fāxiàn'")
    row = cur.fetchone()
    if row:
        faxian_id = row[0]
    else:
        cur.execute("INSERT INTO word (pinyin, definition) VALUES ('fāxiàn', 'discover; find out; realize')")
        faxian_id = cur.lastrowid
        cur.execute("INSERT INTO character (character, pinyin, definition, audio, word_id) VALUES ('发', 'fā', 'send out; emit', '/audio/faxian_char1.mp3', ?)", (faxian_id,))
        cur.execute("INSERT INTO character (character, pinyin, definition, audio, word_id) VALUES ('现', 'xiàn', 'appear; present', '/audio/faxian_char2.mp3', ?)", (faxian_id,))
    
    # Word 3: yiwei
    cur.execute("SELECT id FROM word WHERE pinyin='yiwei' OR pinyin='yǐwéi'")
    row = cur.fetchone()
    if row:
        yiwei_id = row[0]
    else:
        cur.execute("INSERT INTO word (pinyin, definition) VALUES ('yǐwéi', 'think (mistakenly); assume')")
        yiwei_id = cur.lastrowid
        cur.execute("INSERT INTO character (character, pinyin, definition, audio, word_id) VALUES ('以', 'yǐ', 'use; take', '/audio/yiwei_char1.mp3', ?)", (yiwei_id,))
        cur.execute("INSERT INTO character (character, pinyin, definition, audio, word_id) VALUES ('为', 'wéi', 'think; consider', '/audio/yiwei_char2.mp3', ?)", (yiwei_id,))
    
    # Word 4: renwei
    cur.execute("SELECT id FROM word WHERE pinyin='renwei' OR pinyin='rènwéi'")
    row = cur.fetchone()
    if row:
        renwei_id = row[0]
    else:
        cur.execute("INSERT INTO word (pinyin, definition) VALUES ('rènwéi', 'think; consider; believe')")
        renwei_id = cur.lastrowid
        cur.execute("INSERT INTO character (character, pinyin, definition, audio, word_id) VALUES ('认', 'rèn', 'recognize; know', '/audio/renwei_char1.mp3', ?)", (renwei_id,))
        cur.execute("INSERT INTO character (character, pinyin, definition, audio, word_id) VALUES ('为', 'wéi', 'think; consider', '/audio/renwei_char2.mp3', ?)", (renwei_id,))
    
    # Word 5: yinwei
    cur.execute("SELECT id FROM word WHERE pinyin='yinwei' OR pinyin='yīnwèi'")
    row = cur.fetchone()
    if row:
        yinwei_id = row[0]
    else:
        cur.execute("INSERT INTO word (pinyin, definition) VALUES ('yīnwèi', 'because; since')")
        yinwei_id = cur.lastrowid
        cur.execute("INSERT INTO character (character, pinyin, definition, audio, word_id) VALUES ('因', 'yīn', 'cause; reason', '/audio/yinwei_char1.mp3', ?)", (yinwei_id,))
        cur.execute("INSERT INTO character (character, pinyin, definition, audio, word_id) VALUES ('为', 'wèi', 'for; because', '/audio/yinwei_char2.mp3', ?)", (yinwei_id,))
    
    # Word 6: suoyi
    cur.execute("SELECT id FROM word WHERE pinyin='suoyi' OR pinyin='suǒyǐ'")
    row = cur.fetchone()
    if row:
        suoyi_id = row[0]
    else:
        cur.execute("INSERT INTO word (pinyin, definition) VALUES ('suǒyǐ', 'so; therefore')")
        suoyi_id = cur.lastrowid
        cur.execute("INSERT INTO character (character, pinyin, definition, audio, word_id) VALUES ('所', 'suǒ', 'place; that which', '/audio/suoyi_char1.mp3', ?)", (suoyi_id,))
        cur.execute("INSERT INTO character (character, pinyin, definition, audio, word_id) VALUES ('以', 'yǐ', 'use; by means of', '/audio/suoyi_char2.mp3', ?)", (suoyi_id,))
    
    # Insert confusable pairs
    pairs = [
        {
            'w1': fasheng_id, 'w2': faxian_id,
            'reason': 'Both start with the character "fa" and have similar pinyin, making them easy to confuse.',
            'difference': 'fasheng: indicates the occurrence or emergence of an event, emphasizing something coming into being.\nfaxian: indicates finding or realizing something that already exists but was not noticed.',
            'examples': 'Yesterday something big happened. (fasheng)\nI discovered a secret. (faxian)\nYou cannot say: I "happened" a secret.\nYou cannot say: Yesterday something big was "discovered".',
            'tips': 'fasheng = happen (events appear)\nfaxian = discover (find existing things)',
            'level': 1
        },
        {
            'w1': yiwei_id, 'w2': renwei_id,
            'reason': 'Both express "thinking/believing" but differ in certainty and correctness of the judgment.',
            'difference': 'yiwei: subjective belief, usually implies the judgment was WRONG.\nrenwei: objective thinking/believing, neutral expression.',
            'examples': 'I thought (yiwei) he was a teacher, but actually he is a student.\nI think (renwei) this plan is very good.\nNote: "yiwei" often implies later discovering the judgment was wrong.',
            'tips': 'yiwei = assume (often wrong)\nrenwei = think/believe (neutral judgment)',
            'level': 2
        },
        {
            'w1': yinwei_id, 'w2': suoyi_id,
            'reason': 'These two words are often used together but express opposite logical directions: cause vs. result.',
            'difference': 'yinwei: introduces the REASON/CAUSE.\nsuoyi: introduces the RESULT/CONCLUSION.\nThey are often paired: yinwei...suoyi... (because...therefore...)',
            'examples': 'Because (yinwei) it rained, therefore (suoyi) I stayed home.\nyinwei introduces the cause; suoyi introduces the result.',
            'tips': 'yinwei = because (cause)\nsuoyi = therefore (result)\nOften used together as a pair!',
            'level': 1
        },
    ]
    
    for p in pairs:
        cur.execute(
            "INSERT INTO confusable_pairs (word1_id, word2_id, reason, difference, examples, tips, difficulty_level) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (p['w1'], p['w2'], p['reason'], p['difference'], p['examples'], p['tips'], p['level'])
        )
    
    conn.commit()
    print(f"Seeded {len(pairs)} confusable pairs successfully!")
    
    # Verify
    cur.execute("SELECT COUNT(*) FROM confusable_pairs")
    print(f"Total confusable pairs in DB: {cur.fetchone()[0]}")
    
    conn.close()

if __name__ == '__main__':
    setup_confusable_tables()
