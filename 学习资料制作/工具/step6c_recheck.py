"""第 6c 步　选择题干扰项复查（大模型判两遍，说得通的换掉）。

四级批次 2026-11-04 至 05 做过一次（Gemini 判两遍，见 制作流程.md 第 6c 步），那次是在对话里跑的；
三级词起改用这个脚本、DeepSeek 判（作者 2026-11-12）。在第 7 步生成 素材.json 之后运行：

    HSK_LEVEL=3 DEEPSEEK_ENDPOINT=relay LLM_WORKERS=6 .venv/bin/python 工具/step6c_recheck.py 第01批 第02批 … --model deepseek-v4-pro
    （--all：3_审核 下全部批次）

1. 判两遍：每批一个任务，一次只判干扰项，逐个给理由。第二遍打乱题目和选项的顺序再判。两遍里任何一遍说「也说得通」就算冲突。
   搭配题附上这条搭配的英文意思（系统在题干下面显示它，作者 2026-11-05 定），按意思判。
   释义题里的易混淆词是论文有意放的（2.1 节），不判、不换。
2. 换：冲突的干扰项从学过的词（hsk_known）里随机给 40 个候选，让大模型挑说不通、类别分散的，再另开一遍判新的选项；
   还有冲突的，列进清单人工处理。
3. 产出：
   - 3_审核/<等级>/干扰项复查.json（不提交）：{批: {词: [{stem, correct_answer, old, options}]}}，第 7 步重新生成时
     按（题干、答案）换成复查后的选项（step7_build.apply_recheck）。
   - 3_审核/<等级>/干扰项复查.md：每道换过的题、判为说得通的理由，给人逐条看。
任务和回答在 2_加工结果/<等级>/干扰项复查/，已有合格回答的不再调用（同第 4 步）。
"""
import json
import random
import re
import sys

import common
import step4_semantic_tasks
import step5_select

JUDGE_INSTRUCTIONS = common.for_level("""你在检查给学习新 HSK 四级词汇的外国学习者（学过一至三级词）做的选择题。每道题只有一个正确答案 answer，
其余是干扰项 distractors。逐个看每个干扰项：学习者选它，在题目给的条件下是否也说得通、也算对。
- 释义题（definition）：题干是英文意思，问哪个中文词是这个意思。干扰项的意思和题干相同或非常接近（同义词、近义词、
  包含这个意思的常用说法）才算说得通。
- 搭配题（collocation）：题干是一个两词搭配，目标词换成了括号「( )」；gloss 是这条搭配的英文意思，学习者能看到。
  干扰项放进括号后，组成的短语是自然、常用的说法，而且意思符合 gloss，才算说得通。只是语法上能接、意思和 gloss 不同的，不算。
每个干扰项回答 fits（true 表示也说得通）和一句中文理由。拿不准的标 true。只按下面的 JSON 格式回答，不要输出别的内容。""")

JUDGE_FORMAT = {'q1': {'词A': {'fits': False, 'reason': '意思是……，和题干不同'},
                       '词B': {'fits': True, 'reason': '「词B 时间」也常说，意思也是……'}}}

PICK_INSTRUCTIONS = common.for_level("""你在为学习新 HSK 四级词汇的外国学习者（学过一至三级词）的选择题换干扰项。每道题给了题干、
正确答案 answer、保留的选项 keep，以及要换掉的个数 need 和候选词 candidates。
从 candidates 里挑 need 个新干扰项，要求：
1. 放进题目里明显说不通、不会被当成正确答案（释义题：意思和题干不同；搭配题：放进括号后不是常用说法，或意思和 gloss 不同）；
2. 不要都是同一类词，词性、类别尽量分散，也不要和 keep 里的词同类；
3. 不要挑和正确答案读音或字形很像、容易误导的词。
只按下面的 JSON 格式回答（每道题一个列表，正好 need 个，都必须来自 candidates），不要输出别的内容。""")

PICK_FORMAT = {'q1': ['词C', '词D']}


def strip_levels(text):
    return re.sub(r'（.级）', '', text).replace(' ', '')


def questions_of(material):
    """一个词的选择题（释义题、搭配题），搭配题带上英文意思"""
    gloss = {strip_levels(c['collocation']): c.get('translation') for c in material.get('collocations') or []}
    out = []
    for q in material['exercises']:
        if q['question_type'] not in ('definition', 'collocation'):
            continue
        item = {'type': q['question_type'], 'stem': q['stem'], 'answer': q['correct_answer'], 'options': list(q['options'])}
        if q['question_type'] == 'collocation':
            item['gloss'] = gloss.get(q['stem'].replace('( )', q['correct_answer']).replace(' ', ''))
        out.append(item)
    return out


def load_batch(batch):
    path = common.REVIEW / batch / '素材.json'
    if not path.exists():
        raise SystemExit(f'找不到 {path}：先跑第 7 步')
    return json.loads(path.read_text(encoding='utf-8'))


def judge_task(items, shuffle_seed=None):
    """items: [(词, 题)]。shuffle_seed 不为空时打乱题目和干扰项的顺序（第二遍）"""
    rows = list(items)
    rng = random.Random(shuffle_seed) if shuffle_seed else None
    if rng:
        rng.shuffle(rows)
    qs = {}
    for i, (word, q) in enumerate(rows, 1):
        distractors = [o for o in q['options'] if o != q['answer'] and o not in keep_confusables(word, q)]
        if rng:
            rng.shuffle(distractors)
        if not distractors:
            continue
        entry = {'type': q['type'], 'stem': q['stem'], 'answer': q['answer'], 'distractors': distractors}
        if q.get('gloss'):
            entry['gloss'] = q['gloss']
        qs[f'q{i}'] = entry
    return {'instructions': JUDGE_INSTRUCTIONS, 'answer_format': JUDGE_FORMAT, 'questions': qs}


CONFUSABLES = {}


def keep_confusables(word, q):
    """释义题里的易混淆词：论文有意放的，不判、不换"""
    return set(CONFUSABLES.get(word, [])) if q['type'] == 'definition' else set()


def validate_judge(answer, task):
    problems = []
    for k, q in task['questions'].items():
        got = answer.get(k)
        if not isinstance(got, dict):
            problems.append(f'{k} 漏答')
            continue
        for d in q['distractors']:
            v = got.get(d)
            if not (isinstance(v, dict) and isinstance(v.get('fits'), bool)):
                problems.append(f'{k} 的「{d}」没有回答 fits')
    return problems


def validate_pick(answer, task):
    problems = []
    for k, q in task['questions'].items():
        got = answer.get(k)
        if not (isinstance(got, list) and len(got) == q['need'] and len(set(got)) == q['need']
                and all(w in q['candidates'] for w in got)):
            problems.append(f'{k} 应从候选里挑 {q["need"]} 个不同的词，回答是 {got}')
    return problems


def conflicts_from(task, answer):
    """{(stem, answer): {干扰项: 理由}}"""
    out = {}
    for k, q in task['questions'].items():
        for d, v in answer[k].items():
            if d in q['distractors'] and v.get('fits'):
                out.setdefault((q['stem'], q['answer']), {})[d] = v.get('reason', '')
    return out


def main(batches, model):
    levels = common.hsk_levels()
    pool = common.hsk_known(levels)
    outdir = common.OUT / '干扰项复查'
    outdir.mkdir(parents=True, exist_ok=True)
    data = {b: load_batch(b) for b in batches}
    items = {b: [(m['hanzi'], q) for m in d['words'] for q in questions_of(m)] for b, d in data.items()}
    # 素材是第 7 步按上一次复查换过选项的：退回换之前的选项再判，结果和上一次一致（回答都已存好，不重复请求），
    # 也不会因为「换过的选项没冲突」把上一次的替换记录冲掉
    result_path = common.REVIEW / '干扰项复查.json'
    previous = json.loads(result_path.read_text(encoding='utf-8'))['batches'] if result_path.exists() else {}
    for b in batches:
        for word, q in items[b]:
            for r in previous.get(b, {}).get(word, []):
                if r['stem'] == q['stem'] and r['correct_answer'] == q['answer'] and r['options'] == q['options']:
                    q['options'] = list(r['old'])
    for d in data.values():
        for m in d['words']:
            CONFUSABLES[m['hanzi']] = m.get('confusables') or []

    # 1. 判两遍
    keys = []
    for b in batches:
        for p, seed in (('A', None), ('B', f'{b}-B')):
            common.write_json(outdir / f'{b}-{p}.任务.json', judge_task(items[b], seed))
            keys.append(f'{b}-{p}')
    step4_semantic_tasks.answer_with(model, outdir, keys, kind='判断', check=validate_judge)
    conflicts = {}
    # 干扰项和题干里的词相同（「小 ( )」的选项里有「小」）：不用判，直接换
    for b in batches:
        for word, q in items[b]:
            same = [o for o in q['options'] if o != q['answer'] and o in q['stem'].replace('( )', ' ').split()]
            for o in same:
                conflicts.setdefault(b, {}).setdefault((q['stem'], q['answer']), {})[o] = '和题干里的词相同'
    for key in keys:
        task = json.loads((outdir / f'{key}.任务.json').read_text(encoding='utf-8'))
        answer = json.loads((outdir / f'{key}.判断.{model}.json').read_text(encoding='utf-8'))
        b = key.rsplit('-', 1)[0]
        for k, v in conflicts_from(task, answer).items():
            conflicts.setdefault(b, {}).setdefault(k, {}).update(v)

    # 2. 换：每批一个挑选任务
    pick_keys, picks = [], {}
    for b in batches:
        qs = {}
        for i, (word, q) in enumerate(items[b], 1):
            bad = conflicts.get(b, {}).get((q['stem'], q['answer']))
            if not bad:
                continue
            keep = [o for o in q['options'] if o not in bad]
            exclude = set(q['options']) | set(CONFUSABLES.get(word, [])) | {word}
            cands = step5_select.distractor_pool(word, exclude, pool)
            rng = random.Random(f"{word}|{q['stem']}")
            entry = {'type': q['type'], 'stem': q['stem'], 'answer': q['answer'], 'keep': keep, 'need': len(bad),
                     'candidates': rng.sample(cands, min(40, len(cands)))}
            if q.get('gloss'):
                entry['gloss'] = q['gloss']
            qs[f'q{i}'] = entry
        if qs:
            common.write_json(outdir / f'{b}-换.任务.json',
                              {'instructions': PICK_INSTRUCTIONS, 'answer_format': PICK_FORMAT, 'questions': qs})
            pick_keys.append(f'{b}-换')
    step4_semantic_tasks.answer_with(model, outdir, pick_keys, kind='挑选', check=validate_pick)

    new_options = {}  # (批, stem, answer) → 新选项
    for b in batches:
        key = f'{b}-换'
        if key not in pick_keys:
            continue
        task = json.loads((outdir / f'{key}.任务.json').read_text(encoding='utf-8'))
        answer = json.loads((outdir / f'{key}.挑选.{model}.json').read_text(encoding='utf-8'))
        for k, q in task['questions'].items():
            word, old = next((w, x) for w, x in items[b] if x['stem'] == q['stem'] and x['answer'] == q['answer'])
            bad = conflicts[b][(q['stem'], q['answer'])]
            fresh = iter(answer[k])
            new_options[(b, q['stem'], q['answer'])] = [next(fresh) if o in bad else o for o in old['options']]

    # 3. 新选项再判一遍（打乱顺序）
    verify_keys = []
    for b in batches:
        changed = [(w, dict(q, options=new_options[(b, q['stem'], q['answer'])])) for w, q in items[b]
                   if (b, q['stem'], q['answer']) in new_options]
        if changed:
            common.write_json(outdir / f'{b}-复核.任务.json', judge_task(changed, f'{b}-复核'))
            verify_keys.append(f'{b}-复核')
    step4_semantic_tasks.answer_with(model, outdir, verify_keys, kind='判断', check=validate_judge)
    still = {}
    for key in verify_keys:
        task = json.loads((outdir / f'{key}.任务.json').read_text(encoding='utf-8'))
        answer = json.loads((outdir / f'{key}.判断.{model}.json').read_text(encoding='utf-8'))
        for k, v in conflicts_from(task, answer).items():
            still.setdefault(key.rsplit('-', 1)[0], {})[k] = v

    # 4. 写结果
    result = json.loads(result_path.read_text(encoding='utf-8')) if result_path.exists() else {
        '说明': '第 6c 步选择题干扰项复查（step6c_recheck.py）。第 7 步重新生成时按（词、题干、答案）用这里的选项。', 'batches': {}}
    md = ['# 干扰项复查', '', f'模型 {model}。每道题列出判为「也说得通」的干扰项和理由、换上的词；⚠ 是换了以后复核仍有冲突的，要人工处理。', '']
    total = changed_n = stuck_n = 0
    for b in batches:
        result['batches'][b] = {}
        md += [f'## {b}', '']
        for word, q in items[b]:
            total += 1
            key = (q['stem'], q['answer'])
            if key not in conflicts.get(b, {}):
                continue
            new = new_options[(b, *key)]
            changed_n += 1
            result['batches'][b].setdefault(word, []).append(
                {'stem': q['stem'], 'correct_answer': q['answer'], 'old': q['options'], 'options': new})
            reasons = '；'.join(f'{d}：{r}' for d, r in conflicts[b][key].items())
            md.append(f"- **{word}**　{q['stem']}" + (f"（{q['gloss']}）" if q.get('gloss') else '')
                      + f"　{' / '.join(q['options'])} → {' / '.join(new)}\n  - 说得通：{reasons}")
            if left := still.get(b, {}).get(key):
                stuck_n += 1
                md.append('  - ⚠ 复核仍说得通：' + '；'.join(f'{d}：{r}' for d, r in left.items()))
        md.append('')
    common.write_json(result_path, result)
    (common.REVIEW / '干扰项复查.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    print(f'选择题 {total} 道，换了干扰项的 {changed_n} 道，换了以后复核仍有冲突的 {stuck_n} 道 → {result_path}、干扰项复查.md')


if __name__ == '__main__':
    args = sys.argv[1:]
    model = args[args.index('--model') + 1] if '--model' in args else None
    if not model:
        raise SystemExit('要加 --model')
    names = sorted(p.parent.name for p in common.REVIEW.glob('第*批/素材.json')) if '--all' in args else \
        [a for a in args if re.fullmatch(r'第\d+批', a)]
    main(names, model)
