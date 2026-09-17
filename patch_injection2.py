# 补充英文 disregard 模式的英文宾语
p = 'app/agents/injection_guard.py'
s = open(p, encoding='utf-8').read()
old = '    r"(disregard|override).{0,8}(之前|以上|上述|所有|一切|规则|约束|指令)",'
new = ('    r"(disregard|override).{0,8}(之前|以上|上述|所有|一切|规则|约束|指令)",\n'
       '    r"disregard.{0,12}(all\\s+)?(rules|instructions|prompts|constraints)",')
assert old in s
open(p, 'w', encoding='utf-8', newline='\n').write(s.replace(old, new, 1))
print('ok')
