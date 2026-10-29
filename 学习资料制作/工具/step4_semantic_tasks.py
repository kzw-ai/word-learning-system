"""第 4 步　语义判断任务（大模型）：义项、例句属于哪个义项、搭配是否成立、字词释义。

用法：学习资料制作/.venv/bin/python 学习资料制作/工具/step4_semantic_tasks.py 第01批 [--model deepseek-flash]
产出：2_加工结果/判断/第01批/<词>.任务.json（发给大模型的输入与回答格式）
      回答存为同目录的 <词>.判断.<来源>.json，格式见下面 ANSWER_FORMAT；来源是 claude-code（在对话里填写）
      或 deepseek-flash / deepseek-v4-pro（加 --model 时自动调用接口）。回答里记下任务指纹 _task：
      已有回答且对应同一版任务、结构合格的词跳过；改了指令或候选清单后，旧回答作废，会重新作答。
      第 5 步读 <词>.判断.json：核对后把采用的那一份复制成这个名字。

规则判断（选哪个义项、哪句例句、哪两条搭配）不在这里做，见第 5 步。
"""
import json
import sys

import common
import llm
import step2_confusables

INSTRUCTIONS = """你在为学习新 HSK 四级词汇的外国学习者（中级，学过一至三级词）编写学习资料，按北京大学硕士论文的方法。
只做语义判断，不做取舍（取舍由程序按论文规则完成）。

1. senses：这个词面向中级学习者的义项，1–3 个，以 CC-CEDICT 为依据合并细碎的英文释义；
   每个义项给词性缩写（n. v. adj. adv. prep. conj. m. aux. 等）和简洁的英文释义（沿用 CC-CEDICT 的措辞）。
   只合并同一个意思的不同说法；意思不同的要分开（如「想」的 want to 和 miss 是两个义项），不要为凑数合并。
2. sentence_senses：每个例句里这个词用的是哪个义项（填义项 id）。例句会直接展示给学习者，要求从严，
   有下列情况之一就填 null，并在 sentence_notes 里简述原因：
   句首或句中引号、括号不配对（是对话或引文的片段）；列举中的一项（「一是……」「二是……」）或明显承接上文、离开上下文看不懂；
   标题和正文粘在一起；缺字、错字、混进页码、繁体字、数字被截断等录入问题；文言、方言或过于文学化；
   句子在讨论词语本身的用法（元语言）而不是在使用这个词。
3. collocation_senses：搭配是从语料自动抽取的，大量是偶然共现，要从严。成立的条件：学习者会把这两个词当作一个短语来说，
   两词之间有直接的语法关系（动宾、偏正、主谓、状中），而且这个组合本身有意义（如「认真 考虑」「时间 允许」「收拾 房间」）。
   填 null 的：几乎能和任何动词搭配的副词或虚词（也、都、还、又、已经、就、只、才、一边），除非组合是固定说法（如「本 想」）；
   随意的名词作主语或宾语（如「银行 估计」「北京 邀请」「手机 允许」）；颠倒了正常语序、生僻或不自然的。
   成立的搭配填它对应的义项 id，要确认搭配里的意思确实是那个义项（如「想 家」属于 miss，不属于 want to）。
4. characters：词里每个字在这个词里的读音（带声调拼音）、词性缩写和英文释义（取 CC-CEDICT 里与这个词意思相关的义项）。
只按下面的 JSON 格式回答，不要输出别的内容。"""

ANSWER_FORMAT = {
    'senses': [{'id': 's1', 'pos': 'v.', 'definition': 'think over; consider'}],
    'sentence_senses': {'1': 's1', '2': None},
    'sentence_notes': {'2': '句子不完整'},
    'collocation_senses': {'edu1': 's1', 'edu2': None, 'wiki1': 's1'},
    'characters': [{'character': '考', 'pinyin': 'kǎo', 'pos': 'v.', 'definition': 'examine; consider'}],
}


# 另有一至三级条目的四级词（600 个里只有这两个）：汉办词表的四级条目只指一个义项，学习材料只做这个义项，
# 不然教材里多见的低级义项（「过得很开心」的结构助词 de）会按句数被选为主义项。只加在这两个词的任务里，
# 不改 INSTRUCTIONS：改了它，所有词的任务指纹都会变、已有回答全部作废
HSK4_ENTRY = {
    '得': '汉办词表里「得」另有二级条目（助词 de，「过得很开心」）；四级条目是助动词 děi（to have to; must; need to）。'
          'senses 只列助动词 děi 这一个义项；例句、搭配里用的是别的意思的，一律填 null，sentence_notes 写「不是四级义项」；'
          'characters 只有一项，读音、释义按 děi。',
    '等': '汉办词表里「等」另有二级条目（动词 děng，to wait）；四级条目是助词（and so on; etc.，如「北京、上海等城市」）。'
          'senses 只列这个助词义项；例句、搭配里用的是别的意思的，一律填 null，sentence_notes 写「不是四级义项」；'
          'characters 只有一项，读音、释义按这个助词。',
}


def validate(answer, task):
    """检查语义判断的结构：义项编号唯一，每个例句、每条搭配都有回答且引用的义项存在，每个字都有释义。"""
    problems = []
    senses = answer.get('senses')
    if not isinstance(senses, list) or not senses:
        return ['senses 为空']
    if task.get('hsk4_entry') and len(senses) != 1:
        problems.append(f'只该列四级条目的一个义项，回答列了 {len(senses)} 个')
    ids = [s.get('id') for s in senses if isinstance(s, dict)]
    if len(ids) != len(senses) or not all(isinstance(i, str) and i for i in ids) or len(set(ids)) != len(ids):
        problems.append(f'义项编号缺失、不是字符串或重复：{ids}')
    for s in senses:
        if not (isinstance(s, dict) and s.get('pos') and s.get('definition')):
            problems.append(f'义项缺词性或释义：{s}')
    for key, items in (('sentence_senses', task['sentences']), ('collocation_senses', task['collocations'])):
        got = answer.get(key)
        if not isinstance(got, dict):
            problems.append(f'{key} 缺失')
            continue
        if missing := [k for k in items if k not in got]:
            problems.append(f'{key} 漏答 {missing}')
        if extra := [k for k in got if k not in items]:
            problems.append(f'{key} 多出不存在的编号 {extra}')
        if bad := {k: v for k, v in got.items() if v is not None and v not in ids}:
            problems.append(f'{key} 引用了不存在的义项 {bad}')
    chars = [c.get('character') for c in answer.get('characters', []) if isinstance(c, dict)]
    if chars != list(task['word']):
        problems.append(f"characters 应依次是 {list(task['word'])}，回答是 {chars}")
    elif not all(c.get('pinyin') and c.get('pos') and c.get('definition') for c in answer['characters']):
        problems.append('有字缺拼音、词性或释义')
    return problems


def answer_with(model, outdir, words, kind='判断', check=validate):
    """读 <词>.任务.json，调用接口，把回答存为 <词>.<kind>.<model>.json（第 6 步也用它）。
    已有回答且对应同一版任务、结构合格的词跳过；回答不合格就报错停止，不写文件。"""
    log = outdir / f'用量.{model}.jsonl'
    for word in words:
        out = outdir / f'{word}.{kind}.{model}.json'
        task = json.loads((outdir / f'{word}.任务.json').read_text(encoding='utf-8'))
        if out.exists() and not common.answer_problems(json.loads(out.read_text(encoding='utf-8')), task, check):
            continue
        payload = {k: v for k, v in task.items() if k not in ('instructions', 'answer_format')}
        system = task['instructions'] + '\n\n回答格式（JSON）示例：\n' + json.dumps(task['answer_format'], ensure_ascii=False)
        answer, usage = llm.ask_json(model, system, json.dumps(payload, ensure_ascii=False, indent=1))
        with open(log, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'word': word, 'task': common.task_hash(task), **usage}, ensure_ascii=False) + '\n')
        answer['_task'] = common.task_hash(task)
        if problems := check(answer, task):
            bad = out.with_name(out.name + '.不合格')
            common.write_json(bad, answer)
            raise SystemExit(f'{word}：{model} 的回答不合格（{"；".join(problems[:5])}），已存为 {bad.name}，已停止')
        common.write_json(out, answer)
        print(f"{word}：输入 {usage.get('prompt_tokens')}，输出 {usage.get('completion_tokens')} token，{usage['seconds']} 秒", flush=True)


# 判断任务里来自候选清单的部分；说明和回答格式不算（只改了说明不必重新判断）
INPUT_KEYS = ('word', 'cedict_word', 'cedict_chars', 'sentences', 'collocations')


def task_inputs(word, c):
    """由候选清单生成判断任务的输入：词典、例句和搭配（编号即回答里用的 1、2… 和 edu1、wiki1…）"""
    return {
        'word': word,
        'cedict_word': [f"[{e['pinyin']}] " + ' / '.join(e['senses']) for e in c['cedict_word']],
        'cedict_chars': {ch: [f"[{e['pinyin']}] " + ' / '.join(e['senses'][:10]) for e in es[:4]] for ch, es in c['cedict_chars'].items()},
        'sentences': {str(i): s['sentence'] for i, s in enumerate(c['sentences'], 1)},
        'collocations': {**{f'edu{i}': x['collocation'] for i, x in enumerate(c['collocations_edu'], 1)},
                         **{f'wiki{i}': x['collocation'] for i, x in enumerate(c['collocations_wiki'], 1)}},
    }


def check_candidates(task, candidates, word):
    """判断里的例句、搭配编号对应生成任务时的候选清单；第 4 步之后重跑过第 3 步、候选变了，旧判断就不能用"""
    if {k: task.get(k) for k in INPUT_KEYS} != task_inputs(word, candidates):
        raise SystemExit(f'「{word}」的候选清单在第 4 步之后改过，判断里的例句、搭配编号已对不上：重新跑第 4 步')


def main(batch, model=None):
    words = step2_confusables.words_from_args([batch])
    src = common.OUT / '候选清单' / batch
    outdir = common.OUT / '判断' / batch
    outdir.mkdir(parents=True, exist_ok=True)
    for word in words:
        c = json.loads((src / f'{word}.json').read_text(encoding='utf-8'))
        inputs = task_inputs(word, c)
        # 键的顺序与以前相同，任务文件和指纹不变
        task = {'word': word, 'instructions': INSTRUCTIONS, 'answer_format': ANSWER_FORMAT,
                **{k: inputs[k] for k in INPUT_KEYS[1:]}}
        if word in HSK4_ENTRY:
            task['hsk4_entry'] = HSK4_ENTRY[word]
        common.write_json(outdir / f'{word}.任务.json', task)
    print(f'已生成 {len(words)} 个判断任务：{outdir}')
    if model:
        answer_with(model, outdir, words)


if __name__ == '__main__':
    args = sys.argv[1:]
    model = args[args.index('--model') + 1] if '--model' in args else None
    main(args[0], model)
