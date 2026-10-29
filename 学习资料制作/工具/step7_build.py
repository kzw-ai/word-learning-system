"""第 7 步　汇总成学习资料，并生成审核清单。

用法：学习资料制作/.venv/bin/python 学习资料制作/工具/step7_build.py 第01批 [--check deepseek-flash]
输入：第 5 步 2_加工结果/取舍/第01批/<词>.json，第 6 步 2_加工结果/检查/第01批/<词>.检查.json
      （--check 来源 改读 <词>.检查.<来源>.json）
产出：3_审核/第01批/素材.json（字段同 data/learning_materials/supplement_confusable_words.json，另加 senses、exercises；
      confusable_pairs 的字段同系统的 confusable_pairs 表：reason、difference、examples、tips、difficulty_level，
      另加 questions（二选一辨析题，论文 3.2.4））
      3_审核/第01批/审核清单.md（给人核对）

第 6 步判定「也说得通」的干扰项，换成第 5 步抽好、第 6 步检查过说不通的备用词，清单里标出换了哪些；
释义题里的易混淆词不换（论文 2.1：有意把易混淆词设为一个选项）。互信息为负的搭配在清单里提醒。
备用词用完仍有冲突的，清单里标明需要人工处理。检查回答漏答（缺翻译、拼音等）会直接报错，不会输出空内容。
填字题有其他字也说得通时，给出挖掉那个字的拼音作提示（hint）。
"""
import json
import random
import sys

from pypinyin import Style, pinyin

import common
import draft_examples
import step2_confusables
import step5_select
import step6_check_tasks


def collocation_text(c, word):
    return ' '.join(t + common.level_label(c['level']) if t == c['other'] else t for t in c['collocation'].split())


def replace_conflicts(question, conflicts, keep=()):
    """把说得通的干扰项换成检查过、说不通的备用词。keep 里的词不换（释义题里的易混淆词是论文有意放的）。
    返回 (换掉的词, 没能换掉的词)。"""
    bad = list(dict.fromkeys(o for o in conflicts if o in question['options'] and o != question['correct_answer'] and o not in keep))
    fresh = [w for w in question['spares'] if w not in conflicts and w not in question['options']]
    stuck = []
    for o in bad:
        if fresh:
            question['options'][question['options'].index(o)] = fresh.pop(0)
        else:
            stuck.append(o)
    return [o for o in bad if o not in stuck], stuck


QUIZ_PER_WORD = 2


def initial(syllable_char):
    """一个字的声母（零声母的字没有声母，返回空串）。"""
    return pinyin(syllable_char, style=Style.INITIALS, strict=False)[0][0]


def fill_hint(answer, full_pinyin, other_fits):
    """论文 3.2.4：填字题括号里能填不止一个字时，给出答案那个字的声母，保证只能填这一个字。
    别的能填的字声母相同（如「原 ( ) 」的「因 yīn / 由 yóu」）或答案是零声母时，声母区分不开，改给完整拼音。"""
    ini = initial(answer)
    if ini and all(initial(c) != ini for c in other_fits):
        return ini
    return full_pinyin


def pick_quiz(key, word, other, candidates, checks):
    """辨析题（论文 3.2.4）：两个选项，一个是正确的词，一个是易混淆词。每个词取 QUIZ_PER_WORD 道
    另一个词填不进去、又适合出题的，按候选顺序（复杂度从低到高）。"""
    rng = random.Random(key)
    questions, notes = [], []
    for w in (word, other):
        ok = [dict(q, key=k) for k, q in candidates.items() if q['answer'] == w and checks[k]['usable'] and not checks[k]['other_fits']]
        for q in ok[:QUIZ_PER_WORD]:
            options = [word, other]
            rng.shuffle(options)
            questions.append({'question_type': 'confusable', 'stem': q['stem'], 'options': options, 'correct_answer': w,
                              'explanation': checks[q['key']]['explanation']})
        if len(ok) < QUIZ_PER_WORD:
            notes.append(f'答案是「{w}」的辨析题只有 {len(ok)} 道（候选句里另一个词也能填或不适合出题）')
    return questions, notes


def characters(word, sel, check, senses):
    """字的读音和释义。单字词的字就是这个词本身：读音用第 6 步校对过的整词拼音，释义用保留下来的主义项。
    第 4 步的字释义按第 4 步的第一个义项写，第 5 步保留的可能是另一个义项（「转」保留 zhuàn 旋转，字却写了 zhuǎn）"""
    if len(word) == 1 and senses:
        return [{'character': word, 'pinyin': check.get('word_pinyin', '') or sel['characters'][0]['pinyin'],
                 'definition': f"{senses[0]['pos']} {senses[0]['definition']}"}]
    return [{'character': c['character'], 'pinyin': c['pinyin'], 'definition': f"{c['pos']} {c['definition']}"}
            for c in sel['characters']]


def build(word, sel, check):
    examples = {e['sentence']: e for e in check['examples']}
    coll_tr = {c['collocation']: c['translation'] for c in check['collocations']}
    notes, exercises = [], []
    ex = sel['exercises'] or {}
    notes += [f"例句由大模型编写（教材里没有可用句子），请重点审：{s['example']['sentence']}"
              for s in sel['senses'] if s['example'] and s['example'].get('book') == draft_examples.SOURCE]
    # 第 6 步截短过的句子：审核时对照原句看截得对不对
    notes += [f"例句截自原句：{s['example']['original']}" for s in sel['senses'] if s['example'] and s['example'].get('original')]
    if (ex.get('fill_word') or {}).get('original') and ex['fill_word']['original'] not in \
            [s['example'].get('original') for s in sel['senses'] if s['example']]:
        notes.append(f"填字题截自原句：{ex['fill_word']['original']}")
    conflicts = check.get('distractor_conflicts', {})
    choice = ([('definition', '释义题', ex['definition'])] if ex.get('definition') else []) + \
             [(f'collocation{i}', f'搭配题 {i}', c) for i, c in enumerate(ex.get('collocation', []), 1)]
    for key, name, src in choice:
        q = {k: list(src[k]) if k == 'options' else src[k] for k in ('question_type', 'stem', 'options', 'correct_answer', 'spares')}
        keep = sel['confusables'] if key == 'definition' else ()
        replaced, stuck = replace_conflicts(q, conflicts.get(key, []), keep)
        if replaced:
            notes.append(f"{name}换掉了说得通的干扰项：{'、'.join(replaced)}")
        if stuck:
            notes.append(f"{name}的干扰项「{'、'.join(stuck)}」也说得通，备用词用完了，需要人工换")
        notes += step5_select.option_problems(q)
        q.pop('spares')
        exercises.append(q)
    if ex.get('fill_word'):
        fill = check.get('fill_word') or {}
        q = {k: ex['fill_word'][k] for k in ('question_type', 'stem', 'correct_answer')}
        q['options'] = []
        if fill.get('other_fits'):
            q['hint'] = fill_hint(q['correct_answer'], fill['hint'], fill['other_fits'])
            q['stem'] = q['stem'].replace('( )', f"( {q['hint']} )", 1)
            notes.append(f"填字题括号里也能填：{'、'.join(fill['other_fits'])}，已在括号里给出提示 {q['hint']}")
        exercises.append(q)

    for s in sel['senses']:
        notes += [f"搭配「{c['collocation']}」互信息为负（{c['mi']:.2f}）：两个词一起出现得比偶然还少，请确认是否常用"
                  for c in s['collocations'] if c['mi'] < 0]
    senses = []
    for s in sel['senses']:
        e = s['example']
        senses.append({
            'pos': s['pos'], 'definition': s['definition'],
            'example': {'sentence': e['sentence'], 'pinyin': examples.get(e['sentence'], {}).get('pinyin', ''),
                        'translation': examples.get(e['sentence'], {}).get('translation', ''),
                        'hsk4_6_words': e['hsk4_6_words'], 'book': e['book']} if e else None,
            'collocations': [{'collocation': collocation_text(c, word), 'translation': coll_tr.get(c['collocation'], ''),
                              'source': c['source'], 'mutual_information': round(c['mi'], 2)} for c in s['collocations']],
        })
    material = {
        'hanzi': word,
        'pinyin': check.get('word_pinyin', ''),
        'definition': ' | '.join(f"{s['pos']} {s['definition']}" for s in senses),
        'characters': characters(word, sel, check, senses),
        'collocations': [c for s in senses for c in s['collocations']],
        'examples': [s['example'] for s in senses if s['example']],
        'senses': senses,
        'exercises': exercises,
        'hsk_level': sel['hsk_level'], 'rank': sel['rank'], 'tier': sel['tier'], 'confusables': sel['confusables'],
    }
    return material, notes


def checklist_entry(m, sel, notes):
    lines = [f"## {m['hanzi']} {m['pinyin']}　HSK {m['hsk_level']} 级｜{m['tier']}" + (f"（第 {m['rank']} 名）" if m['rank'] else ''), '']
    if m['confusables']:
        lines.append(f"- 易混淆词：{'、'.join(m['confusables'])}（释义题选项里有，之后单独学习）")
    lines.append(f"- 字：" + '；'.join(f"{c['character']} {c['pinyin']} {c['definition']}" for c in m['characters']))
    lines.append(f"- 可用例句 {sel['usable_sentences']} 句；保留义项：" + '；'.join(
        f"{s['pos']} {s['definition']}（{s['sentences']} 句）" for s in sel['senses']))
    for d in sel['dropped_senses']:
        lines.append(f"- 舍去义项：{d['pos']} {d['definition']}（{d['sentences']} 句）")
    for s in m['senses']:
        lines += ['', f"**{s['pos']} {s['definition']}**", '']
        e = s['example']
        if e:
            lines.append(f"- 例句：{e['sentence']}" + (f"　〔四至六级词：{'、'.join(e['hsk4_6_words'])}〕" if e['hsk4_6_words'] else '')
                         + f"　（{e['book']}）")
            lines.append(f"  - {e['pinyin']}")
            lines.append(f"  - {e['translation']}")
        for c in s['collocations']:
            lines.append(f"- 搭配：{c['collocation']} — {c['translation']}（{c['source']}，互信息 {c['mutual_information']}）")
    lines += ['', '练习：', '']
    for q in m['exercises']:
        if q['question_type'] == 'fill_word':
            lines.append(f"- 填字：{q['stem']}　答案 {q['correct_answer']}" + (f"　提示 {q['hint']}" if q.get('hint') else ''))
        else:
            name = '释义' if q['question_type'] == 'definition' else '搭配'
            lines.append(f"- {name}：{q['stem']}　选项 {' / '.join(q['options'])}　答案 {q['correct_answer']}")
    for n in sel['problems'] + notes:
        lines.append(f"- ⚠ {n}")
    return lines + ['']


def main(batch, source=None):
    sel_dir = common.OUT / '取舍' / batch
    check_dir = common.OUT / '检查' / batch
    outdir = common.REVIEW / batch
    outdir.mkdir(parents=True, exist_ok=True)
    materials, md = [], [f'# 审核清单　{batch}', '',
                         '请逐词核对：义项是否恰当、例句是否适合学习者、翻译与拼音是否准确、搭配是否常用、练习题有没有两个正确答案。',
                         '标 ⚠ 的是程序发现需要特别看一下的地方。', '']
    pair_only = step2_confusables.pair_only_words(batch)
    if pair_only:
        md += [f"只做辨析（论文词库已有学习材料，不重做）：{'、'.join(sorted(pair_only))}", '']
    for word in step2_confusables.words_from_args([batch]):
        if word in pair_only:
            continue
        sel = json.loads((sel_dir / f'{word}.json').read_text(encoding='utf-8'))
        name = f'{word}.检查.{source}.json' if source else f'{word}.检查.json'
        task = json.loads((check_dir / f'{word}.任务.json').read_text(encoding='utf-8'))
        check = common.load_answer(check_dir / name, task, step6_check_tasks.validate)
        fill = (sel['exercises'] or {}).get('fill_word')
        if fill and fill.get('from_example'):
            # 填字题由 step6b 改用了例句：用它的检查结果（第 6 步检查的是原来那句）
            import step6b_fill_from_example
            check = dict(check, fill_word=step6b_fill_from_example.load_check(batch, word, fill, source or 'deepseek-flash'))
        material, notes = build(word, sel, check)
        materials.append(material)
        md += checklist_entry(material, sel, notes)
    pairs = []
    levels = common.hsk_levels()
    for word, other, stats in step6_check_tasks.confusable_pairs(batch):
        key = step6_check_tasks.pair_key(word, other)
        name = f'{key}.辨析.{source}.json' if source else f'{key}.辨析.json'
        task = json.loads((check_dir / f'{key}.任务.json').read_text(encoding='utf-8'))
        a = common.load_answer(check_dir / name, task, step6_check_tasks.validate_pair)
        corpus = (f"In the HSK Dynamic Composition Corpus, learners made {stats['word1_errors']} mistakes where "
                  f"{word} was needed; {stats['wrote_word2']} of them ({stats['share']:.0%}) used {other} instead.")
        if back := stats.get('reverse'):
            corpus += (f" The other way round, of {back['word1_errors']} mistakes where {other} was needed, "
                       f"{back['wrote_word2']} ({back['share']:.0%}) used {word}.")
        reason = '\n'.join([a['reason'].rstrip(), corpus, 'Common mistakes:'] + [f'· {x}' for x in a['confusion_points']])
        difference = '\n'.join([a['english'].rstrip(), a['difference'].rstrip(), 'Collocations:']
                                + [f'· {x}' for x in a['collocation_contrast']])
        questions, quiz_notes = pick_quiz(key, word, other, task['quiz_candidates'], a['quiz_checks'])
        pairs.append({'word1': word, 'word2': other, 'reason': reason, 'difference': difference,
                      'examples': '\n'.join(a['examples']), 'tips': a['tips'], 'difficulty_level': a['difficulty_level'],
                      'questions': questions, 'corpus': stats, 'word2_level': levels.get(other)})
        md += [f'## 易混淆词辨析：{word} / {other}', '', '为什么容易混：', ''] + [f'> {x}' for x in reason.splitlines()]
        md += ['', '区别：', ''] + [f'> {x}' for x in difference.splitlines()]
        md += ['', '例句：', ''] + [f'- {x}' for x in a['examples']] + ['', f'提示：{a["tips"]}　难度：{a["difficulty_level"]}', '', '辨析题：', '']
        md += [f"- {q['stem']}　选项 {' / '.join(q['options'])}　答案 {q['correct_answer']}\n  - {q['explanation']}" for q in questions]
        md += [f'- ⚠ {n}' for n in quiz_notes] + ['']
    common.write_json(outdir / '素材.json', {'batch': batch, 'status': '待审核', 'words': materials, 'confusable_pairs': pairs})
    (outdir / '审核清单.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    print(f'{len(materials)} 个词、{len(pairs)} 对易混淆词 → {outdir / "素材.json"}、{outdir / "审核清单.md"}')


if __name__ == '__main__':
    args = sys.argv[1:]
    main(args[0], args[args.index('--check') + 1] if '--check' in args else None)
