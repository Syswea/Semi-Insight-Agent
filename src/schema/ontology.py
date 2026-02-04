"""
src/schema/ontology.py

本模块定义了半导体行业分析系统的图谱本体 (Ontology)。
它规定了实体标签 (Entities) 和关系类型 (Relationships)，
作为 LlamaIndex 提取器和 Neo4j 查询的唯一事实来源。
"""

from enum import Enum

class EntityLabel(str, Enum):
    """定义图数据库中的节点标签"""
    ORGANIZATION = "Organization"      # 公司、协会、机构 (如: NVIDIA, TSMC, SEMI)
    GEOGRAPHY = "Geography"            # 国家或地区 (如: USA, Taiwan, China)
    INDUSTRY_SEGMENT = "IndustrySegment" # 产业环节 (如: Foundry, EDA, SME)
    TECHNOLOGY = "Technology"          # 技术/产品 (如: HBM3e, 2nm, EUV)
    POLICY = "Policy"                  # 政策/法律 (如: CHIPS Act)
    METRIC = "Metric"                  # 财务或行业指标 (如: Revenue, MarketShare)

class RelationType(str, Enum):
    """定义节点之间的关系类型"""
    HEADQUARTERED_IN = "HEADQUARTERED_IN"  # (Org)-[:HEADQUARTERED_IN]->(Geo)
    OPERATES_IN = "OPERATES_IN"            # (Org)-[:OPERATES_IN]->(IndustrySegment)
    SUPPLIES = "SUPPLIES"                  # (Org)-[:SUPPLIES]->(Org)
    DEVELOPS = "DEVELOPS"                  # (Org)-[:DEVELOPS]->(Technology)
    IMPLEMENTS = "IMPLEMENTS"              # (Geo)-[:IMPLEMENTS]->(Policy)
    IMPACTS = "IMPACTS"                    # (Policy)-[:IMPACTS]->(Org|Technology)
    COMPETES_WITH = "COMPETES_WITH"        # (Org)-[:COMPETES_WITH]->(Org)
    PART_OF = "PART_OF"                    # 通用层级关系

# 思考: 
# 为了让 LLM 提取更精准，我们可以定义一些三元组约束建议 (Allowed Triplets)。
# 这将在后续的 LLMGraphTransformer 中使用。
ALLOWED_RELATIONS = [
    (EntityLabel.ORGANIZATION, RelationType.HEADQUARTERED_IN, EntityLabel.GEOGRAPHY),
    (EntityLabel.ORGANIZATION, RelationType.OPERATES_IN, EntityLabel.INDUSTRY_SEGMENT),
    (EntityLabel.ORGANIZATION, RelationType.SUPPLIES, EntityLabel.ORGANIZATION),
    (EntityLabel.ORGANIZATION, RelationType.DEVELOPS, EntityLabel.TECHNOLOGY),
    (EntityLabel.GEOGRAPHY, RelationType.IMPLEMENTS, EntityLabel.POLICY),
    (EntityLabel.POLICY, RelationType.IMPACTS, EntityLabel.ORGANIZATION),
    (EntityLabel.POLICY, RelationType.IMPACTS, EntityLabel.TECHNOLOGY),
    (EntityLabel.ORGANIZATION, RelationType.COMPETES_WITH, EntityLabel.ORGANIZATION),
]
