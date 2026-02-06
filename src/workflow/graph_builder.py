"""
src/workflow/graph_builder.py

构建 LangGraph 状态机。
定义节点流转逻辑：
- 基础流程：Start -> Reasoning -> Tool -> Reflection -> Debate -> END
- 支持条件路由扩展

Architecture:
    User -> Reasoning -> (query_graph/web_search) -> Tool -> Reflection -> Debate -> END
"""

import json
import logging
import re
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage

from src.state import AgentState
from src.workflow.nodes import reasoning_node, tool_execution_node, reflection_node
from src.workflow.debate import debate_node

logger = logging.getLogger(__name__)


def router(state: AgentState) -> str:
    """
    路由函数：根据 Reasoning 节点的输出决定下一步。
    """
    last_message = state["messages"][-1]
    try:
        content = last_message.content
        if not isinstance(content, str):
            content = str(content)

        decision = json.loads(content)
        action = decision.get("action")

        if action == "query_graph":
            return "tool_execution"
        elif action == "web_search":
            return "tool_execution"  # Web search also goes to tool_execution
        elif action == "final_answer":
            return "reflection"  # 最终答案先进入反思节点
        else:
            return "end"  # 默认结束
    except:
        return "end"


def reflection_router(state: AgentState) -> str:
    """
    反思后的智能路由：
    1. 如果反思失败 -> 返回 reasoning (重新思考)
    2. 如果反思通过 -> 检查是否需要辩论
    3. 如果是简单事实或高置信度 -> 直接 END
    4. 否则 -> 进入 debate
    """
    messages = state["messages"]
    last_msg = messages[-1]

    # 1. 检查反思结果
    if "FAILED" in last_msg.content:
        # 如果还没达到最大反思次数，尝试重新推理
        if state.get("reflection_count", 0) < state.get("max_reflections", 2):
            logger.info("[Router] Reflection failed, returning to reasoning")
            return "reasoning"
        else:
            logger.info("[Router] Max reflections reached, forced to debate")
            return "debate"

    # 2. 获取之前的 AI 决策以判断是否需要辩论
    requires_debate = True
    confidence = 0.0

    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            try:
                # 使用正则清洗可能存在的 <think>
                content = msg.content
                if not isinstance(content, str):
                    content = str(content)
                clean_content = re.sub(
                    r"<think>.*?</think>", "", content, flags=re.DOTALL
                )
                decision = json.loads(clean_content)
                if decision.get("action") == "final_answer":
                    requires_debate = decision.get("requires_debate", True)
                    confidence = decision.get("confidence", 0.0)
                    break
            except:
                continue

    # 3. 智能判定
    if not requires_debate:
        logger.info(
            "[Router] Simple fact detected (requires_debate=False), skipping debate"
        )
        return "end"

    if confidence > 0.9:
        logger.info(f"[Router] High confidence ({confidence}), skipping debate")
        return "end"

    logger.info(
        f"[Router] Routing to debate (confidence={confidence}, requires_debate={requires_debate})"
    )
    return "debate"


def build_agent_graph():
    """构建并编译图"""

    # =========================================================================
    # 1. 创建 StateGraph
    # =========================================================================
    workflow = StateGraph(AgentState)

    # =========================================================================
    # 2. 添加节点
    # =========================================================================
    # 核心节点
    workflow.add_node("reasoning", reasoning_node)
    workflow.add_node("tool_execution", tool_execution_node)
    workflow.add_node("reflection", reflection_node)

    # 辩论模块节点
    workflow.add_node("debate", debate_node)

    # =========================================================================
    # 3. 设置入口
    # =========================================================================
    workflow.set_entry_point("reasoning")

    # =========================================================================
    # 4. 添加边 - Reasoning 路由
    # =========================================================================
    workflow.add_conditional_edges(
        "reasoning",
        router,
        {
            "tool_execution": "tool_execution",
            "reflection": "reflection",
            "end": END,
        },
    )

    # =========================================================================
    # 5. 添加边 - Tool 执行完回到推理 (ReAct Loop)
    # =========================================================================
    workflow.add_edge("tool_execution", "reasoning")

    # =========================================================================
    # 6. 添加边 - Reflection 路由到辩论
    # =========================================================================
    workflow.add_conditional_edges(
        "reflection",
        reflection_router,
        {
            "reasoning": "reasoning",  # 失败时可选择重新推理
            "debate": "debate",  # 直接进入辩论节点
            "end": END,
        },
    )

    # =========================================================================
    # 7. 移除中间的多余路由
    # =========================================================================

    # =========================================================================
    # 8. 添加边 - 辩论节点结束
    # =========================================================================
    workflow.add_edge("debate", END)

    # =========================================================================
    # 9. 编译图
    # =========================================================================
    return workflow.compile()


# =========================================================================
# 路由扩展说明
# =========================================================================
"""
未来可添加的路由分支：

1. 置信度路由 (confidence_router):
   if confidence > 0.9: return "direct_output"  # 高置信度直接输出
   else: return "debate"  # 低置信度进入辩论

2. 问题类型路由 (question_type_router):
   if is_investment_question: return "debate"
   elif is_factual_question: return "direct_output"
   else: return "reasoning"

3. 用户偏好路由 (user_preference_router):
   if user.preference == "quick": return "direct_output"
   elif user.preference == "deep": return "debate"
   else: return "reasoning"

4. 风险等级路由 (risk_router):
   if risk_level > HIGH: return "human_review"
   else: return "debate"
"""


if __name__ == "__main__":
    # 简单测试
    import logging

    logging.basicConfig(level=logging.INFO)

    app = build_agent_graph()
    print("Graph compiled successfully.")
    print("\nAvailable nodes:")
    for node in app.nodes:
        print(f"  - {node}")
