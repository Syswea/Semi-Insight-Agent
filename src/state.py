"""
src/state.py

定义 LangGraph 智能体的状态 (State) 结构。
这是多 Agent 协作时的共享内存。
"""

from typing import TypedDict, Annotated, List, Union, Dict
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
        reflection_count: 记录反思次数，防止无限循环。
        max_reflections: 最大反思次数（默认2）。

        # 辩论模块字段
        debate_transcript: 多代理辩论过程记录
        debate_scores: 辩论评分 (bull_score, bear_score, final_score)
        debate_key_points: 辩论关键论点
        debate_assessment: 辩论评估结果
        final_report: 最终研判报告
    """

    messages: Annotated[List[AnyMessage], operator.add]
    context: List[str]
    plan: List[str]
    error: Union[str, None]
    reflection_count: int
    max_reflections: int
    debate_transcript: Union[Dict, None]
    debate_scores: Union[Dict, None]
    debate_key_points: Union[Dict, None]
    debate_assessment: Union[Dict, None]
    final_report: Union[str, None]
