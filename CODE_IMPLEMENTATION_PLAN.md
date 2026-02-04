# Semi-Insight-Agent 代码实施计划书

## 1. 项目概述
本项目旨在构建一个基于 **GraphRAG**（图增强检索生成）与**多智能体协作**的半导体行业深度研判助手。通过整合产业链图谱、实时资讯与多维度辩论机制，为用户提供具备深度逻辑支撑的行业见解。

## 2. 系统架构逻辑
系统分为三个核心层级：

### 2.1 知识引擎层 (Knowledge Engine) - [已完成]
*   **GraphRAG 实现**：采用自定义的**两阶段过滤流水线**（Filter -> Extract）。使用原生 Cypher 驱动写入 Neo4j，杜绝 LlamaIndex 默认生成的冗余节点（如 Chunk, __Entity__）。
*   **本体设计 (Ontology)**：严格遵循 `src/schema/ontology.py` 定义的实体与关系。

### 2.2 思维编排层 (Reasoning Layer) - [已完成基础架构]
*   **LangGraph 状态机**：管理整个分析链路的状态。
*   **核心工具**：
    *   `CypherQueryEngine`：Text-to-Cypher 引擎，支持自然语言查询图数据库。
*   **当前节点**：
    *   `Reasoning`：基于 JSON 决策的推理节点。
    *   `Tool Execution`：执行图查询工具。

### 2.3 多代理对弈层 (Collaboration Layer) - [进行中]
*   **AutoGen 辩论**：在 LangGraph 流程的末端，启动 `BullishAnalyst` (多头) 与 `BearishAnalyst` (空头) 的对抗性评审。
*   **实时资讯集成**：接入 Web Search 工具解决知识滞后。

---

## 3. 项目目录排版 (File Structure)

```text
C:\Worksapce\Semi-Insight-Agent\
├── .env                    # 环境配置文件
├── requirements.txt        # 依赖项清单
├── docker-compose.yml      # Neo4j 运行时支持
├── AGENTS.md               # 智能体开发规范 (已更新)
├── DEVELOPMENT_LOG.md      # 详细开发进度日志 (已更新)
├── data/                   # 原始行业报告 (PDF)
├── src/                    # 核心代码目录
│   ├── app.py              # 系统入口：Streamlit Web 交互界面
│   ├── state.py            # LangGraph 状态定义 (TypedDict)
│   ├── schema/             # 本体与模式定义
│   │   └── ontology.py     # 定义节点标签及关系类型
│   ├── engine/             # 知识引擎 (GraphRAG)
│   │   └── indexer.py      # 自定义双重过滤索引脚本
│   ├── tools/              # 工具集
│   │   ├── cypher_query.py # Text-to-Cypher 执行封装
│   │   └── inspect_graph.py # 数据库调试工具
│   ├── workflow/           # 工作流编排
│   │   ├── nodes.py        # LangGraph 各节点函数实现
│   │   └── graph_builder.py # 组装 LangGraph 图逻辑
│   └── utils/              # 数据库连接等辅助工具
└── neo4j/                  # Neo4j 数据持久化卷
```

---

## 4. 系统设置与运行环境
*   **本地 LLM**：LM Studio (`qwen/qwen3-14b`) 运行于 `http://127.0.0.1:1234/v1`
*   **数据库**：Neo4j (Docker) 运行于 `bolt://localhost:7687`
*   **前端**：Streamlit 运行于 `http://localhost:8501`

---

## 5. 详细实施路线图

### 第一阶段：索引器开发 (已完成)
1.  定义本体与 Neo4j 约束。
2.  实现受控的两阶段提取流，解决图谱污染问题。

### 第二阶段：LangGraph 骨架 (已完成)
1.  定义 AgentState 共享内存。
2.  实现 Text-to-Cypher 自动查询。
3.  构建 Streamlit 可视化界面。

### 第三阶段：能力增强 (进行中)
1.  集成 Web 搜索工具。
2.  引入 AutoGen 多代理辩论节点。
