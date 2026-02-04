"""
src/workflow/graph_builder.py

构建 LangGraph 状态机。
定义节点流转逻辑：Start -> Reasoning -> (Condition) -> Tool -> Reasoning ...
"""

import json
from langgraph.graph import StateGraph, END

from src.state import AgentState
from src.workflow.nodes import reasoning_node, tool_execution_node


def router(state: AgentState) -> str:
    """
    路由函数：根据 Reasoning 节点的输出决定下一步。
    """
    last_message = state["messages"][-1]
    try:
        decision = json.loads(last_message.content)
        action = decision.get("action")

        if action == "query_graph":
            return "tool_execution"
        elif action == "final_answer":
            return "end"
        else:
            return "end"  # 默认结束
    except:
        return "end"


def build_agent_graph():
    """构建并编译图"""
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("reasoning", reasoning_node)
    workflow.add_node("tool_execution", tool_execution_node)

    # 设置入口
    workflow.set_entry_point("reasoning")

    # 添加条件边
    workflow.add_conditional_edges(
        "reasoning", router, {"tool_execution": "tool_execution", "end": END}
    )

    # 工具执行完必然回到推理节点 (ReAct Loop)
    workflow.add_edge("tool_execution", "reasoning")

    return workflow.compile()


if __name__ == "__main__":
    # 简单测试
    app = build_agent_graph()
    print("Graph compiled successfully.")
