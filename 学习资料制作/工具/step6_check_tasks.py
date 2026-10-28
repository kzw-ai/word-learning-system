"""第 6 步　翻译与检查任务（大模型）：例句和搭配的英文翻译、拼音校对、练习题干扰项和填字题的检查；
有入选的易混淆词对时，再起草辨析内容（论文 2.2.4、3.2.4）。

用法：学习资料制作/.venv/bin/python 学习资料制作/工具/step6_check_tasks.py 第01批 [--model deepseek-flash]
输入：第 5 步的取舍结果 2_加工结果/取舍/第01批/<词>.json
产出：2_加工结果/检查/第01批/<词>.任务.json；回答存为 <词>.检查.<来源>.json（同第 4 步）。
      第 7 步读 <词>.检查.json：核对后把采用的那一份复制成这个名字。回答里记下任务指纹，规则同第 4 步。

易混淆词对单独一个任务 <目标词>-<易混淆词>.任务.json，回答存为 <目标词>-<易混淆词>.辨析.<来源>.json，
采用的复制成 <目标词>-<易混淆词>.辨析.json。辨析例句优先用两个词各自学习资料里的例句，不用语料库里学习者写的句子。

拼音先由 pypinyin 按结巴分词自动标注（格式同现有材料「我/wǒ 认为/rènwéi …」），大模型只负责改错（轻声、多音字）。
"""
import csv
import json
import sys

import jieba
from pypinyin import Style, lazy_pinyin

import common
import step2_confusables
import step4_semantic_tasks
import step5_select

INSTRUCTIONS = """你在为学习新 HSK 四级词汇的外国学习者（中级，学过一至三级词）检查学习资料。取舍已经按规则定好，不要改动选了哪些句子和搭配。

1. word_pinyin：目标词的带声调拼音（轻声不标调，如 shōushi）。
2. examples：每个例句给自然、准确的英文翻译；核对 pinyin_auto（逐词标注，自动生成，常把轻声标成本调、多音字读错），
   给出改正后的 pinyin，格式保持「词/拼音」，词与词之间用空格，标点单独占位不加斜杠。
3. collocations：每条搭配给简短的英文翻译（像词典里的搭配释义）。
4. distractor_conflicts：选择题里，除正确答案外，options 和 spares（备用干扰项）中哪些词放进题干也说得通
   （释义题：这个词也符合这个英文释义；搭配题：放进括号也是自然的搭配）。会造成两个正确答案的都要列出。
   key 为题号（definition、collocation1、collocation2，以任务里有的为准），值为说得通的词的列表，没有就给空列表。
5. fill_word：填字题挖掉的是目标词的一个字。other_fits 列出放进括号也能组成通顺句子的其他常用汉字（没有就空列表）；
   hint 是挖掉那个字的带声调拼音，只在 other_fits 不为空时给出，否则为 null。
只按下面的 JSON 格式回答，不要输出别的内容。"""

ANSWER_FORMAT = {
    'word_pinyin': 'kǎolǜ',
    'examples': [{'sentence': '我会认真考虑的。', 'pinyin': '我/wǒ 会/huì 认真/rènzhēn 考虑/kǎolǜ 的/de 。',
                  'translation': "I'll think it over carefully."}],
    'collocations': [{'collocation': '认真 考虑', 'translation': 'consider carefully'}],
    'distractor_conflicts': {'definition': [], 'collocation1': ['仔细', '好好'], 'collocation2': []},
    'fill_word': {'other_fits': [], 'hint': None},
}


def auto_pinyin(sentence):
    out = []
    for t in jieba.lcut(sentence):
        out.append(t if t in common.PUNCTUATION or not t.strip() else f"{t}/{''.join(lazy_pinyin(t, style=Style.TONE))}")
    return ' '.join(out)


PAIR_INSTRUCTIONS = """学习者常把这两个词用混：HSK 动态作文语料库里，该用 word1 的地方，学习者常写成 word2
（corpus：该用 word1 的偏误共 word1_errors 处，其中 wrote_word2 处写成了 word2）。辨析要对准学习者实际的混淆点。
请为易混淆词辨析编写内容，写给中级学习者（学过一至三级词），用中文；句子里除这两个词外只用一至三级常用词。
任务里给了两个词各自学习资料中的义项、例句、搭配；learner_errors 是改正后的原句（「正确的词{CC学习者写的词}」，
其余括号是别的标注），只供你分析混淆点，不要照抄进任何学习内容。
1. reason：一两句话，说明两个词为什么容易混（意思、用法上的相同点）。
2. confusion_points：根据 learner_errors 归纳学习者实际在哪些用法上该用 word1 却写成了 word2，1–3 条，每条一句。
3. difference：分条说明区别（词性、搭配对象、语义轻重、句式限制等），每条一行，要覆盖上面的混淆点。
4. collocation_contrast：2–4 行搭配对比，如「考虑问题（✓） / 想问题（✓），想家（✓） / 考虑家（✗）」，尽量用任务里的搭配。
5. english：一行英文对比，说明两个词对应的英文意思和区别。
6. examples：4–6 行，每行以「✓ 」或「✗ 」开头。✓ 的句子必须是换成另一个词就不对或意思变了的（否则分不出两个词），
   优先用任务里给的例句；✗ 的句子是换词后确实不能说的，句末括号里简述原因。
   至少两句 ✗ 要对准 confusion_points，即该用 word1 却用了 word2 的句子；自己用一至三级词编写，不要照抄 learner_errors。
7. tips：一句话的记忆提示。
8. difficulty_level：1–3，1 表示最容易分清。
9. quiz_checks：quiz_candidates 是辨析题候选，括号处挖掉了 answer。对每一题判断：
   other_fits——把另一个词放进括号，句子是否仍然正确通顺（是则这题有两个答案，不能用）；
   usable——句子是否完整、易懂、适合作辨析题。
只按下面的 JSON 格式回答，不要输出别的内容。"""

PAIR_FORMAT = {
    'reason': '两个词都表示"事情发生得快、出乎意料"，且都能作状语。',
    'confusion_points': ['学习者在"很___"里也用「忽然」，但「忽然」不能被"很"修饰。'],
    'difference': '「突然」是形容词，可以作状语、定语、谓语，可以被"很"修饰；\n「忽然」是副词，只能作状语。',
    'collocation_contrast': ['很突然（✓） / 很忽然（✗）', '突然的变化（✓） / 忽然的变化（✗）'],
    'english': '突然 = sudden / suddenly (adj. & adv.); 忽然 = suddenly (adv. only).',
    'examples': ['✓ 这件事发生得很突然。', '✗ 这件事发生得很忽然。（忽然是副词，不能被"很"修饰）'],
    'tips': '能说"很突然"，不能说"很忽然"。',
    'difficulty_level': 2,
    'quiz_checks': {'q1': {'other_fits': False, 'usable': True}, 'q2': {'other_fits': True, 'usable': True}},
}

QUIZ_PER_WORD = 6


def pair_key(word, other):
    return f'{word}-{other}'


def quiz_candidates(words, batch):
    """辨析题候选（论文 3.2.4：句子来自学习材料里的例句）：两个词各自可用的例句，按复杂度从低到高，
    目标词作为完整的词只出现一次的，整词挖空。返回 {'q1': {'stem', 'answer', 'sentence'}}。"""
    out = {}
    for w in words:
        cand_path = common.OUT / '候选清单' / batch / f'{w}.json'
        judge_path = common.OUT / '判断' / batch / f'{w}.判断.json'
        if not (cand_path.exists() and judge_path.exists()):
            continue
        cand = json.loads(cand_path.read_text(encoding='utf-8'))
        senses = json.loads(judge_path.read_text(encoding='utf-8'))['sentence_senses']
        n = 0
        for i, c in enumerate(cand['sentences'], 1):
            if n == QUIZ_PER_WORD:
                break
            start = step5_select.word_start(c['sentence'], c['tokens'], w)
            if senses.get(str(i)) is None or start is None:
                continue
            s = c['sentence']
            n += 1
            out[f'q{len(out) + 1}'] = {'stem': (s[:start] + step5_select.BLANK + s[start + len(w):]).strip(),
                                       'answer': w, 'sentence': s}
    return out


def pair_task(word, other, src, stats, batch):
    def side(w):
        path = src / f'{w}.json'
        if not path.exists():
            return {'word': w}
        sel = json.loads(path.read_text(encoding='utf-8'))
        return {'word': w, 'hsk_level': sel['hsk_level'],
                'senses': [f"{s['pos']} {s['definition']}" for s in sel['senses']],
                'examples': [s['example']['sentence'] for s in sel['senses'] if s['example']],
                'collocations': [c['collocation'] for s in sel['senses'] for c in s['collocations']]}
    quiz = quiz_candidates([word, other], batch)
    return {'word': pair_key(word, other), 'instructions': PAIR_INSTRUCTIONS, 'answer_format': PAIR_FORMAT,
            'word1': side(word), 'word2': side(other), 'corpus': stats,
            'learner_errors': step2_confusables.error_sentences(word, other),
            'quiz_candidates': {k: {'stem': q['stem'], 'answer': q['answer']} for k, q in quiz.items()}}


def validate_pair(answer, task):
    problems = [f'缺 {k}' for k in ('reason', 'difference', 'tips', 'english')
                if not isinstance(answer.get(k), str) or not answer[k].strip()]
    for k in ('confusion_points', 'collocation_contrast'):
        if not isinstance(answer.get(k), list) or not answer[k] or not all(isinstance(x, str) and x.strip() for x in answer[k]):
            problems.append(f'{k} 应是非空的句子列表')
    lines = answer.get('examples')
    if not isinstance(lines, list) or len(lines) < 3 or not all(isinstance(x, str) and x[:1] in '✓✗' for x in lines):
        problems.append('examples 应是至少 3 行、以 ✓ 或 ✗ 开头的句子')
    elif not any(x.startswith('✓') for x in lines) or not any(x.startswith('✗') for x in lines):
        problems.append('examples 要同时有 ✓ 和 ✗ 的句子')
    if answer.get('difficulty_level') not in (1, 2, 3):
        problems.append('difficulty_level 应是 1、2、3')
    checks = answer.get('quiz_checks')
    for k in task['quiz_candidates']:
        c = checks.get(k) if isinstance(checks, dict) else None
        if not (isinstance(c, dict) and isinstance(c.get('other_fits'), bool) and isinstance(c.get('usable'), bool)):
            problems.append(f'quiz_checks 缺 {k} 或格式不对')
    return problems


def confusable_pairs(words):
    """这一批里入选的易混淆词对：[(目标词, 易混淆词, 语料库统计)]。"""
    rows = list(csv.DictReader(open(step2_confusables.RESULT, encoding='utf-8'))) if step2_confusables.RESULT.exists() else []
    return [(r['target'], r['confused_with'], {'wrote_word2': int(r['times']), 'word1_errors': int(r['target_errors']),
                                                'share': float(r['share'])})
            for r in rows if r['target'] in words and r['selected'] == 'yes']


def hanzi_of(pinyin_line):
    """「我/wǒ 想/xiǎng 。」→「我想。」，用来核对标注后的拼音没有漏词、改字。"""
    return ''.join(t.split('/')[0] for t in pinyin_line.split())


def validate(answer, task):
    """检查翻译与检查回答：每个例句、每条搭配都有翻译，拼音里的字和原句一致，每道选择题都给了冲突列表。"""
    problems = []
    if not isinstance(answer.get('word_pinyin'), str) or not answer['word_pinyin'].strip():
        problems.append('缺 word_pinyin')
    got = {e.get('sentence'): e for e in answer.get('examples', []) if isinstance(e, dict)}
    for e in task['examples']:
        a = got.get(e['sentence'])
        if not a or not a.get('translation') or not a.get('pinyin'):
            problems.append(f"例句缺翻译或拼音：{e['sentence']}")
        elif hanzi_of(a['pinyin']) != e['sentence'].replace(' ', ''):
            problems.append(f"例句拼音里的字和原句不一致：{a['pinyin']}")
    got = {c.get('collocation'): c for c in answer.get('collocations', []) if isinstance(c, dict)}
    problems += [f'搭配缺翻译：{c}' for c in task['collocations'] if not (got.get(c) or {}).get('translation')]
    conflicts = answer.get('distractor_conflicts')
    for key, q in task['exercises'].items():
        if key == 'fill_word':
            continue
        if not isinstance(conflicts, dict) or not isinstance(conflicts.get(key), list):
            problems.append(f'distractor_conflicts 缺 {key}')
        elif stray := [w for w in conflicts[key] if w not in q['options'] + q['spares'] or w == q['correct_answer']]:
            problems.append(f'{key} 的冲突列表里有不是干扰项的词：{stray}')
    if 'fill_word' in task['exercises']:
        fill = answer.get('fill_word')
        if not isinstance(fill, dict) or not isinstance(fill.get('other_fits'), list):
            problems.append('fill_word 缺 other_fits')
        elif fill['other_fits'] and not fill.get('hint'):
            problems.append('填字题有其他字也说得通，却没有给拼音提示 hint')
    return problems


def main(batch, model=None):
    words = step2_confusables.words_from_args([batch])
    src = common.OUT / '取舍' / batch
    outdir = common.OUT / '检查' / batch
    outdir.mkdir(parents=True, exist_ok=True)
    for word in words:
        sel = json.loads((src / f'{word}.json').read_text(encoding='utf-8'))
        ex = sel['exercises'] or {}
        exercises = {}
        if ex.get('definition'):
            exercises['definition'] = {k: ex['definition'][k] for k in ('stem', 'options', 'correct_answer', 'spares')}
        for i, c in enumerate(ex.get('collocation', []), 1):
            exercises[f'collocation{i}'] = {k: c[k] for k in ('stem', 'options', 'correct_answer', 'spares')}
        if ex.get('fill_word'):
            exercises['fill_word'] = {k: ex['fill_word'][k] for k in ('stem', 'correct_answer')}
        task = {
            'word': word,
            'instructions': INSTRUCTIONS,
            'answer_format': ANSWER_FORMAT,
            'senses': [f"{s['pos']} {s['definition']}" for s in sel['senses']],
            'examples': [{'sentence': s['example']['sentence'], 'pinyin_auto': auto_pinyin(s['example']['sentence'])}
                         for s in sel['senses'] if s['example']],
            'collocations': [c['collocation'] for s in sel['senses'] for c in s['collocations']],
            'exercises': exercises,
        }
        common.write_json(outdir / f'{word}.任务.json', task)
    pairs = confusable_pairs(words)
    for word, other, stats in pairs:
        common.write_json(outdir / f'{pair_key(word, other)}.任务.json', pair_task(word, other, src, stats, batch))
    print(f'已生成 {len(words)} 个检查任务、{len(pairs)} 个易混淆词辨析任务：{outdir}')
    if model:
        step4_semantic_tasks.answer_with(model, outdir, words, kind='检查', check=validate)
        step4_semantic_tasks.answer_with(model, outdir, [pair_key(w, o) for w, o, _ in pairs], kind='辨析', check=validate_pair)


if __name__ == '__main__':
    args = sys.argv[1:]
    main(args[0], args[args.index('--model') + 1] if '--model' in args else None)
