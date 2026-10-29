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
import step5_select as s5  # noqa: E402  # pyrefly: ignore
import step6_check_tasks as s6  # noqa: E402  # pyrefly: ignore
import step7_build as s7  # noqa: E402  # pyrefly: ignore
import step6b_fill_from_example as s6b  # noqa: E402  # pyrefly: ignore

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


class TestTrimLongSentences:
    ORIGINAL = '每天早上9点上班，工资三千来块，试用期一个月。'

    def test_only_a_clause_bounded_by_punctuation(self):
        assert s6.is_clause_of(self.ORIGINAL, '工资三千来块，试用期一个月。')
        assert s6.is_clause_of(self.ORIGINAL, '工资三千来块。'), '末尾的逗号可以改成句号'
        assert not s6.is_clause_of(self.ORIGINAL, '早上9点上班。'), '不能从分句中间截'
        assert not s6.is_clause_of(self.ORIGINAL, '工资三千块，试用期一个月。'), '不能改字'
        assert not s6.is_clause_of(self.ORIGINAL, self.ORIGINAL), '要比原句短'

    def test_validate_trim(self):
        task = {'sentences': {'1': self.ORIGINAL, '2': '他特意拿了个旧书包，要我同他一起到附近的银行取钱。'}}
        assert s6.validate_trim({'trims': {'1': '工资三千来块，试用期一个月。', '2': None}}, task) == []
        assert s6.validate_trim({'trims': {'1': '工资很高。', '2': None}}, task)
        assert s6.validate_trim({'trims': {'1': None}}, task), '漏答'

    def test_apply_keeps_original_and_is_idempotent(self):
        e = {'sentence': self.ORIGINAL, 'tokens': [], 'book': '书', 'complexity': 1.0, 'hsk4_6_words': []}
        sel = {'senses': [{'example': e}], 'exercises': {'fill_word': None}}
        trims = {self.ORIGINAL: '工资三千来块，试用期一个月。'}
        assert s6.apply_trims('工资', sel, trims, {}, {}) == 1
        ex = sel['senses'][0]['example']
        assert (ex['sentence'], ex['original']) == ('工资三千来块，试用期一个月。', self.ORIGINAL)
        s6.apply_trims('工资', sel, trims, {}, {})
        assert sel['senses'][0]['example']['original'] == self.ORIGINAL

    def test_trim_without_the_target_word_is_ignored(self):
        e = {'sentence': self.ORIGINAL, 'tokens': [], 'book': '书', 'complexity': 1.0, 'hsk4_6_words': []}
        sel = {'senses': [{'example': e}], 'exercises': {'fill_word': None}}
        assert s6.apply_trims('上班', sel, {self.ORIGINAL: '工资三千来块，试用期一个月。'}, {}, {}) == 0
        assert sel['senses'][0]['example']['sentence'] == self.ORIGINAL

    def test_bad_trims_fall_back_to_the_original(self):
        task = {'sentences': {'1': self.ORIGINAL, '2': '电视里有很多精彩的体育节目，大家都爱看。'}}
        a = {'trims': {'1': '工资三千来块，试用期一个月。', '2': '电视里有精彩的体育节目。'}}
        s6.drop_bad_trims(a, task)
        assert a['trims']['2'] is None and a['rejected'] == {'2': '电视里有精彩的体育节目。'}
        assert s6.validate_trim(a, task) == []


class TestShortExamplesFirst:
    def test_short_usable_sentence_wins_over_lower_complexity_long_one(self):
        long_s = {'sentence': '每天早上9点上班，工资三千来块，试用期一个月，下个月开始转正。', 'tokens': [], 'complexity': 0.5}
        short_s = {'sentence': '他的工资不高。', 'tokens': ['他', '的', '工资', '不', '高', '。'], 'complexity': 0.9}
        judgment = {'senses': [{'id': 's1', 'pos': 'n.', 'definition': 'wages'}],
                    'sentence_senses': {'1': 's1', '2': 's1'}, 'collocation_senses': {}, 'characters': []}
        candidates = {'sentences': [long_s, short_s], 'collocations_edu': [], 'collocations_wiki': [],
                      'confusables': [], 'hsk_level': 4}
        pool = [f'词{i}' for i in range(40)]
        result = s5.select('工资', candidates, judgment, pool)
        assert result['senses'][0]['example']['sentence'] == '他的工资不高。'


class TestWordsTheTokenizerGlues:
    def test_split_glued_measure_words_and_complements(self):
        assert s3.split_glued(['墙边', '种着', '几棵', '小', '果树'], '棵') == ['墙边', '种着', '几', '棵', '小', '果树']
        assert s3.split_glued(['很帅'], '帅') == ['很', '帅']
        assert s3.split_glued(['桥上', '走'], '桥') == ['桥', '上', '走']
        assert s3.split_glued(['到底'], '底') == ['到底'], '到底不是「底」'

    def test_force_token_for_drafted_sentences(self):
        assert s3.force_token(['我们', '班有', '百分之六十', '的'], '百分之') == ['我们', '班有', '百分之', '六十', '的']
        assert s3.force_token(['这', '篇'], '篇') == ['这', '篇']

    def test_draft_validation(self):
        import draft_examples as d  # noqa: E402  # pyrefly: ignore
        task = {'word': '签证'}
        good = ['我需要先办签证。', '我的签证下个月到期。', '别忘了带签证。', '办签证要几天？']
        assert d.validate({'sentences': good}, task) == []
        assert d.validate({'sentences': good[:3]}, task), '至少 4 句'
        assert d.validate({'sentences': good[:3] + ['签证签证都办好了。']}, task), '目标词只能出现一次'
        assert d.validate({'sentences': good[:3] + ['我需要先办签证']}, task), '要有句末标点'


class TestFillFromExample:
    """第 6b 步：填字题改用学习页上的例句（论文 3.2 节）"""

    def sel(self, sentence, tokens):
        return {'senses': [{'example': {'sentence': sentence, 'tokens': tokens}}], 'exercises': {}}

    def test_blanks_the_last_character_of_the_word_in_the_example(self):
        fill = s6b.fill_from_example('原因', self.sel('我慢慢去想其中的原因。', ['我', '慢慢', '去', '想', '其中', '的', '原因', '。']))
        assert fill['stem'] == '我慢慢去想其中的原 ( ) 。' and fill['correct_answer'] == '因'
        assert fill['sentence'] == '我慢慢去想其中的原因。' and fill['from_example']

    def test_keeps_the_old_question_when_the_word_appears_twice(self):
        assert s6b.fill_from_example('想', self.sel('我想你想我。', ['我', '想', '你', '想', '我', '。'])) is None

    def test_hint_only_when_other_characters_fit(self):
        fill = {'stem': '人 ( ) 人之间应该多一些宽容。', 'correct_answer': '与'}
        assert s6b.question(fill, {'other_fits': [], 'hint': None})['stem'] == '人 ( ) 人之间应该多一些宽容。'
        q = s6b.question(fill, {'other_fits': ['和', '跟'], 'hint': 'yǔ'})
        assert q['stem'] == '人 ( y ) 人之间应该多一些宽容。' and q['hint'] == 'y'
        # 别的能填的字声母相同时给完整拼音（论文 3.2.4）
        assert s6b.question({'stem': '原 ( ) 是什么？', 'correct_answer': '因'}, {'other_fits': ['由'], 'hint': 'yīn'})['hint'] == 'yīn'

    def test_validate_and_tidy(self):
        task = {'answer': '与'}
        answer = {'other_fits': ['和', '与', '和 '], 'hint': ' Yǔ '}
        s6b.tidy(answer, task)
        assert answer == {'other_fits': ['和'], 'hint': 'yǔ'} and s6b.validate(answer, task) == []
        assert s6b.validate({'other_fits': ['和'], 'hint': None}, task)
        assert s6b.validate({'other_fits': ['和跟'], 'hint': 'yǔ'}, task)
        empty = {'other_fits': [], 'hint': 'yǔ'}
        s6b.tidy(empty, task)
        assert empty['hint'] is None and s6b.validate(empty, task) == []
