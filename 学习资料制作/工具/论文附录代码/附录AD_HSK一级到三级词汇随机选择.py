# 论文附录AD：HSK一级到三级词汇随机选择（原样提取，仅作对照）

import pandas as pd
import random

df = pd.read_excel('/Users/kangzhengwei/Desktop/HSK-2012.xls', header=None)
df1 = df[df.iloc[:, 0].str.contains('一级')]
df2 = df[df.iloc[:, 0].str.contains('二级')]
df3 = df[df.iloc[:, 0].str.contains('三级')]

low_grade_vocabulary = pd.concat([df1, df2, df3])
low_grade_vocabulary['等级'] = low_grade_vocabulary.iloc[:, 0].str[-3:-1]
low_grade_vocabulary['词汇'] = low_grade_vocabulary.iloc[:, 0].str[:-4]

low_grade_words = list(low_grade_vocabulary['词汇'].values)

HSK1_to_HSK3 = low_grade_words
HSK1_to_HSK3

my_str = 'A.' + random.choice(HSK1_to_HSK3) + '  B.' + random.choice(
    HSK1_to_HSK3) + '  C.' + random.choice(
        HSK1_to_HSK3) + '  D.' + random.choice(HSK1_to_HSK3)
print(my_str)
