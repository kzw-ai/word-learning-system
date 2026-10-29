"""学习资料制作的公共函数：读取源数据，并实现论文附录里共用的处理。

每个函数注明对应论文的哪个附录。和附录不同的地方，在函数说明里写明理由。
路径都相对于「学习资料制作」文件夹，从哪里运行都可以。
"""
import csv
import hashlib
import io
import json
import math
import os
import pathlib
import re
import zipfile

import jieba
import openpyxl
import xlrd

W = pathlib.Path(__file__).resolve().parents[1]          # 学习资料制作/
SRC = W / '1_源数据'
OUT = W / '2_加工结果'
REVIEW = W / '3_审核'

HSK_XLS = SRC / 'HSK词表' / 'HSK-2012（分级词汇表 国家汉办-权威）.xls'
BCC_HSK4 = SRC / 'BCC词频' / '新HSK四级词汇词频排序（参照BCC语料库.xlsx'
BCC_ALL = SRC / 'BCC词频' / 'multi_domain_total_word_freq.zip'
TEXTBOOKS = SRC / '教材语料'
CCA_EDU = SRC / '搭配知识库' / 'edu_collocation_data.xlsx'
CCA_WIKI = SRC / '搭配知识库' / 'wiki_collocation_data.txt.zip'
CEDICT = SRC / 'CC-CEDICT词典' / 'cedict_1_0_ts_utf-8_mdbg.zip'
HSK_CORPUS = SRC / 'HSK动态作文语料库'

jieba.setLogLevel(60)

LEVEL_NAMES = '一二三四五六'
PUNCTUATION = ['，', '。', '？', '！', '”', '“', '：', '、', '；', '（', '）', '《', '》']


# ---------- HSK 2012 词表（附录 A、I、K、AD 都从它取词） ----------

def hsk_entries():
    """汉办词表的全部条目：[(词, 等级)]，同一个词可以有多个条目（如「等（动词）（二级）」「等（助词）（四级）」）。

    附录用 `str[:-4]` 去掉「（X级）」取词。有 24 个条目格式特殊：标了词性的「长（形容词）（二级）」、
    组合形式的「因为……所以……（二级）」。这里去掉词性、把组合拆成单个词。
    """
    out = []
    for v in xlrd.open_workbook(HSK_XLS).sheet_by_index(0).col_values(0):
        m = re.match(r'(.+?)（(.)级）$', str(v).strip())
        if not m:
            continue
        body = re.sub(r'（.+?）', '', m.group(1)).strip()
        lv = LEVEL_NAMES.index(m.group(2)) + 1
        out += [(w, lv) for w in (p.strip() for p in re.split(r'…+', body) if p.strip())]
    return out


def hsk_levels():
    """词 → 等级（1–6）。同一个词有多个条目时取最低等级（学习者最早学到它的级别）。"""
    level = {}
    for w, lv in hsk_entries():
        if w not in level or lv < level[w]:
            level[w] = lv
    return level


def hsk_grade4_words():
    """汉办词表里有四级条目的词（含「等」「得」这类另有低级条目的词）。"""
    return sorted({w for w, lv in hsk_entries() if lv == 4})


def hsk1_to_3(levels=None):
    levels = levels or hsk_levels()
    return sorted(w for w, lv in levels.items() if lv <= 3)


# ---------- 教材语料（附录 B、C、H） ----------

_KEEP = re.compile('[。！；，：“”（）、？《》一-龥0-9０-９%％]')
# 数字之间的小数点、比号、范围号要留下，否则「2.99元」「1:4」「20~ 30年」会变成「299元」「14」「2030年」。
# 分隔符和数字之间可以夹空格（空格本身不保留）。
_SEPARATORS = set('.．:：—–-~～')
_DIGITS = set('0123456789０１２３４５６７８９')


def _between_digits(text, i):
    before = text[:i].rstrip(' \u3000')
    after = text[i + 1:].lstrip(' \u3000')
    return bool(before) and bool(after) and before[-1] in _DIGITS and after[0] in _DIGITS


def _clean(text):
    return ''.join(ch for i, ch in enumerate(text)
                   if _KEEP.match(ch) or (ch in _SEPARATORS and _between_digits(text, i)))


def textbook_texts():
    """[(教材名, 清洗后的课文)]。

    附录 B：只保留汉字与中文标点。附录 B 的标点里没有「！」，但附录 H 按「！」切句，原意是按感叹号断句，
    所以这里也保留「！」。另外保留数字、百分号和数字之间的小数点、比号、范围号：只留汉字会把「晚上6点了」变成
    「晚上点了」、把「2.99元」变成「299元」；拉丁字母不留，因为教材里的拼音和英文注释会混进句子。附录 C 把各本合并成一个文件；这里保留教材名，方便注明例句出处，内容不变。
    """
    out = []
    for f in sorted(TEXTBOOKS.iterdir()):
        if f.suffix == '.txt':
            text = f.read_text(encoding='utf-8', errors='ignore')
        elif f.suffix == '.docx':
            xml = zipfile.ZipFile(f).read('word/document.xml').decode('utf-8')
            text = re.sub(r'<[^>]+>', '', re.sub(r'</w:p>', '\n', xml))
        else:
            continue
        out.append((f.stem.replace(' 课文语料', ''), _clean(text)))
    return out


def split_sentences(text):
    """附录 H 的 seg_tail_split：按「。？！」切句，句末标点留在句尾。"""
    parts = re.split(r'(。|？|！)', text)
    return [a + b for a, b in zip(parts[0::2], parts[1::2] + [''])]


def tokenize(sentence):
    """附录 D、H、K：结巴分词，默认词典。"""
    return jieba.lcut(sentence)


def without_punctuation(tokens):
    """附录 I、M：去掉中文标点。"""
    return [t for t in tokens if t not in PUNCTUATION]


# ---------- 词汇复杂度、句子复杂度（附录 L、M） ----------

def word_complexity():
    """附录 L：词汇复杂度 = 词频取对数后取倒数，再最小–最大规范化到 [0, 1]。

    论文用 BCC Global 词频表；新版 BCC 不再提供它，这里用多领域总表（与 Global 的四级词排名相关 0.91）。
    词频为 1 的词取对数为 0，倒数无意义，与附录一样无法计算，这里跳过。
    """
    z = zipfile.ZipFile(BCC_ALL)
    inv = {}
    with z.open(z.namelist()[0]) as f:
        for row in csv.DictReader(io.TextIOWrapper(f, encoding='utf-8')):
            try:
                n = int(row['count'])
            except (KeyError, ValueError):
                continue
            if n > 1:
                inv[row['token'].strip()] = 1 / math.log(n)
    lo, hi = min(inv.values()), max(inv.values())
    return {w: (v - lo) / (hi - lo) for w, v in inv.items()}


def sentence_complexity(tokens, complexity):
    """附录 M：句中各词（去掉标点）复杂度之和；词频表里查不到的词按 0 计（同附录 `get(i, 0)`）。"""
    return sum(complexity.get(t, 0.0) for t in without_punctuation(tokens))


# ---------- 搭配（附录 N） ----------

CCA_TYPES = {'V_O': '动宾', 'V_HV_O': '动宾', 'V_2HV_O': '动宾', 'D_V': '状中', 'S_V_HV': '主谓', 'P_X_DN': '介方',
             'V_C': '述补', 'S_V': '主谓', 'D_A': '状中', 'Q_N': '量名', 'V_D_C': '述补', 'P_X_U': '介方', 'P_X_V': '介谓',
             'A_N': '定中', 'A_X_DE_N': '定中', 'D_X_A': '状中', 'P_X_V_HV': '介谓', 'D_X_V': '状中', 'V_U_C': '述补',
             'A_DE_N': '定中', 'V_X_C': '述补', 'V_C_U': '述补', 'D_DI_V': '状中', 'V_U_X_C': '述补', 'V_M_C': '述补',
             'V_U_A_C': '述补', 'A_X_N': '定中', 'V_U_D_C': '述补', 'V_U_M_C': '述补', 'A_DE_X_N': '定中',
             'P_X_V_2HV': '介谓', 'S_V_2HV': '主谓', 'V_A_C': '述补', 'C_X_C': '关联'}


def load_collocation_rows():
    """中文搭配知识库的两个子库：(教材库行, 维基库行)，每行为
    (ID, Collocation, Type, Parent, Frequency, Frequency_with_variants, Mutual_Information)。"""
    edu = list(openpyxl.load_workbook(CCA_EDU, read_only=True).worksheets[0].iter_rows(values_only=True))[1:]
    wiki = []
    with zipfile.ZipFile(CCA_WIKI) as z:
        name = next(n for n in z.namelist() if n.endswith('.txt') and not n.startswith('__MACOSX'))
        with z.open(name) as f:
            for line in io.TextIOWrapper(f, encoding='utf-8'):
                p = line.rstrip('\n').split('\t')
                if len(p) == 7:
                    wiki.append(p)
    return edu, wiki


def collocations_for(word, rows, levels):
    """附录 N：去掉目标词取出搭配词，标注 HSK 等级，只留一至三级，按互信息降序。

    附录用中文搭配助手网站导出的表；这里直接用它的知识库原始数据（字段相同）。
    附录判断等级用「包含」（'服务' in '服务员'，注释里说明是有意的），会把「学」记成「学生」的等级；
    这里改为精确匹配，只认词表里确有的词。只取两个词组成的搭配。
    """
    out = []
    for r in rows:
        toks = str(r[1]).split()
        if len(toks) != 2 or word not in toks or toks[0] == toks[1]:
            continue
        other = toks[1] if toks[0] == word else toks[0]
        lv = levels.get(other)
        if lv is None or lv > 3:
            continue
        try:
            out.append({'collocation': ' '.join(toks), 'other': other, 'level': lv,
                        'type': CCA_TYPES.get(str(r[2]), str(r[2])), 'freq': int(float(r[4])), 'mi': float(r[6])})
        except (TypeError, ValueError):
            continue
    out.sort(key=lambda c: -c['mi'])
    return out


# ---------- CC-CEDICT（Pleco 内置的免费词典，论文脚注 15） ----------

def cedict():
    """简体词 → [{'pinyin': 'kao3 lu:4', 'senses': [...]}]"""
    z = zipfile.ZipFile(CEDICT)
    entries = {}
    for line in z.read(z.namelist()[0]).decode('utf-8').splitlines():
        m = re.match(r'(\S+) (\S+) \[([^\]]+)\] /(.+)/$', line)
        if m:
            entries.setdefault(m.group(2), []).append({'pinyin': m.group(3), 'senses': m.group(4).split('/')})
    return entries


def level_label(lv):
    return f'（{LEVEL_NAMES[lv - 1]}级）'


# ---------- 任务指纹（大模型回答对应哪一版任务） ----------

def task_hash(task):
    """任务内容（指令、格式、输入）的指纹。回答里记下它，任务一变就知道旧回答不能再用。"""
    return hashlib.sha256(json.dumps(task, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def batch_file(sub, batch, name):
    """2_加工结果/<sub>/<批>/<name>；本批没有时用别的批次里的（易混淆词只在第一次出现的那批做，后面的批次辨析时要用它）"""
    path = OUT / sub / batch / name
    if path.exists():
        return path
    others = sorted((OUT / sub).glob(f'*/{name}'))
    return others[0] if others else path


def write_json(path, data):
    """先写临时文件再改名，中途出错不会留下写了一半的文件。"""
    tmp = path.with_name(f'{path.name}.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(path)


def answer_problems(answer, task, validate):
    """回答能不能用：任务指纹对得上（回答里的 _task），且 validate(answer, task) 没有挑出问题。返回问题列表。"""
    if answer.get('_task') != task_hash(task):
        return ['回答对应的不是现在这一版任务（任务改过，或回答里没有记录任务指纹）']
    return validate(answer, task)


def load_answer(path, task, validate):
    """读取并检查一份回答；不能用就报错退出，说明原因。"""
    if not path.exists():
        raise SystemExit(f'找不到 {path}')
    answer = json.loads(path.read_text(encoding='utf-8'))
    if problems := answer_problems(answer, task, validate):
        raise SystemExit(f'{path.name} 不能用：' + '；'.join(problems[:5]))
    return answer
