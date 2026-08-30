"""情感识别 v1：中文情绪词典打分（-1 负面 ~ +1 正面）

实现：基于电商客服场景的情绪词典（NEGATIVE_WORDS / POSITIVE_WORDS），
统计命中次数后归一化到 [-1, 1]：
  score = (正面命中 - 负面命中) / (正面命中 + 负面命中)
label 阈值：score<-0.4 → negative；>0.4 → positive；否则 neutral

用途：
1. Supervisor 中，强负面情绪（negative）会自动升级转人工，
   避免用户情绪积压（"服务太差"即使没被意图识别为投诉也会转人工）
2. 后续可扩展为客服质检指标（情绪曲线、负面率）

升级路径：生产环境可替换为微调的情感分类模型（输出仍对齐 score/label）。
"""
import re

# 词典：覆盖电商客服场景
NEGATIVE_WORDS = [
    "生气", "愤怒", "投诉", "差评", "垃圾", "太差", "很差", "烂", "失望", "气死",
    "恶心", "糟糕", "不满", "不满意", "退款", "退货", "骗子", "欺诈", "坑", "被坑",
    "客服", "没人管", "不解决", "敷衍", "拖", "等太久", "着急", "急死", "烦", "讨厌",
    "恶心", "受伤", "难过", "哭", "伤心", "倒霉", "糟心", "离谱", "无语", "不能忍",
]
POSITIVE_WORDS = [
    "感谢", "谢谢", "满意", "很好", "不错", "喜欢", "棒", "赞", "好评", "开心",
    "舒服", "贴心", "耐心", "专业", "推荐", "支持", "认可", "给力", "完美", "放心",
]


def analyze_sentiment(text: str) -> dict:
    """情感打分

    返回：{score, label, negative, neg_hits, pos_hits}
    score：-1 ~ 1；negative=True 表示强负面（会触发转人工升级）
    """
    text = text or ""
    neg = sum(1 for w in NEGATIVE_WORDS if w in text)
    pos = sum(1 for w in POSITIVE_WORDS if w in text)
    total = neg + pos
    score = 0.0
    if total:
        score = round((pos - neg) / total, 2)
    label = "negative" if score < -0.4 else ("positive" if score > 0.4 else "neutral")
    return {
        "score": score,
        "label": label,
        "negative": label == "negative",
        "neg_hits": neg,
        "pos_hits": pos,
    }


def is_strong_negative(text: str) -> bool:
    return analyze_sentiment(text)["negative"]
