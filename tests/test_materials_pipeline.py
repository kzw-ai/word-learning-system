"""学习资料制作第 3–7 步的纯函数：句首杂质清理、回答整理、单字词的字音。不联网，不调用大模型。"""
import sys
from pathlib import Path

import pytest

pytest.importorskip('pypinyin')
pytest.importorskip('jieba')
pytest.importorskip('openpyxl')
pytest.importorskip('xlrd')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / '学习资料制作' / '工具'))

import step3_candidates as s3  # noqa: E402  # pyrefly: ignore
import step6_check_tasks as s6  # noqa: E402  # pyrefly: ignore
import step7_build as s7  # noqa: E402  # pyrefly: ignore

SPEAKERS = {'王静', '朋友', '售货员'}


def clean(sentence, word='讨论'):
    return s3.clean_start(sentence, word, SPEAKERS)


class TestCleanStart:
    def test_strips_speaker_quote_and_item_number(self):
        assert clean('朋友：她去年秋天出生的，刚过完一岁生日。', '出生') == '她去年秋天出生的，刚过完一岁生日。'
        assert clean('”3孩子出生以后，从医院回到家中。', '出生') == '孩子出生以后，从医院回到家中。'
        assert clean('”王静：“你别担心。”', '担心') == '“你别担心。”'
        assert clean('6如果你最喜欢灰色。', '如果') == '如果你最喜欢灰色。'
        assert clean('2、时间很紧张。', '紧张') == '时间很紧张。'
        assert clean('2.年龄很重要。', '年龄') == '年龄很重要。'
        assert clean('13797915397002000“那妻子的字条呢？', '字条') == '“那妻子的字条呢？'

    def test_keeps_numbers_that_belong_to_the_sentence(self):
        for s in ('20世纪的黄昏已经来临。', '3天后再讨论。', '8：30开始讨论。', '8:00了，我开始讨论。',
                  '20~30人参加讨论。', '2.5倍的人参加讨论。', '28岁的人参加讨论。'):
            assert clean(s) == s

    def test_keeps_colons_that_are_not_speakers(self):
        assert clean('我决定：明天参加讨论。') == '我决定：明天参加讨论。', '只出现一两次的不是说话人'
        assert clean('售货员：这件衣服打折。', '售货员') == '这件衣服打折。', '标签里的目标词不算用法，后面按分词筛掉'

    def test_speakers_are_labels_seen_at_least_three_times(self):
        sents = [('书', s) for s in ['小丽：好。', '小丽：走吧。', '小丽：对。', '我决定：去。', '罗伟说：好。'] * 1]
        sents += [('书', '罗伟说：好。')] * 3
        assert s3.speaker_labels(sents) == {'小丽'}, '以说话动作结尾的不算'

    def test_sentence_without_prefix_is_unchanged(self):
        assert clean('我们明天再讨论这个问题。') == '我们明天再讨论这个问题。'


class TestTidyCheck:
    def test_joins_split_syllables(self):
        a = {'examples': [{'sentence': '一个活动', 'pinyin': '一个/yí ge 活动/huódòng'}]}
        s6.join_split_pinyin(a)
        assert a['examples'][0]['pinyin'] == '一个/yíge 活动/huódòng'

    def test_drops_conflicts_outside_options_and_restores_collocation_spaces(self):
        task = {'collocations': ['收 好'], 'exercises': {
            'collocation1': {'options': ['流行', '北京'], 'spares': ['饿'], 'correct_answer': '流行'}}}
        a = {'distractor_conflicts': {'collocation1': ['听', '北京', '流行']}, 'collocations': [{'collocation': '收好'}]}
        s6.tidy_check(a, task)
        assert a['distractor_conflicts']['collocation1'] == ['北京']
        assert a['collocations'][0]['collocation'] == '收 好'


class TestSingleCharacterReading:
    def test_follows_the_kept_sense(self):
        sel = {'characters': [{'character': '转', 'pinyin': 'zhuǎn', 'pos': 'v.', 'definition': 'to turn'}]}
        senses = [{'pos': 'v.', 'definition': 'to revolve; to turn; to circle'}]
        assert s7.characters('转', sel, {'word_pinyin': 'zhuàn'}, senses) == \
            [{'character': '转', 'pinyin': 'zhuàn', 'definition': 'v. to revolve; to turn; to circle'}]

    def test_multi_character_words_keep_step4_entries(self):
        sel = {'characters': [{'character': '出', 'pinyin': 'chū', 'pos': 'v.', 'definition': 'to go out'},
                              {'character': '生', 'pinyin': 'shēng', 'pos': 'v.', 'definition': 'to be born'}]}
        assert [c['pinyin'] for c in s7.characters('出生', sel, {'word_pinyin': 'chūshēng'}, [{}])] == ['chū', 'shēng']
