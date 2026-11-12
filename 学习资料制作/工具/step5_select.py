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
   - 填字题：用主义项的例句本身（学习页上显示的那句，论文 3.2 节：句子来自学习模块的例句；作者 2026-10-30），
     挖掉目标词的最后一个字。按分词结果定位，目标词必须作为完整的词出现且只出现一次（否则「理想」里的「想」会被挖掉，
     或另一处目标词泄露答案），例句不符合时换同一义项的下一句可用例句。此前用的是下一句例句，学习者没见过那句，
     有的句子里别的字比答案自然得多；已做好的批次由 step6b_fill_from_example.py 补改。
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
# 汉办词表里有两个本级条目的词（「只（量词）」「只（副词）」、「花（名词）」「花（动词）」）：两个意思都要学，
# 第二个义项有例句就保留，不按 30% 的门槛（作者 2026-11-12）。四级没有这样的词
TWO_ENTRIES = {'只', '花'} if common.TARGET_LEVEL == 3 else set()

# 三级：Claude 预审（2026-11-12）后的改动，四级不受影响。教材是中级的，按复杂度选出的最简单的句子
# 对三级学习者常常还是太难或不合适（「说着就过去拿褡子」「农村包围城市」「只恨不善画」）。
# 指定例句：这个词的某个义项有这句可用例句时就用它。指定的是 补充例句/<词>.json 里 Claude 写的句子时，
# 那是教材里没有合适句子的词。
CHOSEN_EXAMPLES = {
    '就': ['好，那就听你的。'],
    '过去': ['一个多小时过去了。'],
    '是': ['什么是幸福？'],
    '城市': ['我们经常到中国的一些小城市旅行。'],
    '舒服': ['听听音乐，喝喝咖啡，好舒服啊！'],
    '被': ['我们经常被别人认错。'],
    '离开': ['离开朋友，我们的生活一定会非常无聊。'],
    '冰箱': ['先把茶和杯子放好，然后把冰箱里的西瓜拿出来。'],
    '同事': ['那个漂亮的新同事是谁？'],
    '终于': ['你终于回来了！'],
    '我': ['我也想要啊！'],
    '为了': ['为了健康，我真应该多锻炼锻炼了。'],
    '认为': ['我认为都很正常，没什么问题呀。'],
    '老': ['还是老样子，他让我以后不要再抽烟了。'],
    '蓝': ['妈妈，为什么草是绿的，而天是蓝的？'],
    '最后': ['最后父亲让女儿喝了一口咖啡。'],
    # 以下是 Claude 写的句子（补充例句）
    '画': ['他画了一只小猫。', '墙上的画很漂亮。'],
    '包': ['这个包太重了。'],
    '辆': ['我想买一辆自行车。'],
    '节目': ['这个节目很有意思。'],
    '洗澡': ['我习惯晚上洗澡。'],
    '春': ['春来了，草绿了，花也开了。'],
    '秋': ['北京的秋很美，不冷也不热。'],
    '西': ['从这儿往西走，就是火车站。'],
    '树': ['学校里有很多树。'],
    '中间': ['他坐在爸爸和妈妈中间。'],
    '长': ['孩子长得真快！'],
    '离': ['我家离学校很近。'],
    '坏': ['抽烟是个坏习惯。'],
    '段': ['我在北京住过一段时间。'],
    '搬': ['我们下个星期搬到新家去。'],
    '校长': ['我们的校长是一位女老师。'],
    '地铁': ['我每天坐地铁去上班。'],
    '地图': ['我们看一下地图吧。'],
    '久': ['我等了你很久。'],
    '极': ['这个主意好极了！'],
    '鸟': ['树上有一只小鸟。'],
    '少': ['这儿的人很少。'],
    '电梯': ['我们坐电梯上去吧。'],
    '嘴': ['她的嘴很小，眼睛很大。'],
    '张': ['我买了两张电影票。'],
    '提高': ['我想提高我的汉语水平。'],
    '种': ['你喜欢哪种水果？'],
    '楼': ['我家住在五楼。'],
    # 「欢迎」两个义项判成了一个：用欢迎别人的句子，不用「很受欢迎」
    '欢迎': ['这个小熊猫送给你，欢迎你以后再到中国来。'],
    '帮助': ['谢谢你帮助我。'],
} if common.TARGET_LEVEL == 3 else {}
# 不用的搭配（统计上成立，但不常用、有歧义或意思不对），跳过后取下一条
REJECTED_COLLOCATIONS = {
    '放心 药', '关 阿姨', '决定 票', '慢 班',              # 不常用；「关」是姓
    '两 难', '本 是', '一般 为', '年 久',                  # 偏书面
    '绿 帽子',                                              # 「戴绿帽子」是贬义
    '旧 中国', '红 太阳',                                   # 有政治含义
    '鼻子 舒服', '矮 鼻子', '开 电梯', '画 脚', '好 画',    # 不自然；「好画」是「容易画」，不属于名词义项
    '分 差', '季节 来', '把 香蕉',                          # 「分差」是一个词；「一把香蕉」的翻译错成 hold a banana
    '分 米', '画 像', '新 搬', '长 花', '久 坐',            # 上面去掉后顺延上来的：「分米」「画像」是一个词；不自然；偏书面
} if common.TARGET_LEVEL == 3 else set()


def pick_senses(judgment, sentences, keep_two=False):
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
        if (n >= SECOND_SENSE_MIN_SENTENCES and n / usable >= SECOND_SENSE_MIN_SHARE) or (keep_two and n >= 1):
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
            if judgment['collocation_senses'].get(f'{prefix}{i}') != sense_id or c['other'] in used_others \
                    or c['collocation'] in REJECTED_COLLOCATIONS:
                continue
            used_others.add(c['other'])
            out.append(dict(c, source='分级阅读库' if prefix == 'edu' else '维基库'))
    return out


def distractor_pool(word, exclude, pool):
    return [w for w in pool if w not in exclude and not set(w) & set(word)]


def draw(candidates, rng, n):
    if len(candidates) < n:
        raise SystemExit(f'可用的{common.KNOWN_LABEL}随机词只有 {len(candidates)} 个，不够抽 {n} 个')
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
    for c in ([main['example']] if main['example'] else []) + main['other_sentences']:
        at = blank_position(c['sentence'], c['tokens'], word)
        if at is None:
            continue
        s = c['sentence']
        fill = {'question_type': 'fill_word', 'stem': (s[:at] + BLANK + s[at + 1:]).strip(), 'correct_answer': s[at],
                'sentence': s, 'same_as_example': c is main['example']}
        break
    if fill is None:
        notes.append('没有能出填字题的句子（目标词都出现了不止一次）')
    elif not fill['same_as_example']:
        notes.append('填字题没能用例句本身（例句里目标词出现了不止一次），用了下一句可用例句')
    for q in [definition] + collocation:
        notes += option_problems(q)
    return {'definition': definition, 'collocation': collocation, 'fill_word': fill}, notes


def select(word, candidates, judgment, pool, rank=None, tier=f'{common.KNOWN_LABEL}易混淆词', name=''):
    """按规则取舍一个词，返回结果（不写文件；对比脚本也直接调用）。"""
    kept, dropped, usable, problems = pick_senses(judgment, [str(i) for i in range(1, len(candidates['sentences']) + 1)],
                                                  keep_two=word in TWO_ENTRIES)
    used_others = set()
    for s in kept:
        mine = sentences_of(s['id'], judgment, candidates)
        mine = [c for c in mine if len(c['sentence']) <= SHORT] + [c for c in mine if len(c['sentence']) > SHORT]
        mine.sort(key=lambda c: c['sentence'] not in CHOSEN_EXAMPLES.get(word, ()))
        s['example'] = mine[0] if mine else None
        s['other_sentences'] = mine[1:]
        s['collocations'] = collocations_of(s['id'], judgment, candidates, used_others)
    picked = {s['example']['sentence'] for s in kept if s['example']}
    problems += [f'⚠ 指定的例句没有用上（候选里没有，或判成了别的义项）：{x}'
                 for x in CHOSEN_EXAMPLES.get(word, ()) if x not in picked]
    confusables = candidates['confusables']
    if not usable:
        problems.append('没有可用例句')
    for s in kept:
        if len(s['collocations']) < 2:
            problems.append(f"义项「{s['definition']}」成立的搭配不足两条（{len(s['collocations'])} 条）")
    exercises = None
    if usable:
        # 释义题的干扰项只用学过的易混淆词（pool 就是学过的词：四级词是一至三级，三级词是一二级）：同级的易混淆词学习者可能还没学
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
    pool = common.hsk_known(levels)
    tiers = {}
    for r in csv.DictReader(open(common.TIERS_CSV, encoding='utf-8')):
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
        result = select(word, candidates, judgment, pool, *tiers.get(word, (None, f'{common.KNOWN_LABEL}易混淆词')), name=name)
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
