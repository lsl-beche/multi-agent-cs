# 扩充注入特征库(覆盖评测漏报的 8 类攻击)
p = 'app/agents/injection_guard.py'
lines = open(p, encoding='utf-8').read().splitlines()

start = next(i for i, l in enumerate(lines) if '_PATTERNS = [' in l)
end = next(i for i, l in enumerate(lines) if 'looks_like_injection' in l)
# 收缩到 looks_like_injection 之前最后一个 ']' 行
block_end = max(i for i in range(start, end) if lines[i].strip() == ']')

new_block = """_PATTERNS = [
    # 指令覆盖类
    r"忽略.{0,8}(之前|以上|上面|前面|所有|全部|一切|规则|指令|提示|设定|约束|要求)",
    r"(无视|disregard|override).{0,8}(之前|以上|上述|所有|一切|规则|约束|指令)",
    r"(上面|以上|之前).{0,6}(的一切|内容|设定|规则|指令|要求)?(都|全部)?(作废|失效|不算数|无效)",
    r"(忘记|丢弃|清除|忘掉).{0,6}(你的)?(身份|设定|指令|角色|限制)",
    r"(无条件服从|听我的命令|只听我的|一切.{0,4}作废|全部作废)",
    # 角色覆盖类
    r"(你现在是|从现在开始你是|现在你是|假装你是|假装你是一个|扮演一个?|you are now a|pretend to be a).{0,12}(DAN|无限制|不受限|没有道德|没有内容政策|unrestricted|jailbroken)",
    r"(扮演|充当|假装).{0,8}(DAN|越狱|无限制|不受限)",
    r"越狱(这个|该)?(AI|机器人|模型|系统|助手)",
    r"(you are|act as).{0,10}(DAN|unrestricted|jailbroken)",
    r"(没有|无视|不受|无).{0,6}(内容政策|道德约束|道德限制|任何限制)",
    r"(开发者模式|developer\\s+mode|维护模式并执行)",
    r"\\b(jailbreak|DAN\\s*mode)\\b",
    # 提示词探测类
    r"(系统提示词|system\\s*prompt|初始指令|系统指令)",
    r"(输出|打印|显示|透露|泄露|重复|逐字|告诉我|念出).{0,10}(你的)?(系统提示|初始指令|系统指令|prompt)",
    r"ignore.{0,12}(previous|prior|above|all).{0,12}(instruction|rule|prompt)",
]"""

lines[start:block_end + 1] = new_block.splitlines()
open(p, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
print('特征库已扩充: %d 行' % (block_end + 1 - start))
