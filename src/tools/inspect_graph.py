"""
src/tools/inspect_graph.py

用于检查 Neo4j 数据库内容的调试工具。
"""

from src.utils.database import Neo4jClient


def inspect_nodes(limit=20):
    client = Neo4jClient()
    print("\n--- Nodes (Top 20) ---")
    nodes = client.run_query(
        f"MATCH (n) RETURN labels(n) as Labels, n.name as Name, n.source as Source LIMIT {limit}"
    )
    for n in nodes:
        print(
            f"[{', '.join(n['Labels'])}] {n['Name']} (from {n.get('Source', 'Unknown')})"
        )


def inspect_relations(limit=20):
    client = Neo4jClient()
    print("\n--- Relations (Top 20) ---")
    rels = client.run_query(
        f"MATCH (s)-[r]->(o) RETURN s.name as Subject, labels(s) as SLabel, type(r) as Relation, o.name as Object, labels(o) as OLabel LIMIT {limit}"
    )
    for r in rels:
        print(
            f"{r['Subject']} ({r['SLabel'][0]}) --[{r['Relation']}]--> {r['Object']} ({r['OLabel'][0]})"
        )


if __name__ == "__main__":
    inspect_nodes()
    inspect_relations()
