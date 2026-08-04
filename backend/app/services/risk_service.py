"""
高风险问题识别服务

这个文件保存确定性的人工审核规则。虽然系统提示词会要求模型遇到投诉、赔偿、法律、隐私等问题时创建工单，但模型判断不是强约束，所以后端还需要一层规则兜底
存在的原因是：高风险客服问题必须工程化管控，不能完全交给大模型自由发挥
"""


# 高风险规则表：集中维护关键词、风险等级和进入人工审核的说明
HIGH_RISK_RULES = [
    {"keyword": "投诉", "risk_level": "high", "reason": "用户投诉需要人工审核"},
    {"keyword": "赔偿", "risk_level": "high", "reason": "赔偿不能由 AI 直接承诺"},
    {"keyword": "律师", "risk_level": "high", "reason": "法律风险需要人工处理"},
    {"keyword": "法律", "risk_level": "high", "reason": "法律风险需要人工处理"},
    {"keyword": "起诉", "risk_level": "high", "reason": "法律风险需要人工处理"},
    {"keyword": "隐私", "risk_level": "high", "reason": "隐私问题需要人工处理"},
    {"keyword": "泄露", "risk_level": "high", "reason": "隐私问题需要人工处理"},
    {"keyword": "举报", "risk_level": "high", "reason": "举报问题需要人工审核"},
    {"keyword": "账号被盗", "risk_level": "high", "reason": "账号安全问题需要人工核验"},
    {"keyword": "账号异常", "risk_level": "high", "reason": "账号异常需要人工核验"},
    {"keyword": "人工处理", "risk_level": "high", "reason": "用户明确要求人工处理"},
]


# 检测用户消息是否命中高风险规则，返回完整风险结果供 Agent 和工单使用
def detect_risk(message: str) -> dict:
    for rule in HIGH_RISK_RULES:
        if rule["keyword"] in message:
            return {
                "risk_level": rule["risk_level"],
                "reason": rule["reason"],
                "matched_keyword": rule["keyword"],
            }

    return {
        "risk_level": "normal",
        "reason": "",
        "matched_keyword": "",
    }
