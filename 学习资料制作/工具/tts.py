"""Azure 语音合成（第 8 步用）：晓晓女声、语速慢 10%（作者试听后选定），多音字按校对过的拼音指定读音。

Key 放在 工具/azure_speech_key.txt（第一行 Key，第二行区域，如 eastus；不提交）。
免费档（F0）每分钟最多 20 次请求、每月 50 万字符（一个汉字计 2 个字符，SSML 标签也计费）；
额度用完只拒绝、不收费。出错直接报错退出，不自动重试；已生成的文件保留，重新运行从这里继续。

读音标注（SSML phoneme，alphabet="sapi"，如「得」→ dei 3）只加在需要的字上：
标注会让引擎完全照标的读，「一」「不」的变调、轻声就由不得它了，而且标签也计费。
所以只有多音字、而且校对过的拼音和 pypinyin 默认读法不同（拼音不同，或者声调不同且都不是轻声）时才标，
例如「我得走了」的「得」（默认 dé，应为 děi）；「一」「不」只差变调的不标，儿化的「儿」也不标。
"""
import hashlib
import html
import re
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

from pypinyin import Style, lazy_pinyin, pinyin

KEY_FILE = Path(__file__).resolve().parent / 'azure_speech_key.txt'
VOICE = 'zh-CN-XiaoxiaoNeural'
RATE = '-10%'
FORMAT = 'audio-24khz-48kbitrate-mono-mp3'
MIN_INTERVAL = 3.2  # 免费档每分钟 20 次
TONE_MARKS = {'̄': 1, '́': 2, '̌': 3, '̀': 4}
SANDHI = set('一不')
# 不标注的字：「一」「不」的变调交给引擎；儿化的「儿」在 sapi 里要和前一个音节合写（「一会儿」hui r 4），不单独标
NO_MARK = SANDHI | {'儿'}
_last_request = [0.0]


def _key():
    lines = [l.strip() for l in KEY_FILE.read_text(encoding='utf-8').splitlines() if l.strip()] if KEY_FILE.exists() else []
    if len(lines) < 2:
        raise SystemExit(f'{KEY_FILE}：第一行填 Azure 语音的 Key，第二行填区域（如 eastus）')
    return lines[0], lines[1]


def split_tone(syllable):
    """带调拼音 → (不带调的拼音，ü 保留, 声调 1–5)；没有调号的是轻声 5"""
    tone, base = 5, []
    for ch in unicodedata.normalize('NFD', syllable.lower()):
        if ch in TONE_MARKS:
            tone = TONE_MARKS[ch]
        else:
            base.append(ch)
    return unicodedata.normalize('NFC', ''.join(base)), tone


def to_sapi(syllable):
    """带调拼音 → Azure 普通话 sapi 音标：nǚ → nv 3，lüè → lue 4，qù → qu 4，ba → ba 5
    （Azure 文档：单独的 ü 韵母写 v，如「女 nv 3」；üe 写 ue，如「略 lue 4」）"""
    base, tone = split_tone(syllable)
    base = re.sub('(?<=[nl])ü$', 'v', base).replace('ü', 'u')
    return f'{base} {tone}'


def readings(ch):
    """一个字可能的读音（带调和不带调两种写法，不带调的对应轻声）"""
    out = set()
    for p in pinyin(ch, style=Style.TONE, heteronym=True)[0]:
        out |= {p, split_tone(p)[0]}
    if ch == '儿':
        out.add('r')
    return out


def split_syllables(hanzi, word_pinyin):
    """「考虑」+「kǎolǜ」→ ['kǎo', 'lǜ']；拆不出来（含非汉字、拼音对不上）时返回 None"""
    s = unicodedata.normalize('NFC', re.sub(r"[\s'’\-]", '', word_pinyin.lower()))

    def go(i, k):
        if i == len(hanzi):
            return [] if k == len(s) else None
        for r in sorted(readings(hanzi[i]), key=len, reverse=True):
            if s.startswith(r, k) and (rest := go(i + 1, k + len(r))) is not None:
                return [r] + rest
        return None
    return go(0, 0)


def is_polyphonic(ch):
    return len({split_tone(p) for p in pinyin(ch, style=Style.TONE, heteronym=True)[0]}) > 1


def needs_mark(ch, mine, default):
    if ch in NO_MARK or not is_polyphonic(ch):
        return False
    (a, ta), (b, tb) = split_tone(mine), split_tone(default)
    return a != b or (ta != tb and 5 not in (ta, tb))


def marked(tokens):
    """[(汉字串, 拼音或 None)] → SSML 正文：需要的字加 phoneme 标注，其余照原文（转义）"""
    out = []
    for text, py in tokens:
        syllables = split_syllables(text, py) if py else None
        if not syllables:
            out.append(html.escape(text))
            continue
        defaults = lazy_pinyin(text, style=Style.TONE)  # 按词给的默认读法（pypinyin 的词典考虑了词内上下文）
        for ch, mine, default in zip(text, syllables, defaults):
            if needs_mark(ch, mine, default):
                out.append(f'<phoneme alphabet="sapi" ph="{to_sapi(mine)}">{html.escape(ch)}</phoneme>')
            else:
                out.append(html.escape(ch))
    return ''.join(out)


def ssml(tokens):
    return (f'<speak version="1.0" xml:lang="zh-CN"><voice name="{VOICE}">'
            f'<prosody rate="{RATE}">{marked(tokens)}</prosody></voice></speak>')


def file_name(doc):
    """内容指纹作文件名：声音、语速、格式、SSML 不变就不重新生成"""
    return hashlib.sha256('|'.join((VOICE, RATE, FORMAT, doc)).encode()).hexdigest()[:16] + '.mp3'


def synthesize(doc, path):
    """生成一个 mp3；文件已存在就跳过。返回是否发了请求。"""
    if path.exists():
        return False
    key, region = _key()
    wait = MIN_INTERVAL - (time.time() - _last_request[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(
        f'https://{region}.tts.speech.microsoft.com/cognitiveservices/v1', data=doc.encode('utf-8'), method='POST',
        headers={'Ocp-Apim-Subscription-Key': key, 'Content-Type': 'application/ssml+xml',
                 'X-Microsoft-OutputFormat': FORMAT, 'User-Agent': 'learnchinese-materials'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        raise SystemExit(f'Azure 返回 HTTP {e.code}：{e.read()[:200]!r}。已停止；已生成的音频保留，重新运行会从这里继续')
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        raise SystemExit(f'连接 Azure 出错（{type(e).__name__}: {e}），已停止；重新运行会从这里继续')
    finally:
        _last_request[0] = time.time()
    if not data:
        raise SystemExit('Azure 返回了空音频，已停止')
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_bytes(data)
    tmp.replace(path)
    return True
