# 论文附录K：添加句子中高等级词汇个数，标注出现的高等级词汇（原样提取，仅作对照）

# 前面需要保存为.pickle格式，这样分词列与新分词列的每行内容才是列表，如果保存为.xls，每行内容则成为字符串了。
data = pd.read_pickle('/Users/kangzhengwei/Desktop/新实验/新分词.pickle')
data

# 四五六级词汇 选择

import pandas as pd

df = pd.read_excel('/Users/kangzhengwei/Desktop/HSK-2012.xls', header=None)
df4 = df[df.iloc[:, 0].str.contains('四级')]
df5 = df[df.iloc[:, 0].str.contains('五级')]
df6 = df[df.iloc[:, 0].str.contains('六级')]

high_grade_vocabulary = pd.concat([df4, df5, df6])
# high_grade_vocabulary
high_grade_vocabulary['等级'] = high_grade_vocabulary.iloc[:, 0].str[-3:-1]
high_grade_vocabulary['词汇'] = high_grade_vocabulary.iloc[:, 0].str[:-4]
len(high_grade_vocabulary)
# high_grade_vocabulary

high_grade_words = list(high_grade_vocabulary['词汇'].values)
print(high_grade_words)

# 统计每个句子的高等级词汇出现次数
def high_grade_words_count(x):

    result = 0
    for i in x:
        if i in high_grade_words:
            result += 1

    return result


data["high_grade_words_count"] = data['分词'].apply(high_grade_words_count)
data

# 统计每个句子中出现的高等级词汇
def high_grade_words_appear(x):

    result = []
    for i in x:
        if i in high_grade_words:
            result.append(i)

    return result


data["high_grade_words_appear"] = data['分词'].apply(
    high_grade_words_appear)  # 函数还是会作用于所选列的每一行～～
data
# 保存为.pickle文件
data.to_pickle('/Users/kangzhengwei/Desktop/新实验/句子_加high_grade_words_appear.pickle')
