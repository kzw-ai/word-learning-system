"""补充例句（大模型起草，作者审核）：教材里找不到可用例句的词，让大模型按论文的要求写几句简单例句。

用法：学习资料制作/.venv/bin/python 学习资料制作/工具/draft_examples.py 师傅 签证 … [--model deepseek-flash]
产出：2_加工结果/补充例句/<词>.任务.json、<词>.例句.<来源>.json（回答）、<词>.json（第 3 步读的句子清单）

作者 2026-10-30 决定：教材里一句可用例句都没有的 12 个词（师傅、签证、大使馆、勺子、理发、填空、百分之、推、篇、
葡萄、凉快、预习）由大模型起草例句。第 3 步把这些句子和教材句子一起作为候选（来源记为 SOURCE），之后照常走
第 4 步判断、第 5 步取舍、第 6 步翻译和拼音、第 8 步音频；第 7 步的审核清单里标明是大模型写的，请作者重点审。
"""
import json
import sys

import common
import step4_semantic_tasks

OUT = common.OUT / '补充例句'
SOURCE = '大模型编写（教材里没有可用句子）'
MIN_LEN, MAX_LEN = 6, 30

INSTRUCTIONS = """你在为学习新 HSK 四级词汇的外国学习者（中级，学过一至三级词）编写例句。教材里找不到目标词 word 的合适例句，请写 5 句：
1. 每句都用到目标词，作为一个完整的词，而且只出现一次（不要只出现在更长的词里，如「理发」不能只出现在「理发店」里）；
2. 简短自然，像中级教材里的句子：10–25 个字；除目标词外尽量只用一至三级的常用词；
3. 覆盖这个词面向中级学习者最常用的意思（参考 cedict 里的义项，常用的 1–2 个），每个常用意思至少 2 句；
4. 意思完整，离开上下文也看得懂；不要对话的说话人标签，不要堆砌人名地名，不要书面语、成语或文言；
5. 以句号、问号或感叹号结尾。
只按下面的 JSON 格式回答，不要输出别的内容。"""

ANSWER_FORMAT = {'sentences': ['我每天早上都喝一杯牛奶。']}


def validate(answer, task):
    sents = answer.get('sentences')
    if not isinstance(sents, list) or not 4 <= len(sents) <= 8:
        return ['sentences 应是 4–8 句的列表']
    word = task['word']
    problems = []
    for s in sents:
        if not isinstance(s, str) or not MIN_LEN <= len(s) <= MAX_LEN or s[-1:] not in '。！？':
            problems.append(f'长度应在 {MIN_LEN}–{MAX_LEN} 字、以句号问号或感叹号结尾：{s}')
        elif s.count(word) != 1:
            problems.append(f'目标词应只出现一次：{s}')
    return problems


def task_for(word):
    """任务里放词典义项，让大模型知道要覆盖哪些意思"""
    dictionary = common.cedict()
    senses = [f"[{e['pinyin']}] " + ' / '.join(e['senses']) for e in dictionary.get(word, [])]
    return {'word': word, 'instructions': INSTRUCTIONS, 'answer_format': ANSWER_FORMAT, 'cedict_word': senses}


def main(words, model):
    OUT.mkdir(parents=True, exist_ok=True)
    for word in words:
        common.write_json(OUT / f'{word}.任务.json', task_for(word))
    step4_semantic_tasks.answer_with(model, OUT, words, kind='例句', check=validate)
    for word in words:
        task = json.loads((OUT / f'{word}.任务.json').read_text(encoding='utf-8'))
        answer = common.load_answer(OUT / f'{word}.例句.{model}.json', task, validate)
        common.write_json(OUT / f'{word}.json', {'word': word, 'source': model, 'sentences': answer['sentences']})
        print(f"{word}：{' '.join(answer['sentences'])}", flush=True)


if __name__ == '__main__':
    args = sys.argv[1:]
    model = args[args.index('--model') + 1] if '--model' in args else 'deepseek-flash'
    main([a for i, a in enumerate(args) if a != '--model' and (i == 0 or args[i - 1] != '--model')], model)
