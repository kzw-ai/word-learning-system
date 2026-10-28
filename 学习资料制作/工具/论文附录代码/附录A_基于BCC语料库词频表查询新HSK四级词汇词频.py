# 论文附录A：基于BCC语料库词频表查询新HSK四级词汇词频（原样提取，仅作对照）

# 获取词表中的四级词汇
import pandas as pd
df = pd.read_excel('/Users/kangzhengwei/Desktop/HSK-2012.xls', header=None)
df4 = df[df.iloc[:, 0].str.contains('四级')]
df4['等级'] = df4.iloc[:, 0].str[-3:-1]
df4['词汇'] = df4.iloc[:, 0].str[:-4]
df4

# 读取BCC语料库词频
import pandas as pd

word_freq = pd.read_csv('./global_wordfreq.txt', sep='\t', header=None)
word_freq

# 修改df4列名
df4 = df4.rename(columns={0:'original','等级':'grade', '词汇':'vocabulary'})
df4

# 修改word_freq列名
word_freq= word_freq.rename(columns={0:'vocabulary',1:'frequency'})
word_freq

# 建立 四级词汇表 与 词频表 的左连接

import pandas as pd
from pandas import DataFrame
from pandasql import sqldf

pysqldf = lambda sql: sqldf(sql, globals())
sql = "select df4.vocabulary, word_freq.frequency from df4 left join word_freq on df4.vocabulary == word_freq.vocabulary"

grade4_word_freq = pysqldf(sql)
grade4_word_freq

# 对四级词汇按照词频进行降序排列
grade4_word_freq = grade4_word_freq.sort_values(by='frequency', ascending=False)
grade4_word_freq

# 写入到excel文件中
grade4_word_freq.to_excel('/Users/kangzhengwei/Desktop/新实验/四级词汇即及词频.xlsx')
