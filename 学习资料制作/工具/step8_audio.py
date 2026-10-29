"""第 8 步　发音音频（论文 5.3：字、词、搭配、句子都配发音，见附录 O；这里改用 Azure 语音，见 tts.py）。

用法：学习资料制作/.venv/bin/python 学习资料制作/工具/step8_audio.py 第01批
        给这一批的整词、每个字、每条搭配、每条例句各生成一个 mp3，音频地址写回 3_审核/<批>/素材.json，
        并生成 3_审核/<批>/试听.html 供审核。第 7 步重跑后要再跑这一步（已生成的不重复请求）。
      学习资料制作/.venv/bin/python 学习资料制作/工具/step8_audio.py --thesis [--db 路径]
        论文词库（默认 words_extended.db；本地库比服务器旧时，用跑过启动初始化的副本）里已有材料的词：生成音频，清单写到 data/learning_materials/audio/论文词库.json，
        后端启动时按清单补进库里（scripts/apply_audio_manifest.py）。
产出：data/learning_materials/audio/<内容指纹>.mp3（不提交，部署时连同批次素材复制到服务器）。

拼音：整词、字用校对过的拼音；例句用第 6 步校对过的分词拼音（「我/wǒ 得/děi …」）；
搭配没有单独校对的拼音，只给其中的目标词按整词拼音标注，其余交给引擎按上下文读。
"""
import html
import json
import re
import sqlite3
import sys

import common
import tts

AUDIO = common.W.parent / 'data' / 'learning_materials' / 'audio'
URL = '/api/audio/'
THESIS_DB = common.W.parent / 'words_extended.db'
THESIS_MANIFEST = AUDIO / '论文词库.json'
LEVEL_NOTE = re.compile(r'（[一二三四五六]级）')


def clean_collocation(text):
    """「认真（三级） 考虑」→「认真考虑」：去掉等级标注和分隔空格"""
    return LEVEL_NOTE.sub('', text).replace(' ', '').replace('　', '')


def collocation_tokens(text, hanzi, word_pinyin):
    s = clean_collocation(text)
    i = s.find(hanzi) if hanzi else -1
    if i < 0:
        return [(s, None)]
    return [(s[:i], None), (hanzi, word_pinyin), (s[i + len(hanzi):], None)]


SPEAKER = re.compile(r'^[一-鿿]{1,4}：')


def sentence_tokens(sentence, pinyin_line):
    """「我/wǒ 得/děi 走/zǒu 了/le 。」→ [('我', 'wǒ'), …, ('。', None)]。
    按词对齐原句：拼音行里漏掉的标点照原句补上；人名拼音里的空格（「李进/Lǐ Jìn」）并回前一个词；
    拼音行缺了句尾几个词时，那几个词照原文读、不标注；中间对不上时整句不标注。
    对话例句开头的说话人（「李进：」）不读。"""
    s = re.sub(r'\s', '', sentence)
    out, k = [], 0
    for t in (pinyin_line or '').split():
        word, sep, py = t.partition('/')
        if not sep and out and out[-1][1] is not None and re.fullmatch(r'[a-zA-Zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜü]+', word):
            out[-1] = (out[-1][0], out[-1][1] + word)
            continue
        j = s.find(word, k)
        if j < 0 or not only_punctuation(s[k:j]):
            return drop_speaker([(s, None)])
        out += [(s[k:j], None)] if j > k else []
        out.append((word, py if sep else None))
        k = j + len(word)
    return drop_speaker(out + ([(s[k:], None)] if k < len(s) else []))


def only_punctuation(text):
    return not re.search(r'[0-9A-Za-z一-鿿]', text)


def drop_speaker(tokens):
    text = ''.join(t for t, _ in tokens)
    m = SPEAKER.match(text)
    if not m:
        return tokens
    n, out = len(m.group(0)), []
    for t, py in tokens:
        if n >= len(t):
            n -= len(t)
        elif n:
            out.append((t[n:], None))  # 说话人和台词连在一个词里：这一段不标注
            n = 0
        else:
            out.append((t, py))
    return out


def billable(doc):
    """计费字符数的估计：汉字计 2，<speak>、<voice> 标签不计（Azure 文档）"""
    body = re.sub(r'</?(speak|voice)[^>]*>', '', doc)
    return sum(2 if '一' <= ch <= '鿿' else 1 for ch in body)


class Generator:
    """收集要生成的音频，先算新增的计费字符，再逐个生成"""

    def __init__(self):
        self.jobs = {}

    def add(self, tokens):
        doc = tts.ssml(tokens)
        name = tts.file_name(doc)
        self.jobs[name] = doc
        return URL + name

    def run(self):
        todo = {n: d for n, d in self.jobs.items() if not (AUDIO / n).exists()}
        chars = sum(billable(d) for d in todo.values())
        print(f'共 {len(self.jobs)} 个音频，要新生成 {len(todo)} 个，约 {chars} 个计费字符'
              f'（免费档每月 50 万），约 {len(todo) * tts.MIN_INTERVAL / 60:.0f} 分钟', flush=True)
        for i, (name, doc) in enumerate(todo.items(), 1):
            tts.synthesize(doc, AUDIO / name)
            if i % 20 == 0 or i == len(todo):
                print(f'  {i}/{len(todo)}', flush=True)


def add_word(gen, w):
    """一个词的全部音频，写进各自的 audio 字段"""
    w['audio'] = gen.add([(w['hanzi'], w['pinyin'])])
    for c in w['characters']:
        c['audio'] = gen.add([(c['character'], c['pinyin'])])
    for c in w['collocations']:
        c['audio'] = gen.add(collocation_tokens(c['collocation'], w['hanzi'], w['pinyin']))
    for e in w['examples']:
        e['audio'] = gen.add(sentence_tokens(e['sentence'], e.get('pinyin')))


def listening_page(batch, words):
    """试听页：每个词一节，字、词、搭配、例句旁边是播放按钮（音频在仓库的 data/learning_materials/audio）"""
    rel = '../../../data/learning_materials/audio/'
    play = lambda url: f'<audio controls preload="none" src="{rel}{url[len(URL):]}"></audio>'
    parts = []
    for w in words:
        rows = [('整词', f"{w['hanzi']}　{w['pinyin']}", w['audio'])]
        rows += [('字', f"{c['character']}　{c['pinyin']}", c['audio']) for c in w['characters']]
        rows += [('搭配', c['collocation'], c['audio']) for c in w['collocations']]
        rows += [('例句', e['sentence'], e['audio']) for e in w['examples']]
        body = ''.join(f'<tr><td class="k">{k}</td><td>{html.escape(t)}</td><td>{play(a)}</td></tr>' for k, t, a in rows)
        parts.append(f'<h3>{html.escape(w["hanzi"])}</h3><table>{body}</table>')
    return (f'<!doctype html><meta charset="utf-8"><title>试听　{batch}</title><style>'
            'body{font:15px -apple-system,sans-serif;margin:24px;max-width:900px}table{border-collapse:collapse;width:100%}'
            'td{border:1px solid #ddd;padding:6px 8px}td.k{color:#888;width:3em}audio{height:32px}</style>'
            f'<h2>试听　{batch}</h2><p>声音 {tts.VOICE}，语速 {tts.RATE}。读错的字记下来：改正拼音后重跑第 8 步。</p>'
            + ''.join(parts))


def batch_main(batch):
    path = common.REVIEW / batch / '素材.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    gen = Generator()
    for w in data['words']:
        add_word(gen, w)
    gen.run()
    common.write_json(path, data)
    (common.REVIEW / batch / '试听.html').write_text(listening_page(batch, data['words']), encoding='utf-8')
    print(f'音频地址已写回 {path}；试听：{common.REVIEW / batch / "试听.html"}')


def thesis_words(db=THESIS_DB):
    """论文词库里有字的词（没有字的是早期种子留下的空壳，不配音），字段同批次素材"""
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    words = []
    for w in conn.execute('SELECT id, pinyin FROM word ORDER BY id'):
        chars = [dict(r) for r in conn.execute('SELECT character, pinyin FROM character WHERE word_id = ? ORDER BY id', (w['id'],))]
        if not chars:
            continue
        words.append({
            'hanzi': ''.join(c['character'] for c in chars), 'pinyin': w['pinyin'], 'characters': chars,
            'collocations': [dict(r) for r in conn.execute('SELECT collocation FROM collocation WHERE word_id = ? ORDER BY id', (w['id'],))],
            'examples': [dict(r) for r in conn.execute('SELECT sentence, pinyin FROM example WHERE word_id = ? ORDER BY id', (w['id'],))],
        })
    conn.close()
    return words


def thesis_main(db=THESIS_DB):
    words = thesis_words(db)
    gen = Generator()
    for w in words:
        add_word(gen, w)
    gen.run()
    manifest = {'voice': tts.VOICE, 'rate': tts.RATE, 'words': [
        {'hanzi': w['hanzi'], 'audio': w['audio'],
         'characters': [{'character': c['character'], 'audio': c['audio']} for c in w['characters']],
         'collocations': [{'collocation': c['collocation'], 'audio': c['audio']} for c in w['collocations']],
         'examples': [{'sentence': e['sentence'], 'audio': e['audio']} for e in w['examples']]}
        for w in words]}
    common.write_json(THESIS_MANIFEST, manifest)
    page = common.W / '3_审核' / '论文词库试听.html'
    page.write_text(listening_page('论文词库', words).replace('../../../', '../../'), encoding='utf-8')
    print(f'{len(words)} 个词 → {THESIS_MANIFEST}；试听：{page}')


if __name__ == '__main__':
    args = sys.argv[1:]
    if args and args[0] == '--thesis':
        thesis_main(args[args.index('--db') + 1] if '--db' in args else THESIS_DB)
    else:
        batch_main(args[0])
