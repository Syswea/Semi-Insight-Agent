"""
src/state.py

定义 LangGraph 智能体的状态 (State) 结构。
这是多 Agent 协作时的共享内存。
"""

from typing import TypedDict, Annotated, List, Union
from langchain_core.messages import AnyMessage
import operator


class AgentState(TypedDict):
    """
    Agent 的核心状态定义。

    Attributes:
        messages: 完整的对话历史 (User, Assistant, Tool, System)。
                  Annotated[list, operator.add] 表示新消息会追加到列表末尾。
        context:  从图数据库或搜索工具检索到的事实片段。
        plan:     当前的推理计划或步骤。
        error:    如果执行出错，存储错误信息以便 Reflector 节点处理。
    """

    messages: Annotated[List[AnyMessage], operator.add]
    context: List[str]
    plan: List[str]
    error: Union[str, None]
