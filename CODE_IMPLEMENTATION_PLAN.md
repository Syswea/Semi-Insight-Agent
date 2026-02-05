# Semi-Insight-Agent 代码实施计划书

## 1. 项目概述
本项目旨在构建一个基于 **GraphRAG**（图增强检索生成）与**多智能体协作**的半导体行业深度研判助手。通过整合产业链图谱、实时资讯与多维度辩论机制，为用户提供具备深度逻辑支撑的行业见解。

## 2. 系统架构逻辑
系统分为三个核心层级：

### 2.1 知识引擎层 (Knowledge Engine) - [已完成]
*   **GraphRAG 实现**：采用自定义的**两阶段过滤流水线**（Filter -> Extract）。使用原生 Cypher 驱动写入 Neo4j，杜绝 LlamaIndex 默认生成的冗余节点（如 Chunk, __Entity__）。
*   **本体设计 (Ontology)**：严格遵循 `src/schema/ontology.py` 定义的实体与关系。

### 2.2 思维编排层 (Reasoning Layer) - [已完成]
*   **LangGraph 状态机**：管理整个分析链路的状态。
*   **核心工具**：
    *   `CypherQueryEngine`：Text-to-Cypher 引擎，支持自然语言查询图数据库。
    *   `WebSearchTool`：Web 搜索工具，支持 MCP 协议代理调用。
*   **当前节点**：
    *   `Reasoning`：基于 JSON 决策的推理节点（支持 query_graph / web_search / final_answer）。
    *   `Tool Execution`：执行图查询或 Web 搜索工具。
    *   `Reflection`：自检节点，评估答案质量决定是否重新推理。
    *   `Debate Router`：辩论路由节点（可扩展条件分支）。
    *   `Debate`：多代理辩论节点，生成评分式报告。

### 2.3 多代理对弈层 (Collaboration Layer) - [已完成]
*   **多代理辩论**：
    *   `BullishAnalyst`：看多分析师，乐观视角寻找投资机会
    *   `BearishAnalyst`：看空分析师，审慎视角识别风险
    *   `JudgeAgent`：裁判/评分员，综合评估给出评分
*   **辩论流程**：
    1.  Round 1：初始陈述（Bullish vs Bearish）
    2.  Round 2：最终陈述
    3.  Judge 评分裁决
*   **评分输出**：
    *   Bull Score (0-100)
    *   Bear Score (0-100)
    *   Final Score (综合评分)
    *   Risk Level & Recommendation

---

## 3. 项目目录排版 (File Structure)

```
C:\Worksapce\Semi-Insight-Agent\
├── .env                    # 环境配置文件
├── requirements.txt        # 依赖项清单
├── docker-compose.yml      # Neo4j 运行时支持
├── README.md              # 项目说明文档
├── AGENTS.md              # 智能体开发规范
├── DEVELOPMENT_LOG.md      # 详细开发进度日志
├── CODE_IMPLEMENTATION_PLAN.md  # 代码实施计划
├── data/                   # 原始行业报告 (PDF)
├── src/                    # 核心代码目录
│   ├── app.py              # 系统入口：Streamlit Web 交互界面
│   ├── state.py            # LangGraph 状态定义 (TypedDict)
│   ├── schema/             # 本体与模式定义
│   │   └── ontology.py     # 定义节点标签及关系类型
│   ├── engine/             # 知识引擎 (GraphRAG)
│   │   └── indexer.py      # 自定义双重过滤索引脚本
│   ├── agents/             # 多代理辩论模块
│   │   ├── __init__.py
│   │   └── debate_agents.py # Bullish/Bearish/Judge Agent 定义
│   ├── tools/              # 工具集
│   │   ├── cypher_query.py  # Text-to-Cypher 执行封装
│   │   ├── web_search.py    # Web 搜索工具 (MCP 代理)
│   │   ├── mcp_client.py    # MCP Client 包装器
│   │   └── inspect_graph.py # 数据库调试工具
│   ├── mcp/                # MCP Server 实现
│   │   └── server.py       # MCP Server (双模式: stdio + HTTP)
│   ├── workflow/           # 工作流编排
│   │   ├── nodes.py        # LangGraph 各节点函数实现
│   │   ├── debate.py       # 辩论节点和路由器
│   │   └── graph_builder.py # 组装 LangGraph 图逻辑
│   └── utils/              # 数据库连接等辅助工具
├── neo4j/                  # Neo4j 数据持久化卷
├── test_reflection.py     # Reflection 测试脚本
├── test_mcp_integration.py # MCP 集成测试脚本
└── mcp.log                # MCP Server 日志
```

---

## 4. 系统设置与运行环境
*   **本地 LLM**：LM Studio (`qwen/qwen3-14b`) 运行于 `http://127.0.0.1:1234/v1`
*   **数据库**：Neo4j (Docker) 运行于 `bolt://localhost:7687`
*   **前端**：Streamlit 运行于 `http://localhost:8501`
*   **MCP Server**：HTTP 模式运行于 `http://localhost:8002`

---

## 5. 详细实施路线图

### 第一阶段：索引器开发 (已完成)
1.  定义本体与 Neo4j 约束。
2.  实现受控的两阶段提取流，解决图谱污染问题。

### 第二阶段：LangGraph 骨架 (已完成)
1.  定义 AgentState 共享内存。
2.  实现 Text-to-Cypher 自动查询。
3.  构建 Streamlit 可视化界面。
4.  实现 Reflection 自检机制。

### 第三阶段：能力增强 (已完成)
1.  ✅ 集成 MCP Server + DuckDuckGo Web 搜索
2.  ✅ 实现多代理辩论模块（Bullish vs Bearish vs Judge）
3.  ✅ 添加辩论路由节点（保留扩展性）

---

## 6. 路由扩展设计

### 当前路由策略
```
Reflection → Debate Router → Debate → END
              ↑
              总是进入辩论（无条件）
```

### 未来可扩展分支
```
Reflection → Debate Router
                │
                ├─ high_confidence → 直接输出（高置信度）
                ├─ investment_question → 辩论（投资问题）
                ├─ risk_assessment → 辩论（风险评估）
                └─ user_preference=quick → 直接输出
```

### 辩论节点设计
```
Debate Node 输入：
- 用户问题
- 基础分析上下文
- Reflection 结果

Debate Node 输出：
- debate_transcript: 辩论过程记录
- debate_scores: 评分结果 (bull/bear/final)
- debate_key_points: 关键论点
- debate_assessment: 评估结果
- final_report: 最终研判报告
```

---

## 7. 演示场景

### 场景 1: 基础问题
**问题**: "NVIDIA 有什么技术？"
**流程**: GraphRAG → Reflection → Debate → 最终报告

### 场景 2: 投资建议
**问题**: "你觉得 NVIDIA 值得投资吗？"
**流程**: GraphRAG + Web Search → Reflection → Debate (核心价值) → 评分报告

### 场景 3: 行业分析
**问题**: "半导体行业前景如何？"
**流程**: GraphRAG → Reflection → Debate (多空交织) → 平衡报告

---

## 8. 面试亮点

### 技术亮点
1.  **手写 MCP Server**：符合面试官要求的协议理解
2.  **LangGraph 条件路由**：展示系统架构设计能力
3.  **多代理辩论**：创新性地将 AutoGen 思想融入工作流
4.  **完整的可观测性**：每步都有日志和 UI 展示

### 架构优势
1.  **模块化设计**：工具、代理、节点解耦
2.  **可扩展路由**：保留未来添加条件的空间
3.  **协议合规**：MCP 标准、JSON-RPC 协议
