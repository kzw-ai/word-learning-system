# 论文附录L：获取词汇复杂度字典（原样提取，仅作对照）

# 读取BCC语料库词频
import pandas as pd

word_freq = pd.read_csv('./global_wordfreq.txt', sep='\t', header=None)
word_freq

from sklearn import preprocessing
import numpy as np
import math

# 取对数后再取倒数
# 利用to_frame()将Series转换为DataFrame

x = word_freq.iloc[:, 1].apply(lambda x: math.log(x)).apply(
    lambda x: 1 / x).to_frame()
# 将数据进行[0,1]规范化
min_max_scaler = preprocessing.MinMaxScaler()
minmax_x = min_max_scaler.fit_transform(x)
print(minmax_x)

# 将词汇难度添加到词频表
word_complexity_with_log_reciprocal_MinMaxScale = pd.concat([
    word_freq, pd.DataFrame(minmax_x, columns=['word_complexity_log_reciprocal_MinMaxScale'])], axis=1,join='inner')

word_complexity_with_log_reciprocal_MinMaxScale

# 修改列名
word_complexity_with_log_reciprocal_MinMaxScale.rename(columns={
    0:
    'words',
    1:
    'word_freq',
    'word_complexity_log_reciprocal_MinMaxScale':
    'word_complexity_log_reciprocal_MinMaxScale'
}, inplace=True)
word_complexity_with_log_reciprocal_MinMaxScale

# 特征选择
word_complexity_with_log_reciprocal_MinMaxScale = word_complexity_with_log_reciprocal_MinMaxScale[
    ['words', 'word_complexity_log_reciprocal_MinMaxScale']]
word_complexity_with_log_reciprocal_MinMaxScale

# 写入csv文件
word_complexity_with_log_reciprocal_MinMaxScale.to_csv(
    '/Users/kangzhengwei/Desktop/新实验/最终版/word_complexity_with_log_reciprocal_MinMaxScale.csv',index=False
)

# 获取词汇复杂度字典
import csv


def csv2dict(in_file, key, value):
    new_dict = {}
    with open(in_file, 'r') as f:
        reader = csv.reader(f, delimiter=',')
        fieldnames = next(reader)
        reader = csv.DictReader(f, fieldnames=fieldnames, delimiter=',')
        for row in reader:
            new_dict[row[key]] = row[value]
    return new_dict


word_complexity_dict = csv2dict(
    '/Users/kangzhengwei/Desktop/新实验/最终版/word_complexity_with_log_reciprocal_MinMaxScale.csv',
    'words', 'word_complexity_log_reciprocal_MinMaxScale')
word_complexity_dict
