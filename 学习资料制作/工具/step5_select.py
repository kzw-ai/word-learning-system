"""第 5 步　按论文规则取舍：保留哪些义项、每个义项用哪句例句和哪两条搭配、出哪几道练习题（论文 5.3.2–5.3.5，附录 AD）。

用法：学习资料制作/.venv/bin/python 学习资料制作/工具/step5_select.py 第01批 [--judgment claude-code]
输入：第 3 步的候选清单 + 第 4 步的语义判断（默认读 <词>.判断.json；--judgment 来源 改读 <词>.判断.<来源>.json）
产出：2_加工结果/取舍/第01批/<词>.json

规则（全部由程序决定，大模型不参与取舍）：
1. 义项（5.3.3）：统计候选例句（复杂度最低的前 20 句）里各义项出现的句数。保留句数最多的义项；
   第二个义项句数 ≥ 2 且占可用例句 ≥ 30% 时也保留。最多 2 个。句数相同时，最简单的那句例句排在前面的义项优先，
   并在 problems 里提醒。没被保留的义项写进 dropped_senses，审核时可以看到。
2. 例句（5.3.2）：每个保留的义项取复杂度最低的一句可用例句（候选清单已按复杂度、四至六级词个数排好序）。
   有 SHORT 字以内的可用例句时先从这些短句里取（作者 2026-10-29：例句要短，论文词库的例句中位数 16 字、最长 27 字）；
   复杂度是各词之和，一般句子越长越高，但常用词多的长句也可能比生僻词多的短句低。第 6 步再把仍然过长的句子截短。
3. 搭配（5.3.4）：每个义项取成立的搭配里互信息最高的两条，先用分级阅读库，不够再用维基库；同一个搭配词不重复。
   两道搭配题：有两个义项时各取一条，再从剩下的搭配里补足。
4. 练习（附录 AD）：
   - 释义题：题干是主义项的英文释义，选项 = 目标词 + 易混淆词（有的话）+ 一至三级随机词，共 4 个；
   - 搭配题：两道，用选出的搭配，把目标词换成括号，选项 = 目标词 + 3 个一至三级随机词；
   - 填字题：用主义项的下一句可用例句（没有就用例句本身），挖掉目标词的最后一个字。按分词结果定位，
     目标词必须作为完整的词出现且只出现一次（否则「理想」里的「想」会被挖掉，或另一处目标词泄露答案），不符合的换下一句。
   随机词排除目标词、易混淆词和与目标词有相同汉字的词；用词本身作随机种子，重复运行结果不变。
   每道选择题另抽 8 个备用干扰项（spares）。干扰项和备用词会不会也说得通、填字是否需要提示拼音，由第 6 步检查；
   第 7 步用检查过、说不通的备用词替换说得通的干扰项。
"""
import csv
import json
import random
import sys

import common
import step2_confusables
import step4_semantic_tasks

SECOND_SENSE_MIN_SENTENCES = 2
SECOND_SENSE_MIN_SHARE = 0.3
BLANK = ' ( ) '
SPARES = 8
SHORT = 30  # 例句超过这么多字算长：先选短句，第 6 步截短


def pick_senses(judgment, sentences):
    """返回 (保留的义项, 舍去的义项, 可用例句数, 提醒)。句数相同时，最简单的那句例句排在前面的义项优先。"""
    counts = {s['id']: 0 for s in judgment['senses']}
    first = {}
    for i, k in enumerate(sentences):
        sid = judgment['sentence_senses'].get(k)
        if sid in counts:
            counts[sid] += 1
            first.setdefault(sid, i)
    usable = sum(counts.values())
    ranked = sorted(judgment['senses'], key=lambda s: (-counts[s['id']], first.get(s['id'], len(sentences))))
    kept = ranked[:1]
    if len(ranked) > 1:
        n = counts[ranked[1]['id']]
        if n >= SECOND_SENSE_MIN_SENTENCES and n / usable >= SECOND_SENSE_MIN_SHARE:
            kept.append(ranked[1])
    notes = []
    tie = lambda i: i + 1 < len(ranked) and counts[ranked[i]['id']] and counts[ranked[i]['id']] == counts[ranked[i + 1]['id']]
    if tie(0):
        notes.append(f"义项「{ranked[0]['definition']}」和「{ranked[1]['definition']}」句数相同（{counts[ranked[0]['id']]} 句），"
                     '按最简单例句的先后定了主义项')
    if len(kept) == 2 and tie(1):
        notes.append(f"义项「{ranked[1]['definition']}」和「{ranked[2]['definition']}」句数相同（{counts[ranked[1]['id']]} 句），"
                     '只能保留两个，按最简单例句的先后保留了前者')
    dropped = [dict(s, sentences=counts[s['id']]) for s in ranked if s not in kept]
    return [dict(s, sentences=counts[s['id']]) for s in kept], dropped, usable, notes


def sentences_of(sense_id, judgment, candidates):
    return [c for i, c in enumerate(candidates['sentences'], 1) if judgment['sentence_senses'].get(str(i)) == sense_id]


def collocations_of(sense_id, judgment, candidates, used_others):
    out = []
    for prefix, key in (('edu', 'collocations_edu'), ('wiki', 'collocations_wiki')):
        for i, c in enumerate(candidates[key], 1):
            if len(out) == 2:
                return out
            if judgment['collocation_senses'].get(f'{prefix}{i}') != sense_id or c['other'] in used_others:
                continue
            used_others.add(c['other'])
            out.append(dict(c, source='分级阅读库' if prefix == 'edu' else '维基库'))
    return out


def distractor_pool(word, exclude, pool):
    return [w for w in pool if w not in exclude and not set(w) & set(word)]


def draw(candidates, rng, n):
    if len(candidates) < n:
        raise SystemExit(f'可用的一至三级随机词只有 {len(candidates)} 个，不够抽 {n} 个')
    return rng.sample(candidates, n)


def question(qtype, stem, answer, extra, spares, rng, **more):
    options = [answer] + extra
    rng.shuffle(options)
    return {'question_type': qtype, 'stem': stem, 'options': options, 'correct_answer': answer, 'spares': spares, **more}


def option_problems(q):
    """选项必须 4 个、互不相同、正确答案恰好出现一次。"""
    opts = q['options']
    if len(opts) != 4 or len(set(opts)) != 4 or opts.count(q['correct_answer']) != 1:
        return [f"{q['stem']} 的选项不合格：{opts}"]
    return []


def word_start(sentence, tokens, word):
    """目标词作为一个完整的词、且只出现一次时，返回它在句子里的起始位置；否则 None。"""
    if ''.join(tokens) != sentence or tokens.count(word) != 1:
        return None
    i = tokens.index(word)
    return sum(len(t) for t in tokens[:i])


def blank_position(sentence, tokens, word):
    """填字题要挖掉的那个字（目标词的最后一个字）的位置；目标词不是只出现一次的完整词时 None。"""
    start = word_start(sentence, tokens, word)
    return None if start is None else start + len(word) - 1


def build_exercises(word, senses, confusables, pool):
    """返回 (练习题, 提醒)。每道选择题另外抽 SPARES 个备用干扰项，第 6 步一起检查，第 7 步用来替换说得通的干扰项。"""
    rng = random.Random(word)
    candidates = distractor_pool(word, {word, *confusables}, pool)
    main = senses[0]
    notes = []
    picked = draw(candidates, rng, 3 - len(confusables[:1]) + SPARES)
    definition = question('definition', main['definition'], word, confusables[:1] + picked[:3 - len(confusables[:1])],
                          picked[3 - len(confusables[:1]):], rng)
    # 有两个义项时各取一条，再从所有保留义项剩下的搭配里补足两条
    firsts = [s['collocations'][0] for s in senses if s['collocations']] if len(senses) > 1 else []
    rest = [c for s in senses for c in s['collocations'] if c not in firsts]
    collocation = []
    for c in (firsts + rest)[:2]:
        picked = draw(candidates, rng, 3 + SPARES)
        stem = ' '.join('( )' if t == word else t for t in c['collocation'].split())
        collocation.append(question('collocation', stem, word, picked[:3], picked[3:], rng, collocation=c['collocation']))
    if len(collocation) < 2:
        notes.append(f'搭配题只有 {len(collocation)} 道（成立的搭配不够）')
    fill = None
    for c in main['other_sentences'] + ([main['example']] if main['example'] else []):
        at = blank_position(c['sentence'], c['tokens'], word)
        if at is None:
            continue
        s = c['sentence']
        fill = {'question_type': 'fill_word', 'stem': (s[:at] + BLANK + s[at + 1:]).strip(), 'correct_answer': s[at],
                'sentence': s, 'same_as_example': c is main['example']}
        break
    if fill is None:
        notes.append('没有能出填字题的句子（目标词都出现了不止一次）')
    elif fill['same_as_example']:
        notes.append('填字题只能用例句本身（没有第二句可用例句）')
    for q in [definition] + collocation:
        notes += option_problems(q)
    return {'definition': definition, 'collocation': collocation, 'fill_word': fill}, notes


def select(word, candidates, judgment, pool, rank=None, tier='一至三级易混淆词', name=''):
    """按规则取舍一个词，返回结果（不写文件；对比脚本也直接调用）。"""
    kept, dropped, usable, problems = pick_senses(judgment, [str(i) for i in range(1, len(candidates['sentences']) + 1)])
    used_others = set()
    for s in kept:
        mine = sentences_of(s['id'], judgment, candidates)
        mine = [c for c in mine if len(c['sentence']) <= SHORT] + [c for c in mine if len(c['sentence']) > SHORT]
        s['example'] = mine[0] if mine else None
        s['other_sentences'] = mine[1:]
        s['collocations'] = collocations_of(s['id'], judgment, candidates, used_others)
    confusables = candidates['confusables']
    if not usable:
        problems.append('没有可用例句')
    for s in kept:
        if len(s['collocations']) < 2:
            problems.append(f"义项「{s['definition']}」成立的搭配不足两条（{len(s['collocations'])} 条）")
    exercises = None
    if usable:
        # 释义题的干扰项只用一至三级的易混淆词（pool 就是一至三级词）：四级的易混淆词学习者可能还没学
        exercises, notes = build_exercises(word, kept, [c for c in confusables if c in pool], pool)
        problems += notes
    return {
        'word': word, 'hsk_level': candidates['hsk_level'], 'rank': rank, 'tier': tier,
        'confusables': confusables, 'judgment': name,
        'characters': judgment['characters'],
        'senses': [{k: v for k, v in s.items() if k != 'other_sentences'} for s in kept],
        'dropped_senses': dropped, 'usable_sentences': usable,
        'exercises': exercises, 'problems': problems,
    }


def main(batch, source=None):
    levels = common.hsk_levels()
    pool = common.hsk1_to_3(levels)
    tiers = {}
    for r in csv.DictReader(open(common.OUT / '四级词加权词频分档.csv', encoding='utf-8')):
        tiers[r['word']] = (int(r['rank']), r['tier'])
    cand_dir = common.OUT / '候选清单' / batch
    judge_dir = common.OUT / '判断' / batch
    outdir = common.OUT / '取舍' / batch
    outdir.mkdir(parents=True, exist_ok=True)
    for word in step2_confusables.words_from_args([batch]):
        candidates = json.loads((cand_dir / f'{word}.json').read_text(encoding='utf-8'))
        name = f'{word}.判断.{source}.json' if source else f'{word}.判断.json'
        task = json.loads((judge_dir / f'{word}.任务.json').read_text(encoding='utf-8'))
        step4_semantic_tasks.check_candidates(task, candidates, word)
        judgment = common.load_answer(judge_dir / name, task, step4_semantic_tasks.validate)
        result = select(word, candidates, judgment, pool, *tiers.get(word, (None, '一至三级易混淆词')), name=name)
        # 取舍依据的候选清单和判断（回答内容本身，回答可能被修订）的指纹：第 6 步据此认出过期的取舍
        result['inputs'] = common.task_hash({'candidates': candidates, 'judgment': judgment})
        kept, dropped, problems = result['senses'], result['dropped_senses'], result['problems']
        common.write_json(outdir / f'{word}.json', result)
        senses_text = '；'.join(f"{s['pos']} {s['definition']}（{s['sentences']} 句）" for s in kept)
        print(f"{word}：{senses_text}" + (f"｜舍去 {'、'.join(d['definition'] + '（' + str(d['sentences']) + ' 句）' for d in dropped)}" if dropped else '')
              + (f"｜⚠ {'；'.join(problems)}" if problems else ''), flush=True)


if __name__ == '__main__':
    args = sys.argv[1:]
    main(args[0], args[args.index('--judgment') + 1] if '--judgment' in args else None)
