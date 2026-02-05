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
import sys
from typing import List, Tuple
from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from llama_index.core import SimpleDirectoryReader
from llama_index.llms.openai_like import OpenAILike
from llama_index.core.node_parser import SentenceSplitter

from src.utils.database import Neo4jClient
from src.schema.ontology import EntityLabel, RelationType

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data_extraction.log", mode="a", encoding="utf-8"),
    ],
)
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
        # Pre-calculate sets for faster validation
        self.valid_labels = {e.value for e in EntityLabel}
        self.valid_relations = {r.value for r in RelationType}

    def _filter_chunk(self, text: str, chunk_id: str) -> bool:
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
            response = self.llm.complete(prompt, timeout=90.0).text.strip().upper()
            return "YES" in response
        except Exception as e:
            # Re-raise context errors to be handled by recursive split
            error_str = str(e).lower()
            if any(msg in error_str for msg in ["context size", "400", "too long"]):
                raise e
            logger.warning(f"[{chunk_id}] Filter check failed (non-critical): {e}")
            return True  # Keep text if unsure

    def _clean_entity_name(self, name: str) -> str:
        """清洗实体名称"""
        # 移除 Markdown、标点符号
        name = re.sub(r"[*_`'\"\[\]]", "", name)

        # 分割驼峰命名: NVIDIAProducts -> NVIDIA Products
        name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)

        # 移除开头结尾的非字母数字
        name = re.sub(r"^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$", "", name)

        # 移除多余空格
        name = re.sub(r"\s+", " ", name).strip()

        return name

    def _is_valid_entity(self, name: str) -> bool:
        """校验实体有效性"""
        name_lower = name.lower()

        # 长度检查
        if len(name) < 3 or len(name) > 50:
            return False

        # 如果整个名称是黑名单词，拒绝
        if name_lower in ENTITY_BLACKLIST:
            return False

        # 如果名称包含任何黑名单词，拒绝
        for word in ENTITY_BLACKLIST:
            if word in name_lower:
                return False

        # 过滤纯数字
        if name.isdigit():
            return False

        # 过滤纯符号
        if not re.search(r"[a-zA-Z]", name):
            return False

        return True

    def extract_triplets_manually(
        self, text: str, chunk_id: str
    ) -> List[Tuple[str, str, str, str, str]]:
        """
        Step 2: 精细提取三元组。
        """
        logger.info(f"[{chunk_id}] --- INPUT TEXT SEGMENT ---\n{text}\n{'-' * 40}")
        valid_labels = ", ".join([e.value for e in EntityLabel])
        valid_relations = ", ".join([r.value for r in RelationType])

        prompt = f"""You are a Semiconductor Industry Expert.

TASK: Extract Entity-Relation-Entity triplets from the provided TEXT only.

RULES:
1. Subject and Object MUST be SPECIFIC NAMED ENTITIES found in the provided TEXT.
2. Do NOT extract entities from the EXAMPLES below.
3. Labels: {valid_labels}
4. Relations: {valid_relations}
5. Output: Subject|Label|Relation|Object|Label (one per line)

EXAMPLES:
NVIDIA|Organization|DEVELOPS|Blackwell|Technology
TSMC|Organization|SUPPLIES|NVIDIA|Organization
US|Geography|RESTRICTED_EXPORT|H20|Technology
NVIDIA|Organization|REVENUE|$35B|Metric
Data Center|IndustrySegment|REVENUE|$26B|Metric
Taiwan|Geography|LOCATED_AT|TSMC|Organization

TEXT:
{text}

OUTPUT:"""

        try:
            raw_response = self.llm.complete(prompt, timeout=180.0).text
            logger.info(
                f"[{chunk_id}] --- RAW LLM RESPONSE ---\n{raw_response}\n{'-' * 40}"
            )
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
                        if s_l not in self.valid_labels:
                            logger.debug(
                                f"[{chunk_id}] Dropped triplet due to invalid Subject Label: {s_l}"
                            )
                            continue
                        if o_l not in self.valid_labels:
                            logger.debug(
                                f"[{chunk_id}] Dropped triplet due to invalid Object Label: {o_l}"
                            )
                            continue
                        if r not in self.valid_relations:
                            logger.debug(
                                f"[{chunk_id}] Dropped triplet due to invalid Relation: {r}"
                            )
                            continue

                        if self._is_valid_entity(s) and self._is_valid_entity(o):
                            triplets.append((s, s_l, r, o, o_l))
            return triplets
        except Exception as e:
            error_str = str(e).lower()
            if any(msg in error_str for msg in ["context size", "400", "too long"]):
                raise e
            logger.error(f"[{chunk_id}] Extraction failed: {e}")
            return []

    def _ingest_chunk_recursive(
        self, chunk_text: str, chunk_id: str, source_file: str
    ) -> int:
        """递归处理 Chunk，如果遇到上下文超限则继续切分"""
        try:
            # Step 1: Filter
            if not self._filter_chunk(chunk_text, chunk_id):
                logger.info(
                    f"[{chunk_id}] SKIP: No relevant semiconductor facts found."
                )
                return 0

            # Step 2: Extract
            triplets = self.extract_triplets_manually(chunk_text, chunk_id)
            if not triplets:
                logger.info(
                    f"[{chunk_id}] WARNING: No triplets extracted from this chunk."
                )
                return 0

            logger.info(f"[{chunk_id}] SUCCESS: Extracted {len(triplets)} triplets:")

            # Step 3: Ingest
            count = 0
            for s, s_l, r, o, o_l in triplets:
                logger.info(f"    - Found: ({s}:{s_l}) -[{r}]-> ({o}:{o_l})")
                query = (
                    f"MERGE (a:{s_l} {{name: $s_name}}) "
                    f"ON CREATE SET a.source = $source "
                    f"MERGE (b:{o_l} {{name: $o_name}}) "
                    f"ON CREATE SET b.source = $source "
                    f"MERGE (a)-[r:{r}]->(b)"
                )
                params = {
                    "s_name": s,
                    "o_name": o,
                    "source": source_file,
                }
                try:
                    self.db.run_query(query, params)
                    count += 1
                except Exception as e:
                    logger.error(
                        f"[{chunk_id}] Failed to insert relation {s}->{o}: {e}"
                    )
            return count

        except Exception as e:
            if "context size" in str(e).lower():
                logger.warning(
                    f"[{chunk_id}] ERROR: Context size exceeded. Re-splitting this chunk..."
                )

                # 将文本大致对半切分，尽量在换行或点处切断
                mid = len(chunk_text) // 2
                split_pos = chunk_text.find("\n", mid)
                if split_pos == -1 or split_pos > mid + 200:
                    split_pos = chunk_text.find(". ", mid)
                if split_pos == -1:
                    split_pos = chunk_text.find(" ", mid)
                if split_pos == -1:
                    split_pos = mid

                part1 = chunk_text[:split_pos].strip()
                part2 = chunk_text[split_pos:].strip()

                logger.info(
                    f"[{chunk_id}] SPLIT: Split into Part 1 ({len(part1)} chars) and Part 2 ({len(part2)} chars)"
                )

                c1 = self._ingest_chunk_recursive(part1, f"{chunk_id}-p1", source_file)
                c2 = self._ingest_chunk_recursive(part2, f"{chunk_id}-p2", source_file)
                return c1 + c2
            else:
                logger.error(f"[{chunk_id}] Unexpected error: {e}")
                return 0

    def ingest_document(
        self, file_path: str, chunk_size: int = 1024, chunk_overlap: int = 200
    ) -> int:
        """处理文档并流式写入 Neo4j，返回插入的关系总数"""
        filename = os.path.basename(file_path)
        logger.info(f"[{filename}] [START] Start processing...")

        reader = SimpleDirectoryReader(input_files=[file_path])
        documents = reader.load_data()

        splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        total_relations = 0

        for i, doc in enumerate(documents):
            chunks = splitter.split_text(doc.text)
            logger.info(f"[{filename}] Page {i + 1}: {len(chunks)} chunks.")

            for chunk_idx, chunk_text in enumerate(chunks):
                chunk_id = f"{filename}][Page {i + 1}-Chunk {chunk_idx}"
                total_relations += self._ingest_chunk_recursive(
                    chunk_text, chunk_id, filename
                )

            logger.info(
                f"[{filename}] Page {i + 1} processed. Total relations so far: {total_relations}"
            )

        logger.info(f"[{filename}] [DONE] Finished. Total inserted: {total_relations}")
        return total_relations


if __name__ == "__main__":
    indexer = SemiIndexer()

    # 清空旧数据 (危险操作，仅开发阶段使用)
    indexer.db.clear_database()

    # 重新添加约束
    from src.utils.database import init_constraints

    init_constraints()

    # 单文件测试 - 使用最小的文件
    test_pdf = "data/NVDA-F3Q26-Quarterly-Presentation.pdf"
    if os.path.exists(test_pdf):
        logger.info(f"Processing: {test_pdf}")
        indexer.ingest_document(test_pdf)
    else:
        logger.error(f"File not found: {test_pdf}")
