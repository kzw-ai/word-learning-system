"""第 8b 步　练习题中文选项的发音（练习页每个中文选项旁边的小喇叭）。

用法：学习资料制作/.venv/bin/python 学习资料制作/工具/step8b_option_audio.py [--db 路径]
        从库里（默认 words_extended.db；本地库比服务器旧时，用跑过启动初始化的副本）所有练习题的中文选项生成 mp3，
        清单写到 data/learning_materials/audio/选项.json（{选项原文: 地址}），出题接口按清单给每个选项带上发音。
产出：data/learning_materials/audio/<内容指纹>.mp3，和第 8 步的音频放在一起（不提交，部署时复制到服务器）。

以前选项没有音频，用的是手机自带的朗读：iPhone 打开静音开关时不出声，声音也和学习页的晓晓不一样。

读音：选项正好是库里的词时，用这个词校对过的拼音（和学习页整词发音是同一个文件，不重复生成）；
其余多字词交给引擎按词读；单个多音字没有上下文，一律标注读音：带词性说明的（「还（动词）」）按说明，
其余用最常用的读音（READING 里改过几个）。
"""
import json
import re
import sqlite3
import sys

from pypinyin import Style, pinyin

import common
import tts
from step8_audio import AUDIO, THESIS_DB, Generator

MANIFEST = AUDIO / '选项.json'
NOTE = re.compile(r'（[^）]*）')
# 带词性说明的选项：说明决定读音
NOTED = {'喂（叹词）': 'wèi', '地（助词）': 'de', '种（量词）': 'zhǒng', '等（动词）': 'děng', '花（动词）': 'huā',
         '花（名词）': 'huā', '过（助词）': 'guo', '还（副词）': 'hái', '还（动词）': 'huán'}
# 单字单独出现时的读音，和 pypinyin 的默认读音不同的几个
READING = {'教': 'jiāo', '长': 'cháng', '谁': 'shéi'}


def forced(ch, py):
    """单个字，强制按给的读音读"""
    body = f'<phoneme alphabet="sapi" ph="{tts.to_sapi(py)}">{ch}</phoneme>'
    return (f'<speak version="1.0" xml:lang="zh-CN"><voice name="{tts.VOICE}">'
            f'<prosody rate="{tts.RATE}">{body}</prosody></voice></speak>')


def option_texts(conn):
    texts = set()
    for (raw,) in conn.execute('SELECT options_json FROM exercise_item'):
        for option in json.loads(raw or '[]'):
            if isinstance(option, str) and re.search(r'[一-鿿]', option):
                texts.add(option)
    return sorted(texts)


def word_pinyin(conn):
    out = {}
    for word_id, py in conn.execute('SELECT id, pinyin FROM word'):
        hanzi = ''.join(c for (c,) in conn.execute('SELECT character FROM character WHERE word_id = ? ORDER BY id', (word_id,)))
        if hanzi:
            out[hanzi] = py
    return out


def main(db=THESIS_DB):
    conn = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    words = word_pinyin(conn)
    texts = option_texts(conn)
    conn.close()
    gen = Generator()
    manifest, skipped = {}, []
    for option in texts:
        clean = NOTE.sub('', option).strip()
        if not re.fullmatch(r'[一-鿿]+', clean):
            skipped.append(option)  # 「因为 …… 所以 ……」这类句式，不读
            continue
        if option in NOTED or (len(clean) == 1 and clean not in words and tts.is_polyphonic(clean)):
            py = NOTED.get(option) or READING.get(clean) or pinyin(clean, style=Style.TONE)[0][0]
            doc = forced(clean, py)
            name = tts.file_name(doc)
            gen.jobs[name] = doc
            manifest[option] = '/api/audio/' + name
        else:
            manifest[option] = gen.add([(clean, words.get(clean))])
    gen.run()
    common.write_json(MANIFEST, {'voice': tts.VOICE, 'rate': tts.RATE, 'options': manifest})
    print(f'{len(manifest)} 个选项 → {MANIFEST}；没有配音：{"、".join(skipped) or "无"}')


if __name__ == '__main__':
    args = sys.argv[1:]
    main(args[args.index('--db') + 1] if '--db' in args else THESIS_DB)
