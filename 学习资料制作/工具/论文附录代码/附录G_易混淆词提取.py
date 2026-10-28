# 论文附录G：易混淆词提取（原样提取，仅作对照）

# 读取数据
select_word = '原因'
#显示所有行
# pd.set_option('display.max_rows', None)
#设置value的显示长度为100，默认为50
pd.set_option('max_colwidth', 100)

import pandas as pd
from pandas import DataFrame

# https://blog.csdn.net/qq_32650831/article/details/121000332
data = pd.read_csv('/Users/kangzhengwei/Desktop/新实验/易混淆词/' + select_word +
                   '.csv',
                   index_col=False)
data

# 筛选出错的目标词
df1 = data[data['检索原句'].str.contains(select_word+'{CC') == True]
df1

# 提取混淆词
# 第一步 提取 目标词 + 后面的易混淆词 + 标注
df2 = df1['检索原句'].str.extract(r'(' + select_word +
                              '\{CC\d*[\u4e00-\u9fa5]+\[?[A-Z]*\]?\})',
                              expand=False)
df2

# 正确的第二步 删除目标词
df3 = df2.str.extract(r'([^(' + select_word + ')].+)', expand=False)  
df3

# 第三步：提取易混淆词
df4 = df3.str.extract(r'([\u4e00-\u9fa5]+)')
df4

# 查询每个混淆词出现的次数并排序
df5 = df4.groupby(df4.iloc[:,0]).count()
df5

# 确定是否为易混淆词并筛选易混淆词
import numpy as np
# 计算错误总频次
error_total_time = np.sum(df5.iloc[:, 0].values, axis=0)
# 计算行数
total_rows = df5.shape[0]
# 设置错误总频次数组
df_sum = np.array([error_total_time] * total_rows)
# 添加错误总频次列
# df5的index也得加进来，否则concat不是想要的结果
df_add_errorTotalTime = pd.concat(
    [df5, pd.DataFrame(df_sum, index=df5.index)], axis=1)
# 添加 目标词误用为该词的频次占偏误总频次的占比
# 可以这样除啊
df_add_errorTotalTime[
    'error_rate'] = df_add_errorTotalTime.iloc[:,
                                               0] / df_add_errorTotalTime.iloc[:,
                                                                               1]
# 筛选易混淆词
df_common_confused_words = df_add_errorTotalTime[
    df_add_errorTotalTime['error_rate'] > 0.2]
df_common_confused_words

# 查询易混淆词的等级
import pandas as pd
df = pd.read_excel('/Users/kangzhengwei/Desktop/HSK-2012.xlsx', header=None)

# 获取易混淆词索引，即易混淆词
a = df_common_confused_words.index
# 这就对了
df6 = pd.DataFrame()
for i in a:
    # 暂时先不考虑不在HSK等级词汇表里的词汇了
    df7 = df[df.iloc[:, 0].str.contains(i) == True]
    df6 = pd.concat([df6, df7], axis=0)  # axis=0在y轴的方向上进行合并
# 取消索引
df6 = df6.reset_index()
# 删除index列
df6 = df6.drop('index', axis=1)
df6

# 把目标词的易混淆词写入到文件
df6.to_csv('/Users/kangzhengwei/Desktop/新实验/目标词及其易混淆词/' + select_word + '.csv')
