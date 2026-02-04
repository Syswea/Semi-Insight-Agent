"""
src/engine/indexer.py

本模块是系统的知识注入核心。
针对本地模型优化：放弃复杂的 LlamaIndex 自动提取器，改用受控的“两阶段”提取流。
直接使用 Neo4j Cypher 写入，确保图谱纯净（无 Vector Chunk 污染）。
"""

import os
import logging
import re
import asyncio
from typing import List, Tuple
from dotenv import load_dotenv

from llama_index.core import SimpleDirectoryReader
from llama_index.llms.openai_like import OpenAILike
from llama_index.core.node_parser import SentenceSplitter

from src.utils.database import Neo4jClient
from src.schema.ontology import EntityLabel, RelationType

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 黑名单：如果在实体名称中发现这些词，直接丢弃
ENTITY_BLACKLIST = {
    "products",
    "solutions",
    "company",
    "customers",
    "partners",
    "market",
    "industry",
    "technology",
    "revenue",
    "growth",
    "factors",
    "results",
    "operations",
    "business",
    "example",
    "text",
    "subject",
    "object",
}


class SemiIndexer:
    """受控的半导体知识索引器"""

    def __init__(self):
        # 1. 配置本地 LLM (LM Studio)
        self.llm = OpenAILike(
            model=os.getenv("LLM_MODEL", "qwen/qwen3-14b"),
            api_base=os.getenv("OPENAI_API_BASE", "http://127.0.0.1:1234/v1"),
            api_key=os.getenv("OPENAI_API_KEY", "lm-studio"),
            is_chat_model=True,
            timeout=300.0,
            temperature=0.0,  # 强制确定性输出
        )
        self.db = Neo4jClient()

    def _filter_chunk(self, text: str) -> bool:
        """
        Step 1: 粗筛。
        判断文本块是否包含具体的半导体行业关系信息。
        """
        prompt = (
            "You are a data filter for a semiconductor knowledge graph.\n"
            "Analyze the following text. Does it contain SPECIFIC facts about:\n"
            "- Supply chain relationships (who supplies whom)\n"
            "- Specific technologies (e.g., Blackwell, HBM3e)\n"
            "- Competition (e.g., NVIDIA vs AMD)\n"
            "- Policy impacts (e.g., Export controls)\n\n"
            "Return ONLY 'YES' or 'NO'. Do not explain.\n"
            "--- Text ---\n"
            f"{text}\n"
            "--- Decision ---\n"
        )
        try:
            response = self.llm.complete(prompt).text.strip().upper()
            return "YES" in response
        except Exception as e:
            logger.warning(f"Filter check failed: {e}")
            return False

    def _clean_entity_name(self, name: str) -> str:
        """清洗实体名称"""
        # 移除 Markdown、标点
        name = re.sub(r"[*_`'\"\[\]]", "", name)
        # 移除开头结尾的非字母数字
        name = re.sub(r"^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$", "", name)
        return name.strip()

    def _is_valid_entity(self, name: str) -> bool:
        """校验实体有效性"""
        name_lower = name.lower()
        if len(name) < 2 or len(name) > 50:
            return False
        if name_lower in ENTITY_BLACKLIST:
            return False
        # 过滤纯数字
        if name.isdigit():
            return False
        return True

    def extract_triplets_manually(
        self, text: str
    ) -> List[Tuple[str, str, str, str, str]]:
        """
        Step 2: 精细提取。
        """
        # 动态构建有效标签列表
        valid_labels = ", ".join([e.value for e in EntityLabel])
        valid_relations = ", ".join([r.value for r in RelationType])

        prompt = (
            "You are a strict Semiconductor Industry Analyst.\n"
            "Extract Entity-Relation-Entity triplets from the text.\n"
            "Format: Subject|SubjectLabel|Relation|Object|ObjectLabel\n\n"
            "Rules:\n"
            f"1. SubjectLabel/ObjectLabel MUST be one of: {valid_labels}\n"
            f"2. Relation MUST be one of: {valid_relations}\n"
            "3. IGNORE generic terms like 'Products', 'Customers', 'Company'. Extract ONLY specific names (e.g., 'NVIDIA', 'H100', 'TSMC').\n"
            "4. If no specific named entities exist, output nothing.\n"
            "--- Example ---\n"
            "NVIDIA|Organization|DEVELOPS|Blackwell|Technology\n"
            "TSMC|Organization|HEADQUARTERED_IN|Taiwan|Geography\n"
            "--- Text ---\n"
            f"{text}\n"
            "--- Output ---\n"
        )

        try:
            raw_response = self.llm.complete(prompt).text
            # 清洗 DeepSeek/Qwen 的思维链标签
            clean_response = re.sub(
                r"<think>.*?</think>", "", raw_response, flags=re.DOTALL
            )
            clean_response = re.sub(
                r"```.*?```", "", clean_response, flags=re.DOTALL
            ).strip()

            triplets = []
            for line in clean_response.split("\n"):
                if "|" in line:
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) == 5:
                        s, s_l, r, o, o_l = parts

                        s = self._clean_entity_name(s)
                        o = self._clean_entity_name(o)

                        # Enforce strict ontology compliance
                        # Optimization: Pre-compute these sets in __init__ if performance matters,
                        # but for now list comprehension is fine for readability.
                        if s_l not in [e.value for e in EntityLabel]:
                            logger.debug(
                                f"Dropped triplet due to invalid Subject Label: {s_l}"
                            )
                            continue
                        if o_l not in [e.value for e in EntityLabel]:
                            logger.debug(
                                f"Dropped triplet due to invalid Object Label: {o_l}"
                            )
                            continue
                        if r not in [rel.value for rel in RelationType]:
                            logger.debug(
                                f"Dropped triplet due to invalid Relation: {r}"
                            )
                            continue

                        if self._is_valid_entity(s) and self._is_valid_entity(o):
                            triplets.append((s, s_l, r, o, o_l))
            return triplets
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return []

    def ingest_document(self, file_path: str):
        """处理文档并直接写入 Neo4j"""
        logger.info(f"Processing {file_path}...")

        # 使用 LlamaIndex 读取 PDF，但只作为文本加载器
        reader = SimpleDirectoryReader(input_files=[file_path])
        documents = reader.load_data()

        # 文本切分 (Chunking) - 使用 SentenceSplitter 保持语义完整性
        splitter = SentenceSplitter(chunk_size=1024, chunk_overlap=100)

        total_relations = 0

        for i, doc in enumerate(documents):
            chunks = splitter.split_text(doc.text)
            logger.info(f"Page {i + 1}: {len(chunks)} chunks.")

            for chunk_idx, chunk_text in enumerate(chunks):
                # Step 1: Filter
                if not self._filter_chunk(chunk_text):
                    logger.debug(f"Chunk {chunk_idx} filtered out (irrelevant).")
                    continue

                # Step 2: Extract
                triplets = self.extract_triplets_manually(chunk_text)
                if not triplets:
                    continue

                # Step 3: Ingest (Direct Cypher)
                for s, s_l, r, o, o_l in triplets:
                    query = (
                        f"MERGE (a:{s_l} {{name: $s_name}}) "
                        f"ON CREATE SET a.source = $source "
                        f"MERGE (b:{o_l} {{name: $o_name}}) "
                        f"ON CREATE SET b.source = $source "
                        f"MERGE (a)-[r:{r}]->(b) "
                    )
                    params = {
                        "s_name": s,
                        "o_name": o,
                        "source": os.path.basename(file_path),
                    }
                    try:
                        self.db.run_query(query, params)
                        total_relations += 1
                    except Exception as e:
                        logger.error(f"Failed to insert relation {s}->{o}: {e}")

            logger.info(
                f"Page {i + 1} processed. Total relations so far: {total_relations}"
            )

        logger.info(f"Finished {file_path}. Total inserted: {total_relations}")


if __name__ == "__main__":
    indexer = SemiIndexer()

    # 清空旧数据 (危险操作，仅开发阶段使用)
    indexer.db.clear_database()

    # 重新添加约束
    from src.utils.database import init_constraints

    init_constraints()

    # 测试文件
    test_pdf = "data/reports/NVDA-F1Q26-Quarterly-Presentation-FINAL.pdf"
    if os.path.exists(test_pdf):
        indexer.ingest_document(test_pdf)
    else:
        logger.error("Data reports not found.")
