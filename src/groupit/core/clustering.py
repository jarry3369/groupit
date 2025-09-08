"""
Clustering and graph-based analysis functionality.
"""

import re
from typing import List, Dict
import numpy as np
import networkx as nx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_distances
from sklearn.cluster import DBSCAN

from .models.change_block import ChangeBlock

# Optional SentenceTransformer import
try:
    from sentence_transformers import SentenceTransformer
    _HAS_ST = True
except ImportError:
    _HAS_ST = False


def build_graph(blocks: List[ChangeBlock]) -> nx.Graph:
    """Build graph of relationships between ChangeBlocks"""
    G = nx.Graph()
    for b in blocks:
        G.add_node(b.key(), obj=b)

    # Add proximity edges within files
    by_file: Dict[str, List[ChangeBlock]] = {}
    for b in blocks:
        by_file.setdefault(b.file_path, []).append(b)
    for fp, blist in by_file.items():
        blist = sorted(blist, key=lambda x: x.start_line)
        for i in range(len(blist) - 1):
            a, c = blist[i], blist[i+1]
            dist = max(1, c.start_line - a.end_line)
            w = 1.0 / dist
            G.add_edge(a.key(), c.key(), kind='proximity', weight=w)

    # Add import edges
    mod_index: Dict[str, List[ChangeBlock]] = {}
    for b in blocks:
        for m in b.imports:
            mod_index.setdefault(m, []).append(b)
    for m, blist in mod_index.items():
        for i in range(len(blist)):
            for j in range(i+1, len(blist)):
                if G.has_edge(blist[i].key(), blist[j].key()):
                    G[blist[i].key()][blist[j].key()]['weight'] += 1.0
                else:
                    G.add_edge(blist[i].key(), blist[j].key(), kind='import', weight=1.0)

    # Add basename edges
    by_base: Dict[str, List[ChangeBlock]] = {}
    for b in blocks:
        base = re.sub(r"\.(test|spec)$", "", b.basename)
        by_base.setdefault(base, []).append(b)
    for base, blist in by_base.items():
        if len(blist) > 1:
            for i in range(len(blist)):
                for j in range(i+1, len(blist)):
                    if G.has_edge(blist[i].key(), blist[j].key()):
                        G[blist[i].key()][blist[j].key()]['weight'] += 0.7
                    else:
                        G.add_edge(blist[i].key(), blist[j].key(), kind='basename', weight=0.7)

    return G


def make_corpus(blocks: List[ChangeBlock]) -> List[str]:
    """Create corpus from ChangeBlocks for vectorization"""
    return [f"path:{b.file_path} kind:{b.kind} imports:{' '.join(b.imports)}\n{b.diff_text}\n{b.code_text}" for b in blocks]


def vectorize(corpus: List[str]):
    """Vectorize corpus using SentenceTransformer or TF-IDF"""
    if _HAS_ST:
        try:
            model = SentenceTransformer('all-MiniLM-L6-v2')
            X = model.encode(corpus, show_progress_bar=False)
            return model, np.asarray(X)
        except Exception:
            pass
    vec = TfidfVectorizer(max_features=4096, ngram_range=(1,2))
    X = vec.fit_transform(corpus)
    return vec, X.toarray()


def adjacency_matrix_from_graph(G: nx.Graph, nodes: List[str]) -> np.ndarray:
    """Convert networkx graph to adjacency matrix"""
    n = len(nodes)
    A = np.zeros((n,n), dtype=float)
    idx = {k:i for i,k in enumerate(nodes)}
    for u,v,data in G.edges(data=True):
        if u in idx and v in idx:
            i,j = idx[u], idx[v]
            A[i,j] = data.get('weight', 1.0)
            A[j,i] = A[i,j]
    if A.sum() > 0:
        A = A / (A.max() or 1.0)
    return A


def combined_distance_matrix(X: np.ndarray, G: nx.Graph, alpha: float=0.4) -> np.ndarray:
    """Combine cosine distance with graph-based similarity"""
    D_cos = cosine_distances(X)
    nodes = [n for n in G.nodes()]
    A = adjacency_matrix_from_graph(G, nodes)
    G_sim = A
    S = (1.0 - D_cos) * (1.0 - alpha) + G_sim * alpha
    D = np.clip(1.0 - S, 0.0, 1.0)
    return D


def cluster_vectors_with_graph(X: np.ndarray, G: nx.Graph, eps: float=0.35, min_samples: int=2, alpha: float=0.4):
    """Cluster using DBSCAN with combined distance matrix"""
    D = combined_distance_matrix(X, G, alpha=alpha)
    db = DBSCAN(eps=eps, min_samples=min_samples, metric='precomputed')
    labels = db.fit_predict(D)
    if (labels == -1).any():
        next_id = labels.max() + 1
        for i, lab in enumerate(labels):
            if lab == -1:
                labels[i] = next_id
                next_id += 1
    return labels.tolist()


def group_blocks(blocks: List[ChangeBlock], labels: List[int]) -> Dict[int, List[ChangeBlock]]:
    """Group ChangeBlocks by cluster labels"""
    groups: Dict[int, List[ChangeBlock]] = {}
    for b, lab in zip(blocks, labels):
        groups.setdefault(lab, []).append(b)
    return groups
