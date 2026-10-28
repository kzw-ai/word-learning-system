# 论文附录C：合并教材语料（原样提取，仅作对照）

# 字符串添加
total_corpus = ''
import re
for info in os.listdir('/Users/kangzhengwei/Desktop/课文语料/无空格的语料'):
    domain = os.path.abspath('/Users/kangzhengwei/Desktop/课文语料/无空格的语料')
    complete_path = os.path.join(domain, info)  #将路径与文件名结合起来就是每个文件的完整路径
    print(complete_path)
    information = open(complete_path, 'r')
    a = information.read()
    
    total_corpus += a
with open('/Users/kangzhengwei/Desktop/课文语料/所有的中级教材语料', 'w') as f:
        f.write(total_corpus)
