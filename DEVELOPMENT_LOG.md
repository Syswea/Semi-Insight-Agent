# Semi-Insight-Agent 开发日志

## 2026-02-03: 第一阶段 - 索引器开发与基础架构

### 任务 1: 定义本体 (Ontology) 与 Neo4j 约束 - [已完成]
*   成功定义 `EntityLabel` 和 `RelationType`。
*   Neo4j 唯一性约束已成功注入数据库。

### 任务 2: 构建索引器 (Indexer) - [已修复并完成测试]
*   **修复动作**：
    1.  将 `OpenAI` 类替换为 `OpenAILike` 类，解决了对 OpenAI 模型名称的强制校验问题。
    2.  正式使用了用户指定的 `qwen/qwen3-14b` 模型。
    3.  安装了缺少的 `llama-index-llms-openai-like` 依赖。
*   **最终验证**：
    *   成功从 NVIDIA 报告中提取并保存了 14 条行业关系。
    *   全链路本地化运行通畅（LM Studio -> OpenAILike -> Neo4j）。

## 2026-02-04: 第一阶段 - 索引器重构与数据清洗

### 任务 3: 索引器深度重构 (Refactoring Indexer) - [已完成]
*   **痛点解决**：之前的版本引入了 `__Entity__`, `Chunk`, `embedding` 等冗余数据，污染了图谱。
*   **架构变更**：
    1.  **双重过滤流水线 (Two-Stage Pipeline)**：
        *   Stage 1: LLM 判别器过滤掉无意义文本（免责声明、目录）。
        *   Stage 2: 严格的三元组提取器，配合黑名单（Products, Solutions）过滤。
    2.  **原生 Cypher 写入**：
        *   移除 `Neo4jPropertyGraphStore`，改用 `src/utils/database.py` 的原生驱动。
        *   实现了 `MERGE` 逻辑，确保数据库中只存在纯净的 `(Entity)-[RELATION]->(Entity)`。
*   **验证结果**：
    *   执行 `src/tools/inspect_graph.py`，确认图中无 Chunk 节点，无 Embedding 向量。
    *   提取出高质量关系：`NVIDIA --[DEVELOPS]--> Blackwell`。

## 2026-02-04: 第二阶段 - 思维编排层与基础工具

### 任务 4: 构建 Text-to-Cypher 工具 - [已完成]
*   **功能实现**：`src/tools/cypher_query.py` 实现了自然语言转 Cypher 查询。
*   **关键特性**：
    *   动态注入 Ontology 定义到 Prompt。
    *   Prompt 工程优化：禁止 `UNION`，推荐 `OPTIONAL MATCH`，强制变量定义。
    *   自我纠错：捕获语法错误并记录。

### 任务 5: 搭建 LangGraph ReAct 循环 - [已完成]
*   **状态定义**：`src/state.py` 定义了 `AgentState`。
*   **核心节点**：`src/workflow/nodes.py` 实现了 `reasoning_node` (JSON 决策) 和 `tool_execution_node` (工具执行)。
*   **工作流**：`src/workflow/graph_builder.py` 串联了推理与执行的循环。

### 任务 6: 构建交互界面 - [已完成]
*   **Streamlit App**：`src/app.py` 提供了 Web 聊天界面。
*   **可视化增强**：实时展示 Agent 的思维链（Thinking Process）和工具调用细节。
*   **日志系统**：集成了控制台日志，方便开发者后台监控 LLM 行为。

### 任务 7: 项目清理与文档更新 - [已完成]
*   **架构一致性**：移除了 `src/main.py` (CLI) 和 `src/test_workflow.py`，统一使用 `src/app.py` 作为入口。
*   **Agent 规范更新**：更新了 `AGENTS.md`，废弃了过时的 `PropertyGraphIndex` 指引，确立了"原生 Cypher + 双重过滤"的新标准。

## 2026-02-05: 第二阶段 - Reflection 自检机制

### 任务 8: Reflection 自检机制实现 - [已完成]
*   **概述**：实现了 Reflection 功能，完成推理模式中的自检组件。
*   **状态扩展** (`src/state.py`)：
    *   新增 `reflection_count`: 记录反思次数
    *   新增 `max_reflections`: 最大反思次数（默认 2）
*   **反思节点** (`src/workflow/nodes.py`)：
    *   `reflection_node()` 函数实现自检逻辑
    *   **检查维度**：答案是否直接回应问题，信息是否具体、是否引用图谱数据
    *   **决策逻辑**：PASS → 结束 / FAILED → 重新推理 / 达到上限 → 强制通过
*   **工作流更新** (`src/workflow/graph_builder.py`)：
    *   新增 `reflection_router()` 函数
    *   `final_answer` action 改为先进入 reflection 节点
*   **评估优化**：调整 Reflection Prompt，认可"基于现有数据+诚实说明局限性"的答案

## 2026-02-05: 第三阶段 - Web 搜索集成与 MCP Server

### 任务 9: 手写 MCP Server 实现 - [已完成]
*   **技术决策**：手写 MCP Server 而非直接使用 SDK，体现协议理解和架构设计能力。
*   **核心实现**：`src/mcp/server.py`
    *   使用 **FastMCP** 实现 stdio 传输模式（兼容 Claude Desktop/Cursor）
    *   使用 **FastAPI** 实现 HTTP 传输模式（支持 Web 应用调用）
    *   集成 **DuckDuckGo** 搜索（免费，无 API Key 需求）
    *   完整的日志追踪：`[MCP]`, `[MCP Tool]`, `[HTTP API]` 前缀
*   **协议支持**：
    *   `/mcp` - MCP JSON-RPC 协议端点
    *   `/api/search` - 简化的 REST API
    *   `/health` - 健康检查端点

### 任务 10: LangGraph 工具集成 - [已完成]
*   **工具封装**：`src/tools/web_search.py`
    *   `WebSearchTool` 类支持两种模式：
        *   **DIRECT**: 直接调用 DuckDuckGo SDK
        *   **MCP_PROXY**: 通过 MCP Server 代理调用（协议合规）
    *   默认使用 MCP_PROXY 模式，展示协议兼容性
*   **节点更新**：`src/workflow/nodes.py`
    *   `reasoning_node` 新增 `web_search` action 判断
    *   `tool_execution_node` 支持调用 Web 搜索工具

### 任务 11: Streamlit 自动启动 MCP Server - [已完成]
*   **自动启动机制**：`src/app.py`
    *   应用启动时自动检测 MCP Server 端口占用
    *   未运行时自动启动 MCP Server 子进程
    *   侧边栏实时显示服务状态
    *   健康检查确保服务可用性

### 任务 12: 测试与验证 - [已完成]
*   **MCP 协议测试**：通过 `curl` 测试 `/mcp` 端点的 JSON-RPC 协议
*   **LangGraph 集成测试**：`test_mcp_integration.py`
    *   验证 Agent 能正确调用 Web 搜索
    *   验证 Reflection 机制能正确评估搜索结果

## 2026-02-05: 第三阶段 - 多代理辩论模块

### 任务 13: AutoGen 辩论 Agent 定义 - [已完成]
*   **核心实现**：`src/agents/debate_agents.py`
    *   `BullishAgent`: 看多分析师，乐观视角寻找投资机会
    *   `BearishAgent`: 看空分析师，审慎视角识别风险
    *   `JudgeAgent`: 裁判/评分员，综合评估给出评分
*   **角色设计**：
    *   每种 Agent 有明确的 System Message 定义
    *   输出结构化信息，便于 LangGraph 处理
    *   保留完整辩论过程记录

### 任务 14: 辩论节点实现 - [已完成]
*   **核心实现**：`src/workflow/debate.py`
    *   `debate_node()`: 执行辩论流程
    *   `debate_router()`: 路由判断（可扩展条件分支）
    *   `generate_final_report()`: 生成最终研判报告
*   **辩论流程**：
    1.  收集基础分析上下文
    2.  模拟 Bullish/Bearish 辩论
    3.  Judge 评分并生成最终报告
*   **评分输出**：
    *   Bull Score (0-100)
    *   Bear Score (0-100)
    *   Final Score (综合评分)
    *   Key Bull/Bear Points
    *   Risk Level & Recommendation

### 任务 15: LangGraph 工作流整合 - [已完成]
*   **状态扩展** (`src/state.py`)：
    *   `debate_transcript`: 辩论过程记录
    *   `debate_scores`: 评分结果
    *   `debate_key_points`: 关键论点
    *   `debate_assessment`: 评估结果
    *   `final_report`: 最终报告
*   **节点更新** (`src/workflow/graph_builder.py`)：
    *   新增 `debate_router`: 路由到辩论
    *   新增 `debate`: 辩论执行节点
    *   更新边关系：Reflection → Debate → END
*   **路由设计**：
    *   保留扩展性，可添加条件分支
    *   当前策略：总是进入辩论（无条件）

### 任务 16: Streamlit UI 更新 - [已完成]
*   **界面增强** (`src/app.py`)：
    *   初始状态添加辩论相关字段
    *   显示辩论路由状态
    *   **辩论结果展示**：
        *   三列评分展示 (Bull/Bear/Final)
        *   置信度、建议、风险等级
        *   关键论点列表
        *   可展开的完整辩论记录
    *   使用最终报告作为输出

### 任务 17: 文档更新 - [已完成]
*   合并 REFLECTION_IMPLEMENTATION.md 到 DEVELOPMENT_LOG.md
*   更新 CODE_IMPLEMENTATION_PLAN.md
*   删除冗余文档
