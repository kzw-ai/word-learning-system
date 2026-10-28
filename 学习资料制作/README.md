# 学习资料制作

为新 HSK 四级词编写学习资料（词、字、搭配、例句、练习题、易混淆词），方法按论文第五章 5.3 节。**操作步骤见 [制作流程.md](制作流程.md)**；这份说明讲文件夹怎么分、数据从哪里来。

## 文件夹

| 文件夹 | 放什么 | 提交到仓库吗 |
|---|---|---|
| `1_源数据/` | 下载或作者提供的原始数据，只读不改 | 不提交（版权、许可、令牌） |
| `2_加工结果/` | 程序算出来的中间结果：分档、易混淆词、候选清单、大模型判断与检查、取舍 | 不提交（含教材原句） |
| `3_审核/` | 每批的 `词表.txt`（这一批做哪些词）、`素材.json`（汇总的学习资料）、`审核清单.md`（给作者核对） | 不提交（含教材原句） |
| `工具/` | 各步脚本；`论文附录代码/` 是论文附录代码的原样摘录，作对照用 | 提交。不提交的：`deepseek_api_key.txt`，以及 `hsk_client.py`（调用的是语料库网站给自己网页用的内部接口，只留在本地） |
| `.venv/` | Python 虚拟环境 | 不提交 |

只有 `README.md`、`制作流程.md` 和 `工具/` 里的代码进仓库；换一台机器时按下表重新获取数据。

### 准备环境

```bash
cd 学习资料制作
python3 -m venv .venv
.venv/bin/pip install -r 工具/requirements.txt
```

## 源数据（获取日期 2026-10-29）

| 位置（`1_源数据/` 下） | 内容 | 来源 | 论文中的用途 |
|---|---|---|---|
| `HSK词表/HSK-2012（分级词汇表 国家汉办-权威）.xls` | 新 HSK 词汇（2012 年修订版），一至六级共 5000 词，每个词标注等级 | 作者提供（原发布于汉考国际，论文脚注 39 的下载页现已 404） | 5.3.1 选词范围；5.3.4 搭配词限一至三级；5.3.2 标出四至六级词；5.3.5 练习干扰项 |
| `BCC词频/新HSK四级词汇词频排序（参照BCC语料库.xlsx` | 四级词按 BCC Global 词频降序（附录 A 的输出） | 作者论文写作时整理（论文脚注 3） | 5.3.1 选词：BCC 词频，权重 0.3 |
| `BCC词频/multi_domain_total_word_freq.zip` | BCC「多领域」词频总表（约 45 万词，`token,count`） | [BCC 语料库](https://bcc.blcu.edu.cn/)，下载接口 `https://bcc.blcu.edu.cn/api/datasets/multi_domain_total_word_freq.txt/download`（文件名是 .txt，实际是 zip） | 5.3.2 例句难度（附录 L）。Global 版已不在新版 BCC 的下载列表中，以此代替；两者四级词排名斯皮尔曼相关 0.91 |
| `教材语料/` | 13 本中级教材的课文（博雅汉语 4 本、成功之路 4 本、发展汉语 2 本、HSK 标准教程 3 本），约 14.7 万汉字 | 作者提供（论文脚注 4） | 5.3.1 教材词频，权重 0.7；5.3.2 例句来源；5.3.3 统计义项 |
| `搭配知识库/edu_collocation_data.xlsx` | 汉语分级阅读语料库（约 240 万词）抽取的搭配 25 万条，含类型、频次、互信息 | [中文搭配知识库](https://github.com/iris2hu/Chinese-collocation-complexity/tree/main/collocation_data)（胡韧奋课题组） | 5.3.4 搭配（附录 N） |
| `搭配知识库/wiki_collocation_data.txt.zip` | 中文维基百科（约 1.38 亿词）抽取的搭配 112 万条 | 同上 | 同上，补充教材库搭配太少的词 |
| `CC-CEDICT词典/cedict_1_0_ts_utf-8_mdbg.zip` | CC-CEDICT 汉英词典（CC BY-SA 4.0） | [MDBG](https://www.mdbg.net/chinese/dictionary?page=cc-cedict) | 5.3.3 义项、5.3.5 字词释义（论文用的 Pleco 内置免费词典就是它，脚注 15） |
| `HSK动态作文语料库/下载的语料/<词>.csv` | 含目标词的标注语料，每词一份 | [HSK 动态作文语料库](https://hsk.blcu.edu.cn/)，用作者账号按网页「下载」取回（第 2 步自动完成） | 5.3.1 易混淆词（附录 G） |
| `HSK动态作文语料库/登录令牌.txt` | 作者账号的登录令牌，约两周过期 | 已登录的语料库页面，控制台执行 `copy(localStorage.getItem('flutter.token'))` 后粘贴进来 | 第 2 步下载语料 |

大模型的 API Key 放在 `工具/deepseek_api_key.txt`（[DeepSeek 开放平台](https://platform.deepseek.com/) 的「API keys」页创建），同样不提交。

## 引用

- 搭配数据：胡韧奋, 肖航. 面向二语教学的汉语搭配知识库构建及其应用研究. 语言文字应用, 2019(1): 135-144。字段说明见知识库的 [collocation_data.md](https://github.com/iris2hu/Chinese-collocation-complexity/blob/main/collocation_data/collocation_data.md)，互信息以该文件的公式为准（论文原文公式有排版错误）。
- 词典：CC-CEDICT，CC BY-SA 4.0。

## 论文中其他资源的现状

- **中文搭配助手网站**：论文里的 `cca.xingtanlu.cn` 域名已被他人占用，变成不相关的网站，**不要再访问**。工具现在的地址是 [cca.irishu.cn](http://cca.irishu.cn/)；我们直接用上面的原始数据，不再逐词在网站上查询。
- **语料库在线拼音标注**（5.3.5）：`corpus.zhonghuayuwen.org` 已无法访问，改用 pypinyin 自动标注、大模型校对、作者审核。
- **谷歌翻译**（5.3.5）：改由大模型翻译、作者审核。
- **百度翻译发音**（5.3.5）：系统用浏览器语音合成朗读，不需要音频文件。
