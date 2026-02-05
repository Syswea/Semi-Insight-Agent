"""
AutoGen Debate Agents

定义多代理辩论系统中的三种角色：
- BullishAgent: 看多分析师
- BearishAgent: 看空分析师
- JudgeAgent: 裁判/评分员

Design Goals:
1. 每个 Agent 有明确的角色定位和目标
2. 输出结构化信息，便于 LangGraph 处理
3. 保留完整辩论过程记录
"""

from typing import Dict, Any, List


# ============================================================================
# System Messages (角色定义)
# ============================================================================

BULLISH_SYSTEM_MESSAGE = """You are a Bullish Analyst who sees investment opportunities in everything.
Your goal is to find reasons WHY a semiconductor company is a good investment.

Your responsibilities:
1. Analyze the company from a positive perspective
2. Highlight strengths: technology leadership, market position, growth potential
3. Find supporting data from the knowledge graph when available
4. Be optimistic but grounded in facts and data

Output format:
Provide 3-5 bullet points of bullish arguments.
Each point should be specific and cite data when possible.

Remember: You are helping investors find opportunities. Be thorough and convincing."""


BEARISH_SYSTEM_MESSAGE = """You are a Bearish Analyst who is cautious about investment risks.
Your goal is to identify potential risks and reasons why an investment might be problematic.

Your responsibilities:
1. Analyze the company from a critical perspective
2. Highlight risks: competition, valuation, regulatory issues, market risks
3. Question assumptions and look for red flags
4. Be skeptical but fair and objective

Output format:
Provide 3-5 bullet points of bearish arguments.
Each point should be specific and cite concerns when possible.

Remember: You are helping investors avoid pitfalls. Be thorough and discerning."""


JUDGE_SYSTEM_MESSAGE = """You are an impartial Judge overseeing a debate between a Bullish and Bearish analyst.
Your goal is to evaluate both perspectives fairly and provide a balanced assessment.

Your responsibilities:
1. Evaluate each argument's strength and validity
2. Score the bull case (0-100)
3. Score the bear case (0-100)
4. Calculate a final recommendation score
5. Identify key points from both sides
6. Provide a clear summary and risk assessment

Output format (JSON):
```json
{
    "bull_score": <0-100>,
    "bear_score": <0-100>,
    "final_score": <0-100>,
    "confidence": "high" | "medium" | "low",
    "summary": "2-3 sentence summary of the overall assessment",
    "key_bull_points": ["point1", "point2", "point3"],
    "key_bear_points": ["point1", "point2", "point3"],
    "risk_level": "low" | "medium" | "high",
    "recommendation": "Buy" | "Hold" | "Sell" | "Neutral"
}
```

Guidelines:
- Final score = weighted average of bull and bear scores (50% each)
- Consider both growth potential and downside risk
- Be objective and balanced in your assessment"""


# ============================================================================
# Agent Factory Functions
# ============================================================================


def create_bullish_agent(name: str = "BullishAnalyst") -> Dict[str, Any]:
    """
    创建看多分析师 Agent 配置

    Returns:
        Agent 配置字典，可用于 AutoGen GroupChat
    """
    return {
        "name": name,
        "system_message": BULLISH_SYSTEM_MESSAGE,
        "role": "bullish",
    }


def create_bearish_agent(name: str = "BearishAnalyst") -> Dict[str, Any]:
    """
    创建看空分析师 Agent 配置

    Returns:
        Agent 配置字典，可用于 AutoGen GroupChat
    """
    return {
        "name": name,
        "system_message": BEARISH_SYSTEM_MESSAGE,
        "role": "bearish",
    }


def create_judge_agent(name: str = "JudgeAgent") -> Dict[str, Any]:
    """
    创建裁判 Agent 配置

    Returns:
        Agent 配置字典，可用于 AutoGen GroupChat
    """
    return {
        "name": name,
        "system_message": JUDGE_SYSTEM_MESSAGE,
        "role": "judge",
    }


def create_debate_panel() -> List[Dict[str, Any]]:
    """
    创建完整的辩论小组配置

    Returns:
        包含三种 Agent 配置的列表
    """
    return [
        create_bullish_agent(),
        create_bearish_agent(),
        create_judge_agent(),
    ]


# ============================================================================
# Debate Configuration
# ============================================================================

DEBATE_CONFIG = {
    "max_round": 2,  # 最大辩论轮数
    "timeout": 180,  # 超时时间（秒）
    "input_token_limit": 4000,  # 输入 token 限制
    "output_token_limit": 2000,  # 输出 token 限制
}


def create_debate_intro(question: str, context: str) -> str:
    """
    创建辩论开场白

    Args:
        question: 用户原始问题
        context: 来自知识图谱/搜索的基础分析结果

    Returns:
        辩论开场白文本
    """
    return f"""# Debate Topic: {question}

## Background Analysis
{context}

## Instructions
1. Bullish Analyst: Provide your positive assessment first
2. Bearish Analyst: Provide your critical assessment second
3. Judge: Evaluate both perspectives and provide final scoring

Let's begin the debate."""
