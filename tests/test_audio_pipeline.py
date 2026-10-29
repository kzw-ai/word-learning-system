"""学习资料制作第 8 步（发音音频）的纯函数：读音标注、音标、对话说话人。不联网，不调用 Azure。"""
import sys
from pathlib import Path

import pytest

pytest.importorskip('pypinyin')
pytest.importorskip('jieba')
pytest.importorskip('openpyxl')
pytest.importorskip('xlrd')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / '学习资料制作' / '工具'))

import step8_audio  # noqa: E402  # pyrefly: ignore
import tts  # noqa: E402  # pyrefly: ignore


class TestPhonemeMarks:
    def test_sapi_notation(self):
        assert [tts.to_sapi(s) for s in ('děi', 'nǚ', 'lǜ', 'lüè', 'qù', 'ba')] == \
            ['dei 3', 'nv 3', 'lv 4', 'lue 4', 'qu 4', 'ba 5']

    def test_marks_only_where_the_usual_reading_differs(self):
        assert tts.marked([('我', 'wǒ'), ('得', 'děi'), ('走', 'zǒu'), ('了', 'le'), ('。', None)]) == \
            '我<phoneme alphabet="sapi" ph="dei 3">得</phoneme>走了。'
        assert tts.marked([('长城', 'chángchéng')]) == '长城', '默认就读对的不标'
        assert tts.marked([('喜欢', 'xǐhuan')]) == '喜欢', '只差轻声不标'

    def test_sandhi_and_erhua_are_left_to_the_engine(self):
        assert tts.marked([('不', 'bú'), ('去', 'qù')]) == '不去'
        assert tts.marked([('一个', 'yígè')]) == '一个'
        assert '<phoneme' not in tts.marked([('点儿', 'diǎnr')])

    def test_text_is_escaped(self):
        assert tts.marked([('A<B&C', None)]) == 'A&lt;B&amp;C'


class TestSentenceTokens:
    def test_every_speaker_label_is_dropped(self):
        tokens = step8_audio.sentence_tokens(
            '小王：表演得真棒。李老师：是我孙子。',
            '小/xiǎo 王/wáng 表演/biǎoyǎn 得/de 真/zhēn 棒/bàng 李/lǐ 老师/lǎoshī 是/shì 我/wǒ 孙子/sūnzi')
        assert ''.join(t for t, _ in tokens) == '表演得真棒。是我孙子。'

    def test_reported_speech_is_read(self):
        for sentence in ('她想：幸亏当时自己没拒绝他的邀请。', '他说：我明天来。'):
            assert ''.join(t for t, _ in step8_audio.sentence_tokens(sentence, '')) == sentence

    def test_aligns_around_missing_punctuation_and_truncated_lines(self):
        assert step8_audio.sentence_tokens('生意就这样成了。', '生意/shēngyì 就/jiù 这样/zhèyàng 成/chéng') == \
            [('生意', 'shēngyì'), ('就', 'jiù'), ('这样', 'zhèyàng'), ('成', 'chéng'), ('了。', None)]

    def test_collocation_level_notes_are_removed(self):
        assert step8_audio.collocation_tokens('认真（三级） 考虑', '考虑', 'kǎolǜ') == \
            [('认真', None), ('考虑', 'kǎolǜ'), ('', None)]
