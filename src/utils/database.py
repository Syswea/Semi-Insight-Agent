"""
src/utils/database.py

本模块负责 Neo4j 数据库的连接管理与基础环境配置。
包含建立连接、执行 Cypher 语句以及设置数据库唯一性约束的逻辑。
"""

import os
import logging
from typing import Any
from neo4j import GraphDatabase, Driver
from dotenv import load_dotenv

# 加载环境变量以获取数据库凭据
load_dotenv()

# 设置日志
logger = logging.getLogger(__name__)


class Neo4jClient:
    """封装 Neo4j 驱动，提供单例模式思想的连接管理"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Neo4jClient, cls).__new__(cls)
            cls._instance._driver = None
        return cls._instance

    def connect(self) -> Driver:
        """建立数据库连接"""
        if self._driver is None:
            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            user = os.getenv("NEO4J_USERNAME", "neo4j")
            password = os.getenv("NEO4J_PASSWORD", "password")

            try:
                self._driver = GraphDatabase.driver(uri, auth=(user, password))
                # 验证连接是否可用
                self._driver.verify_connectivity()
                logger.info("Successfully connected to Neo4j.")
            except Exception as e:
                logger.error(f"Failed to connect to Neo4j: {e}")
                raise
        return self._driver

    def close(self):
        """关闭数据库连接"""
        if self._driver:
            self._driver.close()
            self._driver = None

    def run_query(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """执行 Cypher 查询并返回结果"""
        driver = self.connect()
        with driver.session() as session:
            result = session.run(query, parameters)
            return [dict(record) for record in result]

    def clear_database(self):
        """危险操作：清空整个数据库"""
        driver = self.connect()
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            logger.warning("⚠️ Database has been CLEARED.")


def init_constraints():
    """
    初始化数据库约束。
    思考过程：
    在知识图谱中，节点的标识符（通常是 name）必须是唯一的。
    如果不设约束，多次索引会导致重复节点。
    """
    from src.schema.ontology import EntityLabel

    client = Neo4jClient()
    logger.info("Initializing Neo4j constraints...")

    for label in EntityLabel:
        # 为每个实体标签的 'name' 属性创建唯一性约束
        # 注意: Neo4j 5.x 语法中使用 'CREATE CONSTRAINT IF NOT EXISTS'
        constraint_query = (
            f"CREATE CONSTRAINT {label.lower()}_name_unique IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.name IS UNIQUE"
        )
        try:
            client.run_query(constraint_query)
            logger.info(f"Constraint ensured for {label}")
        except Exception as e:
            # 某些低版本或特殊配置可能语法略有不同，此处记录错误
            logger.warning(f"Could not create constraint for {label}: {e}")


if __name__ == "__main__":
    # 脚本直接运行可用于环境初始化
    logging.basicConfig(level=logging.INFO)
    init_constraints()
