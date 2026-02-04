"""
src/workflow/nodes.py

定义 LangGraph 的核心节点函数。
实现简单的 ReAct (Reasoning + Acting) 循环。
"""

import json
import logging
from typing import Dict, Any

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from src.state import AgentState
from src.tools.cypher_query import CypherQueryEngine
from llama_index.llms.openai_like import OpenAILike
import os


import re  # Added import

logger = logging.getLogger(__name__)

# 初始化工具
cypher_engine = CypherQueryEngine()

# 初始化 LLM (用于推理规划)
llm = OpenAILike(
    model=os.getenv("LLM_MODEL", "qwen/qwen3-14b"),
    api_base=os.getenv("OPENAI_API_BASE", "http://127.0.0.1:1234/v1"),
    api_key=os.getenv("OPENAI_API_KEY", "lm-studio"),
    is_chat_model=True,
    timeout=300.0,
    temperature=0.0,
)


def reasoning_node(state: AgentState) -> Dict[str, Any]:
    """
    推理节点：分析当前状态，决定下一步行动 (查图谱 or 结束)。
    由于本地模型 Function Calling 不稳定，这里使用严格的 JSON 格式提示工程。
    """
    messages = state["messages"]

    # 构建 Prompt
    system_prompt = (
        "You are a Semiconductor Industry Analyst Agent.\n"
        "You have access to a Knowledge Graph tool: `query_graph`.\n"
        "Input: A natural language question.\n"
        "Output: JSON\n\n"
        "--- Format ---\n"
        "If you need more info from the graph:\n"
        '{"action": "query_graph", "query": "YOUR_QUESTION_HERE"}\n\n'
        "If you have enough info to answer:\n"
        '{"action": "final_answer", "content": "YOUR_FINAL_ANSWER"}\n\n'
        "--- Constraints ---\n"
        "1. Output ONLY valid JSON.\n"
        "2. Do not explain your thought process outside the JSON.\n"
    )

    # 简单的将消息转换为文本上下文
    history_str = ""
    for m in messages:
        if isinstance(m, HumanMessage):
            history_str += f"User: {m.content}\n"
        elif isinstance(m, AIMessage):
            history_str += f"Assistant: {m.content}\n"
        elif isinstance(m, SystemMessage):
            # 这里的 SystemMessage 可能包含工具的返回结果
            history_str += f"Tool Output: {m.content}\n"

    prompt = f"{system_prompt}\n--- History ---\n{history_str}\nNext Step (JSON):"

    try:
        raw_response = llm.complete(prompt).text.strip()

        # 1. 移除 <think> 标签
        clean_response = re.sub(
            r"<think>.*?</think>", "", raw_response, flags=re.DOTALL
        )

        # 2. 提取 JSON 代码块
        if "```json" in clean_response:
            clean_response = clean_response.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_response:
            clean_response = clean_response.split("```")[1].split("```")[0].strip()

        clean_response = clean_response.strip()

        decision = json.loads(clean_response)
        return {"messages": [AIMessage(content=json.dumps(decision))]}
    except Exception as e:
        # Capture raw_response if available, otherwise use "Unknown"
        err_raw = locals().get("raw_response", "Unknown")
        logger.error(f"Reasoning failed: {e}. Raw: {err_raw}")
        # 回退策略
        return {
            "messages": [
                AIMessage(
                    content=json.dumps(
                        {
                            "action": "final_answer",
                            "content": f"Error parsing intent: {err_raw}",
                        }
                    )
                )
            ]
        }


def tool_execution_node(state: AgentState) -> Dict[str, Any]:
    """
    执行节点：解析上一步的 JSON 并执行工具。
    """
    last_message = state["messages"][-1]

    # Check if the last message is an AIMessage with tool calls
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        # Handle native tool calls if we switch to that later
        pass

    # Fallback to JSON parsing for our current implementation
    try:
        content = last_message.content
        if isinstance(content, str):
            decision = json.loads(content)
        else:
            # Handle list content if necessary, or just extract text
            # Assuming simple string content for now
            decision = json.loads(str(content))

        action = decision.get("action")

        if action == "query_graph":
            query = decision.get("query")
            logger.info(f"Executing Tool: query_graph('{query}')")
            result = cypher_engine.run(query)
            return {
                "messages": [SystemMessage(content=f"Graph Search Result: {result}")]
            }

        elif action == "final_answer":
            # 这是一个结束信号，通常不应该进入这个节点，
            # 但如果 LangGraph 路由配置有误，这里可以作为安全网
            return {}

        return {"messages": [SystemMessage(content=f"Unknown action: {action}")]}

    except Exception as e:
        return {"messages": [SystemMessage(content=f"Tool execution failed: {e}")]}
