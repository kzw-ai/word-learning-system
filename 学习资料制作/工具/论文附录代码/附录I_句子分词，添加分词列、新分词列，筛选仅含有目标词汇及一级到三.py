# 论文附录I：句子分词，添加分词列、新分词列，筛选仅含有目标词汇及一级到三级词汇的句子（原样提取，仅作对照）

# 对句子进行分词并添加分词列
data['分词'] = data['句子'].apply(jieba.lcut)
data

# 把目标词汇添加到分词中，作为新分词列
def str_to_list(x):
    list1 = []
    list1.append(x) # 关键的步骤。其实就是列表中可以添加任何东西。这里是把字符串添加进了列表。
    return list1


data['新分词'] = data['词汇'].apply(str_to_list) + data['分词'] # 列表相加
data

# 筛选只包含目标词汇与新HSK一级到三级词汇的句子
# HSK1级- HSK3级的词汇

import pandas as pd

df = pd.read_excel('/Users/kangzhengwei/Desktop/HSK-2012.xls', header=None)
df1 = df[df.iloc[:, 0].str.contains('一级')]
df2 = df[df.iloc[:, 0].str.contains('二级')]
df3 = df[df.iloc[:, 0].str.contains('三级')]

low_grade_vocabulary = pd.concat([df1, df2, df3])
# low_grade_vocabulary
low_grade_vocabulary['等级'] = low_grade_vocabulary.iloc[:, 0].str[-3:-1]
low_grade_vocabulary['词汇'] = low_grade_vocabulary.iloc[:, 0].str[:-4]
len(low_grade_vocabulary)
# low_grade_vocabulary

low_grade_words = list(low_grade_vocabulary['词汇'].values)
print(low_grade_words)
HSK1_to_HSK3 = low_grade_words

def right_sentence(x):

    punctuation = ['，', '。', '？', '！', '”', '”', '：', '、', '；']
    for punc in punctuation:
        if punc in x:
            x.remove(punc)
    result = 1
    for i in x:
        if i in HSK1_to_HSK3 or i == data['新分词'][0]:
            j = 1
        else:
            j = 0
        result = result * j  
    return result


data["True_or_False"] = data['新分词'].apply(right_sentence)
data[data["True_or_False"] == 1]
# 这次竟然有两个这样的句子，但是太少了。因此这种方式还是不能奏效。
