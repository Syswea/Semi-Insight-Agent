"""
src/workflow/debate.py

多代理辩论模块：包含辩论节点和路由器

Components:
1. debate_router: 路由判断节点
2. debate_node: AutoGen 多代理辩论节点

Design:
- 路由节点保留扩展性，可添加条件分支
- 辩论节点使用 AutoGen 实现评分式辩论
"""

import json
import logging
from typing import Dict, Any, List, Optional

from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain_core.messages.utils import convert_to_messages

from src.state import AgentState
from src.agents.debate_agents import (
    create_debate_panel,
    create_debate_intro,
    DEBATE_CONFIG,
)
from llama_index.llms.openai_like import OpenAILike
import os

logger = logging.getLogger(__name__)

# 初始化辩论 LLM (独立配置)
debate_llm = OpenAILike(
    model=os.getenv("LLM_MODEL", "qwen/qwen3-14b"),
    api_base=os.getenv("OPENAI_API_BASE", "http://127.0.0.1:1234/v1"),
    api_key=os.getenv("OPENAI_API_KEY", "lm-studio"),
    is_chat_model=True,
    timeout=300.0,
    temperature=0.7,  # 辩论需要一定创造性
)


def debate_router(state: AgentState) -> str:
    """
    辩论路由节点

    功能：
    1. 接收 Reflection 结果
    2. 判断下一步流向
    3. 支持扩展其他分支（未来可添加条件路由）

    当前策略：
    - 总是路由到辩论节点（无条件）
    - 保留扩展性，可添加：
        * high_confidence → 直接输出
        * investment_question → 辩论
        * risk_assessment → 辩论

    Args:
        state: AgentState

    Returns:
        下一个节点名称
    """
    logger.info("[Debate Router] Evaluating next step...")

    messages = state.get("messages", [])
    reflection_count = state.get("reflection_count", 0)

    # 获取用户问题
    user_question = None
    for msg in messages:
        if isinstance(msg, HumanMessage):
            user_question = msg.content
            break

    # 获取 Reflection 结果
    reflection_passed = False
    for msg in reversed(messages):
        if isinstance(msg, SystemMessage) and "PASSED" in msg.content:
            reflection_passed = True
            break

    logger.info(
        f"[Debate Router] Question: {user_question[:50] if user_question else 'N/A'}..."
    )
    logger.info(f"[Debate Router] Reflection passed: {reflection_passed}")
    logger.info(f"[Debate Router] Reflection count: {reflection_count}")

    # =========================================================================
    # 路由策略（可扩展）
    # =========================================================================
    # 当前策略：总是进入辩论
    # 未来可添加：
    #   - if confidence > 0.9: return "final_answer"  # 高置信度直接输出
    #   - if is_investment_question: return "debate"  # 投资问题进入辩论
    #   - if user_pref == "quick": return "final_answer"  # 用户偏好快速回答

    logger.info("[Debate Router] Routing to: debate (always route for demo)")

    return "debate"


def debate_node(state: AgentState) -> Dict[str, Any]:
    """
    辩论执行节点

    功能：
    1. 收集基础分析上下文
    2. 初始化 AutoGen 辩论
    3. 执行辩论流程
    4. 提取评分和辩论记录
    5. 更新 State

    辩论流程：
    1. Bullish 分析 → 2. Bearish 分析 → 3. Judge 评分

    Args:
        state: AgentState

    Returns:
        更新后的 State 字典
    """
    logger.info("[Debate Node] Starting multi-agent debate...")

    messages = state.get("messages", [])

    # 提取用户问题
    user_question = None
    for msg in messages:
        if isinstance(msg, HumanMessage):
            user_question = msg.content
            break

    # 提取基础分析结果
    context_parts = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            content = msg.content
            if "Search Result:" in content or "Answer" in content:
                context_parts.append(content)

    context = (
        "\n\n".join(context_parts[-5:]) if context_parts else "No additional context."
    )

    # 提取最终答案（如果有）
    final_answer = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            try:
                decision = json.loads(msg.content)
                if decision.get("action") == "final_answer":
                    final_answer = decision.get("content")
                    break
            except:
                pass

    logger.info(
        f"[Debate Node] Question: {user_question[:100] if user_question else 'N/A'}..."
    )
    logger.info(f"[Debate Node] Context length: {len(context)} chars")

    # =========================================================================
    # 简化的辩论流程（不使用完整 AutoGen，降低复杂度）
    # =========================================================================
    # 使用 LLM 模拟辩论过程，输出结构化结果

    debate_prompt = f"""You are facilitating a debate between a Bullish and Bearish analyst about a semiconductor company.

Question: {user_question}

Background Analysis:
{final_answer or context}

## Debate Instructions

Round 1 - Initial Arguments:
1. Write the Bullish Analyst's perspective (3-5 key points, optimistic but grounded)
2. Write the Bearish Analyst's perspective (3-5 key points, critical but fair)

Round 2 - Final Statements:
1. Bullish Analyst's final statement (incorporate counter-arguments if any)
2. Bearish Analyst's final statement (incorporate counter-arguments if any)

Judge's Verdict:
Evaluate both perspectives and provide:
- Bull score (0-100): How convincing are the bullish arguments?
- Bear score (0-100): How valid are the bearish concerns?
- Final score (0-100): Weighted average (50% bull, 50% bear)
- Confidence level: high/medium/low
- Key bull points: top 3 arguments from bull side
- Key bear points: top 3 arguments from bear side
- Risk level: low/medium/high
- Recommendation: Buy/Hold/Sell/Neutral

Output format (JSON only):
```json
{{
    "debate_transcript": {{
        "round_1": {{
            "bullish": "Full bullish argument...",
            "bearish": "Full bearish argument..."
        }},
        "round_2": {{
            "bullish": "Final bullish statement...",
            "bearish": "Final bearish statement..."
        }}
    }},
    "scores": {{
        "bull_score": <0-100>,
        "bear_score": <0-100>,
        "final_score": <0-100>,
        "confidence": "high" | "medium" | "low"
    }},
    "key_points": {{
        "bull": ["point1", "point2", "point3"],
        "bear": ["point1", "point2", "point3"]
    }},
    "assessment": {{
        "risk_level": "low" | "medium" | "high",
        "recommendation": "Buy" | "Hold" | "Sell" | "Neutral"
    }}
}}
```

Respond with ONLY valid JSON."""

    try:
        logger.info("[Debate Node] Running debate simulation...")
        raw_response = debate_llm.complete(debate_prompt).text.strip()

        # 清洗响应
        clean_response = raw_response
        if "```json" in clean_response:
            clean_response = clean_response.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_response:
            clean_response = clean_response.split("```")[1].split("```")[0].strip()

        clean_response = clean_response.strip()
        debate_result = json.loads(clean_response)

        logger.info(
            f"[Debate Node] Debate completed. Final score: {debate_result.get('scores', {}).get('final_score', 'N/A')}"
        )

    except Exception as e:
        logger.error(f"[Debate Node] Debate failed: {e}")
        # 回退到基础结果
        debate_result = {
            "debate_transcript": {
                "round_1": {
                    "bullish": "Debate simulation unavailable.",
                    "bearish": "Debate simulation unavailable.",
                },
                "round_2": {
                    "bullish": "Using fallback assessment.",
                    "bearish": "Using fallback assessment.",
                },
            },
            "scores": {
                "bull_score": 50,
                "bear_score": 50,
                "final_score": 50,
                "confidence": "low",
            },
            "key_points": {
                "bull": ["Unable to analyze"],
                "bear": ["Unable to analyze"],
            },
            "assessment": {"risk_level": "medium", "recommendation": "Neutral"},
        }

    # =========================================================================
    # 生成最终报告
    # =========================================================================

    final_report = generate_final_report(
        question=user_question,
        base_answer=final_answer or context,
        debate_result=debate_result,
    )

    # =========================================================================
    # 更新 State
    # =========================================================================

    return {
        "messages": [
            SystemMessage(
                content=json.dumps(
                    {
                        "action": "debate_complete",
                        "debate_transcript": debate_result.get("debate_transcript", {}),
                        "scores": debate_result.get("scores", {}),
                        "key_points": debate_result.get("key_points", {}),
                        "assessment": debate_result.get("assessment", {}),
                    }
                )
            )
        ],
        "debate_transcript": debate_result.get("debate_transcript", {}),
        "debate_scores": debate_result.get("scores", {}),
        "debate_key_points": debate_result.get("key_points", {}),
        "debate_assessment": debate_result.get("assessment", {}),
        "final_report": final_report,
    }


def generate_final_report(
    question: str,
    base_answer: str,
    debate_result: Dict[str, Any],
) -> str:
    """
    生成最终研判报告

    Args:
        question: 用户问题
        base_answer: 基础分析答案
        debate_result: 辩论结果

    Returns:
        格式化的最终报告
    """
    scores = debate_result.get("scores", {})
    key_points = debate_result.get("key_points", {})
    assessment = debate_result.get("assessment", {})

    bull_score = scores.get("bull_score", 50)
    bear_score = scores.get("bear_score", 50)
    final_score = scores.get("final_score", 50)
    confidence = scores.get("confidence", "medium")
    recommendation = assessment.get("recommendation", "Neutral")
    risk_level = assessment.get("risk_level", "medium")

    # 生成报告
    report = f"""# 半导体行业研判报告

## 一、问题回顾
**用户问题：** {question}

## 二、基础分析
{base_answer}

## 三、多代理辩论评分

### 🟢 看多方观点 (得分: {bull_score}/100)
"""

    for i, point in enumerate(key_points.get("bull", [])[:5], 1):
        report += f"{i}. {point}\n"

    report += f"""

### 🔴 看空方观点 (得分: {bear_score}/100)
"""

    for i, point in enumerate(key_points.get("bear", [])[:5], 1):
        report += f"{i}. {point}\n"

    report += f"""

### 📊 综合评分: {final_score}/100
- **置信度:** {confidence.upper()}
- **风险等级:** {risk_level.upper()}
- **综合建议:** {recommendation}

## 四、结论
"""

    # 根据最终分数生成结论
    if final_score >= 70:
        report += "综合来看，公司基本面良好，技术领先，建议积极关注。"
    elif final_score >= 50:
        report += "综合来看，公司有一定优势但也存在风险，建议谨慎观望。"
    else:
        report += "综合来看，公司面临较大不确定性，建议回避或减持。"

    return report


def extract_legacy_answer(state: AgentState) -> str:
    """提取最终答案（兼容旧代码）"""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            try:
                decision = json.loads(msg.content)
                if decision.get("action") == "final_answer":
                    return decision.get("content", "")
            except:
                pass
    return ""
