"""论文课件题的解析：作者审核后改的干扰项（OPTION_FIXES）在导入时替换，课件原文不动"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
import parse_answer_decks  # noqa: E402


def test_author_option_fixes_apply_on_import():
    slides, _ = parse_answer_decks.parse_all()
    items = {(s['deck'], s['slide'], it['stem']): it for s in slides for it in s['items']}
    for key, fix in parse_answer_decks.OPTION_FIXES.items():
        assert key in items, f'修订对不上课件里的题：{key}'
        for old, new in fix.items():
            assert new in items[key]['options'] and old not in items[key]['options'], key
    together = items[('the answer of the third time of learning', 11, '一起 ( )')]
    assert together['options'] == ['西瓜', '被', '生活', '桌子'] and together['correct_answer'] == '生活'
