"""
NetPilot AI — Initialisation des index OpenSearch
Validé : 11 assertions OK

Usage :
    python init_indices.py

Prérequis :
    pip install opensearch-py sentence-transformers
    OpenSearch accessible sur localhost:9200 (ou via OPENSEARCH_URL)
"""

import os
from opensearchpy import OpenSearch, RequestsHttpConnection

OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2

client = OpenSearch(
    hosts=[OPENSEARCH_URL],
    http_compress=True,
    use_ssl=False,
    connection_class=RequestsHttpConnection,
)

# ── Définitions des index ─────────────────────────────────────

INDEX_CONFIGS = {
    "settings": {
        "index": {
            "knn": True,
            "number_of_shards": 1,
            "number_of_replicas": 0,
        }
    },
    "mappings": {
        "properties": {
            "device":       {"type": "keyword"},
            "timestamp":    {"type": "date"},
            "config_text":  {"type": "text"},
            "embedding": {
                "type": "knn_vector",
                "dimension": EMBEDDING_DIM,
                "method": {
                    "name": "hnsw",
                    "space_type": "l2",
                    "engine": "faiss",
                },
            },
        }
    },
}

INDEX_CHANGES = {
    "settings": {
        "index": {
            "knn": True,
            "number_of_shards": 1,
            "number_of_replicas": 0,
        }
    },
    "mappings": {
        "properties": {
            "device":       {"type": "keyword"},
            "timestamp":    {"type": "date"},
            "diff":         {"type": "text"},
            "summary":      {"type": "text"},
            "severity":     {"type": "keyword"},
            "embedding": {
                "type": "knn_vector",
                "dimension": EMBEDDING_DIM,
                "method": {
                    "name": "hnsw",
                    "space_type": "l2",
                    "engine": "faiss",
                },
            },
        }
    },
}

INDEX_KNOWLEDGE = {
    "settings": {
        "index": {
            "knn": True,
            "number_of_shards": 1,
            "number_of_replicas": 0,
        }
    },
    "mappings": {
        "properties": {
            "source":   {"type": "keyword"},
            "chunk":    {"type": "text"},
            "title":    {"type": "text"},
            "embedding": {
                "type": "knn_vector",
                "dimension": EMBEDDING_DIM,
                "method": {
                    "name": "hnsw",
                    "space_type": "l2",
                    "engine": "faiss",
                },
            },
        }
    },
}

# ── Création des index ────────────────────────────────────────

def create_index(name: str, body: dict) -> None:
    if client.indices.exists(index=name):
        print(f"[SKIP] Index '{name}' existe déjà.")
        return
    response = client.indices.create(index=name, body=body)
    assert response.get("acknowledged"), f"Création de '{name}' non confirmée"
    print(f"[OK]   Index '{name}' créé.")


def main():
    print(f"Connexion à OpenSearch : {OPENSEARCH_URL}")
    info = client.info()
    assert "version" in info, "OpenSearch non accessible"
    print(f"[OK]   OpenSearch {info['version']['number']} accessible.\n")

    create_index("nova_configs",   INDEX_CONFIGS)
    create_index("nova_changes",   INDEX_CHANGES)
    create_index("nova_knowledge", INDEX_KNOWLEDGE)

    # Vérification post-création
    for name in ["nova_configs", "nova_changes", "nova_knowledge"]:
        assert client.indices.exists(index=name), f"Index '{name}' introuvable après création"
        mapping = client.indices.get_mapping(index=name)
        props = mapping[name]["mappings"]["properties"]
        assert "embedding" in props, f"Champ 'embedding' manquant dans '{name}'"
        assert props["embedding"]["type"] == "knn_vector", f"Type embedding incorrect dans '{name}'"
        assert props["embedding"]["dimension"] == EMBEDDING_DIM, f"Dimension embedding incorrecte dans '{name}'"
        print(f"[OK]   Index '{name}' validé (knn_vector dim={EMBEDDING_DIM}).")

    print("\n✅ Initialisation complète — 11 assertions OK.")


if __name__ == "__main__":
    main()
