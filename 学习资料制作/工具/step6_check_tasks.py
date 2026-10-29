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
请为易混淆词辨析编写内容，读者是母语不是中文的中级学习者（学过一至三级词），系统界面是英文：
**讲解一律用简单、清楚的英文**（避免语法术语，非用不可时简单解释），中文只出现在例句、搭配和词本身里；
中文句子里除这两个词外只用一至三级常用词。词第一次出现时写成「汉字 拼音」，如「考虑 kǎolǜ」。
任务里给了两个词各自学习资料中的义项、例句、搭配；learner_errors 是改正后的原句（「正确的词{CC学习者写的词}」，
其余括号是别的标注），只供你分析混淆点，不要照抄进任何学习内容。
1. reason：一两句英文，说明两个词为什么容易混（意思、用法上的相同点）。
2. confusion_points：根据 learner_errors 归纳学习者实际在哪些用法上该用 word1 却写成了 word2，1–3 条，每条一句英文。
3. difference：分条用英文说明区别，每条一行，要覆盖上面的混淆点；可以夹中文短语举例。
4. collocation_contrast：2–4 行搭配对比，格式如「考虑问题 ✓ (think a problem over) / 想问题 ✓ (think about a problem)」，
   说不通的标 ✗，尽量用任务里的搭配，每个搭配后括号里给英文意思。
5. english：一行，两个词各自对应的英文意思，如「考虑 kǎolǜ = to consider, think over; 想 xiǎng = to think, want to, miss」。
6. examples：4–6 行。✓ 行格式「✓ 中文句子。 (English translation)」，✓ 的句子必须是换成另一个词就不对或意思变了的
   （否则分不出两个词），优先用任务里给的例句。✗ 行格式「✗ 错句。 → 正句。 (English translation) Short English reason.」，
   至少两句 ✗ 要对准 confusion_points，即该用 word1 却用了 word2 的句子；自己用一至三级词编写，不要照抄 learner_errors。
7. tips：一句英文的记忆提示。
8. difficulty_level：1–3，1 表示最容易分清。
9. quiz_checks：quiz_candidates 是辨析题候选，括号处挖掉了 answer。对每一题判断：
   other_fits——把另一个词放进括号，句子是否仍然正确通顺（是则这题有两个答案，不能用）；
   usable——句子是否完整、易懂、适合作辨析题；
   explanation——一句简单的英文，说明为什么这里用 answer、另一个词为什么不行（学习者答完题后看）。
只按下面的 JSON 格式回答，不要输出别的内容。"""

PAIR_FORMAT = {
    'reason': 'Both mean "suddenly", and both can come before a verb.',
    'confusion_points': ['Learners use 忽然 after 很 ("very"), but 忽然 cannot follow 很.'],
    'difference': '突然 tūrán can describe a thing (这件事很突然 "this was very sudden") or come before a verb;\n'
                  '忽然 hūrán can only come before a verb.',
    'collocation_contrast': ['很突然 ✓ (very sudden) / 很忽然 ✗', '突然的变化 ✓ (a sudden change) / 忽然的变化 ✗'],
    'english': '突然 tūrán = sudden, suddenly; 忽然 hūrán = suddenly (only before a verb)',
    'examples': ['✓ 这件事发生得很突然。 (This happened very suddenly.)',
                 '✗ 这件事发生得很忽然。 → 这件事发生得很突然。 (This happened very suddenly.) 忽然 cannot follow 很.'],
    'tips': 'If you can put 很 in front, use 突然.',
    'difficulty_level': 2,
    'quiz_checks': {'q1': {'other_fits': False, 'usable': True, 'explanation': 'After 很 you need 突然; 忽然 cannot follow 很.'},
                    'q2': {'other_fits': True, 'usable': True, 'explanation': 'Both words work here.'}},
}

QUIZ_PER_WORD = 6


def pair_key(word, other):
    return f'{word}-{other}'


def word_outputs(word, home):
    """一个词第 3–5 步的产出（候选清单、判断、取舍），都取它所在的那一批（home_batches），
    不混用不同批次的文件：判断里的句子编号对应的是同一批的候选清单。缺了就报错，要先把那一批跑完。"""
    batch = home.get(word)
    paths = {sub: common.OUT / sub / str(batch) / name for sub, name in
             (('候选清单', f'{word}.json'), ('判断', f'{word}.判断.json'), ('取舍', f'{word}.json'))}
    if batch is None or not all(p.exists() for p in paths.values()):
        raise SystemExit(f'「{word}」在 {batch or "任何一批的词表"} 里还没有第 3–5 步的产出：先把那一批跑到第 5 步')
    return {sub: json.loads(p.read_text(encoding='utf-8')) for sub, p in paths.items()}


def quiz_candidates(words, home):
    """辨析题候选（论文 3.2.4：句子来自学习材料里的例句）：两个词各自可用的例句，按复杂度从低到高，
    目标词作为完整的词只出现一次的，整词挖空。返回 {'q1': {'stem', 'answer', 'sentence'}}。"""
    out = {}
    for w in words:
        outputs = word_outputs(w, home)
        cand, senses = outputs['候选清单'], outputs['判断']['sentence_senses']
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


def pair_task(word, other, stats, home):
    def side(w):
        sel = word_outputs(w, home)['取舍']
        return {'word': w, 'hsk_level': sel['hsk_level'],
                'senses': [f"{s['pos']} {s['definition']}" for s in sel['senses']],
                'examples': [s['example']['sentence'] for s in sel['senses'] if s['example']],
                'collocations': [c['collocation'] for s in sel['senses'] for c in s['collocations']]}
    quiz = quiz_candidates([word, other], home)
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
        if not (isinstance(c, dict) and isinstance(c.get('other_fits'), bool) and isinstance(c.get('usable'), bool)
                and isinstance(c.get('explanation'), str) and c['explanation'].strip()):
            problems.append(f'quiz_checks 缺 {k}，或缺 other_fits、usable、explanation')
    return problems


def confusable_pairs(batch, home=None):
    """这一批要做的易混淆词对：[(目标词, 易混淆词, 语料库统计)]。
    - 两个方向都入选的（四级词之间，如「经历 → 经验」「经验 → 经历」）是同一对，只做一次：
      保留学习者写错次数多的方向，另一个方向的统计也写进讲解。
    - 一对放在两个词里靠后出现的那一批做：那时两个词第 3–5 步的产出都有了（易混淆词排在目标词后面或前面的批次）。
      两个词有一个不在任何一批的词表里时不做。"""
    home = home if home is not None else step2_confusables.home_batches()
    rows = sorted(step2_confusables.selected_rows(), key=lambda r: (-int(r['times']), -float(r['share'])))
    order = {b: i for i, b in enumerate(sorted(set(home.values())))}
    pairs, seen = [], {}
    for r in rows:
        word, other = r['target'], r['confused_with']
        stats = {'wrote_word2': int(r['times']), 'word1_errors': int(r['target_errors']), 'share': float(r['share'])}
        key = frozenset((word, other))
        if key in seen:
            seen[key]['reverse'] = stats  # 另一个方向：该用 other 的地方写成了 word
            continue
        seen[key] = stats
        if word in home and other in home and max(home[word], home[other], key=order.get) == batch:
            pairs.append((word, other, stats))
    return pairs


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
    pair_only = step2_confusables.pair_only_words(batch)
    checked = [w for w in words if w not in pair_only]  # 只做辨析的词已有学习材料，不用翻译检查
    src = common.OUT / '取舍' / batch
    outdir = common.OUT / '检查' / batch
    outdir.mkdir(parents=True, exist_ok=True)
    for word in checked:
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
    home = step2_confusables.home_batches()
    pairs = confusable_pairs(batch, home)
    for word, other, stats in pairs:
        common.write_json(outdir / f'{pair_key(word, other)}.任务.json', pair_task(word, other, stats, home))
    print(f'已生成 {len(checked)} 个检查任务、{len(pairs)} 个易混淆词辨析任务：{outdir}')
    if model:
        step4_semantic_tasks.answer_with(model, outdir, checked, kind='检查', check=validate)
        step4_semantic_tasks.answer_with(model, outdir, [pair_key(w, o) for w, o, _ in pairs], kind='辨析', check=validate_pair)


if __name__ == '__main__':
    args = sys.argv[1:]
    main(args[0], args[args.index('--model') + 1] if '--model' in args else None)
