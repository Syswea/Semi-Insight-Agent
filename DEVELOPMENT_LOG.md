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
*   **Agent 规范更新**：更新了 `AGENTS.md`，废弃了过时的 `PropertyGraphIndex` 指引，确立了“原生 Cypher + 双重过滤”的新标准。
