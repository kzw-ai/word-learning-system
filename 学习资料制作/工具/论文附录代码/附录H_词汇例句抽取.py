# 论文附录H：词汇例句抽取（原样提取，仅作对照）

import re
import pandas as pd
from pandas import DataFrame
import jieba

f = open('/Users/kangzhengwei/Desktop/课文语料/所有的中级教材语料.txt', 'r')
element = f.read()


def seg_tail_split(str1, sep=r"。|？|！"):  # 分隔符可为多样的正则表达式
    # 保留分割符号，置于句尾，比如标点符号
    wlist = re.split(sep, str1)
    seg_word = re.findall(sep, str1)
    seg_word.extend(" ")  # 末尾插入一个空字符串，以保持长度和切割成分相同
    wlist = [x + y for x, y in zip(wlist, seg_word)]  # 顺序可根据需求调换
    return wlist


split_article_content = seg_tail_split(element)
print(split_article_content)

# # 部分四级词汇
# words_freq = pd.read_excel(
#     '/Users/kangzhengwei/Desktop/新实验/last_grade4_word_freq.xlsx')

# 高频词
# search_word = words_freq.iloc[:, 1].values[:60]

# 四级中频词、几个易混淆词、低频词
search_word = ['看法', '深', '降低', '重视', '缺点', '气候','关键', '难受', '正式', '号码', '生意', '部分','想法', '大', '下降', '重要', '坏处', '天气','问题', '难过', '学期', '约会', '误会', '孙子','首都', '卫生间', '简直', '暖和', '景色', '堵车','语法', '迷路']

print(search_word)

data = pd.DataFrame(columns=['词汇', '句子'])

# 下面这两个循环的顺序就对了
for word in search_word:
    for i in split_article_content:
        # 判断词汇是不是在句子的词汇中，而不能只是是否出现在句子中。
        # 词频的统计是直接用结巴分词，而这个是先分割好句子，再看词汇有没有在句子中出现过。当然是不同的，因为有的句子中可能出现了两次这个词汇，那么词汇就显得多一些。这是非常合理的情况。
        if word in jieba.lcut(i):

            # 用pandas处理更方便一些
            #             print(word, i)
            new = pd.DataFrame({'词汇': word, '句子': i}, index=[0])
            #             print(new)
            data = data.append(new, ignore_index=True)
