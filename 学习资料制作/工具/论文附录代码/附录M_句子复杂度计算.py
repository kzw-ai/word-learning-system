# 论文附录M：句子复杂度计算（原样提取，仅作对照）

data = pd.read_pickle('/Users/kangzhengwei/Desktop/新实验/最终版/句子_加high_grade_words_appear.pickle')
data

data = data.iloc[:,1:]
data

def calculate_sentence_complexity(x):
    # 去除列表中的中文标点符号
    punctuation = ['，', '。', '？', '！', '”', '”', '：', '、', '；']
    for punc in punctuation:
        if punc in x:
            x.remove(punc)

    # 计算句子复杂度
    result = 0
    for i in x:

        # 对应词汇复杂度的字典
        j = float(word_complexity_dict.get(i, 0))
        #         print(type(j))

        result = result + j  # 认识到了这儿有bug。这次修改过来了。
    return result


data['sentence_complexity'] = data['分词'].apply(calculate_sentence_complexity)
data

# 对句子复杂度进行标准化

from sklearn import preprocessing
import numpy as np

x = data['sentence_complexity'].to_frame()
# 将数据进行[0,1]规范化
min_max_scaler = preprocessing.MinMaxScaler()
minmax_x = min_max_scaler.fit_transform(x)
print(minmax_x)

# 将规范化后的句子复杂度添加到data上

data_with_sentence_complexity_scale = pd.concat([
    data,
    pd.DataFrame(minmax_x, columns=['sentence_complexity_MinMaxScale'])
],
                                                axis=1,
                                                join='inner')
data_with_sentence_complexity_scale

# 按 词汇 进行分组, 并按照句子复杂度（经过标准化）与高等级词汇的数量进行升序排列

data_with_sentence_complexity_scale = data_with_sentence_complexity_scale.groupby(
    '词汇').apply(lambda x: x.sort_values(
        by=['sentence_complexity_MinMaxScale', 'high_grade_words_count'],
        ascending=[True, True]))
data_with_sentence_complexity_scale

# 写入文件
data_with_sentence_complexity_scale.to_pickle(
    '/Users/kangzhengwei/Desktop/新实验/最终版/data_with_sentence_complexity_scale.pickle'
)

# 写入文件
data_with_sentence_complexity_scale.to_excel(
    '/Users/kangzhengwei/Desktop/新实验/最终版/data_with_sentence_complexity_scale.xlsx'
)
