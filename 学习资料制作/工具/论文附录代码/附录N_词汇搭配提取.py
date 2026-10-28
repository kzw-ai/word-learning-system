# 论文附录N：词汇搭配提取（原样提取，仅作对照）

# 读取excel文件
select_word = '通过'
import pandas as pd

data = pd.read_excel('/Users/kangzhengwei/Desktop/新实验/搭配信息获取/' + select_word + '.xlsx')
data

# 获取第二列
df1 = data.iloc[:, 1]
df1

# 使用正则表达式提取出搭配（去除目标词和空格）
# 去除目标词
df1.str.extract(r'([^(' + select_word + ')].*[^(' + select_word + ')])', expand=False)

# 提取词汇搭配
df2 = df1.str.extract(r'([^(' + select_word + ')].*[^(' + select_word + ')])', expand=False).str.extract(r'([\u4e00-\u9fa5]+)')  # 正好可以把‘开放 的’中的‘ 的’去掉。
df2

# 识别词汇搭配及其词汇等级
df3 = pd.read_excel('/Users/kangzhengwei/Desktop/HSK-2012.xlsx', header=None)
df3

import numpy as np


def word_and_level(x):
    for i in df3.iloc[:, 0].values:
        if x is not np.nan:  # 这里还必须用is not，不能用!=
            if x in i: # 比如’服务‘ in ’服务员‘，’服务员‘也可以提取出来。
                return i
        else:
            return None


df4 = df2.iloc[:, 0].apply(word_and_level)
df4

# 把等级列添加到data中
data['word_grade'] = df4
data

# word_grade列过滤空值
data2 = data[data['word_grade'].isnull() == False]
data2

# 筛选新HSK一级到三级词汇，按照互信息降序排列
data3 = data2[data2['word_grade'].str.contains('三级|二级|一级')].sort_values(
    by='Mutual Information', ascending=False)
data3

# 写入到文件
data3.to_csv('/Users/kangzhengwei/Desktop/新实验/搭配信息_添加词汇等级/'+select_word+'.csv')
