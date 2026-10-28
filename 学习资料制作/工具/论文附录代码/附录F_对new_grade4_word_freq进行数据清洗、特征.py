# 论文附录F：对new_grade4_word_freq进行数据清洗、特征选择、数据规范化（原样提取，仅作对照）

# 填充空值
new_grade4_word_freq.fillna(0, inplace=True)
new_grade4_word_freq

# 对new_grade4_word_freq进行特征选择及数据标准化

# 特征选择

new_grade4_word_freq = new_grade4_word_freq[[
    'vocabulary', 'frequency', 'textbook_freq'
]]
new_grade4_word_freq

from sklearn import preprocessing
import numpy as np
x = new_grade4_word_freq[['frequency', 'textbook_freq']]
# 将数据进行[0,1]规范化
min_max_scaler = preprocessing.MinMaxScaler()
minmax_x = min_max_scaler.fit_transform(x)
print(minmax_x)

new_grade4_word_freq[['BCC_freq_MinMax','text_freq_MinMax']] = minmax_x
new_grade4_word_freq

new_grade4_word_freq['last_freq'] = 0.3 * new_grade4_word_freq[
    'BCC_freq_MinMax'] + 0.7 * new_grade4_word_freq['text_freq_MinMax']
new_grade4_word_freq

last_grade4_word_freq = last_grade4_word_freq.sort_values(by='last_freq', ascending=False)
last_grade4_word_freq

last_grade4_word_freq.to_excel(
    '/Users/kangzhengwei/Desktop/新实验/last_grade4_word_freq.xlsx')
