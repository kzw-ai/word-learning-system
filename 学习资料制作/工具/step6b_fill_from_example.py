"""第 6b 步　填字题改用学习页上的例句（作者 2026-10-30；论文 3.2 节：填词题的「句子来自于学习模块的例句」）。

用法：学习资料制作/.venv/bin/python 学习资料制作/工具/step6b_fill_from_example.py 第02批 [--model deepseek-flash] [--apply]

此前第 5 步用主义项的第二句可用例句出填字题，学习者在例句页上没见过那句，有的句子里别的字比答案自然得多
（「我不明白，为什么 ( d ) 有人叫我“奶奶”？」答案「得」，「会」「总」更顺）。现在第 5 步改为先用例句本身；
这一步给已经做好、审核过的批次补做同样的改动，只动填字题：

1. 每个词用主义项的例句（第 6 步截短之后、学习页上显示的那句），按分词结果挖掉目标词的最后一个字（规则同第 5 步）。
   例句里目标词不是只出现一次的完整词时，保留原来的填字题。
2. 句子和原来的填字题不同时，只问大模型一个问题：括号里还能填哪些字（other_fits），以及答案字的拼音（hint）。
   任务 2_加工结果/检查/<批>/<词>-填字.任务.json，回答 <词>-填字.填字.<来源>.json（任务指纹规则同第 4 步）。
   和原来相同的（原来就只能用例句本身的），沿用第 6 步的检查结果，不再问。
3. 取舍结果里的填字题同步改掉，第 7 步重新生成素材时就和这里一致（第 7 步优先用这里的检查结果）。
4. --apply：只替换 data/learning_materials/hsk4/<批>.json 和 3_审核/<批>/素材.json 里每个词的那道填字题，
   别的内容一个字都不动（整批重新生成会带出别处的改动），改动列进 3_审核/<批>/填字题改用例句.md 供作者审核。
"""
import json
import re
import sys

import common
import step2_confusables
import step4_semantic_tasks
import step5_select
import step6_check_tasks
import step7_build

INSTRUCTIONS = """下面是一道给学习新 HSK 四级词汇的外国学习者（中级）做的填字题：句子里挖掉了目标词 word 的一个字，括号 ( ) 处
就是挖掉的位置，正确答案是 answer。请判断：
1. other_fits：除了 answer，还有哪些常用汉字放进括号也能组成通顺、自然的句子（意思可以不同）。没有就空列表；只列单个汉字，不要列 answer。
2. hint：answer 这个字在这句话里的带声调拼音（如 yīn、de）。只在 other_fits 不为空时给出，否则为 null。
只按下面的 JSON 格式回答，不要输出别的内容。"""

ANSWER_FORMAT = {'other_fits': ['来'], 'hint': 'yīn'}

TONED = re.compile(r'^[a-zü]*[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ][a-zü]*$|^[a-zü]+$')


def validate(answer, task):
    problems = []
    fits = answer.get('other_fits')
    if not isinstance(fits, list) or not all(isinstance(c, str) and len(c) == 1 for c in fits):
        problems.append('other_fits 要是单个汉字的列表')
    elif task['answer'] in fits:
        problems.append('other_fits 里不能有答案本身')
    elif fits and not (isinstance(answer.get('hint'), str) and TONED.match(answer['hint'])):
        problems.append('other_fits 不为空时要给答案字的拼音 hint')
    return problems


def tidy(answer, task):
    """去掉 other_fits 里的重复和答案本身、拼音两边的空格（不影响内容的格式问题）"""
    if isinstance(answer.get('other_fits'), list):
        answer['other_fits'] = list(dict.fromkeys(c.strip() for c in answer['other_fits']
                                                  if isinstance(c, str) and c.strip() and c.strip() != task['answer']))
    if isinstance(answer.get('hint'), str):
        answer['hint'] = answer['hint'].strip().lower()
    if not answer.get('other_fits'):
        answer['hint'] = None


def fill_from_example(word, sel):
    """主义项的例句出的填字题（同第 5 步）；例句里目标词不是只出现一次的完整词时 None"""
    e = sel['senses'][0]['example'] if sel['senses'] else None
    if not e:
        return None
    s, tokens = e['sentence'], e.get('tokens') or common.tokenize(e['sentence'])
    at = step5_select.blank_position(s, tokens, word)
    if at is None:
        return None
    return {'question_type': 'fill_word', 'stem': (s[:at] + step5_select.BLANK + s[at + 1:]).strip(), 'correct_answer': s[at],
            'sentence': s, 'same_as_example': True, 'from_example': True}


def task_name(word):
    return f'{word}-填字'


def task_for(word, fill):
    return {'word': word, 'instructions': INSTRUCTIONS, 'answer_format': ANSWER_FORMAT,
            'stem': fill['stem'], 'answer': fill['correct_answer']}


def question(fill, check):
    """素材里的填字题（同第 7 步）"""
    q = {'question_type': 'fill_word', 'stem': fill['stem'], 'correct_answer': fill['correct_answer'], 'options': []}
    if check.get('other_fits'):
        q['hint'] = step7_build.fill_hint(q['correct_answer'], check['hint'], check['other_fits'])
        q['stem'] = q['stem'].replace('( )', f"( {q['hint']} )", 1)
    return q


def load_check(batch, word, fill, source):
    """这道填字题的检查结果：6b 的回答（句子换过时），否则第 6 步的（句子没换）"""
    check_dir = common.OUT / '检查' / batch
    task_path = check_dir / f'{task_name(word)}.任务.json'
    if task_path.exists():
        task = json.loads(task_path.read_text(encoding='utf-8'))
        if task['stem'] == fill['stem']:
            return common.load_answer(check_dir / f'{task_name(word)}.填字.{source}.json', task, validate)
    name = f'{word}.检查.{source}.json'
    task = json.loads((check_dir / f'{word}.任务.json').read_text(encoding='utf-8'))
    return common.load_answer(check_dir / name, task, step6_check_tasks.validate).get('fill_word') or {}


def main(batch, model=None, apply=False, source='deepseek-flash'):
    sel_dir = common.OUT / '取舍' / batch
    check_dir = common.OUT / '检查' / batch
    pair_only = step2_confusables.pair_only_words(batch)
    words = [w for w in step2_confusables.words_from_args([batch]) if w not in pair_only]
    changed, kept, asks = [], [], []
    for word in words:
        path = sel_dir / f'{word}.json'
        sel = json.loads(path.read_text(encoding='utf-8'))
        old = (sel['exercises'] or {}).get('fill_word')
        new = fill_from_example(word, sel)
        if new is None or (old and old['sentence'] == new['sentence']):
            kept.append(word)
            continue
        new['previous'] = {k: old[k] for k in ('stem', 'sentence') if old and k in old}
        sel['exercises']['fill_word'] = new
        common.write_json(path, sel)
        common.write_json(check_dir / f'{task_name(word)}.任务.json', task_for(word, new))
        changed.append(word)
        asks.append(task_name(word))
    # 之前已经改过、取舍结果里已是例句的，也要有检查任务（重复运行时）
    for word in kept:
        sel = json.loads((sel_dir / f'{word}.json').read_text(encoding='utf-8'))
        fill = (sel['exercises'] or {}).get('fill_word')
        if fill and fill.get('from_example'):
            common.write_json(check_dir / f'{task_name(word)}.任务.json', task_for(word, fill))
            asks.append(task_name(word))
    print(f'{batch}：{len(changed)} 道填字题改用例句，{len(kept)} 道不变')
    if model and asks:
        step4_semantic_tasks.answer_with(model, check_dir, asks, kind='填字', check=validate, tidy=tidy)
    if apply:
        apply_batch(batch, words, source)


def apply_batch(batch, words, source):
    """只替换素材里每个词的填字题，其他内容不动；改动写进审核清单"""
    sel_dir = common.OUT / '取舍' / batch
    targets = [common.W.parent / 'data' / 'learning_materials' / 'hsk4' / f'{batch}.json', common.REVIEW / batch / '素材.json']
    docs = {p: json.loads(p.read_text(encoding='utf-8')) for p in targets if p.exists()}
    md = [f'# 填字题改用学习页上的例句　{batch}', '',
          '按论文 3.2 节，填字题的句子改用学习页上的例句（学习者刚在例句页见过这句）。只改了下面这些填字题，其他内容不变。',
          '请核对：括号里只能填答案（有别的字也说得通时，括号里给了答案字的声母或拼音）。', '']
    n = 0
    for word in words:
        sel = json.loads((sel_dir / f'{word}.json').read_text(encoding='utf-8'))
        fill = (sel['exercises'] or {}).get('fill_word')
        if not fill or not fill.get('from_example'):
            continue
        check = load_check(batch, word, fill, source)
        q = question(fill, check)
        for doc in docs.values():
            for w in doc['words']:
                if w['hanzi'] != word:
                    continue
                for i, item in enumerate(w['exercises']):
                    if item['question_type'] == 'fill_word':
                        w['exercises'][i] = q
        n += 1
        prev = fill.get('previous', {}).get('stem', '（原来没有填字题）')
        fits = '、'.join(check.get('other_fits') or []) or '无'
        md += [f'## {word}', '', f'- 原来：{prev}', f"- 现在：{q['stem']}　答案 {q['correct_answer']}",
               f'- 括号里也能填：{fits}' + (f"（已给提示 {q['hint']}）" if q.get('hint') else ''), '']
    for p, doc in docs.items():
        common.write_json(p, doc)
    (common.REVIEW / batch / '填字题改用例句.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    print(f'{batch}：素材里替换了 {n} 道填字题 → {", ".join(str(p) for p in docs)}')


if __name__ == '__main__':
    args = sys.argv[1:]
    main(args[0], args[args.index('--model') + 1] if '--model' in args else None, '--apply' in args)
