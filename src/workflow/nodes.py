"""
src/workflow/nodes.py

定义 LangGraph 的核心节点函数。
实现简单的 ReAct (Reasoning + Acting) 循环。
"""

import json
import logging
import os
import re
from typing import Dict, Any, cast

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from src.state import AgentState
from src.tools.cypher_query import CypherQueryEngine
from llama_index.llms.openai_like import OpenAILike

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
    推理节点：分析当前状态，决定下一步行动 (查图谱 or 查网络 or 结束)。

    由于本地模型 Function Calling 不稳定，这里使用严格的 JSON 格式提示工程。
    """
    messages = state["messages"]

    # 构建 Prompt
    system_prompt = (
        "You are a Semiconductor Industry Analyst Agent.\n"
        "You have access to TWO tools:\n"
        "1. `query_graph` - Query the Knowledge Graph for entities and relationships\n"
        "2. `web_search` - Search the web for real-time information\n\n"
        "--- Decision Rules ---\n"
        "- Use `query_graph` for: relationships between companies, technologies, supply chain info\n"
        "- Use `web_search` for: founding dates, HQ locations, current news, recent events\n"
        "- Use `final_answer` when you have collected sufficient information\n\n"
        "--- Format ---\n"
        "If you need more info from the knowledge graph:\n"
        '{"action": "query_graph", "query": "YOUR_QUESTION_HERE"}\n\n'
        "If you need real-time info from the web:\n"
        '{"action": "web_search", "query": "YOUR_QUESTION_HERE"}\n\n'
        "If you have enough info to answer:\n"
        '{"action": "final_answer", "content": "YOUR_FINAL_ANSWER", "requires_debate": true/false, "confidence": 0.0-1.0}\n\n'
        "--- Constraints ---\n"
        "1. Output ONLY valid JSON.\n"
        "2. Do not explain your thought process outside the JSON.\n"
        "3. Set `requires_debate` to true for investment advice, competitive analysis, or complex industry trends. Set to false for simple facts (founding dates, HQs, single metrics).\n"
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

        decision = json.loads(cast(str, clean_response))
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

    支持的工具：
    - query_graph: 查询知识图谱 (Neo4j)
    - web_search: 网络搜索 (DuckDuckGo via MCP)
    """
    from src.tools.web_search import web_search_tool

    last_message = state["messages"][-1]

    # Fallback to JSON parsing for our current implementation
    try:
        content = last_message.content
        if not isinstance(content, str):
            content = str(content)

        decision = json.loads(cast(str, content))
        action = decision.get("action")

        if action == "query_graph":
            query = decision.get("query")
            logger.info(f"Executing Tool: query_graph('{query}')")
            result = cypher_engine.run(query)
            return {
                "messages": [SystemMessage(content=f"Graph Search Result: {result}")]
            }

        elif action == "web_search":
            query = decision.get("query")
            logger.info(f"Executing Tool: web_search('{query}')")
            result = web_search_tool.search_web(query)
            return {"messages": [SystemMessage(content=f"Web Search Result: {result}")]}

        elif action == "final_answer":
            return {}

        return {"messages": [SystemMessage(content=f"Unknown action: {action}")]}

    except Exception as e:
        return {"messages": [SystemMessage(content=f"Tool execution failed: {e}")]}


def reflection_node(state: AgentState) -> Dict[str, Any]:
    """
    自检节点：评估当前答案质量，决定是否需要重新推理。

    检查项：
    1. 工具调用结果是否有效（非空、非错误）
    2. 答案是否完整（是否回答了用户的核心问题）
    3. 是否达到最大反思次数
    """
    messages = state["messages"]
    reflection_count = state.get("reflection_count", 0)
    max_reflections = state.get("max_reflections", 2)

    logger.info(f"🔍 Reflection Node: Count={reflection_count}/{max_reflections}")

    # 提取用户问题和最终答案
    user_question = None
    final_answer = None

    for msg in messages:
        if isinstance(msg, HumanMessage) and not user_question:
            user_question = msg.content

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

    if not final_answer:
        logger.warning("⚠️ Reflection: No final answer found, skipping reflection.")
        return {
            "messages": [
                SystemMessage(content="Reflection skipped: No answer to evaluate.")
            ]
        }

    # 如果已达到最大反思次数，直接通过
    if reflection_count >= max_reflections:
        logger.info(
            f"✅ Reflection: Max reflections reached ({max_reflections}), passing."
        )
        return {
            "messages": [
                SystemMessage(
                    content=f"✅ Reflection PASSED: Maximum reflection limit reached."
                )
            ],
            "reflection_count": reflection_count + 1,
        }

    # 构建反思 Prompt
    prompt = (
        "You are a Quality Assurance Agent for semiconductor industry analysis.\n"
        "Evaluate the following answer based on what's AVAILABLE IN THE KNOWLEDGE GRAPH.\n\n"
        f"User Question: {user_question}\n\n"
        f"Answer: {final_answer}\n\n"
        "Evaluation Criteria (IMPORTANT):\n"
        "1. Does the answer address the user's question using available knowledge graph data?\n"
        "2. If the knowledge graph lacks certain information (e.g., founding year, HQ location), "
        "the answer should state limitations rather than invent information.\n"
        "3. Is the answer specific given the AVAILABLE data (not generic)?\n"
        "4. Does it cite concrete entities/technologies that exist in the graph?\n\n"
        "Scoring Rules:\n"
        "- PASS if the answer uses available graph data and acknowledges limitations honestly\n"
        "- FAIL only if the answer is generic, off-topic, or makes unverifiable claims\n\n"
        "Respond with JSON ONLY:\n"
        '{"pass": true, "reason": "explanation"} if acceptable\n'
        '{"pass": false, "reason": "specific issue"} if needs improvement\n\n'
        "Output JSON:"
    )

    try:
        raw_response = llm.complete(prompt).text.strip()
        logger.info(f"Reflection LLM response: {raw_response[:200]}...")

        # 清洗响应
        clean_response = re.sub(
            r"<think>.*?</think>", "", raw_response, flags=re.DOTALL
        )

        # 提取 JSON
        if "```json" in clean_response:
            clean_response = clean_response.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_response:
            clean_response = clean_response.split("```")[1].split("```")[0].strip()

        clean_response = clean_response.strip()
        reflection = json.loads(cast(str, clean_response))

        passed = reflection.get("pass", False)
        reason = reflection.get("reason", "No reason provided")

        if passed:
            logger.info(f"✅ Reflection PASSED: {reason}")
            return {
                "messages": [SystemMessage(content=f"✅ Reflection PASSED: {reason}")],
                "reflection_count": reflection_count + 1,
            }
        else:
            logger.warning(
                f"🔄 Reflection FAILED: {reason}. Requesting re-reasoning..."
            )
            return {
                "messages": [
                    SystemMessage(
                        content=f"🔄 Reflection FAILED: {reason}. Please provide a more specific answer based on knowledge graph data."
                    )
                ],
                "reflection_count": reflection_count + 1,
                "error": reason,
            }

    except Exception as e:
        logger.error(f"❌ Reflection check failed: {e}. Defaulting to PASS.")
        return {
            "messages": [
                SystemMessage(
                    content=f"⚠️ Reflection check error: {e}. Proceeding with answer."
                )
            ],
            "reflection_count": reflection_count + 1,
        }
