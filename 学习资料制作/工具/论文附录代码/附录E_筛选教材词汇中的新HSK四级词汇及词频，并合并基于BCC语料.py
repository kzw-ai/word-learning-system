# 论文附录E：筛选教材词汇中的新HSK四级词汇及词频，并合并基于BCC语料库的词汇及词频统计表（原样提取，仅作对照）

# 读取基于BCC语料库的四级词汇及词频表

grade4_words_freq = pd.read_excel(
    "/Users/kangzhengwei/Desktop/新实验/四级词汇即及词频.xlsx")
grade4_words_freq

# 筛选教材词汇中的新HSK四级词汇及词频，并合并基于BCC语料库的词汇及词频统计表

import pandas as pd
from pandas import DataFrame
from pandasql import sqldf

pysqldf = lambda sql: sqldf(sql, globals())
sql = "select grade4_words_freq.vocabulary, grade4_words_freq.frequency, textbook_words_freq.textbook_word, textbook_words_freq.textbook_freq from grade4_words_freq left join textbook_words_freq on grade4_words_freq.vocabulary == textbook_words_freq.textbook_word"

new_grade4_word_freq = pysqldf(sql)
new_grade4_word_freq

new_grade4_word_freq.to_excel('/Users/kangzhengwei/Desktop/新实验/new_grade4_word_freq.xlsx')
new_grade4_word_freq
