# 论文附录B：Python正则表达式匹配课文语料中的中文与中文标点（原样提取，仅作对照）

import re

for info in os.listdir('/Users/kangzhengwei/Desktop/课文语料/课文语料txt'):
    domain = os.path.abspath('/Users/kangzhengwei/Desktop/课文语料/课文语料txt')
    complete_path = os.path.join(domain, info)  #将路径与文件名结合起来就是每个文件的完整路径
    print(complete_path)
    information = open(complete_path, 'r')
    a = information.read()

    t1 = re.findall('[\u3002\uff1b\uff0c\uff1a\u201c\u201d\uff08\uff09\u3001\uff1f\u300a\u300b\u4e00-\u9fa5]',a)
    d = ''.join(t1)

    with open(complete_path[:-4] + 'new.txt', 'w') as f:
        f.write(d)
