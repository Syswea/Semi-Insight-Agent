"""
分批处理 PDF 文件到 Neo4j 数据库 - 流式增量写入版

改进：
1. 流式增量写入（每个 chunk 提取后立即写入 Neo4j）
2. tqdm 进度条实时显示处理进度
3. 单条写入带重试机制
4. 优化的分块策略 (chunk_size=1024)
"""

import os
import sys
import glob
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# 确保项目根目录在 Python 路径中
# batch_index.py 位于: src/engine/batch_index.py
# 需要到达项目根目录: C:\Worksapce\Semi-Insight-Agent
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.engine.indexer import SemiIndexer
from src.utils.database import init_constraints

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(threadName)s] - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 全局统计
stats_lock = Lock()
stats = {
    "files_processed": 0,
    "total_triplets": 0,
}


def process_single_pdf(args):
    """处理单个 PDF 文件 - 用于并行调用"""
    pdf_file, idx, total = args
    filename = os.path.basename(pdf_file)

    try:
        indexer = SemiIndexer()
        triplets = indexer.ingest_document(pdf_file)

        with stats_lock:
            stats["files_processed"] += 1
            stats["total_triplets"] += triplets

        return {
            "success": True,
            "filename": filename,
            "triplets": triplets,
            "thread": __import__("threading").current_thread().name,
        }
    except Exception as e:
        logger.error(f"[{filename}] Error: {e}")
        return {
            "success": False,
            "filename": filename,
            "error": str(e),
            "thread": __import__("threading").current_thread().name,
        }


def process_all_pdfs():
    """并行处理所有 PDF 文件"""
    pdf_files = glob.glob("data/*.pdf")
    pdf_files.sort()

    logger.info(f"Found {len(pdf_files)} PDF files:")
    for f in pdf_files:
        logger.info(f"  - {os.path.basename(f)}")

    # 先清空数据库并初始化约束
    logger.info("\n" + "=" * 60)
    logger.info("Clearing database and initializing constraints...")
    logger.info("=" * 60)

    indexer = SemiIndexer()
    indexer.db.clear_database()
    init_constraints()

    # 准备参数列表
    args_list = [(f, i + 1, len(pdf_files)) for i, f in enumerate(pdf_files)]

    # 并行处理 - 已调整为串行执行 (max_workers=1)
    max_workers = 1

    logger.info(f"\n{'=' * 60}")
    logger.info(f"Starting sequential processing (max_workers=1)...")
    logger.info(f"{'=' * 60}")

    completed = 0
    total_files = len(pdf_files)

    with ThreadPoolExecutor(
        max_workers=max_workers, thread_name_prefix="Worker"
    ) as executor:
        futures = {
            executor.submit(process_single_pdf, args): args for args in args_list
        }

        for future in as_completed(futures):
            args = futures[future]
            result = future.result()

            completed += 1
            if result["success"]:
                logger.info(
                    f"[{completed}/{total_files}] [{result['thread']}] "
                    f"{result['filename']}: {result['triplets']} triplets"
                )
            else:
                logger.error(
                    f"[{completed}/{total_files}] [{result['thread']}] "
                    f"{result['filename']}: FAILED - {result.get('error', 'Unknown')}"
                )

    # 最终统计
    logger.info(f"\n{'=' * 60}")
    logger.info("FINAL STATISTICS")
    logger.info("=" * 60)
    logger.info(f"Files processed: {stats['files_processed']}/{total_files}")
    logger.info(f"Total triplets: {stats['total_triplets']}")
    logger.info(f"{'=' * 60}")

    # 按类型统计
    logger.info("\nNodes by type:")
    result = indexer.db.run_query(
        "MATCH (n) RETURN labels(n)[0] as type, count(n) as count ORDER BY count DESC"
    )
    for row in result:
        logger.info(f"  - {row['type']}: {row['count']}")

    logger.info("\nRelationships by type:")
    result = indexer.db.run_query(
        "MATCH ()-[r]->() RETURN type(r) as type, count(r) as count ORDER BY count DESC"
    )
    for row in result:
        logger.info(f"  - {row['type']}: {row['count']}")

    # Close database connection
    indexer.db.close()


if __name__ == "__main__":
    process_all_pdfs()
