"""
src/tools/cypher_query.py

Text-to-Cypher 转换引擎。
负责将自然语言问题转化为符合 Ontology 定义的 Cypher 查询语句。
"""

import os
import logging
import re
from typing import List, Dict, Any

from llama_index.llms.openai_like import OpenAILike
from src.utils.database import Neo4jClient
from src.schema.ontology import EntityLabel, RelationType

logger = logging.getLogger(__name__)


class CypherQueryEngine:
    def __init__(self):
        self.client = Neo4jClient()
        self.llm = OpenAILike(
            model=os.getenv("LLM_MODEL", "qwen/qwen3-14b"),
            api_base=os.getenv("OPENAI_API_BASE", "http://127.0.0.1:1234/v1"),
            api_key=os.getenv("OPENAI_API_KEY", "lm-studio"),
            is_chat_model=True,
            timeout=120.0,
            temperature=0.0,  # Code generation requires precision
        )

    def _get_schema_str(self) -> str:
        """动态生成 Schema 描述字符串"""
        labels = ", ".join([e.value for e in EntityLabel])
        relations = ", ".join([r.value for r in RelationType])

        return (
            f"Node Labels: [{labels}]\n"
            f"Relation Types: [{relations}]\n"
            "Property keys: ['name'] (All nodes primarily use 'name' as identifier)\n"
        )

    def generate_cypher(self, question: str) -> str:
        """调用 LLM 生成 Cypher 语句"""
        schema_context = self._get_schema_str()

        prompt = (
            "You are a Neo4j Cypher expert for a Semiconductor Knowledge Graph.\n"
            "Generate a SINGLE Cypher query to answer the user's question.\n\n"
            "--- Schema Definition ---\n"
            f"{schema_context}\n"
            "--- Rules (CRITICAL) ---\n"
            "1. Use ONLY the provided Labels and Relation Types.\n"
            "2. Do NOT use markdown code blocks. Output ONLY the raw query.\n"
            "3. Use case-insensitive matching: `WHERE toLower(n.name) CONTAINS toLower('value')`\n"
            "4. NEVER use `UNION` or `UNION ALL`. It causes syntax errors.\n"
            "5. To fetch multiple relationships, use `OPTIONAL MATCH`.\n"
            "6. Always define relationship variables before using `type(r)`. Example: `-[r:REL]->`.\n"
            "7. ALWAYS return explicit columns, do not return complex objects/maps if possible.\n"
            "8. Limit results to 50.\n\n"
            "--- Few-Shot Examples ---\n"
            "User: Who supplies NVIDIA?\n"
            "Cypher: MATCH (s)-[:SUPPLIES]->(o:Organization) WHERE toLower(o.name) CONTAINS 'nvidia' RETURN s.name AS Supplier, o.name AS Organization LIMIT 50\n\n"
            "User: What does NVIDIA do? (Suppliers, Technologies, etc.)\n"
            "Cypher: MATCH (n:Organization) WHERE toLower(n.name) CONTAINS 'nvidia' OPTIONAL MATCH (n)-[:DEVELOPS]->(t) OPTIONAL MATCH (s)-[:SUPPLIES]->(n) RETURN n.name, collect(distinct t.name) as Technologies, collect(distinct s.name) as Suppliers LIMIT 50\n\n"
            "User: What technologies does TSMC develop?\n"
            "Cypher: MATCH (s:Organization)-[:DEVELOPS]->(t:Technology) WHERE toLower(s.name) CONTAINS 'tsmc' RETURN t.name AS Technology LIMIT 50\n\n"
            "--- Current Question ---\n"
            f"User: {question}\n"
            "Cypher:"
        )

        try:
            response = self.llm.complete(prompt).text
            # 清洗结果：移除可能存在的 markdown 标记或思考过程
            clean_query = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL)
            clean_query = re.sub(r"```.*?```", "", clean_query, flags=re.DOTALL)
            clean_query = clean_query.strip()

            # 简单的后处理：如果 LLM 加了 `cypher` 前缀
            if clean_query.lower().startswith("cypher"):
                clean_query = clean_query[6:].strip()

            return clean_query
        except Exception as e:
            logger.error(f"Cypher generation failed: {e}")
            return ""

    def run(self, question: str) -> str:
        """执行问答全流程"""
        cypher = self.generate_cypher(question)
        if not cypher:
            return "Failed to generate valid Cypher query."

        logger.info(f"Generated Cypher: {cypher}")

        try:
            results = self.client.run_query(cypher)
            if not results:
                return "No information found in the knowledge graph."
            return str(results)
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return f"Query execution error: {e}"


if __name__ == "__main__":
    # 简单的本地测试
    logging.basicConfig(level=logging.INFO)
    engine = CypherQueryEngine()

    print("\nTest 1: Who supplies NVIDIA? (Expect empty if not in DB)")
    print(engine.run("Who supplies NVIDIA?"))

    print("\nTest 2: What technologies does NVIDIA develop? (Expect Blackwell, etc.)")
    print(engine.run("What technologies does NVIDIA develop?"))
