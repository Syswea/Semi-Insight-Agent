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
from typing import Dict, Any
from langgraph.graph import StateGraph, END

from src.state import AgentState
from src.workflow.nodes import reasoning_node, tool_execution_node, reflection_node
from src.workflow.debate import debate_router, debate_node

logger = logging.getLogger(__name__)


def router(state: AgentState) -> str:
    """
    路由函数：根据 Reasoning 节点的输出决定下一步。

    支持的工具：
    - query_graph: 查询知识图谱
    - web_search: 网络搜索
    - final_answer: 生成最终答案
    """
    last_message = state["messages"][-1]
    try:
        decision = json.loads(last_message.content)
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
    反思后的路由决策：根据反思结果决定是结束还是重新推理。

    当前策略：
    - 总是路由到辩论节点（无条件）
    - 保留扩展性，可添加：
        * high_confidence → 直接辩论
        * user_preference → 快速回答
    """
    last_msg = state["messages"][-1]

    if "PASSED" in last_msg.content:
        logger.info("[Router] Reflection passed, routing to debate")
        return "debate"  # 反思通过，进入辩论
    elif "FAILED" in last_msg.content:
        logger.info(
            "[Router] Reflection failed, but still routing to debate for multi-perspective"
        )
        return "debate"  # 即使反思失败，也进入辩论获取多视角
    else:
        logger.info("[Router] No clear reflection result, routing to debate")
        return "debate"  # 默认进入辩论


def debate_router(state: AgentState) -> Dict[str, Any]:
    """
    辩论路由节点（可扩展）

    当前策略：辩论完成后直接结束
    保留扩展性，未来可添加：
    - low_confidence → 返回要求更多信息
    - high_impact → 升级到人工审核
    - follow_up_question → 继续对话
    """
    logger.info("[Debate Router] Debate completed, ending workflow")

    # 辩论完成后直接结束，不需要更新状态
    # 这里返回 None 表示不更新状态
    return {}


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
    workflow.add_node("debate_router", debate_router)
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
            "debate": "debate_router",  # 总是进入辩论模块
            "end": END,
        },
    )

    # =========================================================================
    # 7. 添加边 - 辩论路由器到辩论节点
    # =========================================================================
    workflow.add_edge("debate_router", "debate")

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
