# 论文附录D：统计教材语料词频（原样提取，仅作对照）

import jieba
import pandas as pd
from pandas import DataFrame

txt = open('/Users/kangzhengwei/Desktop/课文语料/所有的中级教材语料.txt', 'r').read()
words = jieba.lcut(txt)  #分词 直接返回 list

counts = {}  #词频统计

# 要查询的词汇
df = pd.read_excel('/Users/kangzhengwei/Desktop/新实验/四级词汇即及词频.xlsx')
search_words = df['vocabulary'].values

for word in words:
    counts[word] = counts.get(word, 0) + 1
for key, value in counts.items():  
    print(key, value)

# 把词频统计数据写入到DataFrame中

textbook_words_freq = pd.DataFrame(columns=['textbook_word','textbook_freq'])

for key, value in counts.items():
    new = pd.DataFrame({'textbook_word': key,'textbook_freq': value
    }, index=[0])
    textbook_words_freq = textbook_words_freq.append(new, ignore_index=True)

textbook_words_freq

textbook_words_freq = textbook_words_freq.sort_values(by='textbook_freq',ascending=False)
textbook_words_freq

textbook_words_freq.to_excel('/Users/kangzhengwei/Desktop/新实验/教材语料词频表.xlsx')
