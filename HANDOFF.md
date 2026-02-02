# Project Handoff: Semi-Insight-Agent

## 1. Project Context
An AI-driven semiconductor industry analyst using **GraphRAG** (LlamaIndex + Neo4j), **State Management** (LangGraph), and **Multi-Agent Debate** (AutoGen).

## 2. Current State of Data
The `data/reports/` folder contains a high-quality "Knowledge Pyramid":
- **Strategic Layer**: SIA 2024/2025 State of Industry (Global structure, market shares).
- **Operational Layer**: TSMC & NVIDIA 2025 Q1-Q3 reports (Specific financials and tech roadmaps).
- **Tactical Layer**: SEMI Nov 2025 Newsletters (Latest news, HBM trends, policy changes).

## 3. Proposed Knowledge Graph Schema (Neo4j)
Based on the SIA report analysis, the graph should follow this ontology:
- **Entities**: 
  - `Organization` (e.g., TSMC, NVIDIA, SEMI)
  - `Geography` (e.g., USA, Taiwan, China, EU)
  - `IndustrySegment` (e.g., Foundry, EDA, IP, SME, ATP)
  - `Technology` (e.g., HBM3e, 2nm, SiC, EUV)
  - `Policy` (e.g., CHIPS Act, Export Controls)
  - `Metric` (e.g., MarketShare, Revenue, R&D_Expenditure)
- **Relationships**:
  - `(Org)-[:HEADQUARTERED_IN]->(Geo)`
  - `(Org)-[:OPERATES_IN]->(IndustrySegment)`
  - `(Org)-[:SUPPLIES]->(Org)`
  - `(Org)-[:DEVELOPS]->(Technology)`
  - `(Geo)-[:IMPLEMENTS]->(Policy)`
  - `(Policy)-[:IMPACTS]->(Org|Technology)`

## 4. Technical Implementation Plan
### Phase 1: Knowledge Base (Week 1)
- **Tool**: LlamaIndex `PropertyGraphIndex`.
- **Task**: Implement `src/engine/indexer.py` to parse PDFs and populate Neo4j.
- **Goal**: Answer queries like "Which Chinese firms are impacted by US EUV export controls?" using graph paths.

### Phase 2: Reasoning Engine (Week 2)
- **Tool**: LangGraph.
- **Workflow**: `Planner` -> `ReAct Analyst` (Tools: GraphRetriever, WebSearch) -> `Reflector` (Hallucination check).

### Phase 3: Consensus & Handoff (Week 3)
- **Tool**: AutoGen.
- **Agents**: `BullishAnalyst` vs `BearishAnalyst`.
- **Task**: Debate the LangGraph output to produce a "Multi-perspective Report".

## 5. Immediate Next Steps for the Next Model
1. **Verify Environment**: Run `docker-compose up -d` to start Neo4j.
2. **Setup Schema**: Initialize the Neo4j constraints/indexes based on the ontology above.
3. **Draft Indexer**: Create `src/engine/indexer.py` using `SimpleDirectoryReader` for the `data/reports/` folder.
4. **Graph Extraction**: Use a strong LLM (e.g., GPT-4o or DeepSeek-V3) to extract triplets from the SIA reports to build the "Seed Graph".
