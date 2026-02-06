"""
src/workflow/debate.py

多代理辩论模块：包含辩论节点和基于 AutoGen 的真实多代理对抗。
"""

import json
import logging
import re
import os
from typing import Dict, Any, List, Optional

import autogen
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from llama_index.llms.openai_like import OpenAILike

from src.state import AgentState

logger = logging.getLogger(__name__)

# AutoGen 配置
AUTOGEN_LLM_CONFIG = {
    "config_list": [
        {
            "model": os.getenv("LLM_MODEL", "qwen/qwen3-14b"),
            "base_url": os.getenv("OPENAI_API_BASE", "http://127.0.0.1:1234/v1"),
            "api_key": os.getenv("OPENAI_API_KEY", "lm-studio"),
        }
    ],
    "cache_seed": 42,
    "temperature": 0.7,
}


def run_autogen_debate(question: str, context: str) -> Dict[str, Any]:
    """
    运行完整的 AutoGen 多代理辩论
    """
    from src.agents.debate_agents import (
        BULLISH_SYSTEM_MESSAGE,
        BEARISH_SYSTEM_MESSAGE,
        JUDGE_SYSTEM_MESSAGE,
    )

    logger.info("[AutoGen] Initializing debate agents...")

    # 1. 定义 Agents
    bullish_analyst = autogen.AssistantAgent(
        name="BullishAnalyst",
        system_message=BULLISH_SYSTEM_MESSAGE,
        llm_config=AUTOGEN_LLM_CONFIG,
    )

    bearish_analyst = autogen.AssistantAgent(
        name="BearishAnalyst",
        system_message=BEARISH_SYSTEM_MESSAGE,
        llm_config=AUTOGEN_LLM_CONFIG,
    )

    judge = autogen.AssistantAgent(
        name="JudgeAgent",
        system_message=JUDGE_SYSTEM_MESSAGE,
        llm_config=AUTOGEN_LLM_CONFIG,
    )

    user_proxy = autogen.UserProxyAgent(
        name="UserProxy",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=3,
        is_termination_msg=lambda x: "TERMINATE" in (x.get("content") or ""),
        code_execution_config=False,
    )

    # 2. 组建 GroupChat
    groupchat = autogen.GroupChat(
        agents=[user_proxy, bullish_analyst, bearish_analyst, judge],
        messages=[],
        max_round=6,
        speaker_selection_method="round_robin",
    )

    manager = autogen.GroupChatManager(
        groupchat=groupchat, llm_config=AUTOGEN_LLM_CONFIG
    )

    # 3. 开始辩论
    debate_topic = f"Topic: {question}\n\nBackground Context: {context}\n\nPlease analyze this topic from your respective perspectives. Judge, provide the final structured JSON scores after everyone has spoken."

    logger.info("[AutoGen] Starting Group Chat...")
    user_proxy.initiate_chat(manager, message=debate_topic)

    # 4. 提取结果
    debate_transcript = {}
    last_json = None

    for i, msg in enumerate(groupchat.messages):
        sender = msg.get("name", "Unknown")
        content = msg.get("content", "")
        debate_transcript[f"step_{i}_{sender}"] = content

        if sender == "JudgeAgent":
            try:
                clean_msg = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
                if "```json" in clean_msg:
                    clean_msg = clean_msg.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_msg:
                    clean_msg = clean_msg.split("```")[1].split("```")[0].strip()

                potential_json = json.loads(clean_msg.strip())
                if "bull_score" in potential_json:
                    last_json = potential_json
            except:
                continue

    if not last_json:
        # 回退逻辑
        logger.warning("[AutoGen] Judge failed to provide JSON, using default scores.")
        last_json = {
            "bull_score": 50,
            "bear_score": 50,
            "final_score": 50,
            "confidence": "low",
            "key_bull_points": ["分析未完成"],
            "key_bear_points": ["风险评估未完成"],
            "risk_level": "medium",
            "recommendation": "Hold",
        }

    return {
        "debate_transcript": debate_transcript,
        "scores": {
            "bull_score": last_json.get("bull_score", 50),
            "bear_score": last_json.get("bear_score", 50),
            "final_score": last_json.get("final_score", 50),
            "confidence": last_json.get("confidence", "medium"),
        },
        "key_points": {
            "bull": last_json.get("key_bull_points", []),
            "bear": last_json.get("key_bear_points", []),
        },
        "assessment": {
            "risk_level": last_json.get("risk_level", "medium"),
            "recommendation": last_json.get("recommendation", "Hold"),
        },
    }


def debate_node(state: AgentState) -> Dict[str, Any]:
    """
    辩论执行节点：调用 AutoGen 进行多代理对抗。
    """
    logger.info("[Debate Node] Starting multi-agent debate with AutoGen...")

    messages = state.get("messages", [])

    # 提取用户问题
    user_question = None
    for msg in messages:
        if isinstance(msg, HumanMessage):
            user_question = msg.content
            break

    # 提取最终答案或上下文作为背景
    final_answer = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            try:
                content = msg.content
                if not isinstance(content, str):
                    content = str(content)
                clean_content = re.sub(
                    r"<think>.*?</think>", "", content, flags=re.DOTALL
                )
                decision = json.loads(clean_content)
                if decision.get("action") == "final_answer":
                    final_answer = decision.get("content")
                    break
            except:
                pass

    context_parts = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            if "Search Result:" in msg.content:
                context_parts.append(msg.content)

    context = (
        "\n\n".join(context_parts[-3:])
        if context_parts
        else "No specific search context."
    )
    background = final_answer if final_answer else context

    try:
        debate_result = run_autogen_debate(user_question or "未知问题", background)
    except Exception as e:
        logger.error(f"[Debate Node] AutoGen debate failed: {e}")
        debate_result = {
            "debate_transcript": {"error": str(e)},
            "scores": {
                "bull_score": 50,
                "bear_score": 50,
                "final_score": 50,
                "confidence": "low",
            },
            "key_points": {"bull": ["辩论执行失败"], "bear": ["辩论执行失败"]},
            "assessment": {"risk_level": "medium", "recommendation": "Hold"},
        }

    final_report = generate_final_report(
        question=user_question,
        base_answer=background,
        debate_result=debate_result,
    )

    return {
        "debate_transcript": debate_result.get("debate_transcript", {}),
        "debate_scores": debate_result.get("scores", {}),
        "debate_key_points": debate_result.get("key_points", {}),
        "debate_assessment": debate_result.get("assessment", {}),
        "final_report": final_report,
    }


def generate_final_report(
    question: Any,
    base_answer: Any,
    debate_result: Dict[str, Any],
) -> str:
    """
    生成最终研判报告
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

    report_lines = [
        "# 半导体行业研判报告",
        "",
        "## 一、问题回顾",
        f"**用户问题：** {question}",
        "",
        "## 二、基础分析",
        f"{base_answer}",
        "",
        "## 三、多代理辩论评分 (via AutoGen)",
        "",
        f"### 🟢 看多方观点 (得分: {bull_score}/100)",
    ]

    for i, point in enumerate(key_points.get("bull", [])[:5], 1):
        report_lines.append(f"{i}. {point}")

    report_lines.append("")
    report_lines.append(f"### 🔴 看空方观点 (得分: {bear_score}/100)")
    for i, point in enumerate(key_points.get("bear", [])[:5], 1):
        report_lines.append(f"{i}. {point}")

    report_lines.extend(
        [
            "",
            f"### 📊 综合评分: {final_score}/100",
            f"- **置信度:** {str(confidence).upper()}",
            f"- **风险等级:** {str(risk_level).upper()}",
            f"- **综合建议:** {recommendation}",
            "",
            "## 四、结论",
        ]
    )

    if final_score >= 70:
        report_lines.append("综合来看，公司基本面良好，技术领先，建议积极关注。")
    elif final_score >= 50:
        report_lines.append("综合来看，公司有一定优势但也存在风险，建议谨慎观望。")
    else:
        report_lines.append("综合来看，公司面临较大不确定性，建议回避或减持。")

    return "\n".join(report_lines)
